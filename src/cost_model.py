"""
cost_model.py  (Day 4, task 3)
------------------------------
אומד את פונקציית העלות ומריץ את מבחן הטאוטולוגיה.

המשתנה התלוי הוא נתח מהתקציב, לא דולרים:

    share(i) = salary(i) / team_payroll(season)

הנימוק: תקציב מכבי נע 7.74M -> 6.31M -> 10.80M בשלוש עונות. דאמי
לעונה היה עולה שני פרמטרים מתוך תקציב של ארבעה. חלוקה בתקציב מסלקת
את אפקט העונה בעלות אפס פרמטרים, ומסלקת גם את אינפלציית השכר, שער
החליפין, והקפיצה של 72% - שלושתם נעלמים ביחס.
זה גם המבנה הנכון: PuLP מקצה נתח מתקציב נתון.

מפרט (אושר יום 4, מצומצם בגלל n):
    log(share) = b0 + b1*pir_lag_shrunk + b2*age_c2 + b3*el_seasons

ירדו מהמפרט המלא: min_lag (מתואם ל-PIR), age_c הליניארי,
ו-el_seasons הקטגוריאלי -> רציף. חוזרים אם יימצא מועדון נוסף.

אזהרה על גודל מדגם: ~39 תצפיות, 4 פרמטרים = כ-10 לפרמטר, אבל
11 מתוך 28 השחקנים מופיעים ביותר מעונה אחת, ולכן ה-n האפקטיבי
קרוב יותר ל-28. שגיאות התקן מקובצות לפי שחקן. הסימנים הם מה
שנקרא כאן, לא הגדלים.

תחזיות נכתבו לפני ההרצה - ראו PREDICTIONS.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR

FEATURES = ["pir_lag_shrunk", "age_c2", "el_seasons"]

PREDICTIONS = {
    "pir_lag_shrunk": ("+", "תפוקה אחרונה היא העוגן; הגורם הדומיננטי"),
    "age_c2":         ("-", "שיא מחיר סביב 27 - הפוך מצד השרידות, שם הוא נזרק"),
    "el_seasons":     ("+", "פרמיית ודאות על שחקן מוכח"),
}
SPEARMAN_PREDICTED = (0.60, 0.80)
SPEARMAN_EMPTY = 0.90          # מעל זה המודל ריק


def load():
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})

    cal = anch[(anch.usage == "calibrate") & anch.player_code.notna()].copy()
    payroll = cal.groupby("season").salary_mid.sum().rename("team_payroll")
    cal = cal.merge(payroll, left_on="season", right_index=True)
    cal["share"] = cal.salary_mid / cal.team_payroll
    cal["log_share"] = np.log(cal.share)

    df = cal.merge(feat, on=["player_code", "season"], how="inner",
                   suffixes=("", "_f"))
    print(f"[JOIN] עוגני כיול: {len(cal)} | עם פיצ'רים: {len(df)} | "
          f"נשרו: {len(cal) - len(df)}")
    if len(df) < len(cal):
        missing = set(cal.player_code) - set(df.player_code)
        lost = cal[cal.player_code.isin(missing)]
        print("  ללא pir_lag (אין עונת יורוליג קודמת):")
        print("   ", ", ".join(sorted(lost.player_name_el.unique())))
    return df


def fit(df, features=FEATURES, label=""):
    d = df.dropna(subset=features + ["log_share"])
    X = sm.add_constant(d[features].astype(float))
    m = sm.OLS(d.log_share, X).fit(cov_type="cluster",
                                   cov_kwds={"groups": d.player_code})
    if label:
        print(f"\n[{label}] n={int(m.nobs)} | "
              f"clusters={d.player_code.nunique()} | R2={m.rsquared:.3f}")
    return m, d


def report_vs_predictions(m):
    print("\n" + "=" * 74)
    print("תחזיות מול תוצאה")
    print("=" * 74)
    print(f"{'פרמטר':<18}{'תחזית':>7}{'בפועל':>11}{'p':>9}"
          f"{'CI 95%':>22}{'':>6}")
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


def tautology_test(df, m, d):
    """ספירמן בין עלות משוערת ל-PIR באותה עונה.
    מעל 0.90 המודל ריק - הוא רק משכתב את התפוקה."""
    pred = m.predict(sm.add_constant(d[FEATURES].astype(float)))
    rho, p = spearmanr(pred, d.pir_per_game)
    rho_obs, _ = spearmanr(d.log_share, d.pir_per_game)

    print("\n" + "=" * 74)
    print("מבחן הטאוטולוגיה")
    print("=" * 74)
    lo, hi = SPEARMAN_PREDICTED
    print(f"  תחזית שנכתבה מראש : {lo:.2f}-{hi:.2f}")
    print(f"  עלות חזויה ~ PIR   : rho={rho:+.3f}  (p={p:.4f})")
    print(f"  עלות בפועל ~ PIR   : rho={rho_obs:+.3f}   <- כמה השוק עצמו מתמחר תפוקה")
    if rho > SPEARMAN_EMPTY:
        print(f"  [FAIL] מעל {SPEARMAN_EMPTY} - המודל משכתב PIR ואין שונות עצמאית")
    elif lo <= rho <= hi:
        print("  [OK] בתוך הטווח שנחזה - יש שונות עצמאית")
    else:
        print(f"  [מחוץ לטווח] התחזית הופרכה, אך {rho:.3f} < {SPEARMAN_EMPTY} "
              "- המודל אינו ריק")
    return rho


def sensitivity(df):
    """k ומשקלי ה-lag הם פרמטרים מוצהרים. אם הסימנים מתהפכים ביניהם,
    המודל אינו יציב וזה ממצא."""
    print("\n" + "=" * 74)
    print("רגישות: האם הסימנים יציבים?")
    print("=" * 74)

    rows = []
    for k in (20, 40, 60):
        d = df.dropna(subset=FEATURES + ["log_share"]).copy()
        w = d.games_lag / (d.games_lag + k)
        d["pir_lag_shrunk"] = w * d.pir_lag_raw + (1 - w) * d.league_pir_mean
        m, dd = fit(d)
        rows.append({"k": k, **{f: m.params[f] for f in FEATURES},
                     "R2": m.rsquared})

    r = pd.DataFrame(rows).set_index("k").round(4)
    print(r.to_string())
    signs = {f: r[f].apply(np.sign).nunique() for f in FEATURES}
    flipped = [f for f, n in signs.items() if n > 1]
    if flipped:
        print(f"  [WARN] סימן מתהפך ב: {flipped} - המודל אינו יציב ל-k")
    else:
        print("  [OK] כל הסימנים יציבים על פני k")


def leave_one_season_out(df):
    """עם 3 עונות בלבד - האם התוצאה נשענת על עונה אחת?"""
    print("\n" + "=" * 74)
    print("השמטת עונה אחת בכל פעם")
    print("=" * 74)
    rows = []
    for s in sorted(df.season.unique()):
        sub = df[df.season != s]
        try:
            m, _ = fit(sub)
            rows.append({"בלי": s, "n": int(m.nobs),
                         **{f: round(m.params[f], 4) for f in FEATURES}})
        except Exception as e:
            rows.append({"בלי": s, "n": 0, "error": str(e)[:30]})
    print(pd.DataFrame(rows).to_string(index=False))


def main():
    df = load()
    m, d = fit(df, label="מפרט מלא")
    print(m.summary().tables[1])
    report_vs_predictions(m)
    tautology_test(df, m, d)
    sensitivity(df)
    leave_one_season_out(df)

    print("\n" + "=" * 74)
    print("אזהרה: n אפקטיבי ~28 שחקנים ייחודיים על 4 פרמטרים.")
    print("רווחי הסמך רחבים. הסימנים הם מה שנקרא כאן, לא הגדלים.")
    print("=" * 74)


if __name__ == "__main__":
    main()