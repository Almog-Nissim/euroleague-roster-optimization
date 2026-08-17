"""
age_curve_probe.py  (Day 5, task 1)
-----------------------------------
האם עיקול הגיל קיים אצל מועדון אחר?

ההקשר: ביום 4 יצא age_c2 = +0.0009, p=0.87 על מכבי. אפס מעשי.
זה הפריך את מנוע המציאות של הפרויקט - ההנחה ש-beta3 < 0, כלומר
שיא מחיר סביב 27 וירידה לשני הקצוות, שממנה נובע ש"בני 23-25 עם
דקות רוטציה זולים מדי".

שלושה הסברים אפשריים:
    1. מכבי לבדה אינה מייצגת את הליגה
    2. הגיל נבלע ב-pir_lag - שחקן בשיא מייצר PIR גבוה, והמחיר כבר שם
    3. המנגנון לא קיים

הסקריפט הזה נועד להכריע בין 1 לבין {2,3}.

--------------------------------------------------------------------
אזהרת זיהוי - נכתבה לפני ההרצה
--------------------------------------------------------------------
טווח הגילאים אצל פנא' הוא 26-35. מתחת ל-26 אין אף שחקן.
פרבולה ממורכזת ב-27 לא נאמדת מזרוע אחת. הסקריפט מדפיס את
דיאגנוסטיקת התמיכה לפני המקדם, ומכריז UNIDENTIFIED במפורש כשאין
תצפיות משמעותיות משמאל למרכז.

"המקדם אינו מזוהה בצד אחד" הוא תוצאה תקפה. הוא לא נקרא כ"המנגנון
לא קיים" - אלה שתי טענות שונות, וזו ההבחנה שהסקריפט קיים כדי לשמור.
--------------------------------------------------------------------

structure_only אינו סט כיול (החלטה סגורה, יום 4). ההרצה כאן היא
מבחן מבנה בלבד: הסימנים נקראים, הגדלים לא מוזרמים חזרה למודל.

הרצה:
    python -m src.audits.age_curve_probe
    python src/audits/age_curve_probe.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROCESSED_DIR

FEATURES = ["pir_lag_shrunk", "age_c2", "el_seasons"]
AGE_CENTER = 27
MIN_LEFT_ARM = 4          # פחות מזה - הזרוע השמאלית אינה מזוהה
RIGHT_ARM_FROM = 29       # מבחן השיפוע החד-צדדי

# ====================================================================
# תחזיות - נכתבות לפני ההרצה. זה המקום היחיד לערוך.
# ====================================================================
PREDICTIONS = {
    # אלמוג, יום 5: לא שלילי ולא חיובי - אפס מעשי. וזו התוצאה הגרועה
    # ביותר עבורנו: היא לא מפריכה ולא מאשרת, ומשאירה את ההסברים 2 ו-3
    # פתוחים בלי דרך להכריע ביניהם מהדאטה הקיים.
    "age_c2": (
        "0", "n.s.",
        "[אלמוג] אפס מעשי - לא שלילי ולא חיובי. התוצאה הכי לא-שימושית: "
        "לא מפריכה ולא מאשרת",
    ),
    "pir_lag_shrunk": (
        "+", "sig",
        "[מוסכם] תפוקה אחרונה היא העוגן. אזהרה: הנימוק המקורי "
        "('פנא' מרוכזת פי 7.5') לא שורד את המדידה - ראו DISPERSION למטה. "
        "הכיוון והמובהקות נשארים, סף ה-0.229 יורד",
    ),
    "el_seasons": (
        "+", "n.s.",
        "[מוסכם] חיובי; המדגם קטן מכדי לתת מובהקות. 0.095 במכבי לא "
        "היה מובהק גם שם",
    ),
}

# --- R2: מחלוקת מוצהרת. שני מנגנונים, שניהם נבדקים ---
# אלמוג: פנא' היא קבוצת טופ יורוליג - למה ש-R2 שלה יהיה נמוך יותר?
# קלוד:  התלוי רועש פי שניים (estimated 0.111 מול reported 0.052).
#
# מה שנמדד אחרי המחלוקת ומכריע בין הנימוקים - לא בין התחזיות:
#   שונות log_share בסט האמידה:  TEL 0.397  |  PAN+OLY 0.264
#   יחס #1/חציון בסט האמידה:      TEL 3.67   |  PAN+OLY 3.62
# ה-7.5x של פנא' נמדד על הסגל המלא. 6 מתוך 23 השורות הן בלי קוד
# שחקן - ובדיוק הזולות. בסט האמידה הזנב נחתך, ופנא' *פחות* מפוזרת
# מהפועל. R2 נמוך יכול לנבוע משונות כוללת קטנה יותר, לא רק מרעש.
R2_PREDICTED_BELOW = 0.564   # ה-R2 של מכבי
R2_PREDICTION_OWNER = {"claude": "below", "almog": "above"}
BETA_PIR_MACCABI = 0.229     # ירד מדרגת תחזית לנקודת ייחוס בלבד
SIG = 0.10
PRACTICAL_ZERO_PCT = 0.10    # תזוזה של סטיית תקן אחת בגיל -> פחות מ-10% בנתח
# ====================================================================


def load(clubs, season=2025):
    """נתח מתקציב, מנורמל בתוך מועדון-עונה.

    הנרמול הזה הוא שמאפשר להשוות EUR מוערך מול USD מדווח: הוא מסלק
    רמה, מטבע, ואפקט עונה בעלות אפס פרמטרים. מה שהוא לא מסלק הוא
    יחס נטו/ברוטו משתנה בתוך סגל - ראו LIMITATION בסוף הקובץ.

    המכנה הוא סך הסגל כולל שורות בלי קוד שחקן. זה נכון: התקציב
    כולל אותם, גם אם הרגרסיה לא יכולה להשתמש בהם.
    """
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})

    sub = anch[anch.club.isin(clubs) & (anch.season == season)].copy()
    if sub.empty:
        raise ValueError(f"אין עוגנים ל-{clubs} בעונת {season}")

    payroll = sub.groupby(["club", "season"]).salary_mid.sum().rename(
        "team_payroll")
    sub = sub.merge(payroll, left_on=["club", "season"], right_index=True)
    sub["share"] = sub.salary_mid / sub.team_payroll
    sub["log_share"] = np.log(sub.share)

    named = sub[sub.player_code.notna()]
    df = named.merge(feat, on=["player_code", "season"], how="inner",
                     suffixes=("", "_f"))
    df = df.dropna(subset=FEATURES + ["log_share"])

    print(f"[JOIN] {'+'.join(clubs)} {season}: "
          f"{len(sub)} שורות | {len(named)} עם קוד | "
          f"{len(df)} עם פיצ'רים מלאים | "
          f"מכנה התקציב: {sub.salary_mid.sum():,.0f}")
    if df.empty:
        raise ValueError("אפס תצפיות אחרי ה-join - בדוק dtype של player_code")
    return df


def support_diagnostic(df, label):
    """נדפס לפני המקדם, לא אחריו.

    מקדם ריבועי על מדגם חד-זרועי הוא מספר שנראה כמו תשובה ואינו
    תשובה. הסדר כאן מכוון.
    """
    print("\n" + "=" * 74)
    print(f"דיאגנוסטיקת תמיכה בגיל - {label}")
    print("=" * 74)

    ages = df.age.astype(int)
    left = int((ages < AGE_CENTER).sum())
    right = int((ages > AGE_CENTER).sum())
    at = int((ages == AGE_CENTER).sum())

    print(f"  n={len(df)} | טווח {ages.min()}-{ages.max()} | "
          f"חציון {ages.median():.0f}")
    print(f"  גילאים: {sorted(ages.tolist())}")
    print(f"  משמאל ל-{AGE_CENTER}: {left} | על {AGE_CENTER}: {at} | "
          f"מימין: {right}")
    print(f"  מתחת ל-26: {int((ages < 26).sum())} | "
          f"מתחת ל-25: {int((ages < 25).sum())}")

    identified = left >= MIN_LEFT_ARM
    if identified:
        print(f"  [OK] {left} תצפיות משמאל למרכז - הפרבולה מזוהה משני הצדדים")
    else:
        print(f"  [UNIDENTIFIED] רק {left} תצפיות משמאל ל-{AGE_CENTER} "
              f"(דרוש {MIN_LEFT_ARM}).")
        print("               הזרוע השמאלית אינה בדאטה. מקדם age_c2 שיצא כאן")
        print("               אינו מבחן של 'בני 23-25 זולים מדי' - הוא מבחן")
        print("               של הזרוע הימנית בלבד, בתחפושת של פרבולה.")
    return identified


def fit(df, features, label=""):
    d = df.dropna(subset=list(features) + ["log_share"])
    X = sm.add_constant(d[list(features)].astype(float))
    m = sm.OLS(d.log_share, X).fit(cov_type="cluster",
                                   cov_kwds={"groups": d.player_code})
    if label:
        print(f"\n[{label}] n={int(m.nobs)} | "
              f"clusters={d.player_code.nunique()} | R2={m.rsquared:.3f}")
    return m, d


def zero_band(d):
    """'אפס מעשי' חייב סף, אחרת התחזית לא ניתנת להפרכה.

    ההגדרה: תזוזה של סטיית תקן אחת ב-age_c2 משנה את הנתח בפחות
    מ-PRACTICAL_ZERO_PCT. זה סף שנגזר מהדאטה, לא מספר עגול.
    """
    sd = float(d.age_c2.std())
    thr = float(np.log(1 + PRACTICAL_ZERO_PCT) / sd)
    return sd, thr


def report_vs_predictions(m, d, label):
    print("\n" + "=" * 74)
    print(f"תחזיות מול תוצאה - {label}")
    print("=" * 74)

    sd, thr = zero_band(d)
    print(f"  רצועת האפס המעשי ל-age_c2: |b| < {thr:.4f}")
    print(f"  (sd(age_c2)={sd:.2f}; מעבר לזה, תזוזת סטיית תקן אחת בגיל")
    print(f"   משנה את הנתח ביותר מ-{PRACTICAL_ZERO_PCT:.0%})\n")

    print(f"{'פרמטר':<20}{'תחזית':>10}{'בפועל':>11}{'p':>9}{'CI 95%':>24}"
          f"   {'הערכה'}")
    for f, (sign, sigflag, _) in PREDICTIONS.items():
        if f not in m.params:
            continue
        b, p = m.params[f], m.pvalues[f]
        lo, hi = m.conf_int().loc[f]
        sig_got = "sig" if p < SIG else "n.s."

        if sign == "0":
            in_band = abs(b) < thr
            got = "0" if in_band else ("+" if b > 0 else "-")
            ok = "OK" if (in_band and sig_got == "n.s.") else "REFUTED"
        else:
            got = "+" if b > 0 else "-"
            ok = "OK" if (got == sign and sig_got == sigflag) else (
                "כיוון נכון" if got == sign else "REFUTED")

        print(f"{f:<20}{sign + '/' + sigflag:>10}{b:>11.4f}{p:>9.3f}"
              f"  [{lo:>8.4f},{hi:>8.4f}]   {ok}")
    print()
    for f, (_, _, why) in PREDICTIONS.items():
        print(f"  {f}: {why}")

    dispersion_note(d)

    r2 = m.rsquared
    who = "אלמוג" if r2 >= R2_PREDICTED_BELOW else "קלוד"
    print(f"\n  R2 = {r2:.3f} מול {R2_PREDICTED_BELOW} במכבי")
    print(f"  אלמוג ניבא גבוה יותר (קבוצת טופ) | "
          f"קלוד ניבא נמוך יותר (תלוי רועש פי שניים)")
    print(f"  -> {who} צדק על הכיוון.")

    if "pir_lag_shrunk" in m.params:
        b = m.params["pir_lag_shrunk"]
        print(f"\n  beta(pir) = {b:.4f} | נקודת ייחוס: {BETA_PIR_MACCABI} "
              f"במכבי (לא תחזית - הנימוק שלה נפל)")


def dispersion_note(d):
    """הבדיקה שהפילה את הנימוק של שתי תחזיות.

    ה-7.5x של פנא' נמדד על הסגל המלא. הרגרסיה רצה על תת-קבוצה שממנה
    נחתך בדיוק הזנב הזול - השורות בלי קוד שחקן. זה אותו דפוס בדיוק
    כמו ארטיפקט הצנזורה מיום 4: מדד שנראה כמו תכונה של המועדון והוא
    תכונה של הכיסוי.
    """
    print("\n  --- DISPERSION: מה באמת קורה בסט האמידה ---")
    print(f"    שונות log_share : {d.log_share.var():.4f}  "
          f"(מכבי: 0.3968)")
    print(f"    יחס #1/חציון    : "
          f"{d.salary_mid.max() / d.salary_mid.median():.2f}  (מכבי: 3.67)")
    print("    הערה: 7.5x לפנא' נמדד על הסגל המלא. בסט האמידה הזנב")
    print("    הזול נחתך (שורות בלי קוד שחקן), ופנא' אינה מפוזרת יותר")
    print("    ממכבי. R2 נמוך יכול לנבוע משונות כוללת קטנה - לא רק מרעש.")


def right_arm_slope(df):
    """אם הפרבולה לא מזוהה, עדיין אפשר לשאול על הזרוע הימנית לבדה:
    האם המחיר יורד עם הגיל אחרי 29? זה שיפוע ליניארי על תת-מדגם,
    ואין בו הנחת סימטריה."""
    print("\n" + "=" * 74)
    print(f"מבחן הזרוע הימנית בלבד (גיל >= {RIGHT_ARM_FROM})")
    print("=" * 74)
    d = df[df.age >= RIGHT_ARM_FROM]
    if len(d) < 8:
        print(f"  [SKIP] רק {len(d)} תצפיות - לא מספיק גם לשיפוע ליניארי")
        return None
    m, dd = fit(d, ["pir_lag_shrunk", "age_c", "el_seasons"],
                label=f"זרוע ימנית, גיל>={RIGHT_ARM_FROM}")
    b, p = m.params["age_c"], m.pvalues["age_c"]
    print(f"  beta(age_c) = {b:+.4f}  p={p:.3f}")
    if b < 0 and p < SIG:
        print("  [ממצא] המחיר יורד עם הגיל בקצה העליון - הזרוע הימנית קיימת")
    elif b < 0:
        print("  [כיוון נכון, לא מובהק] עדות חלקית לזרוע הימנית")
    else:
        print("  [REFUTED] אין ירידת מחיר בקצה העליון")
    return m


def verdict(identified, m_pooled, d_pooled, m_right):
    """כלל ההכרעה נוסח לפני ההרצה. הוא לא מנוסח מחדש לפי מה שיצא."""
    print("\n" + "=" * 74)
    print("הכרעה בין שלושת ההסברים")
    print("=" * 74)

    b = m_pooled.params.get("age_c2", np.nan)
    p = m_pooled.pvalues.get("age_c2", np.nan)
    _, thr = zero_band(d_pooled)

    if abs(b) < thr and p >= SIG:
        print(f"  age_c2 = {b:+.4f}, בתוך רצועת האפס (|b| < {thr:.4f}).")
        print("  התחזית של אלמוג אושרה - וזו התוצאה הכי לא-שימושית:")
        print("  אותו אפס מעשי כמו במכבי, על מועדון אחר לגמרי.")
        print()
        print("  מה זה כן שולל: הסבר 1 ('מכבי לבדה אינה מייצגת') נחלש")
        print("  משמעותית. שני מועדונים, שתי ליגות-בית, שתי שכבות")
        print("  אמינות - ואותה תוצאה.")
        print("  מה זה לא מכריע: 2 מול 3. הגיל נבלע ב-pir_lag, או")
        print("  שהמנגנון לא קיים - שתי הטענות עקביות עם אפס.")
        print()
        print("  הבדיקה שכן מפרידה ביניהן, ליום 6:")
        print("  להריץ את המפרט בלי pir_lag_shrunk. אם age_c2 נעשה")
        print("  שלילי ומובהק ברגע ש-PIR יוצא - הסבר 2 מנצח (הגיל נבלע).")
        print("  אם הוא נשאר אפס גם בלי PIR - הסבר 3, המנגנון לא קיים,")
        print("  ומנוע המציאות של הפרויקט צריך מקור אחר.")
    elif b < 0 and p < SIG:
        print("  age_c2 שלילי ומובהק -> הסבר 1 מנצח:")
        print("  מכבי לבדה אינה מייצגת. הפרויקט חוזר לכיוון המקורי,")
        print("  ומכבי היא המקרה החריג שדורש הסבר נפרד.")
    elif b < 0 and m_right is not None and \
            m_right.params.get("age_c", 1) < 0 and \
            m_right.pvalues.get("age_c", 1) < SIG:
        print("  age_c2 שלילי לא מובהק, אבל הזרוע הימנית נותנת שיפוע שלילי")
        print("  מובהק -> עדות חלקית. המלצה: מסלול B על הגיל -")
        print("  מקדם מוצהר, לא נאמד.")
    else:
        print("  age_c2 אפס או חיובי -> הסבר 2 או 3.")
        print("  אי אפשר להכריע ביניהם מהדאטה הקיים.")

    print()
    if identified:
        print("  LEFT_ARM = IDENTIFIED")
    else:
        print("  LEFT_ARM = UNIDENTIFIED")
        print("  לזה דרוש סגל עם 5+ שחקנים מתחת ל-26. אין כזה בארבעת")
        print("  הסטים הקיימים. מועמדים ליום 6: ז'לגיריס, ורז'ה, באסקוניה -")
        print("  סגלים צעירים יותר מהצמרת היוונית.")


def absorption_probe(d, label):
    """מפריד בין הסבר 2 להסבר 3.

    אם הגיל נבלע ב-pir_lag (הסבר 2), אז ברגע ש-PIR יוצא מהמפרט
    age_c2 אמור להיעשות שלילי ומובהק - האות היה שם, רק תפוס.
    אם הוא נשאר אפס גם בלי PIR (הסבר 3), אין מנגנון גיל בדאטה.

    זו לא בדיקה של מפרט טוב יותר - להוציא את המשתנה הדומיננטי זו
    הטיית משתנה מושמט מכוונת. היא בדיקה של איפה האות יושב.
    """
    print("\n" + "=" * 74)
    print(f"מבחן הבליעה - {label}")
    print("=" * 74)
    print("  מוציאים את pir_lag_shrunk בכוונה. אם הגיל נבלע בו,")
    print("  age_c2 אמור להתעורר. אם לא - אין מה להתעורר.")

    m, _ = fit(d, ["age_c2", "el_seasons"], label="בלי pir_lag_shrunk")
    b, p = m.params["age_c2"], m.pvalues["age_c2"]
    _, thr = zero_band(d)
    print(f"\n  age_c2 בלי PIR = {b:+.4f}  p={p:.3f}  "
          f"(רצועת אפס: |b| < {thr:.4f})")
    if b < 0 and p < SIG:
        print("  [הסבר 2] הגיל היה נבלע ב-pir_lag. המנגנון קיים,")
        print("  הוא פשוט לא נפרד מהתפוקה על 29 תצפיות.")
    elif abs(b) < thr:
        print("  [הסבר 3] אפס גם בלי PIR. אין מנגנון גיל בדאטה הזה,")
        print("  ומנוע המציאות של הפרויקט צריך מקור אחר.")
    else:
        print("  [לא מוכרע] מחוץ לרצועה אך לא מובהק.")
    return m


def main():
    print("=" * 74)
    print("משימה 1 - האם עיקול הגיל קיים מחוץ למכבי?")
    print("=" * 74)

    # פנא' לבדה - הבדיקה כפי שנוסחה ביום 4
    pan = load(["PAN"])
    id_pan = support_diagnostic(pan, "פנאתינייקוס 25/26")
    m_pan, d_pan = fit(pan, FEATURES, label="פנא' בלבד")
    report_vs_predictions(m_pan, d_pan, "פנא' בלבד")

    # פנא' + אולימפיאקוס - שני מועדונים, אותה עונה, אותו מטבע ואותה
    # שכבת אמינות. הנתח מנורמל בתוך מועדון, ולכן אין צורך בדאמי מועדון.
    pool = load(["PAN", "OLY"])
    id_pool = support_diagnostic(pool, "פנא' + אולימפיאקוס 25/26")
    m_pool, d_pool = fit(pool, FEATURES, label="פנא' + אולימפיאקוס")
    report_vs_predictions(m_pool, d_pool, "פנא' + אולימפיאקוס")

    m_right = right_arm_slope(pool)
    absorption_probe(d_pool, "פנא' + אולימפיאקוס")

    # רגישות ל-k. אם הסימן מתהפך בין 20 ל-60, אין ממצא.
    print("\n" + "=" * 74)
    print("רגישות ל-k (הפרמטר המוצהר של ההתכווצות)")
    print("=" * 74)
    rows = []
    for k in (20, 40, 60):
        d = d_pool.copy()
        w = d.games_lag / (d.games_lag + k)
        d["pir_lag_shrunk"] = w * d.pir_lag_raw + (1 - w) * d.league_pir_mean
        mk, _ = fit(d, FEATURES)
        rows.append({"k": k, **{f: round(mk.params[f], 4) for f in FEATURES},
                     "R2": round(mk.rsquared, 3)})
    r = pd.DataFrame(rows).set_index("k")
    print(r.to_string())
    flipped = [f for f in FEATURES if r[f].apply(np.sign).nunique() > 1]
    if flipped:
        print(f"  [WARN] סימן מתהפך ב: {flipped} - לא יציב ל-k")
    else:
        print("  [OK] כל הסימנים יציבים על פני k")

    verdict(id_pool, m_pool, d_pool, m_right)

    print("\n" + "=" * 74)
    print("LIMITATIONS")
    print("=" * 74)
    print("  - PAN/OLY הם estimated: פיזור 0.111 מול 0.052 ב-reported.")
    print("    רעש כפול בתלוי מרחיב רווחי סמך ומטה R2 כלפי מטה.")
    print("  - נרמול הנתח מסלק מטבע ורמה, אך לא יחס נטו/ברוטו שמשתנה")
    print("    בתוך סגל. במכבי המכפיל נע 1.26 (זרים) מול 1.96 (ישראלים);")
    print("    פיצול מקומי/זר קיים גם בסגלים היווניים.")
    print("  - structure_only אינו סט כיול. הסימנים נקראים כאן,")
    print("    הגדלים אינם מוזרמים חזרה למודל.")
    print("=" * 74)


if __name__ == "__main__":
    main()