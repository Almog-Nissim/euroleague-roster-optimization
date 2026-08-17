"""
oos_hapoel.py  (Day 5, task 3)
------------------------------
מבחן חוץ-מדגמי: לנבא את סגל הפועל 25/26 מהמודל המכויל על מכבי.

זו המקבילה לבדיקת ה-0.664 מול 0.651 של מודל השרידות ביום 3. שם
הפלט היה כיול - הפרש בין הסתברות חזויה לשיעור בפועל, לא דירוג.
הפלט הראשי כאן הוא אותו דבר: הטיה ושגיאה על הנתח, לא ספירמן.

הנימוק כתוב בסעיף 10 של project_state:
    "כיול חשוב יותר מדירוג - מודל שמדרג נכון ומשקר על הרמה הורס
     אלף סימולציות."

PuLP מקצה נתח מתקציב. אם המודל מדרג נכון ומשקר על הרמה, כל
הקצאה שתצא ממנו תהיה שגויה גם אם הסדר נכון.

--------------------------------------------------------------------
אזהרת גודל מדגם - נכתבה לפני ההרצה
--------------------------------------------------------------------
הפועל 25/26: 19 שורות -> 16 עם קוד -> 10 עם פיצ'רים מלאים.
שישה נופלים כי אין להם עונת יורוליג קודמת ולכן אין pir_lag.

ספירמן על 10 תצפיות נושא רווח סמך של כ-+-0.6. הוא מודפס עם רווח
הסמך שלו לידו, כדי שלא ייקרא כמספר. מבחן דירוג בגודל הזה לא יכול
להכריע כמעט כלום, ולכן הוא אינו הפלט הראשי.
--------------------------------------------------------------------

הפועל אינה בסט הכיול (usage='test', החלטה סגורה מיום 4).

הרצה:
    python -m src.audits.oos_hapoel
    python src/audits/oos_hapoel.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROCESSED_DIR

FEATURES = ["pir_lag_shrunk", "age_c2", "el_seasons"]

# ====================================================================
# תחזיות - נכתבות לפני ההרצה. זה המקום היחיד לערוך.
# ====================================================================
PRED_BIAS_DIRECTION = "none"   # compress / expand / none
PRED_BIAS_WHY = (
    "[ננעל אחרי משימה 1c, לפני שנקרא ולו ערך שכר אחד של הפועל] "
    "יחס המכנים sd(pir_lag) מכבי/הפועל = 2.071/2.430 = 0.852, בתוך "
    "הרצועה 0.85-1.18 שנוסחה מראש. הגורם המכני אינו מייצר כיוון. "
    "בנוסף: הפרשי הקורלציה בין שלושת המועדונים אינם מובהקים "
    "(p=0.62 / 0.26 / 0.17) - אין הטרוגניות תמחור מודגמת."
)
# הנימוק הקודם ('דחיסה: הפועל 6.0x מול מכבי 3.7x') נזנח: בדיקת
# הצנזורה במשימה 1b הראתה שיחסי פיזור על סגל מלא קורסים בסט האמידה
# (פנא' 3.92 -> 2.65 עם 61% שרידות). הפועל שורדת 53%.
#
# אזהרת סף כנה: 0.852 רחוק 0.002 מגבול הרצועה. אילו הרצועה היתה
# מתחילה ב-0.86, הכלל היה מכריז 'expand'. הרצועה לא זזה בדיעבד.
# ה-beta הנגזר להפועל הוא 0.1954 מול 0.2293 שיוחל עליה - נטייה
# קלה להרחבה, בתוך מה שהכלל קורא 'ללא כיוון'.
PRED_MAE_SHARE = (0.02, 0.04)
PRED_MAE_WHY = (
    "הנתח הממוצע הוא ~0.10 על 10 שחקנים; 0.02-0.04 הם 20-40% שגיאה "
    "יחסית - מה ש-R2=0.564 מתרגם אליו מחוץ למדגם"
)
PRED_SPEARMAN = (0.55, 0.80)
PRED_SPEARMAN_WHY = "נמוך מ-0.848 בתוך המדגם; רווח הסמך על n=10 חופף כמעט הכל"
PRED_DROPPED_EXPENSIVE = True   # ה-6 שנפלו יקרים ביחס לתרומתם

# כלל הכרעה, נוסח לפני ההרצה
BIAS_CONSISTENT_MIN = 0.70   # שיעור מינימלי של שחקנים באותו כיוון הטיה
# ====================================================================


def load():
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})

    def prep(sub, name):
        payroll = sub.groupby(["club", "season"]).salary_mid.sum().rename(
            "team_payroll")
        sub = sub.merge(payroll, left_on=["club", "season"],
                        right_index=True)
        sub["share"] = sub.salary_mid / sub.team_payroll
        sub["log_share"] = np.log(sub.share)
        named = sub[sub.player_code.notna()]
        df = named.merge(feat, on=["player_code", "season"], how="inner",
                         suffixes=("", "_f")).dropna(
            subset=FEATURES + ["log_share"])
        print(f"[JOIN] {name}: {len(sub)} שורות | {len(named)} עם קוד | "
              f"{len(df)} עם פיצ'רים | מכנה: {sub.salary_mid.sum():,.0f}")
        return sub, df

    cal_raw, cal = prep(anch[anch.usage == "calibrate"].copy(), "מכבי calibrate")
    tst_raw, tst = prep(anch[anch.usage == "test"].copy(), "הפועל test")
    return cal, tst, tst_raw


def audit_dropped(tst_raw, tst):
    """מי נפל ולמה. שורה שנופלת בשקט היא באג; שורה שנופלת בקול היא ממצא.

    התחזית: הנופלים יקרים ביחס לתרומתם - הם בדיוק הקבוצה שמודל
    השרידות מתמחר באפס PIR (לא נרשמו לגיליון / חתימות אמצע עונה).
    """
    print("\n" + "=" * 74)
    print("מי נפל מהמבחן, ולמה")
    print("=" * 74)

    used = set(tst.player_code)
    named = tst_raw[tst_raw.player_code.notna()]
    dropped = named[~named.player_code.isin(used)]
    unnamed = tst_raw[tst_raw.player_code.isna()]

    if len(dropped):
        print("  עם קוד, בלי pir_lag (אין עונת יורוליג קודמת):")
        for _, r in dropped.sort_values("salary_mid",
                                        ascending=False).iterrows():
            print(f"    {r.player_name_el:<26} {r.salary_mid:>12,.0f}")
    if len(unnamed):
        print(f"  בלי קוד שחקן: {len(unnamed)} שורות, "
              f"{unnamed.salary_mid.sum():,.0f}")

    tot = tst_raw.salary_mid.sum()
    cov = tst.salary_mid.sum()
    print(f"\n  כיסוי תקציבי: {cov:,.0f} מתוך {tot:,.0f} = {cov / tot:.1%}")

    # --- הבדיקה שהפילה את ה-7.5x, ואת הנימוק של תחזית ה-bias ---
    full_ratio = tst_raw.salary_mid.max() / tst_raw.salary_mid.median()
    est_ratio = tst.salary_mid.max() / tst.salary_mid.median()
    print(f"\n  --- CENSORING: מה קורה ליחס הפיזור ---")
    print(f"    שרדו עד המבחן : {len(tst)}/{len(tst_raw)} = "
          f"{len(tst) / len(tst_raw):.0%}")
    print(f"    יחס #1/חציון  : סגל מלא {full_ratio:.2f} -> "
          f"סט המבחן {est_ratio:.2f}")
    print(f"    var(log_share): {tst.log_share.var():.4f}   "
          f"(מכבי בסט הכיול: 0.3968)")
    print(f"    לייחוס: 6.0x הפועל שצוטט ביום 4 נמדד על הסגל המלא.")
    print(f"    אצל פנא' אותו מדד קרס מ-3.92 ל-2.65 עם 61% שרידות.")
    if est_ratio < full_ratio * 0.85:
        print("    [WARN] היחס קרס. כל נימוק שנשען על 'הפועל מפוזרת")
        print("    יותר ממכבי' אינו תקף על מה שהמבחן בפועל רואה.")
    print(f"  שכר ממוצע - במבחן: {tst.salary_mid.mean():,.0f} | "
          f"נפלו: {dropped.salary_mid.mean() if len(dropped) else 0:,.0f}")
    if len(dropped):
        got = dropped.salary_mid.mean() > tst.salary_mid.mean()
        print(f"  תחזית 'הנופלים יקרים ביחס לתרומתם': "
              f"{'OK' if got == PRED_DROPPED_EXPENSIVE else 'REFUTED'}")
    print("\n  הערה: 100%-הכיסוי החסר אינו רעש. הוא אותה קבוצה שמודל")
    print("  השרידות מתמחר באפס PIR - עולים כסף, תורמים אפס.")


def fit_calibrate(cal):
    X = sm.add_constant(cal[FEATURES].astype(float))
    m = sm.OLS(cal.log_share, X).fit(cov_type="cluster",
                                     cov_kwds={"groups": cal.player_code})
    print(f"\n[כיול] מכבי: n={int(m.nobs)} | "
          f"clusters={cal.player_code.nunique()} | R2={m.rsquared:.3f}")
    for f in FEATURES:
        print(f"    {f:<20}{m.params[f]:>10.4f}  p={m.pvalues[f]:.3f}")
    return m


def predict(m, tst):
    """שתי החזרות מ-log_share ל-share.

    naive:  exp(x'b) - מוטה כלפי מטה, כי E[exp(e)] > exp(E[e])
    smear:  exp(x'b) * mean(exp(resid)) - אומד Duan, מתקן את ההטיה

    ההפרש בין השניים הוא לא טכני. עם sigma סביב 0.5, התיקון הוא
    כ-13% על כל תחזית - יותר מכל מקדם בודד במודל.
    """
    Xt = sm.add_constant(tst[FEATURES].astype(float), has_constant="add")
    log_pred = m.predict(Xt)
    smear = float(np.mean(np.exp(m.resid)))
    out = tst.copy()
    out["log_share_pred"] = log_pred
    out["share_pred_naive"] = np.exp(log_pred)
    out["share_pred"] = np.exp(log_pred) * smear
    out["err"] = out.share_pred - out.share
    print(f"\n  מקדם Duan (smearing): {smear:.4f}  "
          f"[תיקון של {(smear - 1) * 100:+.1f}% על כל תחזית]")
    return out, smear


def calibration_report(out):
    """הפלט הראשי. לא ספירמן."""
    print("\n" + "=" * 74)
    print("כיול רמה - הפלט הראשי")
    print("=" * 74)

    d = out.sort_values("share", ascending=False)
    print(f"{'שחקן':<26}{'גיל':>5}{'נתח בפועל':>12}{'נתח חזוי':>11}"
          f"{'שגיאה':>10}{'יחס':>8}")
    for _, r in d.iterrows():
        name = str(r.get("player_name_el", r.player_code))[:25]
        print(f"{name:<26}{int(r.age):>5}{r.share:>12.4f}"
              f"{r.share_pred:>11.4f}{r.err:>+10.4f}"
              f"{r.share_pred / r.share:>8.2f}")

    mae = float(np.abs(out.err).mean())
    bias = float(out.err.mean())
    lo, hi = PRED_MAE_SHARE
    print(f"\n  MAE  על share : {mae:.4f}   תחזית {lo:.2f}-{hi:.2f}  "
          f"[{'OK' if lo <= mae <= hi else 'מחוץ לטווח'}]")
    print(f"  Bias על share : {bias:+.4f}  "
          f"(סכום השגיאות: {out.err.sum():+.4f})")
    print(f"  MAE יחסי      : {float((np.abs(out.err) / out.share).mean()):.1%}")

    # האם הכיסוי מסתכם? הנתחים החזויים לא חייבים לסכום ל-1 כי
    # רק 10 מתוך 19 השורות במבחן.
    print(f"\n  סכום נתחים בפועל (10 השחקנים): {out.share.sum():.3f}")
    print(f"  סכום נתחים חזוי               : {out.share_pred.sum():.3f}")


def bias_direction(out):
    """הבדיקה שמכריעה אם זו שגיאה או מקדם חסר.

    הטיה חד-כיוונית ועקבית היא לא כישלון - היא מקדם ריכוזיות שחסר
    מהמפרט, וזה קלט ישיר להכרעת המפרט. הטיה רועשת ולא כיוונית
    אומרת שהמודל פשוט לא מדויק מחוץ למכבי.
    """
    print("\n" + "=" * 74)
    print("כיוון ההטיה - דחיסה או הרחבה?")
    print("=" * 74)

    med = out.share.median()
    top = out[out.share > med]
    bot = out[out.share <= med]
    top_b = float(top.err.mean())
    bot_b = float(bot.err.mean())

    print(f"  חציון הנתח: {med:.4f}")
    print(f"  צמרת (n={len(top)}): הטיה ממוצעת {top_b:+.4f}")
    print(f"  תחתית (n={len(bot)}): הטיה ממוצעת {bot_b:+.4f}")

    if top_b < 0 and bot_b > 0:
        got = "compress"
        print("  -> דחיסה: הקצוות נמשכים פנימה")
    elif top_b > 0 and bot_b < 0:
        got = "expand"
        print("  -> הרחבה: הקצוות נדחפים החוצה")
    else:
        got = "none"
        print("  -> אין כיוון ברור")

    print(f"\n  תחזית: {PRED_BIAS_DIRECTION} | בפועל: {got} | "
          f"{'OK' if got == PRED_BIAS_DIRECTION else 'REFUTED'}")
    print(f"  נימוק התחזית: {PRED_BIAS_WHY}")

    # עקביות - כמה מהשחקנים באותו כיוון בתוך כל חצי
    cons_top = float((top.err < 0).mean()) if len(top) else 0.0
    cons_bot = float((bot.err > 0).mean()) if len(bot) else 0.0
    print(f"\n  עקביות: {cons_top:.0%} מהצמרת מוערכת בחסר | "
          f"{cons_bot:.0%} מהתחתית ביתר")

    consistent = (cons_top >= BIAS_CONSISTENT_MIN and
                  cons_bot >= BIAS_CONSISTENT_MIN)
    print("\n  כלל ההכרעה (נוסח לפני ההרצה):")
    if consistent and got != "none":
        print(f"  [מקדם חסר] ההטיה חד-כיוונית מעל {BIAS_CONSISTENT_MIN:.0%}.")
        print("  זה לא כישלון - זה מקדם ריכוזיות שחסר מהמפרט,")
        print("  וזה קלט ישיר להכרעת המפרט.")
        print("  מתחבר לממצא ה-CBS מיום 4: החרגת שלושת המשתכרים")
        print("  הגבוהים היא סובסידיה לריכוזיות, ומכבי (3.7x) מרוכזת")
        print("  פחות מהפועל (6.0x). המודל למד את העקומה השטוחה.")
    else:
        print("  [חוסר דיוק] ההטיה רועשת ולא כיוונית.")
        print("  המודל פשוט לא מדויק מחוץ למכבי - אין מקדם להוסיף.")
    return got, consistent


def rank_report(out):
    """מודפס אחרון ועם רווח סמך, כדי שלא ייקרא כמספר."""
    print("\n" + "=" * 74)
    print("דירוג - משני, ועם רווח הסמך שלו")
    print("=" * 74)
    n = len(out)
    rho, p = spearmanr(out.share_pred, out.share)
    rho_pir, _ = spearmanr(out.share_pred, out.pir_per_game)

    # Fisher z על ספירמן, קירוב סטנדרטי
    if n > 3:
        z = np.arctanh(np.clip(rho, -0.999, 0.999))
        se = 1.06 / np.sqrt(n - 3)
        ci = (float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se)))
    else:
        ci = (np.nan, np.nan)

    lo, hi = PRED_SPEARMAN
    print(f"  ספירמן (חזוי ~ בפועל): {rho:+.3f}  p={p:.3f}")
    print(f"  רווח סמך 95%          : [{ci[0]:+.3f}, {ci[1]:+.3f}]   n={n}")
    print(f"  תחזית                 : {lo:.2f}-{hi:.2f}  "
          f"[{'OK' if lo <= rho <= hi else 'מחוץ לטווח'}]")
    print(f"  נימוק                 : {PRED_SPEARMAN_WHY}")
    print(f"\n  ספירמן (חזוי ~ PIR): {rho_pir:+.3f}  <- טאוטולוגיה מחוץ למדגם")
    width = ci[1] - ci[0]
    if width > 0.8:
        print(f"\n  [אזהרה] רוחב רווח הסמך {width:.2f}. המספר הזה אינו")
        print("  מבחן. הוא מודפס לשלמות ולא להכרעה.")


def main():
    print("=" * 74)
    print("משימה 3 - מבחן חוץ-מדגמי: הפועל 25/26 מהמודל של מכבי")
    print("=" * 74)

    cal, tst, tst_raw = load()
    if tst.empty:
        raise ValueError("אפס תצפיות מבחן - בדוק dtype של player_code")
    if set(cal.player_code) & set(tst.player_code):
        overlap = set(cal.player_code) & set(tst.player_code)
        raise ValueError(f"דליפה: {len(overlap)} שחקנים בשני הסטים {overlap}")

    audit_dropped(tst_raw, tst)
    m = fit_calibrate(cal)
    out, _ = predict(m, tst)
    calibration_report(out)
    bias_direction(out)
    rank_report(out)

    print("\n" + "=" * 74)
    print("LIMITATIONS")
    print("=" * 74)
    print("  - n=10 מתוך 19. הכיסוי התקציבי מודפס למעלה.")
    print("  - שני המועדונים ישראלים, אותה עונה, אותו מטבע. זה מבחן")
    print("    חוץ-מועדוני, לא חוץ-ליגתי.")
    print("  - מכבי 25/26 שיחקה בנסיבות חריגות (בית מחוץ לישראל).")
    print("=" * 74)


if __name__ == "__main__":
    main()