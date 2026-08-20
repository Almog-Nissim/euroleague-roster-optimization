"""
scale_sensitivity.py — הרוויה כרצועה, לא כנקודה.

למה בלי הרצה מחדש
------------------
הכפלת כל המחירים **והתקציב** באותו קבוע נותנת LP זהה. לכן הרוויה
ביחידות מנורמלות היא קבוע, והסקלה רק מכפילה אותה:

    רוויה(M) = רוויה(מנורמל) × scale

אומת אמפירית: scale=1.2754 נתן 28/30M ו-scale=0.888 נתן 19/21M.
היחס 1.2754/0.888 = 1.436, והיחס בין התוצאות 28/19 = 1.47 —
תואם עד רזולוציית הרשת של 1M.

מקור אי-הוודאות
---------------
    scale = חציון תקציב אמיתי / חציון תקציב מנורמל
          = 13.35M / 15.04 = 0.888

המונה הוא **חציון של 18 מועדונים**, כלומר אומדן עם שגיאת דגימה.
המכנה נגזר מהמאגר ומדויק. לכן כל אי-הוודאות בסקלה היא
אי-הוודאות בחציון התקציב האמיתי, והיא נאמדת בבוטסטרפ.

⚠️ שלוש הסתייגויות
-------------------
1. **2025 אינו שמיש לכיול** — 12 מועדונים מתוך 20, והם העשירים.
   הכיול מ-2024 בלבד, שם הכיסוי מלא (18/18).
2. הבוטסטרפ תופס שגיאת דגימה בלבד. הוא **אינו** תופס שגיאה
   במקור עצמו — התקציבים הם הערכות עיתונאיות.
3. הנטו של 2019 מחושב מהברוטו לפי מכפילי מס ולא נמדד (יום 8).
   לא נכנס לכיול.

הרצה:  python src/scale_sensitivity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from paths import PROCESSED_DIR  # noqa: E402

SEP = "=" * 78
# רוויה ביחידות מנורמלות, משתי הרצות בסקאלות שונות.
# 2024: 19/0.888=21.4 · 28/1.2754=22.0   -> 21.7
# 2025: 21/0.888=23.6 · 30/1.2754=23.5   -> 23.6
SAT_NORM = {2024: 21.7, 2025: 23.6}
BUDGET_NORM_MEDIAN = 15.04     # חציון התקציב המנורמל, עונת 2024
CAL_SEASON = 2024
N_BOOT = 20000


def hdr(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def main() -> int:
    b = pd.read_csv(PROCESSED_DIR / "club_budgets_gemini.csv")
    cal = b[(b.season == CAL_SEASON) & b.net_eur.notna()]
    v = cal.net_eur.to_numpy(float)

    hdr("סט הכיול")
    print(f"  עונה {CAL_SEASON} · {len(v)} מועדונים · נטו במיליוני יורו")
    print(f"  חציון {np.median(v):.2f} · טווח {v.min():.2f}-{v.max():.2f}")
    print("  ⚠️ 2025 לא נכנס — 12 מתוך 20 מועדונים, והם העשירים.")

    rng = np.random.default_rng(11)
    med = np.median(rng.choice(v, size=(N_BOOT, len(v)), replace=True), axis=1)
    lo, hi = np.percentile(med, [2.5, 97.5])
    scale = np.median(v) / BUDGET_NORM_MEDIAN
    s_lo, s_hi = lo / BUDGET_NORM_MEDIAN, hi / BUDGET_NORM_MEDIAN

    hdr("הסקלה")
    print(f"  חציון תקציב אמיתי : {np.median(v):.2f}M  "
          f"[CI95 {lo:.2f}-{hi:.2f}]")
    print(f"  חציון מנורמל      : {BUDGET_NORM_MEDIAN:.2f}")
    print(f"  🔴 scale          : {scale:.3f}  [CI95 {s_lo:.3f}-{s_hi:.3f}]")
    print(f"     אי-ודאות יחסית : ±{(s_hi - s_lo) / 2 / scale:.0%}")

    hdr("הרוויה כרצועה")
    print("  ההמרה מדויקת — אין צורך בהרצה חוזרת של האופטימייזר.\n")
    print(f"  {'עונה':<8}{'מנורמל':>9}{'נקודה':>10}{'CI95':>16}")
    rows = []
    for s, n in SAT_NORM.items():
        rows.append({"season": s, "sat_norm": n, "sat_point": n * scale,
                     "sat_lo": n * s_lo, "sat_hi": n * s_hi})
        print(f"  {s:<8}{n:>9.1f}{n * scale:>9.1f}M"
              f"{f'{n * s_lo:.1f}-{n * s_hi:.1f}M':>16}")
    r = pd.DataFrame(rows)
    a_lo, a_hi = r.sat_lo.mean(), r.sat_hi.mean()
    print(f"\n  🔴 ממוצע שתי העונות: {r.sat_point.mean():.1f}M "
          f"[{a_lo:.1f}-{a_hi:.1f}]")
    print(f"     רוחב הרצועה: {a_hi - a_lo:.1f}M")

    hdr("הרוויה מול מועדונים אמיתיים")
    print(f"  {'':<14}{'תקציב':>9}{'% מהרוויה':>12}")
    sat = r.sat_point.mean()
    for lbl, x in (("החציוני", np.median(v)),
                   ("העני ביותר", v.min()),
                   ("העשיר ביותר", v.max())):
        print(f"  {lbl:<14}{x:>8.1f}M{x / sat:>11.0%}")
    n_below = int((v < sat).sum())
    print(f"\n  🔴 {n_below} מתוך {len(v)} מועדונים ({n_below / len(v):.0%}) "
          f"מתחת לרוויה.")
    print("     כלומר לרוב הליגה, מיליון נוסף עדיין קונה משהו.")
    n_below_lo = int((v < a_lo).sum())
    n_below_hi = int((v < a_hi).sum())
    if n_below_lo != n_below_hi:
        print(f"     ⚠️ תלוי בסקלה: בין {n_below_lo} ל-{n_below_hi} "
              f"מועדונים לאורך הרצועה.")
    else:
        print(f"     ✅ יציב לאורך כל רצועת הסקלה.")

    hdr("מה זה כן ומה זה לא")
    print("  ✅ הרצועה תופסת שגיאת דגימה בחציון התקציב.")
    print("  ❌ היא **אינה** תופסת:")
    print("     · שגיאה במקור — התקציבים הם הערכות עיתונאיות")
    print("     · רעש הרוויה עצמה (±2M לפי מבחן הדילול)")
    print("     · שגיאת מודל העלות (שיפוע שוק~מודל 0.76)")
    print("  ⇒ הרצועה המדווחת היא **חסם תחתון** על אי-הוודאות.")

    p = PROCESSED_DIR / "scale_sensitivity.csv"
    r.to_csv(p, index=False)
    print(f"\n  נשמר: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())