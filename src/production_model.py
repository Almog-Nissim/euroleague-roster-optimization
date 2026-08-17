"""
production_model.py  (Day 6)
----------------------------
הגורם השני בפירוק, ואחרון שנבנה:

    expected value = **(PIR per minute)** × (minutes) × (expected games)

עד עכשיו `ppm` היה פיגור מוכווץ בלבד — כלומר הנחה שהתפוקה בעונה
הבאה שווה למשוקללת של הקודמות. זה לא מודל, וחשוב מכך: **לא היה
לו אומדן פיזור**, ולכן המונטה קרלו לא יכול היה להפיץ דרכו כלום.

--------------------------------------------------------------------
מה שנמדד לפני כתיבת הסקריפט
--------------------------------------------------------------------
    corr(ppm, ppm_lag) = 0.491        התמדה בינונית, לא גבוהה
    ppm ~ ppm_lag       מקדם 0.547    **התכנסות חזקה לממוצע**
    sd שארית            0.185         מול חציון ppm של 0.375
                                      => מקדם שונות של ~49%

וטרוסקדסטיות חדה:

    דקות מפוגרות    n     sd(ppm)
    (0, 10]        160     0.376
    (10, 15]       204     0.167
    (15, 20]       298     0.162
    (20, 25]       328     0.140
    (25, 40]       206     0.142

**פי 2.7 בין הקצוות.** שחקן ששיחק 8 דקות אינו רק פחות טוב - הוא
הרבה פחות *צפוי*. אומדן פיזור אחיד היה מסתיר בדיוק את זה, ולכן
הפיזור נאמד כפונקציה של דקות ולא כקבוע.

זה גם אומר שה-CV=0.25 שהיה פלסטר ב-v0 **הקטין את אי-הוודאות
בערך בחצי.**
--------------------------------------------------------------------

ערכי קיצון: ppm נע -12.0 עד 5.68 בגלמי, כי מי ששיחק דקה אחת מחלק
ב-1. ההתכווצות מטפלת בזה בצד הקלט, והמשקלות בצד המטרה.

WLS: עונה של 30 דקות למשחק נושאת יותר מידע מעונה של 5, והמשקל
הוא סך הדקות.

חלון קלט: עד 2024. עונת 2025 היא היעד.

הרצה:
    python src/production_model.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR

AGE_CENTER = 27.0
K_PPM = 450.0                  # דקות לחצי-משקל, כמו במנוע
FEATURES = ["ppm_lag_shrunk", "min_pg_lag", "age_c",
            "el_seasons_lag", "log_gap"]
TRAIN_MAX_SEASON = 2024
OOS_TEST_SEASON = 2024
OUT = "player_production.csv"

# ====================================================================
# תחזיות - נכתבות לפני ההרצה
# ====================================================================
PREDICTIONS = {
    "ppm_lag_shrunk": ("+", "sig",
                       "התמדה, והגורם הדומיננטי. אבל המקדם צפוי "
                       "**מתחת ל-1** - 0.547 בגלמי, וההתכווצות אמורה "
                       "להעלות אותו כי היא כבר הסירה חלק מהרעש"),
    "min_pg_lag": ("+", "sig",
                   "דקות הן מידע על תפקיד מעבר לתפוקה. מאמן שנותן "
                   "25 דקות יודע משהו שלא נמצא ב-ppm לבדו"),
    "age_c": ("-", "n.s.",
              "דעיכה. אבל הגיל יצא ריק שבע פעמים בפרויקט הזה, "
              "ואין סיבה שהפעם יהיה אחרת"),
    "el_seasons_lag": ("0", "n.s.",
                       "ותק מסביר *מחיר*, לא תפוקה. באגף הערך אין לו "
                       "מה לתרום מעבר ל-ppm ולדקות"),
    "log_gap": ("0", "n.s.",
                "בניגוד לזמינות - כאן הפער כמעט לא אמור להשפיע. "
                "יחס ppm בפועל/מפוגר הוא 0.984 בפער 1 מול 0.976 "
                "בפער 2. הפרש זניח"),
}
SIG = 0.10
CALIB_MAX_GAP = 0.05
# ====================================================================


def prepare():
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    ps = ps[ps.min_per_game > 0].copy()
    ps["ppm"] = ps.pir_per_game / ps.min_per_game
    ps["minutes_tot"] = ps.min_per_game * ps.games
    ps = ps.sort_values(["player_code", "season"])
    g = ps.groupby("player_code", sort=False)

    ps["ppm_lag"] = g.ppm.shift(1)
    ps["min_pg_lag"] = g.min_per_game.shift(1)
    ps["mins_lag"] = g.minutes_tot.shift(1)
    ps["season_lag"] = g.season.shift(1)
    ps["el_seasons_lag"] = g.cumcount()          # עונות קודמות
    ps["age_c"] = ps.age - AGE_CENTER

    # ראו הנימוק ב-availability_model: הפער הוא מידע, לא פסילה
    ps["gap"] = ps.season - ps.season_lag
    ps["log_gap"] = np.log(ps.gap)
    d = ps[ps.gap.notna() & (ps.gap >= 1) & ps.ppm_lag.notna()].copy()

    # התכווצות לממוצע הליגה, משוקללת דקות - אותו מנגנון כמו pir_lag
    league = float((d.ppm_lag * d.mins_lag).sum() / d.mins_lag.sum())
    w = d.mins_lag / (d.mins_lag + K_PPM)
    d["ppm_lag_shrunk"] = w * d.ppm_lag + (1 - w) * league
    d["shrink_w"] = w
    d["league_ppm"] = league

    assert (d.season_lag < d.season).all(), "דליפה: פיצ'ר מעונת היעד"
    return ps, d, league


def fit(d, label=""):
    """WLS: עונה ארוכה נושאת יותר מידע מעונה קצרה."""
    X = sm.add_constant(d[FEATURES].astype(float))
    m = sm.WLS(d.ppm, X, weights=d.minutes_tot).fit(
        cov_type="cluster", cov_kwds={"groups": d.player_code})
    if label:
        print(f"\n[{label}] n={int(m.nobs)} | "
              f"שחקנים={d.player_code.nunique()} | R2={m.rsquared:.3f}")
        print(m.summary2().tables[1].round(4).to_string())
    return m


def report_vs_predictions(m):
    print("\n" + "=" * 74)
    print("תחזיות מול תוצאה")
    print("=" * 74)
    print(f"{'פרמטר':<20}{'תחזית':>10}{'בפועל':>11}{'p':>9}   הערכה")
    for f, (sign, sigflag, _) in PREDICTIONS.items():
        b, p = m.params[f], m.pvalues[f]
        sg = "sig" if p < SIG else "n.s."
        if sign == "0":
            ok = "OK" if sg == "n.s." else "REFUTED"
            got = "0"
        else:
            got = "+" if b > 0 else "-"
            ok = "OK" if (got == sign and sg == sigflag) else (
                "כיוון נכון" if got == sign else "REFUTED")
        print(f"{f:<20}{sign + '/' + sigflag:>10}{b:>11.4f}{p:>9.3f}   {ok}")
    print()
    for f, (_, _, why) in PREDICTIONS.items():
        print(f"  {f}: {why}")

    b = m.params["ppm_lag_shrunk"]
    print(f"\n  התכנסות לממוצע: מקדם {b:.3f}. "
          f"{'מתחת ל-1 כפי שנחזה' if b < 1 else 'מעל 1 — REFUTED'}")
    print(f"  שחקן שסטה מהממוצע נסוג אליו ב-{1 - b:.0%} תוך עונה.")


def dispersion(m, d):
    """**זה התוצר העיקרי של הקובץ.**

    מודל נקודתי לתפוקה שווה מעט; המונטה קרלו צריך התפלגות.
    והפיזור אינו קבוע - הוא פי 2.7 בין מי ששיחק 8 דקות למי ששיחק 30.

    לכן sd השארית נאמד כפונקציה של דקות, ולא כמספר יחיד.
    """
    print("\n" + "=" * 74)
    print("פיזור השארית — התוצר העיקרי")
    print("=" * 74)
    d = d.copy()
    d["resid"] = d.ppm - m.predict(sm.add_constant(d[FEATURES].astype(float)))

    b = pd.cut(d.min_pg_lag, [0, 10, 15, 20, 25, 40])
    t = d.groupby(b, observed=True).agg(
        n=("resid", "size"), sd=("resid", "std")).round(4)
    t["CV"] = (t.sd / d.groupby(b, observed=True).ppm.mean()).round(3)
    print(t.to_string())

    # log(sd) ~ log(דקות): פשוט, מונוטוני, ולא דורש דליים
    dd = d[d.min_pg_lag > 0].copy()
    dd["a"] = np.abs(dd.resid)
    sd_m = sm.OLS(np.log(dd.a.clip(lower=1e-4)),
                  sm.add_constant(np.log(dd.min_pg_lag))).fit()
    slope = float(sd_m.params.iloc[1])
    print(f"\n  log|שארית| ~ log(דקות): שיפוע {slope:+.3f} "
          f"(p={sd_m.pvalues.iloc[1]:.3f})")
    print(f"  שיפוע שלילי = מי ששיחק פחות, פחות צפוי. "
          f"{'מאושר' if slope < 0 else 'REFUTED'}")

    overall = float(np.std(d.resid, ddof=len(m.params)))
    print(f"\n  sd כולל: {overall:.4f} | ppm חציוני: {d.ppm.median():.4f} "
          f"| CV ≈ {overall / d.ppm.median():.0%}")
    print(f"  🔴 ב-v0 הונח CV=0.25. **אי-הוודאות גדולה כמעט פי שניים.**")
    return sd_m, overall


def calibration(m, d):
    print("\n" + "=" * 74)
    print("כיול: חזוי מול נצפה, לפי עשירונים")
    print("=" * 74)
    d = d.copy()
    d["p"] = m.predict(sm.add_constant(d[FEATURES].astype(float)))
    d["dec"] = pd.qcut(d.p, 10, labels=False, duplicates="drop")
    cal = d.groupby("dec").agg(n=("ppm", "size"), חזוי=("p", "mean"),
                               נצפה=("ppm", "mean")).round(3)
    cal["פער"] = (cal.חזוי - cal.נצפה).round(3)
    print(cal.to_string())
    gap = float(cal.פער.abs().max())
    print(f"\n  פער מוחלט מרבי: {gap:.3f}  (סף מראש {CALIB_MAX_GAP})  "
          f"{'[OK]' if gap <= CALIB_MAX_GAP else '[FAIL]'}")
    return gap


def oos(d):
    print("\n" + "=" * 74)
    print(f"מחוץ למדגם: אימון עד {OOS_TEST_SEASON - 1}, "
          f"מבחן על {OOS_TEST_SEASON}")
    print("=" * 74)
    tr, te = d[d.season < OOS_TEST_SEASON], d[d.season == OOS_TEST_SEASON]
    mo = sm.WLS(tr.ppm, sm.add_constant(tr[FEATURES].astype(float)),
                weights=tr.minutes_tot).fit()
    p = mo.predict(sm.add_constant(te[FEATURES].astype(float)))
    print(f"  n אימון={len(tr)} | n מבחן={len(te)}")
    print(f"  ממוצע חזוי {p.mean():.4f} מול נצפה {te.ppm.mean():.4f}  "
          f"(פער {p.mean() - te.ppm.mean():+.4f})")
    print(f"  MAE ברמת שחקן: {float(np.abs(p - te.ppm).mean()):.4f}")
    naive = float(np.abs(te.ppm_lag_shrunk - te.ppm).mean())
    print(f"  MAE של הפיגור המוכווץ לבדו: {naive:.4f}  "
          f"<- מה שהמנוע השתמש בו עד עכשיו")
    print(f"  שיפור: {1 - np.abs(p - te.ppm).mean() / naive:+.1%}")


def main():
    ps, d, league = prepare()
    print("=" * 74)
    print(f"PRODUCTION MODEL | n={len(d)} | "
          f"שחקנים={d.player_code.nunique()} | "
          f"ppm ממוצע ליגה={league:.4f}")
    print("=" * 74)

    train = d[d.season <= TRAIN_MAX_SEASON]
    print(f"  אימון על עונות יעד עד {TRAIN_MAX_SEASON}: n={len(train)}")

    m = fit(train, label="המפרט")
    report_vs_predictions(m)
    calibration(m, train)
    sd_m, overall = dispersion(m, train)
    oos(d)

    # --- פלט לעונת הדמו ---
    tgt = d[d.season == ps.season.max()].copy()
    tgt["ppm_hat"] = m.predict(sm.add_constant(tgt[FEATURES].astype(float)))
    tgt["gap"] = tgt.gap
    tgt["ppm_sd"] = np.exp(sd_m.predict(
        sm.add_constant(np.log(tgt.min_pg_lag.clip(lower=1.0))))) * 1.2533
    out = tgt[["player_code", "season", "ppm_hat", "ppm_sd", "gap",
               "ppm_lag_shrunk", "ppm"]].rename(
        columns={"ppm": "ppm_actual"})
    dest = PROCESSED_DIR / OUT
    out.to_csv(dest, index=False)
    print(f"\n[נכתב] {dest} | {len(out)} שורות")
    print(f"  ppm_hat: חציון {out.ppm_hat.median():.4f} | "
          f"טווח {out.ppm_hat.min():.4f}-{out.ppm_hat.max():.4f}")
    print(f"  ppm_sd : חציון {out.ppm_sd.median():.4f} | "
          f"טווח {out.ppm_sd.min():.4f}-{out.ppm_sd.max():.4f}")
    print("  (הפיזור מומר מ-E|שארית| ל-sd במקדם sqrt(pi/2)=1.2533, "
          "בהנחת נורמליות)")

    print("\n" + "=" * 74)
    print("  זה מודל של תפוקה *ממוצעת לדקה*. הוא אינו יודע על")
    print("  התאמה לקבוצה, על שינוי תפקיד, ולא על פציעות שמשנות")
    print("  איכות ולא רק כמות. ל-Limitations.")
    print("=" * 74)


if __name__ == "__main__":
    main()