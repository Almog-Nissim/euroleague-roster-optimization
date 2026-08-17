"""
spec_min_lag.py  (Day 5, task 2)
--------------------------------
האם min_lag חוזר למפרט?

המפרט המלא שאושר ביום 4 כלל min_lag. המפרט שרץ בפועל ויתר עליו
בגלל n. השאלה שהועלתה: "האם נכון לרוץ על 3 משתנים בלי הדברים
החשובים שמצאנו?"

--------------------------------------------------------------------
מה שנמדד לפני כתיבת הסקריפט
--------------------------------------------------------------------
    corr(min_lag, pir_lag_shrunk) = 0.93
    corr(min_lag, age_c2)         = -0.23
    corr(min_lag, el_seasons)     = -0.14

0.93 על 27 תצפיות ו-18 clusters. הוספת min_lag למפרט לא שואלת
"האם השוק משלם על דקות" - היא מחלקת את אותו אות בין שני משתנים
ומנפחת את שתי שגיאות התקן.

ולכן הסקריפט מריץ שלוש גרסאות:

  1. נאיבי  - min_lag נוסף כמו שהוא. זו הגרסה שהמפרט המלא מבקש
  2. מוחלף  - min_lag במקום pir_lag_shrunk. מי מסביר טוב יותר לבדו
  3. מאונך  - min_lag_resid = השארית של min_lag על pir_lag_shrunk

גרסה 3 היא "דקות מעבר למה שהתפוקה מנבאת", ויש לה פרשנות נקייה:
האם השוק משלם על תפקיד וזמן משחק בנפרד מתוצר. זו השאלה שבגללה
min_lag היה במפרט המלא מלכתחילה.
--------------------------------------------------------------------

הרצה:
    python -m src.audits.spec_min_lag
    python src/audits/spec_min_lag.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROCESSED_DIR

BASE = ["pir_lag_shrunk", "age_c2", "el_seasons"]
SIG = 0.10

# ====================================================================
# תחזיות - נכתבות לפני ההרצה. זה המקום היחיד לערוך.
# ====================================================================
PRED = {
    "naive_min_lag_sig": False,
    "naive_pir_loses_sig": True,
    "naive_why": (
        "r=0.93. VIF צפוי סביב 7-8. שתי שגיאות התקן מתנפחות יחד; "
        "p של pir_lag_shrunk עולה מ-<0.001 ל->0.05"
    ),
    "swap_min_worse_r2": True,
    "swap_why": (
        "דקות הן פרוקסי לתפוקה, לא הפוך. המאמן מחלק דקות לפי מה שראה, "
        "ולכן min_lag נושא פחות מידע מ-pir_lag לבדו"
    ),
    "resid_sign": "+",
    "resid_p_range": (0.05, 0.20),
    "resid_why": (
        "תוספת קטנה אמיתית - שחקן שמקבל דקות מעבר לתפוקתו הוא לרוב "
        "הקמע, המנהיג, או מי שנחתם ביוקר. אבל 27 תצפיות לא יתפסו "
        "את זה במובהקות"
    ),
}

# כלל ההכרעה, נוסח לפני ההרצה:
# min_lag נכנס למפרט הרשמי רק אם גרסה 3 חיובית עם p < 0.10 וגם
# שורדת את רגישות k בלי היפוך סימן.
RESID_ENTRY_P = 0.10
# ====================================================================


def load():
    """המשתנה התלוי הוא log_rel, לא log_share.

    שינוי מיום 5, משימה 3b. share תלוי בגודל הסגל: הנתחים מסתכמים
    ל-1 בהגדרה, ולכן הנתח הממוצע הוא 1/N. סגל מכבי נע 12 -> 12 -> 15,
    כלומר share הכניס הפרש רמה מלאכותי של log(15/12) = 0.223 בעונת
    2025 - שלא קשור לשכר בכלל.

    rel = salary / mean_salary(club, season) = share * N מסלק אותו.
    הראיה שזה לא התאמה לסט המבחן: R2 על סט הכיול עצמו עלה
    מ-0.564 ל-0.619, בלי שום קשר להפועל.
    """
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})
    cal_all = anch[anch.usage == "calibrate"].copy()

    # N ו-mean_salary נספרים על כל שורות הסגל, כולל בלי קוד שחקן
    agg = cal_all.groupby("season").salary_mid.agg(["sum", "size"])
    agg["mean_salary"] = agg["sum"] / agg["size"]
    cal = cal_all[cal_all.player_code.notna()].merge(
        agg[["mean_salary", "size"]].rename(columns={"size": "roster_n"}),
        left_on="season", right_index=True)
    cal["log_rel"] = np.log(cal.salary_mid / cal.mean_salary)

    df = cal.merge(feat, on=["player_code", "season"], how="inner",
                   suffixes=("", "_f"))
    df = df.dropna(subset=BASE + ["min_lag", "log_rel"])
    print(f"[JOIN] מכבי calibrate: {len(df)} תצפיות | "
          f"{df.player_code.nunique()} שחקנים ייחודיים")
    print(f"       תלוי: log_rel (salary / mean_salary). "
          f"N לעונה: {dict(agg['size'])}")
    if df.empty:
        raise ValueError("אפס תצפיות - בדוק dtype של player_code")
    return df


def fit(d, features, label=""):
    X = sm.add_constant(d[list(features)].astype(float))
    m = sm.OLS(d.log_rel, X).fit(cov_type="cluster",
                                   cov_kwds={"groups": d.player_code})
    if label:
        print(f"\n[{label}] n={int(m.nobs)} | "
              f"clusters={d.player_code.nunique()} | "
              f"R2={m.rsquared:.3f} | adjR2={m.rsquared_adj:.3f}")
        for f in features:
            print(f"    {f:<20}{m.params[f]:>10.4f}  "
                  f"p={m.pvalues[f]:.3f}  "
                  f"SE={m.bse[f]:.4f}")
    return m


def vif(d, features):
    """VIF ידני - לא דורש תלות נוספת."""
    out = {}
    for f in features:
        others = [x for x in features if x != f]
        if not others:
            out[f] = 1.0
            continue
        X = sm.add_constant(d[others].astype(float))
        r2 = sm.OLS(d[f].astype(float), X).fit().rsquared
        out[f] = 1.0 / max(1e-9, 1 - r2)
    return out


def correlations(d):
    print("\n" + "=" * 74)
    print("מטריצת המתאמים - זה מה שמכתיב את מבנה הבדיקה")
    print("=" * 74)
    cols = BASE + ["min_lag"]
    print(d[cols].corr().round(3).to_string())
    r = d[["min_lag", "pir_lag_shrunk"]].corr().iloc[0, 1]
    print(f"\n  corr(min_lag, pir_lag_shrunk) = {r:.3f}")
    if abs(r) > 0.85:
        print("  [קולינאריות] מעל 0.85. הוספה נאיבית תחלק את האות")
        print("  בין שני משתנים ותנפח את שתי שגיאות התקן.")


def v1_naive(d, base_m):
    print("\n" + "=" * 74)
    print("גרסה 1 - נאיבי: min_lag נוסף כמו שהוא (המפרט המלא)")
    print("=" * 74)
    feats = BASE + ["min_lag"]
    m = fit(d, feats, label="מפרט + min_lag")

    print("\n  VIF:")
    for f, v in vif(d, feats).items():
        flag = "  <- מנופח" if v > 5 else ""
        print(f"    {f:<20}{v:>8.2f}{flag}")

    print("\n  השוואת שגיאות תקן, בסיס מול מורחב:")
    print(f"    {'פרמטר':<20}{'SE בסיס':>10}{'SE מורחב':>11}{'יחס':>8}"
          f"{'p בסיס':>10}{'p מורחב':>10}")
    for f in BASE:
        ratio = m.bse[f] / base_m.bse[f]
        print(f"    {f:<20}{base_m.bse[f]:>10.4f}{m.bse[f]:>11.4f}"
              f"{ratio:>8.2f}{base_m.pvalues[f]:>10.3f}{m.pvalues[f]:>10.3f}")

    min_sig = m.pvalues["min_lag"] < SIG
    pir_lost = (base_m.pvalues["pir_lag_shrunk"] < SIG and
                m.pvalues["pir_lag_shrunk"] >= SIG)
    print(f"\n  min_lag מובהק?          בפועל {min_sig} | "
          f"תחזית {PRED['naive_min_lag_sig']} | "
          f"{'OK' if min_sig == PRED['naive_min_lag_sig'] else 'REFUTED'}")
    print(f"  pir_lag איבד מובהקות?   בפועל {pir_lost} | "
          f"תחזית {PRED['naive_pir_loses_sig']} | "
          f"{'OK' if pir_lost == PRED['naive_pir_loses_sig'] else 'REFUTED'}")
    print(f"  נימוק: {PRED['naive_why']}")
    return m


def v2_swap(d, base_m):
    print("\n" + "=" * 74)
    print("גרסה 2 - מוחלף: min_lag במקום pir_lag_shrunk")
    print("=" * 74)
    feats = ["min_lag", "age_c2", "el_seasons"]
    m = fit(d, feats, label="מפרט עם min_lag במקום pir_lag")

    worse = m.rsquared < base_m.rsquared
    print(f"\n  R2 עם min_lag : {m.rsquared:.3f}")
    print(f"  R2 עם pir_lag : {base_m.rsquared:.3f}")
    print(f"  min_lag גרוע יותר?  בפועל {worse} | "
          f"תחזית {PRED['swap_min_worse_r2']} | "
          f"{'OK' if worse == PRED['swap_min_worse_r2'] else 'REFUTED'}")
    print(f"  נימוק: {PRED['swap_why']}")
    return m


def v3_orthogonal(d, base_m):
    """min_lag_resid = דקות מעבר למה שהתפוקה מנבאת.

    השארית מאונכת ל-pir_lag בהגדרה, ולכן מקדמי הבסיס לא זזים בכלל
    והתוספת נקראת נקי. הפרשנות: האם השוק משלם על תפקיד וזמן משחק
    בנפרד מתוצר.
    """
    print("\n" + "=" * 74)
    print("גרסה 3 - מאונך: min_lag_resid = דקות מעבר לתפוקה הצפויה")
    print("=" * 74)

    d = d.copy()
    X = sm.add_constant(d[["pir_lag_shrunk"]].astype(float))
    aux = sm.OLS(d.min_lag.astype(float), X).fit()
    d["min_lag_resid"] = aux.resid
    print(f"  רגרסיית העזר: min_lag ~ pir_lag_shrunk | R2={aux.rsquared:.3f}")
    print(f"  השארית מסבירה {1 - aux.rsquared:.1%} מהשונות של min_lag")

    feats = BASE + ["min_lag_resid"]
    m = fit(d, feats, label="מפרט + min_lag_resid")

    print("\n  מקדמי הבסיס לא אמורים לזוז (השארית מאונכת):")
    for f in BASE:
        print(f"    {f:<20}{base_m.params[f]:>10.4f} -> "
              f"{m.params[f]:>10.4f}   "
              f"delta={m.params[f] - base_m.params[f]:+.5f}")

    b, p = m.params["min_lag_resid"], m.pvalues["min_lag_resid"]
    got = "+" if b > 0 else "-"
    lo, hi = PRED["resid_p_range"]
    print(f"\n  min_lag_resid = {b:+.4f}  p={p:.3f}")
    print(f"  תחזית: סימן {PRED['resid_sign']}, p בטווח {lo}-{hi}")
    print(f"  סימן:  {'OK' if got == PRED['resid_sign'] else 'REFUTED'}")
    print(f"  p:     {'OK' if lo <= p <= hi else 'מחוץ לטווח'}")
    print(f"  נימוק: {PRED['resid_why']}")
    return m, d


def sensitivity_resid(d):
    """אם הסימן של השארית מתהפך בין k=20 ל-k=60, אין ממצא."""
    print("\n" + "=" * 74)
    print("רגישות ל-k של גרסה 3")
    print("=" * 74)
    rows = []
    for k in (20, 40, 60):
        dd = d.copy()
        w = dd.games_lag / (dd.games_lag + k)
        dd["pir_lag_shrunk"] = w * dd.pir_lag_raw + (1 - w) * dd.league_pir_mean
        X = sm.add_constant(dd[["pir_lag_shrunk"]].astype(float))
        dd["min_lag_resid"] = sm.OLS(dd.min_lag.astype(float), X).fit().resid
        m = fit(dd, BASE + ["min_lag_resid"])
        rows.append({"k": k,
                     "min_lag_resid": round(m.params["min_lag_resid"], 5),
                     "p": round(m.pvalues["min_lag_resid"], 3),
                     "R2": round(m.rsquared, 3)})
    r = pd.DataFrame(rows).set_index("k")
    print(r.to_string())
    stable = r["min_lag_resid"].apply(np.sign).nunique() == 1
    print(f"\n  סימן יציב על פני k: {stable}")
    return stable


def verdict(m_resid, stable):
    print("\n" + "=" * 74)
    print("כלל ההכרעה (נוסח לפני ההרצה)")
    print("=" * 74)
    print("  min_lag נכנס למפרט הרשמי רק אם גרסה 3 חיובית עם")
    print(f"  p < {RESID_ENTRY_P} וגם שורדת את רגישות k בלי היפוך סימן.")

    b, p = m_resid.params["min_lag_resid"], m_resid.pvalues["min_lag_resid"]
    enters = (b > 0) and (p < RESID_ENTRY_P) and stable
    print(f"\n  b={b:+.4f} | p={p:.3f} | יציב={stable}")
    if enters:
        print("\n  -> min_lag_resid נכנס למפרט.")
        print("     שים לב: מה שנכנס הוא השארית, לא min_lag הגולמי.")
        print("     המשמעות: השוק משלם על תפקיד בנפרד מתוצר.")
    else:
        print("\n  -> min_lag נשאר בהצהרה ומחוץ להרצה.")
        print("     זו לא ויתור על המנגנון - זו הצהרה ש-27 תצפיות")
        print("     לא יכולות להפריד בין שני משתנים שמתואמים ב-0.93.")
        print("     חוזרים לזה כשיימצא מועדון נוסף עם דאטה מדווח.")


def main():
    print("=" * 74)
    print("משימה 2 - האם min_lag חוזר למפרט?")
    print("=" * 74)

    d = load()
    correlations(d)
    base_m = fit(d, BASE, label="בסיס - המפרט המצומצם שרץ ביום 4")

    v1_naive(d, base_m)
    v2_swap(d, base_m)
    m_resid, d_resid = v3_orthogonal(d, base_m)
    stable = sensitivity_resid(d_resid)
    verdict(m_resid, stable)

    print("\n" + "=" * 74)
    print("  n אפקטיבי ~18 שחקנים ייחודיים. הסימנים הם מה שנקרא כאן.")
    print("=" * 74)


if __name__ == "__main__":
    main()