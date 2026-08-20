"""
crowding_extrapolation.py  (Day 9)
----------------------------------
**האם מותר לנו בכלל להשתמש ב-β שאמדנו?**

--------------------------------------------------------------------
הבעיה
--------------------------------------------------------------------
β נאמד על 204 מעברי מועדון. התפלגות ה-Δ בסביבה שם:

    חציון |Δmates|      0.039
    אחוזון 90           0.102
    אחוזון 99           0.140
    מקסימום             0.242

**קפיצת איכות-החברים בסגל שהמנוע בונה: +0.169.**

זה אחוזון 99.5. **מעבר אחד מתוך 204** בכל ההיסטוריה היה בגודל
כזה. כלומר לקחנו מקדם שנאמד על תזוזות של 0.04 והחלנו אותו על
תזוזה של 0.17 — פי 4.3 מהחציון, מחוץ לתחום שבו נמדד.

הצורה הליניארית עושה כאן את כל העבודה. אם הקשר קמור — כלומר
הצפיפות מחריפה ככל שמצטופפים — התיקון שביצענו **חלש מדי**,
והיתרון שנשאר (+10.8%) עדיין מנופח.

--------------------------------------------------------------------
שני מבחנים בלתי תלויים
--------------------------------------------------------------------
**א. קמירות בתוך מדגם המעברים.** מוסיפים Δmates² ובודקים סימן
   ומובהקות; ובנוסף רגרסיה נפרדת בכל דלי. חולשה: 59 תצפיות
   בלבד בדלי הגבוה, ואף אחת קרוב ל-0.169.

**ב. תת-אדיטיביות ברמת הקבוצה.** המבחן החזק יותר, כי הוא נמדד
   בדיוק ביחידה שמעניינת אותנו ובלי אקסטרפולציה.

   לכל אחת מ-158 עונות-הקבוצה:

       תחזית אדיטיבית = Σ (ppm_עצמאי_i · דקות_i)
       בפועל          = ה-PIR של הקבוצה

   `ppm_עצמאי` נלקח מ**העונה הקודמת** של השחקן (מכווץ), ולכן
   אינו מכיל את הסביבה הנוכחית. אם התפוקה אדיטיבית — היחס
   בין השניים לא יהיה תלוי בריכוזיות הכישרון בסגל. אם יש
   צפיפות — קבוצות שמרכזות כישרון **יפגרו** אחרי התחזית.

   ⚠️ בקרה חובה: רמת הכישרון הממוצעת. קבוצה מרוכזת היא גם
      קבוצה טובה, ולשחקנים טובים יש חזרה לממוצע חזקה יותר.
      בלי הבקרה הזו נמדוד חזרה לממוצע ונקרא לה צפיפות.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
PRED_CLAUDE = dict(
    quad_sign="שלילי — הקשר קמור, הצפיפות מחריפה",
    quad_signif="לא מובהק ב-n=204. סימן נכון, t בין -1 ל-2-",
    team_beta="שלילי ומובהק — תת-אדיטיביות ברמת הקבוצה",
    team_r2="0.10 .. 0.30 אחרי בקרת רמת כישרון",
    verdict="התיקון הליניארי מחסיר. היתרון האמיתי מתחת ל-+10.8%",
)
PRED_ALMOG = dict(
    quad_sign="שלילי — מסכים",
    quad_signif="לא מספיק מובהק — מסכים",
    team_beta="שלילי ומובהק — מסכים",
    team_r2="~0.40",          # קלוד: 0.10-0.30. כאן אנחנו חלוקים.
    verdict="התיקון יחסיר, היתרון ירד — אבל לא משמעותית",
)
PRED_CLAUDE_WHY = (
    "יש כדור אחד. כששני שחקנים חולקים אותו הנזק קטן; כששמונה "
    "חולקים אותו הנזק לשחקן גדול בהרבה, כי לכל אחד נשאר נתח "
    "קטן יותר מבסיס קטן יותר. זו הגדרה של קמירות. הסיבה "
    "שהמובהקות תהיה חלשה היא פשוט שאין לנו תצפיות בקצה — "
    "וזו בדיוק הבעיה שהקובץ הזה מתעד."
)
# ====================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR
import roster_optimizer as ro
import optimizer_backtest as ob
from crowding import mates_panel, MIN_MIN

SEP = "=" * 90
ENGINE_JUMP = 0.169

# ⚠️ אין לקרוא לפונקציות כאן בשם test_*. PyCharm מזהה כל קובץ עם
#    שם כזה כקובץ pytest, מריץ אותו כבדיקות, ונופל על "fixture not
#    found" — שגיאה שנראית כמו באג בתוכן ואינה קשורה אליו.


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def transfers(ps):
    p = mates_panel(ps).sort_values(["player_code", "season"])
    g = p.groupby("player_code")
    for c in ("ppm", "mates", "team", "season", "mt", "age"):
        p[c + "_l"] = g[c].shift(1)
    d = p[(p.season - p.season_l == 1) & p.ppm_l.notna() & p.mates.notna()
          & p.mates_l.notna() & (p.mt > MIN_MIN) & (p.mt_l > MIN_MIN)]
    mv = d[d.team != d.team_l].copy()
    mv["dppm"] = mv.ppm - mv.ppm_l
    mv["dm"] = mv.mates - mv.mates_l
    mv["dage"] = mv.age - mv.age_l
    lg = float((mv.ppm_l * mv.mt_l).sum() / mv.mt_l.sum())
    mv["dev"] = mv.ppm_l - lg
    return mv


def check_convexity(mv):
    h("מבחן א' — קמירות בתוך מדגם המעברים")
    print(f"  n = {len(mv)}   |Δmates| חציון {mv.dm.abs().median():.3f}   "
          f"אחוזון 99 {np.percentile(mv.dm.abs(),99):.3f}")
    print(f"  קפיצת המנוע: +{ENGINE_JUMP:.3f}  ->  "
          f"{int((mv.dm>=ENGINE_JUMP).sum())} מעברים בהיסטוריה הגיעו לשם\n")

    mv = mv.copy()
    mv["dm2"] = mv.dm ** 2
    lin = sm.OLS(mv.dppm, sm.add_constant(
        mv[["dm", "dage", "dev"]].astype(float))).fit()
    qua = sm.OLS(mv.dppm, sm.add_constant(
        mv[["dm", "dm2", "dage", "dev"]].astype(float))).fit()
    print(f"  ליניארי : β={lin.params.dm:+.3f} (t={lin.tvalues.dm:+.2f})  "
          f"R²={lin.rsquared:.3f}")
    print(f"  ריבועי  : β={qua.params.dm:+.3f} (t={qua.tvalues.dm:+.2f})  "
          f"γ={qua.params.dm2:+.3f} (t={qua.tvalues.dm2:+.2f})  "
          f"R²={qua.rsquared:.3f}")
    b, g_ = float(qua.params.dm), float(qua.params.dm2)
    slope_med = b + 2 * g_ * mv.dm.median()
    slope_eng = b + 2 * g_ * ENGINE_JUMP
    print(f"\n  שיפוע בחציון ({mv.dm.median():+.3f}) : {slope_med:+.3f}")
    print(f"  שיפוע בקפיצת המנוע (+{ENGINE_JUMP:.3f}) : {slope_eng:+.3f}")
    print(f"  -> התיקון הליניארי {'מחסיר' if slope_eng < slope_med else 'מגזים'}"
          f" בפקטור {abs(slope_eng/slope_med):.2f}" if slope_med else "")

    print("\n  רגרסיה נפרדת בכל דלי:")
    for lo, hi, lab in [(-9, -0.05, "ירידה חדה"), (-0.05, 0.0, "ירידה קלה"),
                        (0.0, 0.05, "עלייה קלה"), (0.05, 9, "עלייה חדה")]:
        s = mv[(mv.dm >= lo) & (mv.dm < hi)]
        if len(s) < 15:
            print(f"    {lab:<12} n={len(s):>3}  מעט מדי")
            continue
        m = sm.OLS(s.dppm, sm.add_constant(
            s[["dm", "dev"]].astype(float))).fit()
        print(f"    {lab:<12} n={len(s):>3}  β={m.params.dm:+.3f} "
              f"(t={m.tvalues.dm:+.2f})")
    return qua


def check_subadditivity(ps, feat):
    h("מבחן ב' — תת-אדיטיביות ברמת הקבוצה  (המבחן החזק)")
    p = ps[ps.min_per_game > 0].copy()
    p["ppm"] = p.pir_per_game / p.min_per_game
    p["mt"] = p.min_per_game * p.games
    p = p.sort_values(["player_code", "season"])
    g = p.groupby("player_code")
    p["ppm_l"] = g.ppm.shift(1)
    p["mt_l"] = g.mt.shift(1)
    p["season_l"] = g.season.shift(1)
    p = p[(p.season - p.season_l == 1) & p.ppm_l.notna()].copy()
    league = float((p.ppm_l * p.mt_l).sum() / p.mt_l.sum())
    w = p.mt_l / (p.mt_l + ro.K_PPM)
    p["standalone"] = w * p.ppm_l + (1 - w) * league     # ppm עצמאי, מכווץ

    rows = []
    for (s, t), gg in p.groupby(["season", "team"]):
        if gg.mt.sum() < 3000:
            continue
        pred = float((gg.standalone * gg.mt).sum())
        act = float((gg.ppm * gg.mt).sum())
        sh = (gg.standalone * gg.mt) / (gg.standalone * gg.mt).sum()
        rows.append(dict(season=s, team=t, pred=pred, act=act,
                         ratio=act / pred, cover=gg.mt.sum(),
                         hhi=float((sh ** 2).sum()),
                         top3=float(sh.nlargest(3).sum()),
                         mean_q=float((gg.standalone * gg.mt).sum() / gg.mt.sum()),
                         n=len(gg)))
    d = pd.DataFrame(rows)
    d["lr"] = np.log(d.ratio)
    for c in ("hhi", "top3", "mean_q"):
        d[c + "_z"] = d.groupby("season")[c].transform(
            lambda x: (x - x.mean()) / x.std(ddof=1))
    print(f"  n = {len(d)} עונות-קבוצה   (כיסוי >= 3000 דקות)")
    print(f"  היחס בפועל/אדיטיבי: חציון {d.ratio.median():.3f}   "
          f"טווח {d.ratio.min():.3f}-{d.ratio.max():.3f}\n")

    for lab, cols in [("ריכוזיות בלבד (HHI)", ["hhi_z"]),
                      ("HHI + בקרת רמת כישרון", ["hhi_z", "mean_q_z"]),
                      ("נתח 3 המובילים + בקרה", ["top3_z", "mean_q_z"])]:
        m = sm.OLS(d.lr, sm.add_constant(d[cols].astype(float))).fit()
        k = cols[0]
        print(f"  {lab:<26} β={m.params[k]:+.4f} "
              f"(t={m.tvalues[k]:+.2f}, p={m.pvalues[k]:.3f})  "
              f"R²={m.rsquared:.3f}")
    r, pv = stats.pearsonr(d.hhi_z, d.lr)
    print(f"\n  קורלציה גולמית (ריכוזיות , יחס) = {r:+.3f} (p={pv:.3g})")
    # 🔴 כאן היו שתי שורות שהדפיסו "התפוקה תת-אדיטיבית" **ללא תלות
    #    בתוצאה**. כתבתי את המסקנה לתוך הקוד לפני שראיתי את המספר,
    #    והיא הודפסה גם כשהמבחן יצא אפס מובהק. הוסרו.
    m2 = sm.OLS(d.lr, sm.add_constant(
        d[["mean_q_z", "hhi_z"]].astype(float))).fit()
    print(f"  רמת כישרון ממוצעת          β={m2.params.mean_q_z:+.4f} "
          f"(t={m2.tvalues.mean_q_z:+.2f}, p={m2.pvalues.mean_q_z:.3f})")
    print("\n  ⚠️ תחום התוקף: איכות ממוצעת של קבוצות אמיתיות "
          f"{d.mean_q.min():.3f}-{d.mean_q.max():.3f}.")
    print("     סגלי המנוע: 0.575-0.668. **כולם מעל המקסימום "
          "ההיסטורי.** המבחן הזה אינו יכול לדבר על המשטר שלהם.")
    d.to_csv(PROCESSED_DIR / "subadditivity.csv", index=False)
    return d


def main():
    print(SEP)
    print("crowding_extrapolation — האם מותר להחיל את β על הקפיצה של המנוע")
    print("תחזיות ננעלו. ראו ראש הקובץ.")
    print(SEP)
    feat, anch, pos, ps = ob.load_all()
    check_convexity(transfers(ps))
    check_subadditivity(ps, feat)
    h("מול התחזיות של קלוד")
    for k, v in PRED_CLAUDE.items():
        print(f"  {k:<14} {v}")
    print(SEP)


if __name__ == "__main__":
    main()