"""
availability_model.py  (Day 6)
------------------------------
כמה משחקים שחקן באמת ישחק בעונה הבאה.

    frac(i,t) = games(i,t) / max_games(t)

--------------------------------------------------------------------
למה זה מחליף את מודל השרידות בפירוק
--------------------------------------------------------------------
הפירוק הוא:  ערך = PIR למשחק * **משחקים צפויים**

מודל השרידות (יום 3) עונה על שאלה אחרת: "בהינתן שהשחקן היה בליגה
בעונה t, האם הוא בליגה ב-t+1". זה מערבב שלושה דברים - פרש, עבר
ל-NBA, **או שהמועדון בחר לא להחתים אותו מחדש**.

והשלישי הוא הבעיה. אנחנו *בוחרים* את הסגל. אם חתמנו על שחקן, הוא
בליגה בהגדרה - חלק ניכר מ"אי-השרידות" הוא ההחלטה שלנו ולא סיכון
חיצוני, ולהכפיל בו זה לספור את אותה החלטה פעמיים.

frac נמדד ישירות ואינו סובל מזה. הוא עדיין לא נקי לגמרי - מאמן
שמושיב שחקן משפיע עליו - אבל זו החלטה *בתוך* העונה, אחרי החתימה,
וזה בדיוק מה ש"משחקים צפויים" אמור לתפוס.

**מודל השרידות אינו נזרק.** הממצא שלו מיום 3 - שצעיר עם דקות
רוטציה שורד ב-77.4% - עומד. הוא פשוט עונה על שאלה על תחלופה
בליגה, לא על זמינות.
--------------------------------------------------------------------

המודל: GLM בינומי. games מתוך max_games הוא ספירת הצלחות מתוך
נסיונות - זו ההתפלגות הנכונה, והיא חסומה ב-[0,1] במבנה. OLS על
שיעור היה מחזיר ערכים מחוץ לתחום ומשקלל עונה של 28 משחקים כמו
עונה של 38.

חלון קלט: עד 2024 בלבד (החלטה סגורה). עונת 2025 היא היעד.

הרצה:
    python src/availability_model.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR

AGE_CENTER = 27.0
FEATURES = ["min_pg_lag", "frac_lag", "age_c", "log_gap"]
TRAIN_MAX_SEASON = 2024        # חלון הקלט
OOS_TEST_SEASON = 2024         # אימון עד 2023, מבחן על 2024
OUT = "player_availability.csv"

# ====================================================================
# תחזיות - נכתבות לפני ההרצה
# ====================================================================
PREDICTIONS = {
    "frac_lag": ("+", "sig",
                 "התמדה. מי ששיחק הרבה בשנה שעברה ישחק הרבה השנה - "
                 "זה אמור להיות הגורם הדומיננטי"),
    "min_pg_lag": ("+", "sig",
                   "דקות הן סימן לתפקיד. שחקן רוטציה נכנס לגיליון "
                   "ומשחק; שחקן 12 לא"),
    "age_c": ("-", "n.s.",
              "פציעות עולות עם הגיל, אבל corr(frac, age)=0.22 בלבד, "
              "ורובו נבלע ב-frac_lag ובדקות"),
    "log_gap": ("-", "sig",
                "פער בין עונות = השחקן היה מחוץ ליורוליג. הנתונים "
                "מצביעים לשם: יחס זמינות בפועל/מפוגרת הוא 0.962 "
                "בפער 1 מול 0.931 בפער 2"),
}
CALIB_MAX_GAP = 0.07           # סף שנקבע מראש, כמו 0.057 בשרידות
SIG = 0.10
# ====================================================================


def prepare():
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    gmax = ps.groupby("season").games.max().rename("gmax")
    ps = ps.merge(gmax, left_on="season", right_index=True)
    ps["frac"] = ps.games / ps.gmax

    ps = ps.sort_values(["player_code", "season"])
    g = ps.groupby("player_code", sort=False)
    ps["frac_lag"] = g.frac.shift(1)
    ps["min_pg_lag"] = g.min_per_game.shift(1)
    ps["season_lag"] = g.season.shift(1)
    ps["age_c"] = ps.age - AGE_CENTER

    # תיקון יום 6: המסנן gap==1 זרק 312 תצפיות (26%) והשאיר 36
    # מתוך 228 המועמדים בלי מודל כלל. אבל המדידה הראתה שהפער אינו
    # פוסל את הפיגור - הוא **מידע בפני עצמו**: יחס זמינות
    # בפועל/מפוגרת 0.962 בפער 1 מול 0.931 בפער 2.
    # לכן הפער נכנס כמשתנה במקום כמסנן. log כדי שהזנב (5,7,8
    # עונות) לא ישלוט.
    ps["gap"] = ps.season - ps.season_lag
    ps["log_gap"] = np.log(ps.gap)
    d = ps[ps.gap.notna() & (ps.gap >= 1) & ps.frac_lag.notna()].copy()

    # אין דליפה: כל פיצ'ר מגיע מ-t-1, המטרה מ-t
    assert (d.season_lag < d.season).all(), "דליפה: פיצ'ר מעונת היעד"
    return ps, d


def fit(d, label=""):
    X = sm.add_constant(d[FEATURES].astype(float))
    y = np.column_stack([d.games.values, (d.gmax - d.games).values])
    m = sm.GLM(y, X, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": d.player_code})
    if label:
        print(f"\n[{label}] n={int(m.nobs)} | "
              f"שחקנים={d.player_code.nunique()}")
        print(m.summary2().tables[1].round(4).to_string())
    return m


def report_vs_predictions(m):
    print("\n" + "=" * 74)
    print("תחזיות מול תוצאה")
    print("=" * 74)
    print(f"{'פרמטר':<16}{'תחזית':>10}{'בפועל':>11}{'p':>9}   הערכה")
    for f, (sign, sigflag, _) in PREDICTIONS.items():
        b, p = m.params[f], m.pvalues[f]
        got = "+" if b > 0 else "-"
        sg = "sig" if p < SIG else "n.s."
        ok = "OK" if (got == sign and sg == sigflag) else (
            "כיוון נכון" if got == sign else "REFUTED")
        print(f"{f:<16}{sign + '/' + sigflag:>10}{b:>11.4f}{p:>9.3f}   {ok}")
    print()
    for f, (_, _, why) in PREDICTIONS.items():
        print(f"  {f}: {why}")


def calibration(m, d):
    """המבחן האמיתי. מודל יכול לדרג נכון ולשקר על הרמה.

    אותו סף ואותה שיטה כמו במודל השרידות: עשירונים, פער מוחלט מרבי.
    """
    print("\n" + "=" * 74)
    print("כיול: חזוי מול נצפה, לפי עשירונים")
    print("=" * 74)
    d = d.copy()
    d["p"] = m.predict(sm.add_constant(d[FEATURES].astype(float)))
    d["dec"] = pd.qcut(d.p, 10, labels=False, duplicates="drop")
    cal = d.groupby("dec").agg(n=("frac", "size"), חזוי=("p", "mean"),
                               נצפה=("frac", "mean")).round(3)
    cal["פער"] = (cal.חזוי - cal.נצפה).round(3)
    print(cal.to_string())
    gap = float(cal.פער.abs().max())
    print(f"\n  פער מוחלט מרבי: {gap:.3f}  (סף שנקבע מראש: "
          f"{CALIB_MAX_GAP})  "
          f"{'[OK]' if gap <= CALIB_MAX_GAP else '[FAIL]'}")
    return gap


def oos(d):
    print("\n" + "=" * 74)
    print(f"מחוץ למדגם: אימון עד {OOS_TEST_SEASON - 1}, "
          f"מבחן על {OOS_TEST_SEASON}")
    print("=" * 74)
    tr = d[d.season < OOS_TEST_SEASON]
    te = d[d.season == OOS_TEST_SEASON]
    X = sm.add_constant(tr[FEATURES].astype(float))
    y = np.column_stack([tr.games.values, (tr.gmax - tr.games).values])
    mo = sm.GLM(y, X, family=sm.families.Binomial()).fit()
    p = mo.predict(sm.add_constant(te[FEATURES].astype(float)))
    print(f"  n אימון={len(tr)} | n מבחן={len(te)}")
    print(f"  ממוצע חזוי {p.mean():.3f} מול נצפה {te.frac.mean():.3f}  "
          f"(פער {p.mean() - te.frac.mean():+.3f})")
    print(f"  MAE ברמת שחקן: {float(np.abs(p - te.frac).mean()):.3f}")
    return float(p.mean() - te.frac.mean())


def curve(m):
    print("\n" + "=" * 74)
    print("שיעור המשחקים החזוי, לפי דקות מפוגרות (frac_lag=0.75, גיל=27)")
    print("=" * 74)
    grid = pd.DataFrame({"min_pg_lag": np.arange(4, 33, 4.0)})
    grid["frac_lag"] = 0.75
    grid["age_c"] = 0.0
    grid["log_gap"] = 0.0
    grid["חזוי"] = m.predict(sm.add_constant(grid, has_constant="add"))
    print(grid[["min_pg_lag", "חזוי"]].round(3).to_string(index=False))


def main():
    ps, d = prepare()
    print("=" * 74)
    print(f"AVAILABILITY MODEL | n={len(d)} | "
          f"שחקנים={d.player_code.nunique()} | "
          f"שיעור משחקים ממוצע={d.frac.mean():.3f}")
    print("=" * 74)
    print(f"  מקס משחקים לעונה: "
          f"{dict(ps.groupby('season').gmax.first().astype(int))}")

    train = d[d.season <= TRAIN_MAX_SEASON]
    print(f"  אימון על עונות יעד עד {TRAIN_MAX_SEASON}: n={len(train)}")

    m = fit(train, label="המפרט")
    report_vs_predictions(m)
    calibration(m, train)
    oos(d)
    curve(m)

    # --- פלט: תחזית לעונת הדמו ---
    tgt = d[d.season == ps.season.max()]
    pred = m.predict(sm.add_constant(tgt[FEATURES].astype(float)))
    out = pd.DataFrame({"player_code": tgt.player_code.values,
                        "season": tgt.season.values,
                        "avail_hat": pred.values,
                        "frac_actual": tgt.frac.values})
    dest = PROCESSED_DIR / OUT
    out.to_csv(dest, index=False)
    print(f"\n[נכתב] {dest} | {len(out)} שורות "
          f"(עונת {int(tgt.season.iloc[0])})")
    print(f"  avail_hat: חציון {out.avail_hat.median():.3f} | "
          f"טווח {out.avail_hat.min():.3f}-{out.avail_hat.max():.3f}")

    print("\n" + "=" * 74)
    print("  frac אינו נקי לגמרי: מאמן שמושיב שחקן משפיע עליו.")
    print("  אבל זו החלטה בתוך העונה, אחרי החתימה - וזה בדיוק מה")
    print("  ש'משחקים צפויים' אמור לתפוס. ל-Limitations.")
    print("=" * 74)


if __name__ == "__main__":
    main()