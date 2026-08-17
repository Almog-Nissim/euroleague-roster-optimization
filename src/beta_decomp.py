"""
beta_decomp.py  (Day 5, task 1c - לא היה בתוכנית)
--------------------------------------------------
למה beta(pir) נע 0.229 -> 0.162 -> 0.097 בין מועדונים?

שלושה מועמדים, ואי אפשר להפריד ביניהם מהמקדם עצמו:

  1. תמחור   - המועדון באמת פחות מתגמל תפוקה
  2. דחיסה   - שכר מוערך מעוגל למרכז ע"י המעריך
  3. הרכב    - הסגל פשוט מגוון יותר בתפוקה

הפירוק שמפריד ביניהם הוא זהות, לא הנחה:

    beta  =  r  x  sd(log_share) / sd(pir_lag)
             ^        ^                ^
             |        |                |
          תמחור    דחיסה            הרכב

כל אחד משלושת המועמדים מזיז גורם אחר. מספיק להסתכל איזה זז.

--------------------------------------------------------------------
משמעת חוץ-מדגמית - קראו לפני שמשנים משהו
--------------------------------------------------------------------
משימה 3 היא מבחן חוץ-מדגמי על הפועל. אם נאמוד את beta של הפועל
כדי לקבוע את התחזית למשימה 3, נשתמש בסט המבחן כדי לנסח את המבחן -
וזה הורס אותו.

לכן הסקריפט הזה נוגע בהפועל **רק בצד הפיצ'רים**: sd(pir_lag).
זה המכנה בפירוק, והוא מחושב מקופסאות סקור בלבד. השכר של הפועל
משמש כאן אך ורק כדי לדעת אילו 10 שורות נכנסות למבחן - הערכים
עצמם לא נקראים, ואין מהם אף חישוב.

מה שזה קונה: תחזית **נגזרת** ל-bias במשימה 3, שמבוססת על מספר
נמדד ולא על ויכוח פרשני, ובלי לגעת בתוצאה.
--------------------------------------------------------------------

הרצה:
    python src/audits/beta_decomp.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROCESSED_DIR

FEATURES = ["pir_lag_shrunk", "age_c2", "el_seasons"]

# מועדוני הכיול והמבנה - כאן מותר להסתכל על השכר
FIT_CONFIGS = [
    ("מכבי", {"usage": "calibrate"}),
    ("פנאתינייקוס", {"club": ["PAN"], "season": 2025}),
    ("אולימפיאקוס", {"club": ["OLY"], "season": 2025}),
    ("פנא'+אולי'", {"club": ["PAN", "OLY"], "season": 2025}),
]
# סט המבחן - כאן קוראים רק את צד הפיצ'רים
TEST_CONFIG = ("הפועל (מבחן)", {"usage": "test"})

REF = "מכבי"


def _select(anch, spec):
    if "usage" in spec:
        return anch[anch.usage == spec["usage"]].copy()
    sub = anch[anch.club.isin(spec["club"])]
    if "season" in spec:
        sub = sub[sub.season == spec["season"]]
    return sub.copy()


def load(spec, with_salary=True):
    """with_salary=False מחזיר את אותן שורות בלי שום חישוב על השכר.

    בחירת השורות עדיין נשענת על קובץ העוגנים - אחרת אי אפשר לדעת
    מי בסגל. אבל salary_mid לא נקרא, ו-log_share לא מחושב.
    """
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})
    sub = _select(anch, spec)
    sub = sub[sub.player_code.notna()]

    if with_salary:
        payroll = sub.groupby(["club", "season"]).salary_mid.sum().rename(
            "team_payroll")
        sub = sub.merge(payroll, left_on=["club", "season"],
                        right_index=True)
        sub["log_share"] = np.log(sub.salary_mid / sub.team_payroll)
        need = FEATURES + ["log_share"]
    else:
        sub = sub[["player_code", "season", "club"]]
        need = FEATURES

    df = sub.merge(feat, on=["player_code", "season"], how="inner",
                   suffixes=("", "_f")).dropna(subset=need)
    return df


def decompose(df, label):
    """beta = r * sd(y)/sd(x). זהות, לא מודל.

    ה-r כאן הוא קורלציה פשוטה בין pir_lag ל-log_share, ולכן ה-beta
    שמתקבל הוא של רגרסיה חד-משתנית. הוא לא זהה למקדם הרב-משתני,
    ובכוונה: הפירוק אמור להיות קריא, לא לשחזר את המודל.
    המקדם הרב-משתני מודפס לצידו לבקרה.
    """
    x = df.pir_lag_shrunk.astype(float)
    y = df.log_share.astype(float)
    r = float(np.corrcoef(x, y)[0, 1])
    sx, sy = float(x.std(ddof=1)), float(y.std(ddof=1))

    X = sm.add_constant(df[FEATURES].astype(float))
    m = sm.OLS(y, X).fit(cov_type="cluster",
                         cov_kwds={"groups": df.player_code})

    return {
        "מועדון": label,
        "n": len(df),
        "r": round(r, 3),
        "sd(שכר)": round(sy, 3),
        "sd(תפוקה)": round(sx, 3),
        "beta פשוט": round(r * sy / sx, 4),
        "beta מלא": round(m.params["pir_lag_shrunk"], 4),
        "R2": round(m.rsquared, 3),
    }


def attribute(rows):
    """מה זז ביחס למכבי, ובאיזה גורם."""
    t = pd.DataFrame(rows).set_index("מועדון")
    ref = t.loc[REF]

    print("\n" + "=" * 74)
    print(f"מה זז ביחס ל{REF} - לפי גורם")
    print("=" * 74)
    print(f"{'מועדון':<16}{'beta יחסי':>11}{'r יחסי':>10}"
          f"{'sd(שכר) יחסי':>15}{'sd(תפוקה) יחסי':>16}")
    print(f"{'':16}{'':>11}{'תמחור':>10}{'דחיסה':>15}{'הרכב':>16}")

    for name, row in t.iterrows():
        if name == REF:
            continue
        rb = row["beta פשוט"] / ref["beta פשוט"]
        rr = row["r"] / ref["r"]
        rs = row["sd(שכר)"] / ref["sd(שכר)"]
        rx = ref["sd(תפוקה)"] / row["sd(תפוקה)"]   # הפוך - הוא במכנה
        print(f"{name:<16}{rb:>11.2f}{rr:>10.2f}{rs:>15.2f}{rx:>16.2f}")

    print("\n  קריאה: כל עמודה היא כמה היא תרמה לשינוי ב-beta.")
    print("  מכפלת שלוש העמודות האחרונות = העמודה הראשונה (זהות).")
    print("  הגורם הרחוק ביותר מ-1.00 הוא זה שמסביר את הפער.")

    print("\n  --- מסקנה לכל מועדון ---")
    for name, row in t.iterrows():
        if name == REF:
            continue
        rr = row["r"] / ref["r"]
        rs = row["sd(שכר)"] / ref["sd(שכר)"]
        rx = ref["sd(תפוקה)"] / row["sd(תפוקה)"]
        gaps = {"תמחור": abs(np.log(rr)), "דחיסה": abs(np.log(rs)),
                "הרכב": abs(np.log(rx))}
        driver = max(gaps, key=gaps.get)
        vals = {"תמחור": rr, "דחיסה": rs, "הרכב": rx}
        print(f"    {name:<16} הגורם הדומיננטי: {driver} "
              f"({vals[driver]:.2f})")
    return t


def hapoel_denominator(t):
    """התחזית הנגזרת למשימה 3 - בלי לגעת בשכר של הפועל.

    ההנחה: הפועל חולקת עם מכבי את שכבת הדאטה (reported) ואת הליגה,
    ולכן r ו-sd(שכר) שלה דומים. מה שכן ידוע עליה בוודאות הוא
    sd(תפוקה), כי הוא מחושב מקופסאות סקור.

    אם sd(תפוקה) של הפועל גדול משל מכבי, אז ה-beta האמיתי שלה
    נמוך יותר מכנית - ומודל עם beta של מכבי יפזר רחב מדי.
    """
    df = load(TEST_CONFIG[1], with_salary=False)
    sx = float(df.pir_lag_shrunk.astype(float).std(ddof=1))
    ref = t.loc[REF]

    print("\n" + "=" * 74)
    print("תחזית נגזרת למשימה 3 - צד הפיצ'רים בלבד")
    print("=" * 74)
    print("  לא נקרא אף ערך שכר של הפועל. רק sd(pir_lag) על אותן")
    print("  שורות שייכנסו למבחן.\n")

    print(f"  sd(תפוקה) מכבי  : {ref['sd(תפוקה)']:.3f}   (n={ref['n']})")
    print(f"  sd(תפוקה) הפועל : {sx:.3f}   (n={len(df)})")

    ratio = ref["sd(תפוקה)"] / sx
    implied = ref["beta מלא"] * ratio
    print(f"\n  יחס המכנים        : {ratio:.3f}")
    print(f"  beta של הפועל שנגזר: {implied:.4f}  "
          f"(בהנחת אותו r ואותו sd(שכר) כמו מכבי)")
    print(f"  beta של מכבי       : {ref['beta מלא']:.4f}  <- מה שיוחל עליה")

    print("\n  כלל ההכרעה (נוסח לפני שנקרא ולו ערך שכר אחד של הפועל):")
    if ratio < 0.85:
        print(f"  [הרחבה] הפועל מגוונת יותר בתפוקה. ה-beta שלה נמוך")
        print(f"  מכנית, ושיפוע של {ref['beta מלא']:.3f} יפזר רחב מדי:")
        print("  הכוכב יקבל תחזית גבוהה מדי, הזול נמוכה מדי.")
        print("  תחזית ל-bias: expand")
    elif ratio > 1.18:
        print("  [דחיסה] הפועל אחידה יותר בתפוקה. ה-beta שלה גבוה")
        print("  מכנית, ושיפוע של מכבי לא יגיע לקצוות.")
        print("  תחזית ל-bias: compress")
    else:
        print(f"  [אין הטיה כיוונית] יחס המכנים {ratio:.2f} בטווח")
        print("  0.85-1.18. הגורם המכני לא מייצר כיוון, ובהיעדר סיבה")
        print("  אחרת התחזית היא bias קרוב לאפס.")
        print("  תחזית ל-bias: none")

    print("\n  מה שהתחזית הזו לא יודעת: אם הפועל שונה ממכבי ב-r")
    print("  (מתמחרת אחרת) או ב-sd(שכר), הכיוון יכול להתהפך. שני")
    print("  אלה נמדדים רק במשימה 3 עצמה - וזו בדיוק הסיבה שהם")
    print("  לא נקראים כאן.")
    return sx, ratio


def main():
    print("=" * 74)
    print("משימה 1c - פירוק beta לשלושה גורמים")
    print("=" * 74)
    print("  beta  =  r  x  sd(log_share) / sd(pir_lag)")
    print("          תמחור      דחיסה         הרכב\n")

    rows = []
    for label, spec in FIT_CONFIGS:
        df = load(spec, with_salary=True)
        if len(df) < 8:
            print(f"[SKIP] {label}: {len(df)} תצפיות")
            continue
        rows.append(decompose(df, label))

    t = pd.DataFrame(rows).set_index("מועדון")
    print(t.to_string())
    print("\n  'beta פשוט' הוא חד-משתני ולכן נבדל מ'beta מלא'.")
    print("  הפירוק תקף לפשוט; המלא מודפס לבקרה בלבד.")

    t = attribute(rows)
    hapoel_denominator(t)

    print("\n" + "=" * 74)
    print("  אזהרה: 14-27 תצפיות לכל מועדון. הפירוק הוא זהות מדויקת,")
    print("  אבל כל אחד משלושת הגורמים נאמד ברעש. פער של פי 1.2")
    print("  אינו ממצא; פער של פי 2 כן.")
    print("=" * 74)


if __name__ == "__main__":
    main()