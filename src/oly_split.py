"""
oly_split.py  (Day 5, task 1b - לא היה בתוכנית)
-----------------------------------------------
למה ה-R2 צנח מ-0.636 (פנא' לבד) ל-0.379 (עם אולימפיאקוס)?

הוספת 15 תצפיות הורידה את ההסבר בשליש, ואת beta(pir) מ-0.162
ל-0.109. עם 29 תצפיות זה יכול להיות רעש, אבל זה גם יכול להיות
משהו שצריך לדעת לפני שמשתמשים ב-structure_only כעדות למבנה.

שלוש השערות, והרצה אחת מפרידה ביניהן:

  A. אולימפיאקוס רועשת    -> R2 נמוך אצלה, beta דומה לפנא'
  B. המועדונים שונים      -> R2 סביר אצלה, beta שונה מהותית
  C. הגבלת טווח           -> שונות log_share קטנה יותר אצלה,
                             ו-beta שטוח מכנית

C היא ההשערה שקשה לראות בלי למדוד, והיא כבר תפסה אותנו פעם אחת
היום (ה-7.5x שהפך ל-3.62). לכן היא נבדקת מפורשות.

תחזית שנכתבה לפני ההרצה:
    C. אותו דפוס בדיוק. אולימפיאקוס היא הסגל היחיד מבין הארבעה
    שכל 15 השורות שלו נושאות קוד שחקן - אין לה זנב חתוך, ולכן
    אין לה גם את הקצוות שמייצרים שיפוע. פנא' לעומתה איבדה 7
    שורות זולות, ומה שנשאר הוא צמרת דחוסה עם שונות מלאכותית.
    ההשוואה בין השתיים היא בין שני מדגמים מצונזרים אחרת.

הרצה:
    python src/audits/oly_split.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROCESSED_DIR

FEATURES = ["pir_lag_shrunk", "age_c2", "el_seasons"]
CONFIGS = [(["PAN"], "פנאתינייקוס"), (["OLY"], "אולימפיאקוס"),
           (["PAN", "OLY"], "משולב")]
MACCABI = {"n": 27, "R2": 0.564, "beta_pir": 0.229, "var_log_share": 0.3968}


def load(clubs, season=2025):
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})
    sub = anch[anch.club.isin(clubs) & (anch.season == season)].copy()
    payroll = sub.groupby(["club", "season"]).salary_mid.sum().rename(
        "team_payroll")
    sub = sub.merge(payroll, left_on=["club", "season"], right_index=True)
    sub["log_share"] = np.log(sub.salary_mid / sub.team_payroll)
    named = sub[sub.player_code.notna()]
    df = named.merge(feat, on=["player_code", "season"], how="inner",
                     suffixes=("", "_f")).dropna(
        subset=FEATURES + ["log_share"])
    return sub, df


def fit(d):
    X = sm.add_constant(d[FEATURES].astype(float))
    return sm.OLS(d.log_share, X).fit(cov_type="cluster",
                                      cov_kwds={"groups": d.player_code})


def censoring_row(raw, df, label):
    """כמה מהסגל שרד עד לרגרסיה, ומה זה עשה לפיזור.

    זו הבדיקה שהפילה את ה-7.5x. היא רצה עכשיו על כל מועדון בנפרד.
    """
    kept = len(df) / len(raw)
    # פיזור על הסגל המלא מול פיזור בסט האמידה
    full_ratio = raw.salary_mid.max() / raw.salary_mid.median()
    est_ratio = df.salary_mid.max() / df.salary_mid.median()
    return {
        "מועדון": label,
        "סגל מלא": len(raw),
        "בסט האמידה": len(df),
        "שרדו": f"{kept:.0%}",
        "יחס מלא": round(full_ratio, 2),
        "יחס אמידה": round(est_ratio, 2),
        "var(log_share)": round(float(df.log_share.var()), 4),
    }


def main():
    print("=" * 74)
    print("משימה 1b - מה קרה כשאולימפיאקוס נכנסה?")
    print("=" * 74)

    fits, cens = [], []
    for clubs, label in CONFIGS:
        raw, df = load(clubs)
        if len(df) < 6:
            print(f"[SKIP] {label}: רק {len(df)} תצפיות")
            continue
        m = fit(df)
        fits.append({
            "מועדון": label,
            "n": int(m.nobs),
            "R2": round(m.rsquared, 3),
            "adjR2": round(m.rsquared_adj, 3),
            "beta(pir)": round(m.params["pir_lag_shrunk"], 4),
            "p": round(m.pvalues["pir_lag_shrunk"], 3),
            "sd(pir_lag)": round(float(df.pir_lag_shrunk.std()), 2),
        })
        cens.append(censoring_row(raw, df, label))

    print("\nהאמידה:")
    f = pd.DataFrame(fits).set_index("מועדון")
    print(f.to_string())
    print(f"\n  לייחוס - מכבי: n={MACCABI['n']}, R2={MACCABI['R2']}, "
          f"beta(pir)={MACCABI['beta_pir']}")

    print("\n" + "=" * 74)
    print("צנזורה ופיזור - הבדיקה שהפילה את ה-7.5x, לכל מועדון בנפרד")
    print("=" * 74)
    c = pd.DataFrame(cens).set_index("מועדון")
    print(c.to_string())
    print(f"\n  מכבי לייחוס: var(log_share)={MACCABI['var_log_share']}")

    # --- הכרעה בין A, B, C ---
    print("\n" + "=" * 74)
    print("הכרעה בין שלוש ההשערות")
    print("=" * 74)

    try:
        pan = f.loc["פנאתינייקוס"]
        oly = f.loc["אולימפיאקוס"]
        cp, co = c.loc["פנאתינייקוס"], c.loc["אולימפיאקוס"]
    except KeyError:
        print("  [SKIP] אין את שני המועדונים בנפרד")
        return

    print(f"  שרדו עד הרגרסיה : פנא' {cp['שרדו']} | אולי' {co['שרדו']}")
    print(f"  יחס מלא->אמידה   : פנא' {cp['יחס מלא']}->{cp['יחס אמידה']} | "
          f"אולי' {co['יחס מלא']}->{co['יחס אמידה']}")
    print(f"  var(log_share)   : פנא' {cp['var(log_share)']} | "
          f"אולי' {co['var(log_share)']}")
    print(f"  beta(pir)        : פנא' {pan['beta(pir)']} | "
          f"אולי' {oly['beta(pir)']}")
    print(f"  R2               : פנא' {pan['R2']} | אולי' {oly['R2']}")

    beta_gap = abs(pan["beta(pir)"] - oly["beta(pir)"])
    var_gap = cp["var(log_share)"] / max(1e-9, co["var(log_share)"])

    print()
    if var_gap > 1.5 or var_gap < 0.67:
        print(f"  [C] שונות ה-log_share נבדלת פי {var_gap:.2f} בין השתיים.")
        print("  שיפוע שטוח יותר על תלוי עם פחות פיזור הוא תוצאה מכנית,")
        print("  לא ממצא על תמחור. הפער ב-beta לא נקרא כהבדל בין מועדונים")
        print("  עד שהטווח מנוטרל.")
    elif beta_gap > 0.08:
        print("  [B] הטווח דומה אבל beta נבדל מהותית - המועדונים באמת")
        print("  מתמחרים אחרת. זה כן ממצא, והוא רלוונטי ישירות לשאלה")
        print("  אם מודל שמכויל על מכבי מעביר להפועל.")
    elif oly["R2"] < 0.25:
        print("  [A] הטווח דומה, beta דומה, אבל אולימפיאקוס לא מוסברת.")
        print("  רעש, לא מבנה. הצניחה ב-R2 המשולב היא דילול.")
    else:
        print("  [לא מוכרע] אף אחד מהתנאים לא נחתך נקי על n הזה.")

    print("\n" + "=" * 74)
    print("  אזהרה: 14 ו-15 תצפיות. כל ההשוואה כאן היא בטווח הרעש")
    print("  אלא אם הפער גדול. היא נועדה לשלול, לא לקבוע.")
    print("=" * 74)


if __name__ == "__main__":
    main()