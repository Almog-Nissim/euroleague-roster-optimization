"""
cost_reality.py  (Day 9 — מטרה 1)
---------------------------------
**האם הסגל שהמנוע בונה נכנס בכלל בתקציב האמיתי?**

--------------------------------------------------------------------
השאלה שנפתחה מהקיר
--------------------------------------------------------------------
    איכות ממוצעת של סגל (ppm משוקלל דקות)
    103 קבוצות יורוליג אמיתיות :  0.370 - 0.509
    38 הסגלים שהמנוע בנה       :  0.575 - 0.668

המנוע מרכיב, **באותו תקציב בדיוק**, סגלים טובים ב-21% מכל מה
שנראה ביורוליג בעשור. יש שתי אפשרויות בלבד:

    1. כל 38 המועדונים, כל שנה, טעו טעות עצומה
    2. מודל העלות שלנו מתמחר כוכבים בזול מדי

אפשרות 1 אינה סבירה. אפשרות 2 מדידה — וזה הקובץ.

--------------------------------------------------------------------
למה דווקא מודל העלות חשוד
--------------------------------------------------------------------
    מודל העלות  : 2 משתנים   (pir_lag_shrunk, el_seasons)
    מודל התפוקה : 5 משתנים   (+ min_pg_lag, age_c, log_gap)

כל פער בין שני המפרטים הוא **ארביטראז' טהור**: שחקן שזול לפי
האחד ויקר לפי השני. האופטימייזר קונה בדיוק אותו.

ובנוסף — מודל העלות כויל על **מכבי בלבד** (usage='calibrate',
12-15 שחקנים לעונה). מכבי היא מועדון תקציב בינוני. אם תלילות
המחיר אצל אולימפיאקוס ופנאתינייקוס גבוהה יותר, המודל מתמחר
כוכבים בזול באופן שיטתי.

--------------------------------------------------------------------
הנתונים
--------------------------------------------------------------------
שכר אמיתי ברמת שחקן, עם קוד מאומת, לעונת 2025:

    אולימפיאקוס    15 שחקנים    19,925,000
    פנאתינייקוס    16 שחקנים    37,205,000
    הפועל ת"א      16 שחקנים    23,030,000
    מכבי ת"א       15 שחקנים    10,800,000

⚠️ `salary_external_2025` **אינו** נכנס למבחן. ההצלבה שם היא לפי
   שם משפחה, ויש חמישה שמות כפולים (BROWN, FALL, HERNANGOMEZ,
   JONES, MADAR) ועשרה שלא הותאמו. הם מודפסים לאימות ידני ולא
   משמשים לחישוב.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
PRED_CLAUDE = dict(
    market_beta="גבוה מ-0.252 של המודל. צפוי 0.35-0.55",
    fit="**לא נכנס.** הסגל של המנוע יעלה 1.5-2.5 מהתקציב האמיתי",
    which_club="הפער יהיה הגדול ביותר במועדון העני ביותר (מכבי)",
)
PRED_ALMOG = dict()
PRED_CLAUDE_WHY = (
    "העקומה כוילה על מכבי, שאין לה כוכב במחיר עולמי. שיא השכר "
    "אצלה ~3M; אצל הפועל מיציץ' ב-6M ואצל פנאתינייקוס נאן ב-4.7M. "
    "עקומה שנאמדה בלי הזנב הימני תחזה אותו נמוך מדי — וזה בדיוק "
    "החלק שהאופטימייזר קונה."
)
# ====================================================================

import io
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR
import roster_optimizer as ro
import optimizer_backtest as ob
from league_backtest import build_pool, club_side, REPL
from optimise_consistent import optimise_v2
from roster_membership_audit import score_rows
from final_day7 import MIN_LEGAL_ROSTER

SEP = "=" * 92
TEST = 2025
TRAIN_MAX = 2024


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def flag_ambiguous():
    """שמות שלא ניתן להצליב חד-משמעית. **לא בשקט.**"""
    s = pd.read_csv(PROCESSED_DIR / "salary_external_2025.csv")
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    p = ps[ps.season == TEST].copy()
    p["l"] = p.player_name.str.split(",").str[0].str.strip().str.upper()
    s["l"] = s["last"].astype(str).str.strip().str.upper()
    m = s.merge(p[["player_code", "player_name", "l"]], on="l", how="left")
    miss = sorted(set(s.l) - set(p.l))
    dup = sorted(m[m.l.duplicated(keep=False) & m.player_code.notna()].l.unique())
    h("אימות ידני נדרש — שכר חיצוני שלא הוצלב חד-משמעית")
    print("  לא נמצאה התאמה (ככל הנראה הבדל כתיב):")
    for x in miss:
        print(f"    {x}")
    print("\n  שם משפחה מופיע ליותר משחקן אחד — לא ניתן להכריע:")
    for x in dup:
        who = m[m.l == x].player_name.dropna().unique()
        print(f"    {x}: {', '.join(who)}")
    print("\n  ⚠️ אף אחד מהם אינו נכנס לחישוב. המבחן משתמש רק")
    print("     ב-salary_anchors, שם הקוד מאומת.")


def market_curve(anch, feat):
    """עקומת המחיר האמיתית, מכל המועדונים שיש להם שכר ברמת שחקן.

    אותו מפרט בדיוק כמו מודל העלות של המנוע, כדי שההשוואה תהיה
    של **מקדמים** ולא של מפרטים.
    """
    a = anch[(anch.season == TEST) & anch.player_code.notna()
             & anch.salary_mid.notna()].copy()
    a["player_code"] = a.player_code.astype(str)
    g = a.groupby("club").salary_mid.agg(["sum", "size"])
    g.columns = ["payroll", "n"]
    g["mean_salary"] = g.payroll / g.n
    a = a.merge(g, left_on="club", right_index=True)
    a["log_rel"] = np.log(a.salary_mid / a.mean_salary)

    F = feat[feat.season == TEST].copy()
    F["player_code"] = F.player_code.astype(str)
    F = F.drop_duplicates("player_code").set_index("player_code")
    d = a.join(F[ro.COST_FEATURES], on="player_code", how="inner")
    d = d.dropna(subset=ro.COST_FEATURES + ["log_rel"])
    m = sm.OLS(d.log_rel, sm.add_constant(
        d[["pir_lag_shrunk", "el_seasons"]].astype(float))).fit()
    return m, d, g


def main():
    print(SEP)
    print("cost_reality — האם הסגל של המנוע נכנס בתקציב האמיתי")
    print("תחזיות ננעלו. ראו ראש הקובץ.")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    anch["salary_mid"] = pd.to_numeric(anch.salary_mid, errors="coerce")
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    flag_ambiguous()

    ob.TRAIN_MAX, ob.TEST = TRAIN_MAX, TEST
    with contextlib.redirect_stdout(io.StringIO()):
        cm, smear, agg, am, pm, PF, lagged = ob.fit_models(ps, feat, anch)
    mk, dd, payroll = market_curve(anch, feat)

    h("א. העקומה שלנו מול עקומת השוק")
    print(f"  {'':<26}{'β₁ (תלילות)':>14}{'שגיאת תקן':>12}{'n':>6}{'R²':>8}")
    print(f"  {'המודל (כויל על מכבי)':<26}"
          f"{cm.params['pir_lag_shrunk']:>14.3f}"
          f"{cm.bse['pir_lag_shrunk']:>12.3f}{int(cm.nobs):>6}"
          f"{cm.rsquared:>8.3f}")
    print(f"  {'השוק (4 מועדונים 2025)':<26}"
          f"{mk.params['pir_lag_shrunk']:>14.3f}"
          f"{mk.bse['pir_lag_shrunk']:>12.3f}{int(mk.nobs):>6}"
          f"{mk.rsquared:>8.3f}")
    ratio = mk.params["pir_lag_shrunk"] / cm.params["pir_lag_shrunk"]
    print(f"\n  יחס התלילות: {ratio:.2f}")
    print("  >1 = השוק תלול יותר, כלומר המודל מתמחר כוכבים **בזול**.")
    print("\n  עקומה נפרדת לכל מועדון:")
    for club, g in dd.groupby("club"):
        if len(g) < 8:
            print(f"    {club:<6} n={len(g):>3}  מעט מדי")
            continue
        mm = sm.OLS(g.log_rel, sm.add_constant(
            g[["pir_lag_shrunk"]].astype(float))).fit()
        print(f"    {club:<6} n={len(g):>3}  β₁={mm.params.pir_lag_shrunk:+.3f}"
              f"  (t={mm.tvalues.pir_lag_shrunk:+.2f})  "
              f"שכר מרבי {g.salary_mid.max():,.0f}")

    h("ב. המבחן — כמה באמת עולה הסגל שהמנוע בנה")
    cand, _ = build_pool(TEST, TRAIN_MAX, feat, anch, pos, ps)
    gmax = float(ps[ps.season == TEST].games.max())
    F = feat[feat.season == TEST].drop_duplicates("player_code").copy()
    F["pc"] = F.player_code.astype(str)
    pirmap = F.set_index("pc").pir_lag_shrunk
    elmap = F.set_index("pc").el_seasons

    def market_price(pcs, scale):
        """מחיר שוק לכל שחקן, בסקלת השכר הממוצע של המועדון."""
        x = pd.DataFrame({"pir_lag_shrunk": [pirmap.get(p, np.nan) for p in pcs],
                          "el_seasons": [elmap.get(p, 0.0) for p in pcs]})
        x = x.fillna(x.median())
        pred = np.exp(mk.predict(sm.add_constant(x.astype(float),
                                                 has_constant="add")))
        return pred.values * float(np.mean(np.exp(mk.resid))) * scale

    print(f"  {'מועדון':<7}{'תקציב':>12}{'סגל מוע.':>12}{'סטייה':>8}"
          f"{'n':>4}{'מנוע12':>11}{'יחס':>7}{'מנוע=n':>11}{'יחס':>7}"
          f"{'לשחקן מוע.':>12}{'לשחקן מנוע':>12}")
    for club in ["TEL", "HTA", "OLY", "PAN"]:
        if club not in payroll.index:
            continue
        real = float(payroll.loc[club, "payroll"])
        scale = float(payroll.loc[club, "mean_salary"])
        keep, _ = club_side(cand, split, club, TEST, gmax, posmap)
        if len(keep) < MIN_LEGAL_ROSTER:
            print(f"  {club:<7}  סגל קטן מדי במאגר — מדולג")
            continue
        n = len(keep)
        B = float(keep.cost.sum())
        sel, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
        eng = cand[sel]
        om = ro.MAX_ROSTER
        ro.MAX_ROSTER = max(om, n)
        sel_n, _ = optimise_v2(cand, B, n)
        ro.MAX_ROSTER = om
        c_club = float(market_price(keep.pc.tolist(), scale).sum())
        c_eng = float(market_price(eng.pc.tolist(), scale).sum())
        c_engn = (float(market_price(cand[sel_n].pc.tolist(), scale).sum())
                  if sel_n is not None else np.nan)
        dev = c_club / real - 1
        print(f"  {club:<7}{real:>12,.0f}{c_club:>12,.0f}{dev:>+8.0%}"
              f"{n:>4}{c_eng:>11,.0f}{c_eng/c_club:>7.2f}"
              f"{c_engn:>11,.0f}{c_engn/c_club:>7.2f}"
              f"{c_club/n:>12,.0f}{c_eng/len(eng):>12,.0f}")

    print("\n  🔴 'סטייה' = בדיקת השפיות. הסגל האמיתי מתומחר בעקומה")
    print("     אמור לצאת קרוב לתקציב האמיתי. סטייה גדולה פירושה")
    print("     שהעקומה אינה מתארת את המועדון הזה, וכל יחס שמתחתיה")
    print("     חשוד. הסיבה הצפויה: העוגנים מכסים 15-16 שחקנים בעוד")
    print("     הסגל המנוקד כולל 17-20 — כלומר מתמחרים יותר ראשים.")
    print("\n  ⚠️ 'מנוע12' מול 'מנוע=n': היחס הראשון מערבב שני דברים —")
    print("     איכות השחקנים **וגודל הסגל**. רק העמודה 'מנוע=n'")
    print("     מבודדת את השאלה 'האם אפשר לקנות סגל כזה בכסף הזה'.")
    print("     ועמודות 'לשחקן' מראות את המחיר הממוצע לראש.")

    h("מול התחזיות של קלוד")
    for k, v in PRED_CLAUDE.items():
        print(f"  {k:<14} {v}")
    print(SEP)


if __name__ == "__main__":
    main()