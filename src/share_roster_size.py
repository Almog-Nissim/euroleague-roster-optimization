"""
share_roster_size.py  (Day 5, task 3b - תיקון שורש)
----------------------------------------------------
משימה 3 נכשלה. הסקריפט שלה הכריז OK.

עשר מתוך עשר השגיאות היו חיוביות. סכום הנתחים החזוי 1.349 מול
0.782 בפועל. MAE יחסי 117%. ובכל זאת bias_direction() הדפיס
"אין כיוון ברור | תחזית none | OK" - כי הוא בדק רק אם הצמרת
והתחתית נעות לכיוונים מנוגדים, ולא אם *כולם* נעים לאותו כיוון.

זה בדיוק "הודעת הצלחה שלא בודקת את מה שהיא מדווחת עליו היא באג",
והפעם הבאג היה שלי.

--------------------------------------------------------------------
הסיבה
--------------------------------------------------------------------
    share(i) = salary(i) / team_payroll(club, season)

הנתחים בסגל מסתכמים ל-1 בהגדרה. לכן הנתח הממוצע הוא 1/N, ו-N
הוא גודל הסגל. מכבי מעגנת 12-15 שחקנים לעונה; הפועל 19.

    מכבי:  נתח ממוצע ~ 1/13 = 0.077
    הפועל: נתח ממוצע ~ 1/19 = 0.053

המודל למד את הרמה של סגל בן 13 והוחל על סגל בן 19. הוא לא יכול
היה לדעת - N לא נמצא בו כמשתנה.

זו אינה טעות אמידה. זו טעות בהגדרת המשתנה התלוי.
--------------------------------------------------------------------

--------------------------------------------------------------------
למה זה חמור יותר ממבחן שנכשל
--------------------------------------------------------------------
PuLP *בוחר* את גודל הסגל. האילוץ הוא sum(x) <= 16, כלומר N הוא
משתנה החלטה. אם cost(i) מוגדר כנתח, אז העלות של כל שחקן תלויה
בכמה שחקנים ייבחרו - והאופטימייזר משנה בדיוק את זה.

עלות שתלויה במה שהאופטימייזר בוחר היא מעגל. הוא היה נסגר בשקט:
הפתרון היה יוצא, נראה סביר, ולא היה שום דבר שזורק.
--------------------------------------------------------------------

התיקון, בעלות אפס פרמטרים:

    rel(i) = salary(i) / mean_salary(club, season)
           = share(i) * N

"פי כמה השחקן הזה מהשחקן הממוצע בסגלו." מסלק עונה, מטבע,
אינפלציה ורמת תקציב - כל מה ש-share סילק - וגם את גודל הסגל.
השחקן הממוצע הוא 1.0 בכל סגל, בכל עונה, בכל מועדון.

--------------------------------------------------------------------
משמעת: מה שרץ כאן אינו מבחן חוץ-מדגמי
--------------------------------------------------------------------
המבחן על הפועל כבר נצפה. לתקן את המפרט ולהריץ שוב על אותו סט
הוא התאמה לסט המבחן, לא אימות. הסקריפט הזה מסומן DIAGNOSTIC.

המספרים שיוצאים ממנו אומרים "האם ההסבר לכשל נכון" - ולא "האם
המודל תקף". תוקף ייבדק על סגל שטרם נראה, וזה הופך את פריט
"עוד סגל reported" מנחמד-שיהיה לחוסם.
--------------------------------------------------------------------

הרצה:
    python src/audits/share_roster_size.py
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
BANNER = "DIAGNOSTIC - לא מבחן חוץ-מדגמי"


def load():
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})

    def prep(sub):
        g = sub.groupby(["club", "season"])
        # N נספר על כל שורות הסגל, כולל אלה בלי קוד שחקן.
        # הן חלק מהתקציב ומגודל הסגל, גם אם לא ניתן להשתמש בהן.
        agg = g.salary_mid.agg(["sum", "size"]).rename(
            columns={"sum": "team_payroll", "size": "roster_n"})
        sub = sub.merge(agg, left_on=["club", "season"], right_index=True)
        sub["mean_salary"] = sub.team_payroll / sub.roster_n
        sub["share"] = sub.salary_mid / sub.team_payroll
        sub["rel"] = sub.salary_mid / sub.mean_salary
        sub["log_share"] = np.log(sub.share)
        sub["log_rel"] = np.log(sub.rel)
        named = sub[sub.player_code.notna()]
        df = named.merge(feat, on=["player_code", "season"], how="inner",
                         suffixes=("", "_f")).dropna(
            subset=FEATURES + ["log_share"])
        return sub, df

    cal_raw, cal = prep(anch[anch.usage == "calibrate"].copy())
    tst_raw, tst = prep(anch[anch.usage == "test"].copy())
    return cal_raw, cal, tst_raw, tst


def roster_table(cal_raw, tst_raw):
    print("=" * 74)
    print("גודל הסגל - המשתנה שלא היה במודל")
    print("=" * 74)
    both = pd.concat([cal_raw, tst_raw])
    t = both.groupby(["usage", "club", "season"]).agg(
        שורות=("salary_mid", "size"),
        תקציב=("salary_mid", "sum"),
        שכר_ממוצע=("salary_mid", "mean"),
    )
    t["נתח_ממוצע"] = (1 / t["שורות"]).round(4)
    print(t.to_string())

    n_cal = cal_raw.groupby(["club", "season"]).size().mean()
    n_tst = tst_raw.groupby(["club", "season"]).size().mean()
    print(f"\n  N ממוצע בכיול : {n_cal:.1f}")
    print(f"  N במבחן        : {n_tst:.1f}")
    print(f"  יחס            : {n_tst / n_cal:.3f}")
    print(f"  ניפוח צפוי בתחזיות הנתח: x{n_tst / n_cal:.2f}")
    return n_cal, n_tst


def fit(d, dep):
    X = sm.add_constant(d[FEATURES].astype(float))
    return sm.OLS(d[dep], X).fit(cov_type="cluster",
                                 cov_kwds={"groups": d.player_code})


def run(cal, tst, dep, label):
    """אותו מפרט, משתנה תלוי אחר. הכל חוץ מ-dep זהה."""
    m = fit(cal, dep)
    Xt = sm.add_constant(tst[FEATURES].astype(float), has_constant="add")
    smear = float(np.mean(np.exp(m.resid)))
    pred_dep = np.exp(m.predict(Xt)) * smear

    # שני המשתנים מומרים חזרה לנתח, כדי שההשוואה תהיה על אותה יחידה
    if dep == "log_share":
        pred_share = pred_dep
    else:
        pred_share = pred_dep / tst.roster_n

    err = pred_share - tst.share
    out = tst.copy()
    out["pred_share"] = pred_share
    out["err"] = err

    print("\n" + "=" * 74)
    print(f"{label}  [{BANNER}]")
    print("=" * 74)
    print(f"  n כיול={int(m.nobs)} | R2={m.rsquared:.3f} | "
          f"Duan={smear:.4f}")
    for f in FEATURES:
        print(f"    {f:<20}{m.params[f]:>10.4f}  p={m.pvalues[f]:.3f}")

    mae = float(np.abs(err).mean())
    bias = float(err.mean())
    same_sign = float((np.sign(err) == np.sign(bias)).mean())
    rho, _ = spearmanr(pred_share, tst.share)

    print(f"\n  סכום נתחים בפועל : {tst.share.sum():.3f}")
    print(f"  סכום נתחים חזוי  : {pred_share.sum():.3f}   "
          f"(יחס {pred_share.sum() / tst.share.sum():.2f})")
    print(f"  MAE              : {mae:.4f}")
    print(f"  Bias             : {bias:+.4f}")
    print(f"  MAE יחסי         : {float((np.abs(err) / tst.share).mean()):.1%}")
    print(f"  שגיאות באותו סימן: {same_sign:.0%}  "
          f"<- 100% פירושו הטיית רמה, לא רעש")
    print(f"  ספירמן           : {rho:+.3f}   <- לא אמור להשתנות")
    return {"מפרט": label, "MAE": round(mae, 4), "Bias": round(bias, 4),
            "יחס סכומים": round(float(pred_share.sum() / tst.share.sum()), 3),
            "אותו סימן": f"{same_sign:.0%}", "ספירמן": round(float(rho), 3),
            "R2 כיול": round(m.rsquared, 3)}, out


def level_audit(out_share, n_cal, n_tst):
    """פירוק שגיאת הרמה. אם גודל הסגל הוא ההסבר, הוא צריך לכסות
    את רוב היחס - ומה שנשאר הוא Duan ושארית."""
    print("\n" + "=" * 74)
    print("פירוק שגיאת הרמה במפרט הנתח")
    print("=" * 74)
    ratio = float(out_share.pred_share.sum() / out_share.share.sum())
    size_factor = n_tst / n_cal
    print(f"  ניפוח נצפה בפועל      : x{ratio:.3f}")
    print(f"  מוסבר ע\"י גודל הסגל   : x{size_factor:.3f}")
    print(f"  שארית                 : x{ratio / size_factor:.3f}")
    if abs(ratio / size_factor - 1) < 0.25:
        print("\n  [אושר] גודל הסגל מסביר את רוב הניפוח. השארית בסדר")
        print("  גודל של תיקון Duan ושל הפרשי כיסוי בין הסטים.")
    else:
        print("\n  [חלקי] גודל הסגל מסביר רק חלק. יש גורם רמה נוסף.")


def main():
    print("=" * 74)
    print("משימה 3b - למה המבחן נכשל, ומה מתקן אותו")
    print(f"  {BANNER}")
    print("=" * 74)

    cal_raw, cal, tst_raw, tst = load()
    n_cal, n_tst = roster_table(cal_raw, tst_raw)

    r_share, out_share = run(cal, tst, "log_share", "מפרט הנתח (מה שרץ)")
    level_audit(out_share, n_cal, n_tst)
    r_rel, out_rel = run(cal, tst, "log_rel", "מפרט היחס (התיקון)")

    print("\n" + "=" * 74)
    print("השוואה")
    print("=" * 74)
    print(pd.DataFrame([r_share, r_rel]).set_index("מפרט").to_string())

    print("\n" + "=" * 74)
    print("קריאה")
    print("=" * 74)
    print("  אם ספירמן זהה בשני המפרטים - הדירוג מעולם לא היה הבעיה,")
    print("  והכשל היה כולו ברמה. זה גם אומר שכל מה שנלמד היום על")
    print("  beta ועל הסימנים עומד: החלפת המשתנה התלוי בקבוע כפלי")
    print("  מזיזה את החותך, לא את השיפועים.")
    print()
    print("  ומה שלא נקבע כאן: תוקף. הסט הזה כבר נצפה.")
    print("  המפרט המתוקן צריך סגל שטרם נראה.")
    print("=" * 74)


if __name__ == "__main__":
    main()