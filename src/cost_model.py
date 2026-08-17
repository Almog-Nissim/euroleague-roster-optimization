"""
cost_model.py  (Day 4; משתנה תלוי הוחלף ביום 5)
------------------------------------------------
אומד את פונקציית העלות ומריץ את מבחן הטאוטולוגיה.

המשתנה התלוי הוא **יחס לשכר הממוצע בסגל**, לא נתח מהתקציב:

    rel(i) = salary(i) / mean_salary(club, season)  =  share(i) * N

--------------------------------------------------------------------
למה זה השתנה (יום 5, משימה 3b)
--------------------------------------------------------------------
share היה ההגדרה עד יום 4. הנימוק שלו היה נכון - הוא מסלק עונה,
מטבע ואינפלציה באפס פרמטרים. מה שהוא לא סילק, והכניס במקום:
**גודל הסגל.**

הנתחים בסגל מסתכמים ל-1 בהגדרה, ולכן הנתח הממוצע הוא 1/N.
סגל מכבי נע 12 -> 12 -> 15, כלומר share הכניס לעונת 2025 הפרש
רמה מלאכותי של log(15/12) = 0.223 שאין לו קשר לשכר. מי שסגלו
גדל נראה זול יותר.

זה נמדד בשני מקומות בלתי תלויים:
  - בכיול: R2 על מכבי לבדה עלה מ-0.564 ל-0.619 בהחלפה
  - במבחן: כל 10 השגיאות על הפועל היו חיוביות, סכום נתחים
    חזוי 1.349 מול 0.782 בפועל. גודל הסגל הסביר x1.462 מתוך x1.726

**וזה היה חוסם ל-PuLP:** האילוץ sum(x) <= 16 הופך את N למשתנה
החלטה. עלות שמוגדרת כנתח תלויה בכמה שחקנים ייבחרו - כלומר בדיוק
במה שהאופטימייזר משנה. מעגל שהיה נסגר בשקט.
--------------------------------------------------------------------

מפרט (סגור יום 5):
    log(rel) = b0 + b1*pir_lag_shrunk + b2*el_seasons

age_c2 ירד: 6 מבחנים, הסימן מקפץ סביב אפס, ומבחן הבליעה נתן
R2=0.044 בלי pir_lag. min_lag ירד: 3 גרסאות, כולן נופלות
(r=0.93 מול pir_lag; הגרסה המאונכת יצאה שלילית ולא מובהקת).

הערה על גודל מדגם: 27 תצפיות, 18 שחקנים ייחודיים. שגיאות התקן
מקובצות לפי שחקן. הסימנים הם מה שנקרא כאן, לא הגדלים.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR

FEATURES = ["pir_lag_shrunk", "el_seasons"]
DEP = "log_rel"

PREDICTIONS = {
    "pir_lag_shrunk": ("+", "תפוקה אחרונה היא העוגן; הגורם הדומיננטי"),
    "el_seasons":     ("+", "פרמיית ודאות על שחקן מוכח"),
}
SPEARMAN_PREDICTED = (0.60, 0.80)
SPEARMAN_EMPTY = 0.90          # מעל זה המודל ריק


def load():
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})

    cal_all = anch[anch.usage == "calibrate"].copy()

    # N ו-mean_salary נספרים על *כל* שורות הסגל, כולל אלה בלי קוד
    # שחקן. הן חלק מהתקציב ומגודל הסגל גם אם הרגרסיה לא יכולה
    # להשתמש בהן.
    agg = cal_all.groupby(["club", "season"]).salary_mid.agg(["sum", "size"])
    agg.columns = ["team_payroll", "roster_n"]
    agg["mean_salary"] = agg.team_payroll / agg.roster_n

    cal = cal_all[cal_all.player_code.notna()].merge(
        agg, left_on=["club", "season"], right_index=True)
    cal["rel"] = cal.salary_mid / cal.mean_salary
    cal["log_rel"] = np.log(cal.rel)

    df = cal.merge(feat, on=["player_code", "season"], how="inner",
                   suffixes=("", "_f"))
    print(f"[JOIN] עוגני כיול: {len(cal)} | עם פיצ'רים: {len(df)} | "
          f"נשרו: {len(cal) - len(df)}")
    print("[N]    גודל סגל לעונה: " +
          ", ".join(f"{s}={int(n)}"
                    for (_, s), n in agg.roster_n.items()))
    if len(df) < len(cal):
        lost = cal[~cal.player_code.isin(df.player_code)]
        print("  ללא pir_lag (אין עונת יורוליג קודמת):")
        print("   ", ", ".join(sorted(lost.player_name_el.dropna().unique())))
    return df


def fit(df, features=FEATURES, label=""):
    d = df.dropna(subset=list(features) + [DEP])
    X = sm.add_constant(d[list(features)].astype(float))
    m = sm.OLS(d[DEP], X).fit(cov_type="cluster",
                              cov_kwds={"groups": d.player_code})
    if label:
        print(f"\n[{label}] n={int(m.nobs)} | "
              f"clusters={d.player_code.nunique()} | R2={m.rsquared:.3f}")
    return m, d


def report_vs_predictions(m):
    print("\n" + "=" * 74)
    print("תחזיות מול תוצאה")
    print("=" * 74)
    print(f"{'פרמטר':<18}{'תחזית':>7}{'בפועל':>11}{'p':>9}{'CI 95%':>22}")
    for f, (sign, _) in PREDICTIONS.items():
        b, p = m.params[f], m.pvalues[f]
        lo, hi = m.conf_int().loc[f]
        got = "+" if b > 0 else "-"
        ok = "OK" if got == sign else "REFUTED"
        if p > 0.10:
            ok += " (n.s.)"
        print(f"{f:<18}{sign:>7}{b:>11.4f}{p:>9.3f}"
              f"  [{lo:>8.4f},{hi:>8.4f}]  {ok}")
    for f, (_, why) in PREDICTIONS.items():
        print(f"  {f}: {why}")


def tautology_test(m, d):
    """ספירמן בין עלות משוערת ל-PIR באותה עונה.
    מעל 0.90 המודל ריק - הוא רק משכתב את התפוקה.

    נמדד מחדש על log_rel. הערך שדווח ביום 4 (0.848) נמדד על
    log_share ואינו תקף למפרט הנוכחי.
    """
    pred = m.predict(sm.add_constant(d[FEATURES].astype(float)))
    rho, p = spearmanr(pred, d.pir_per_game)
    rho_obs, _ = spearmanr(d[DEP], d.pir_per_game)

    print("\n" + "=" * 74)
    print("מבחן הטאוטולוגיה  (נמדד על log_rel)")
    print("=" * 74)
    lo, hi = SPEARMAN_PREDICTED
    print(f"  תחזית שנכתבה מראש : {lo:.2f}-{hi:.2f}")
    print(f"  עלות חזויה ~ PIR   : rho={rho:+.3f}  (p={p:.4f})")
    print(f"  עלות בפועל ~ PIR   : rho={rho_obs:+.3f}   "
          f"<- כמה השוק עצמו מתמחר תפוקה")
    if rho > SPEARMAN_EMPTY:
        print(f"  [FAIL] מעל {SPEARMAN_EMPTY} - המודל משכתב PIR")
    elif lo <= rho <= hi:
        print("  [OK] בתוך הטווח שנחזה - יש שונות עצמאית")
    else:
        print(f"  [מחוץ לטווח] התחזית הופרכה, אך {rho:.3f} < "
              f"{SPEARMAN_EMPTY} - המודל אינו ריק")
    print("  לייחוס: ביום 4 נמדד 0.848/0.765 על log_share. "
          "אינו בר-השוואה ישירה.")
    return rho


def sensitivity(df):
    print("\n" + "=" * 74)
    print("רגישות: האם הסימנים יציבים?")
    print("=" * 74)
    rows = []
    for k in (20, 40, 60):
        d = df.dropna(subset=FEATURES + [DEP]).copy()
        w = d.games_lag / (d.games_lag + k)
        d["pir_lag_shrunk"] = w * d.pir_lag_raw + (1 - w) * d.league_pir_mean
        m, _ = fit(d)
        rows.append({"k": k, **{f: m.params[f] for f in FEATURES},
                     "R2": m.rsquared})
    r = pd.DataFrame(rows).set_index("k").round(4)
    print(r.to_string())
    flipped = [f for f in FEATURES if r[f].apply(np.sign).nunique() > 1]
    if flipped:
        print(f"  [WARN] סימן מתהפך ב: {flipped}")
    else:
        print("  [OK] כל הסימנים יציבים על פני k")


def leave_one_season_out(df):
    print("\n" + "=" * 74)
    print("השמטת עונה אחת בכל פעם")
    print("=" * 74)
    rows = []
    for s in sorted(df.season.unique()):
        m, _ = fit(df[df.season != s])
        rows.append({"בלי": s, "n": int(m.nobs),
                     **{f: round(m.params[f], 4) for f in FEATURES}})
    print(pd.DataFrame(rows).to_string(index=False))


def main():
    df = load()
    m, d = fit(df, label="המפרט הסגור")
    print(m.summary().tables[1])
    report_vs_predictions(m)
    tautology_test(m, d)
    sensitivity(df)
    leave_one_season_out(df)

    print("\n" + "=" * 74)
    print("n אפקטיבי ~18 שחקנים ייחודיים על 3 פרמטרים.")
    print("רווחי הסמך רחבים. הסימנים הם מה שנקרא כאן, לא הגדלים.")
    print("=" * 74)


if __name__ == "__main__":
    main()