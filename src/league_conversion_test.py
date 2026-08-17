"""
league_conversion_test.py  (Day 6)
----------------------------------
האם PIR בליגה הישראלית מנבא PIR ביורוליג?

--------------------------------------------------------------------
תחזיות - נכתבו לפני ההרצה
--------------------------------------------------------------------
**אלמוג:** אין התאמה משמעותית. ההמרה היא הימור, ואחוז ההסבר
יהיה נמוך. "לא תמצא פה התאמה ואחוז שמסביר בין שתי הליגות."

**קלוד:** קורלציה בינונית, 0.45-0.65, ו-R2 סביב 0.30. קשר אמיתי
אך חלש מדי להסתמכות ברמת שחקן בודד.

מתחת ל-0.30 קורלציה -> אלמוג צדק.
--------------------------------------------------------------------

**המבחן המכריע אינו R2.** הוא:

    האם ידיעת ה-PIR המקומי מנבאת טוב יותר מלנחש את ממוצע הליגה?

מודל יכול להראות R2=0.3 ועדיין להיות חסר ערך מעשי אם השגיאה שלו
דומה לזו של ניחוש קבוע. זו אותה הבחנה מיום 5, כשמודל התפוקה נתן
R2=0.455 ושיפור של 3.5% בלבד מול הפיגור המוכווץ.

הבדיקה: leave-one-out. לכל שחקן, מודל שאומן בלעדיו מנבא אותו.
משווים ל-"תמיד תנחש את החציון".

--------------------------------------------------------------------
מקורות רעש שחייבים להיות מנוטרלים לפני שקוראים תוצאה
--------------------------------------------------------------------
1. **דקות זבל.** שחקן עם 4 דקות ביורוליג ייתן ppm רועש מאוד.
   הפילטר על דקות הוא הכרחי, לא ניקוי.
2. **הגבלת טווח.** כל הזוגות הם שחקני מכבי/הפועל - כלומר קבוצה
   שנבחרה. קורלציה נמוכה במדגם מצומצם אינה "אין קשר".
3. **תפקיד.** שחקן ראשי מקומי יכול להיות שחקן ספסל ביורוליג.
   ההפרש הזה אינו רמת יריבות אלא שינוי תפקיד.

הרצה:
    python src/audits/league_conversion_test.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import pearsonr, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROCESSED_DIR

SRC = "israeli_el_matches.csv"
MIN_IL_MIN = 10.0        # דקות למשחק בליגה המקומית
MIN_EL_MIN = 8.0         # ביורוליג
MIN_GAMES = 8

PRED_ALMOG = "אין קשר משמעותי. r < 0.30"
PRED_CLAUDE = "r בטווח 0.45-0.65, R2 ~0.30"
SEP = "=" * 74


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def load():
    d = pd.read_csv(PROCESSED_DIR / SRC)
    d["il_ppm"] = d.il_pir / d.il_min
    d["el_ppm"] = d.el_pir / d.el_min
    print(f"  התאמות שהתקבלו: {len(d)}")

    f = d[(d.il_min >= MIN_IL_MIN) & (d.el_min >= MIN_EL_MIN) &
          (d.il_games >= MIN_GAMES) & (d.el_games >= MIN_GAMES)].copy()
    print(f"  אחרי סינון דקות זבל "
          f"(מקומית>={MIN_IL_MIN}, יורוליג>={MIN_EL_MIN}, "
          f"משחקים>={MIN_GAMES}): {len(f)}")
    print(f"  נשרו {len(d) - len(f)} - רובם שחקנים עם דקות זבל ביורוליג,")
    print("  שאצלם ppm רועש מכדי לשמש כמדידה.")
    return d, f


def correlations(f):
    h("1. הקשר")
    r, pr = pearsonr(f.il_ppm, f.el_ppm)
    rho, prho = spearmanr(f.il_ppm, f.el_ppm)
    print(f"  n={len(f)}")
    print(f"  פירסון  r = {r:+.3f}  (p={pr:.4f})")
    print(f"  ספירמן  ρ = {rho:+.3f}  (p={prho:.4f})")

    z = np.arctanh(np.clip(r, -0.999, 0.999))
    se = 1 / np.sqrt(len(f) - 3)
    lo, hi = np.tanh(z - 1.96 * se), np.tanh(z + 1.96 * se)
    print(f"  רווח סמך 95% ל-r: [{lo:+.3f}, {hi:+.3f}]")

    m = sm.OLS(f.el_ppm, sm.add_constant(f[["il_ppm"]])).fit()
    print(f"\n  el_ppm ~ il_ppm:  R2={m.rsquared:.3f} | "
          f"שיפוע {m.params['il_ppm']:+.3f} (p={m.pvalues['il_ppm']:.4f})")

    print("\n  --- מול התחזיות ---")
    print(f"  אלמוג : {PRED_ALMOG}")
    print(f"  קלוד  : {PRED_CLAUDE}")
    if abs(r) < 0.30:
        print(f"\n  -> r={r:.3f} מתחת ל-0.30. **אלמוג צדק.**")
    elif 0.45 <= abs(r) <= 0.65:
        print(f"\n  -> r={r:.3f} בטווח שקלוד חזה.")
    else:
        print(f"\n  -> r={r:.3f} מחוץ לשני הטווחים. שניהם פספסו.")
    return m, r


def role_effect(f):
    """האם ההפרש הוא רמת ליגה או שינוי תפקיד?

    שחקן ראשי בליגה המקומית שהופך לשחקן ספסל ביורוליג מאבד תפוקה
    לדקה מסיבה שאינה איכות היריבות. אם יחס הדקות מסביר את יחס
    התפוקה, זה תפקיד ולא ליגה.
    """
    h("2. ליגה או תפקיד?")
    d = f.copy()
    d["ratio"] = d.el_ppm / d.il_ppm.replace(0, np.nan)
    d["min_ratio"] = d.el_min / d.il_min
    d = d.dropna(subset=["ratio", "min_ratio"])
    r, p = pearsonr(d.min_ratio, d.ratio)
    print(f"  יחס דקות (יורוליג/מקומית): חציון {d.min_ratio.median():.2f}")
    print(f"  יחס תפוקה                : חציון {d.ratio.median():.2f}")
    print(f"\n  corr(יחס דקות, יחס תפוקה) = {r:+.3f}  (p={p:.4f}, n={len(d)})")
    if p < 0.10 and r > 0:
        print("  -> מי שמקבל יחסית יותר דקות ביורוליג שומר על תפוקתו.")
        print("     כלומר חלק מה'ירידה' הוא **שינוי תפקיד**, לא רמת ליגה.")
    else:
        print("  -> יחס הדקות אינו מסביר את יחס התפוקה.")
    return d


def loo(f):
    """המבחן המכריע. leave-one-out מול ניחוש קבוע.

    R2 בתוך המדגם אינו שאלה מעשית. השאלה היא אם ידיעת ה-PIR
    המקומי מקטינה את שגיאת התחזית לעומת "תמיד תנחש את החציון".
    """
    h("3. המבחן המכריע — האם זה עדיף על ניחוש?")
    X = sm.add_constant(f[["il_ppm"]]).values
    y = f.el_ppm.values
    n = len(f)
    pred_m, pred_c = np.empty(n), np.empty(n)
    for i in range(n):
        k = np.arange(n) != i
        pred_m[i] = sm.OLS(y[k], X[k]).fit().predict(X[i:i + 1])[0]
        pred_c[i] = np.median(y[k])

    mae_m = float(np.abs(pred_m - y).mean())
    mae_c = float(np.abs(pred_c - y).mean())
    print(f"  MAE של המודל (il_ppm) : {mae_m:.4f}")
    print(f"  MAE של ניחוש החציון   : {mae_c:.4f}")
    imp = 1 - mae_m / mae_c
    print(f"  שיפור                 : {imp:+.1%}")
    print(f"\n  לייחוס: ppm ביורוליג חציון {np.median(y):.3f}, "
          f"טווח {y.min():.3f}-{y.max():.3f}")

    if imp < 0.05:
        print("\n  🔴 **הדאטה המקומי כמעט לא מוסיף.** ההמרה היא הימור.")
        print("     אלמוג צדק בטענה המעשית, גם אם יש קורלציה סטטיסטית.")
    elif imp < 0.20:
        print("\n  ⚠️ שיפור קטן. שימושי כאות חלש, לא כאומדן.")
    else:
        print("\n  ✅ שיפור ממשי. הדאטה המקומי נושא מידע.")
    return imp


def worst(f):
    h("4. איפה זה נשבר")
    d = f.copy()
    d["ratio"] = d.el_ppm / d.il_ppm.replace(0, np.nan)
    d = d.sort_values("ratio")
    print(f"{'שחקן':<22}{'עונה':>6}{'ppm מקומי':>11}{'ppm יורוליג':>13}"
          f"{'יחס':>8}{'דק מק':>8}{'דק יור':>8}")
    for t in pd.concat([d.head(4), d.tail(4)]).itertuples():
        print(f"{str(t.name_he)[:21]:<22}{t.season:>6}{t.il_ppm:>11.3f}"
              f"{t.el_ppm:>13.3f}{t.ratio:>8.2f}{t.il_min:>8.1f}"
              f"{t.el_min:>8.1f}")


def main():
    print(SEP + "\nהאם הליגה הישראלית מנבאת יורוליג?\n" + SEP)
    d, f = load()
    if len(f) < 12:
        raise SystemExit(f"רק {len(f)} תצפיות אחרי סינון. מדגם קטן מדי.")
    correlations(f)
    role_effect(f)
    loo(f)
    worst(f)

    h("סייג")
    print("  כל הזוגות הם שחקני מכבי/הפועל - קבוצה שנבחרה, לא מדגם")
    print("  אקראי מהליגה. הגבלת טווח מטה קורלציה כלפי מטה, ולכן")
    print("  'קורלציה נמוכה' כאן אינה 'אין קשר בליגה כולה'.")
    print(SEP)


if __name__ == "__main__":
    main()