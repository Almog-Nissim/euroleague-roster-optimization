"""
depth_value.py  (Day 9)
-----------------------
**כמה שווה עומק — והאם המדד שלנו יכול לראות את זה בכלל.**

--------------------------------------------------------------------
למה זה השאלה האחרונה שנשארה
--------------------------------------------------------------------
חמש השערות נבדקו היום ונשללו: ארטיפקט ניקוד, גודל סגל כשלעצמו,
רצפות עמדה, צפיפות, ותמחור זול של המילוי (`floor_repricing`:
האחוזון הראשון במאגר עולה 42% מהחציון — אין שחקנים בחינם).

מה שנשאר הוא זה:

    המנוע בוחר בדיוק 12 שחקנים, בכל 38 המקרים, בכל רצפת מחיר.
    הוא בוחר 12 כי 12 הוא המינימום החוקי ושחקן 13 שווה לו **אפס**.

וזה נכון: `score_rows` מחלקת 200 דקות, שמונה שחקנים בולעים אותן,
ושחקנים 9-17 לא תורמים לניקוד כלום.

    -> פונקציית המטרה שלנו לא מייחסת שום ערך לעומק.

38 מועדונים אמיתיים מחזיקים 14-20 שחקנים ומוציאים על כך 26.9%
מהתקציב. או שכולם טועים, או שהעומק שווה משהו שהמדד לא רואה.

--------------------------------------------------------------------
המבחן
--------------------------------------------------------------------
ברמת **משחק בודד**, לא עונה. לכל משחק של כל מועדון:

    כמה משחקני הרוטציה נעדרו?         (n_absent)
    כמה עמוק הסגל שמאחוריהם?          (depth)
    מה הייתה תפוקת הקבוצה?            (PIR)

ואז:

    PIR = α_מועדון-עונה + b1·נעדרים + b2·(נעדרים × עומק) + בקרות

**המקדם שמעניין הוא b2.** אם הוא חיובי — עומק **מרפד** היעדרויות,
ולכן יש לו ערך שנעלם לגמרי מהמדד העונתי שלנו. אם הוא אפס — אין
לעומק ערך גם במציאות, וכל 38 המועדונים באמת מבזבזים.

--------------------------------------------------------------------
ההגדרות
--------------------------------------------------------------------
רוטציה  : שחקן עם >= 15 דקות למשחק בממוצע העונתי במועדון הזה
עומק    : סך ה-PIR-לדקה של שחקני **מחוץ** לרוטציה, משוקלל בדקותיהם
          כלומר: כמה טוב הספסל שאינו חלק מהחמישייה-רוטציה
נעדר    : שחקן רוטציה שאינו בבוקסקור של המשחק, או עם 0 דקות

⚠️ בקרות חובה:
   - אפקט קבוע למועדון-עונה: קבוצה חזקה מייצרת יותר בכל מקרה
   - בית/חוץ
   - איכות הרוטציה שנשארה: אם נעדר הכוכב זה לא כמו שנעדר השישי.
     נמדד כסך ה-ppm·דקות של שחקני הרוטציה שכן שיחקו.

בלי הבקרה השלישית נמדוד "מי נעדר" ונקרא לזה "כמה נעדרו".

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
PRED_CLAUDE = dict(
    b1="שלילי ומובהק, וגדול מ--1: חלק מהאובדן נספג",
    b2="חיובי, אבל **חלש ולא מובהק**",
    why=(
        "PIR הוא סכום שנשמר: אם חמישה על הפרקט, מישהו יקלע ויוריד "
        "ריבאונדים גם אם הוא גרוע. בדיוק כמו שמצאנו במבחן "
        "האדיטיביות — הכדור עובר ליד אחרת. לכן אני מצפה שהעומק "
        "יתגלה כשווה מעט מאוד **בתפוקה**, וששוויו האמיתי מגיע "
        "מדברים שהמדד שלנו לא מודד בכלל: ליגה מקומית, גביע, "
        "ועומס לאורך עונה."
    ),
    verdict="אם b2≈0 — המסקנה היא שהמדד שלנו מודד עונה אידיאלית",
)
PRED_ALMOG = dict()
# ====================================================================

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR, RAW_DIR

SEP = "=" * 90
SEASONS = [2024, 2025]
ROTATION_MIN = 15.0


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def code_from_pid(pid):
    """⚠️ Player_ID הוא מזהה, לא מספר. 'P012099   ' -> '12099'."""
    d = re.sub(r"\D", "", str(pid))
    return str(int(d)) if d else None


def mins(x):
    if not isinstance(x, str) or ":" not in x:
        return 0.0
    m, s = x.split(":")
    return int(m) + int(s) / 60


def load_games(season):
    b = pd.read_csv(RAW_DIR / f"boxscore_player_{season}.csv", dtype=str)
    if "Phase" not in b.columns:
        pf = RAW_DIR / f"gamecode_phase_{season}.csv"
        ph = pd.read_csv(pf, dtype=str)
        # ⚠️ הפעם השישית. הבוקסקור מחזיר "1", קובץ השלבים "E2025_1".
        #    זו בדיוק הנורמליזציה של split_multiclub — אותה פונקציה,
        #    כי כל וריאציה עצמאית שברה את זה שוב.
        def gn(v):
            t = str(v).strip()
            return t.split("_")[-1] if "_" in t else t
        b["g"] = b.Gamecode.map(gn)
        ph["g"] = ph.Gamecode.map(gn)
        if not set(b.g) & set(ph.g):
            raise ValueError("חפיפת Gamecode אפס — הנרמול שבור")
        b = b.merge(ph[["g", "Phase"]], on="g", how="left")
    b = b[b.Phase == "RS"].copy()          # עונה סדירה בלבד
    b["pc"] = b.Player_ID.map(code_from_pid)
    b["min"] = b.Minutes.map(mins)
    b["pir"] = pd.to_numeric(b.Valuation, errors="coerce").fillna(0.0)
    b["season"] = season
    b = b[b.pc.notna() & b.Team.notna()].copy()
    b["Team"] = b.Team.str.strip()
    b["gid"] = b.Gamecode.astype(str).str.strip()
    return b


def build():
    rows = []
    for s in SEASONS:
        b = load_games(s)
        # פרופיל עונתי של השחקן במועדון הזה
        prof = b.groupby(["Team", "pc"]).agg(
            tot_min=("min", "sum"), tot_pir=("pir", "sum"),
            g=("gid", "nunique")).reset_index()
        ng = b.groupby("Team").gid.nunique().rename("club_games")
        prof = prof.merge(ng, on="Team")
        prof["mpg"] = prof.tot_min / prof.club_games
        prof["ppm"] = prof.tot_pir / prof.tot_min.replace(0, np.nan)
        prof["rot"] = prof.mpg >= ROTATION_MIN

        for team, gp in prof.groupby("Team"):
            rot = gp[gp.rot]
            bench = gp[~gp.rot]
            if len(rot) < 5:
                continue
            # 🔴 גרסה 1 הגדירה עומק כ-Σ(ppm·דקות) של מי שמחוץ לרוטציה.
            #    זה **הפוך**: ערך גבוה שם פירושו שהקבוצה נאלצת לתת
            #    הרבה דקות למי שאינו ברוטציה — כלומר רוטציה **דקה**.
            #    ואכן: הקבוצות ה"עמוקות" יצאו עם PIR בסיס נמוך יותר
            #    (89.7 מול 92.9) ועם ירידה **גדולה** יותר בהיעדרות.
            #    מדדנו חולשה וקראנו לה עומק.
            #
            #    עומק = **איכות** שלושת הראשונים מחוץ לרוטציה,
            #    בלי הכפלה בדקות. כמה טוב מי שנכנס, לא כמה הוא נכנס.
            bq = bench.sort_values("mpg", ascending=False).head(3)
            depth = float(bq.ppm.fillna(0).mean()) if len(bq) else 0.0
            # וגם: כמה תפוקה "אבדה על הנייר" בכל היעדרות
            rotset = set(rot.pc)
            rq = rot.set_index("pc").ppm.fillna(0)
            rm = rot.set_index("pc").mpg
            tb = b[b.Team == team]
            for gid, gg in tb.groupby("gid"):
                played = set(gg.loc[gg["min"] > 0, "pc"])
                absent = rotset - played
                # 🔴 הבקרה הקודמת (`qual` = איכות מי שנשאר) הייתה
                #    **קולינארית בהגדרה** עם מספר הנעדרים: מי שנשאר
                #    הוא בדיוק מי שלא נעדר. הוספתה הפכה את b1 מ--1.17
                #    ל-+2.45 — יותר נעדרים, יותר תפוקה. סימן בלתי
                #    אפשרי, והוא שהסגיר את הבאג.
                #
                #    במקומה: `lost` = סך התרומה הצפויה של **הנעדרים**.
                #    זה מפריד "כמה נעדרו" מ"מי נעדר" בלי לשכפל את
                #    אותו מידע בשני אגפים.
                lost = float(sum(rq.get(p, 0) * rm.get(p, 0) for p in absent))
                rows.append(dict(
                    season=s, team=team, gid=gid,
                    pir=float(gg.pir.sum()),
                    n_absent=len(absent), n_rot=len(rotset),
                    depth=depth, lost=lost,
                    home=int((gg.Home.astype(str) == "1").any())))
    return pd.DataFrame(rows)


def main():
    print(SEP)
    print("depth_value — האם עומק מרפד היעדרויות")
    print("תחזיות ננעלו. ראו ראש הקובץ.")
    print(SEP)

    d = build()
    d["cs"] = d.season.astype(str) + "_" + d.team
    print(f"\n  n = {len(d)} משחקי-קבוצה   "
          f"{d.cs.nunique()} עונות-מועדון   עונות {SEASONS}")
    print(f"  שחקני רוטציה למועדון: חציון {d.n_rot.median():.0f}")
    print(f"  נעדרים במשחק: " + "  ".join(
        f"{k}:{v}" for k, v in d.n_absent.value_counts().sort_index().items()))
    print(f"  עומק: חציון {d.depth.median():.1f}   "
          f"טווח {d.depth.min():.1f}-{d.depth.max():.1f}")

    # נרמול בתוך עונה-מועדון: מנטרל את רמת הקבוצה לגמרי
    for c in ("depth", "lost"):
        d[c + "_z"] = (d[c] - d.groupby("season")[c].transform("mean")) \
            / d.groupby("season")[c].transform("std")
    d["ab"] = d.n_absent.astype(float)
    d["ab_x_depth"] = d.ab * d.depth_z
    d["lost_x_depth"] = d.lost * d.depth_z

    h("א. בדיקת שפיות — האם היעדרות בכלל מורידה תפוקה")
    fe = pd.get_dummies(d.cs, prefix="cs", drop_first=True).astype(float)
    X = fe.copy()
    X["ab"] = d.ab.values
    X["home"] = d.home.values
    m0 = sm.OLS(d.pir, sm.add_constant(X)).fit()
    print(f"  b1 (נעדרים) = {m0.params.ab:+.3f}  t={m0.tvalues.ab:+.2f}  "
          f"p={m0.pvalues.ab:.4f}")
    print(f"  בית = {m0.params.home:+.2f}   R² = {m0.rsquared:.3f}")

    h("ב. המפרט הנכון — תפוקה שאבדה, לא מספר נעדרים")
    X2 = fe.copy()
    X2["lost"] = d.lost.values
    X2["home"] = d.home.values
    m1 = sm.OLS(d.pir, sm.add_constant(X2)).fit()
    print(f"  b1 (תפוקה שאבדה) = {m1.params.lost:+.3f}  "
          f"t={m1.tvalues.lost:+.2f}  p={m1.pvalues.lost:.4f}")
    print(f"  R² = {m1.rsquared:.3f}")
    print("\n  b1 = -1 פירושו שהאובדן ממומש במלואו: מה שהנעדר היה")
    print("  מייצר פשוט נעלם. b1 קרוב לאפס פירושו שהקבוצה סופגת")
    print("  את זה כמעט לגמרי — מישהו אחר עושה את העבודה.")

    h("ג. המבחן — האם עומק מרפד")
    X3 = X2.copy()
    X3["lost_x_depth"] = d.lost_x_depth.values
    m2 = sm.OLS(d.pir, sm.add_constant(X3)).fit()
    b2, t2, p2 = (float(m2.params.lost_x_depth),
                  float(m2.tvalues.lost_x_depth),
                  float(m2.pvalues.lost_x_depth))
    print(f"  b1 (תפוקה שאבדה)        = {m2.params.lost:+.3f}  "
          f"t={m2.tvalues.lost:+.2f}")
    print(f"  b2 (אבדה × עומק)        = {b2:+.3f}  t={t2:+.2f}  p={p2:.4f}")
    print(f"  R² = {m2.rsquared:.3f}")
    print(f"\n  קריאה: על כל יחידת תפוקה שאבדה,")
    print(f"    קבוצה עמוקה (+1 ס\"ת) מפסידה {m2.params.lost + b2:+.3f}")
    print(f"    קבוצה רדודה (-1 ס\"ת) מפסידה {m2.params.lost - b2:+.3f}")
    if p2 < 0.05 and b2 > 0:
        print("  ✅ העומק מרפד. יש לו ערך שהמדד העונתי שלנו לא רואה.")
    elif b2 > 0:
        print("  ~ הכיוון נכון, לא מובהק.")
    else:
        print("  ❌ אין ריפוד. העומק לא משפיע על עלות ההיעדרות.")

    h("ד. השוואה גסה — שליש עמוק מול שליש רדוד")
    d["tier"] = pd.qcut(d.depth, 3, labels=["רדוד", "בינוני", "עמוק"])
    for lab, g in d.groupby("tier", observed=True):
        a0 = g[g.ab == 0].pir.mean()
        a2 = g[g.ab >= 2].pir.mean()
        print(f"  {lab:<8} איכות ספסל {g.depth.mean():>5.3f}   "
              f"PIR בלי נעדרים {a0:>6.1f}   עם 2+ נעדרים {a2:>6.1f}   "
              f"פער {a2-a0:>+6.1f}   n={len(g)}")
    print("\n  🔴 בדיקה: PIR הבסיס (בלי נעדרים) אמור להיות **דומה**")
    print("     בשלוש השורות, או גבוה יותר לעמוקות. אם הוא נמוך")
    print("     דווקא לעמוקות — מדד העומק עדיין מודד חולשה.")

    d.to_csv(PROCESSED_DIR / "depth_value.csv", index=False)
    h("מול התחזיות של קלוד")
    for k, v in PRED_CLAUDE.items():
        print(f"  {k:<10} {v}")
    print(SEP)


if __name__ == "__main__":
    main()