"""add_budgets_2025.py — יום 13. שמונה תקציבים שהיו בצ'אט ולא בקובץ.

--------------------------------------------------------------------
מה קרה
--------------------------------------------------------------------
`club_budgets_gemini.csv` מכיל 12 מועדוני 2025. שמונה נוספים
(ASV RED VIR PAR BAS MIL MCO PRS) שימשו בפועל בהרצות שהניבו
0.799 · +2.03 · r=0.907 — אבל מעולם לא נכתבו לקובץ.

לכן הסקריפטים מחזירים היום n=12 / n=30 במקום n=20 / n=38.

--------------------------------------------------------------------
למה סקריפט ולא עריכה ידנית
--------------------------------------------------------------------
1. הוא קורא את הכותרת האמיתית ולא מניח סדר עמודות.
2. הוא מסמן `source` — הערכים אינם מ-gemini אלא מ-basketnews,
   ותערובת מקורות היא בדיוק מה שצריך להיות ניתן לסינון אחר כך.
3. הוא מסרב לרוץ פעמיים.
4. גיבוי לפני כתיבה.

⚠️ הערכים הם **נטו**, ביורו, בהתאם להחלטת יום 3. gross נשאר ריק —
   הוא ריק בכל 2025 גם בשורות הקיימות.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה שאחרי
--------------------------------------------------------------------
    יחס 2025 יחזור ל-0.799 (±0.005)     אלמוג ~55% · קלוד 55%
    הכותרת תחזור ל-+2.03 (±0.05)        אלמוג ~60% · קלוד 60%
"""

import shutil
import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from roster_optimizer import PROCESSED_DIR  # noqa: E402

CSV = PROCESSED_DIR / "club_budgets_gemini.csv"
SOURCE = "basketnews_2025"

# שמות המועדונים חייבים להיות זהים ל-NAME2CODE. אלה המפתחות
# המדויקים מ-season_heterogeneity.py / wins_conversion.py.
NEW = [
    ("הכוכב האדום", 16.5, "RED"),
    ("פרטיזן",      14.5, "PAR"),
    ("מילאנו",      14.0, "MIL"),
    ("מונקו",       14.0, "MCO"),
    ("באסקוניה",     8.5, "BAS"),
    ("וירטוס",       8.0, "VIR"),
    ("פריז",         8.0, "PRS"),
    ("ASVEL",        5.0, "ASV"),
]
SEP = "=" * 72


def main() -> int:
    print(SEP)
    print("add_budgets_2025 — השלמת שמונה שורות")
    print(SEP)

    df = pd.read_csv(CSV)
    print(f"\n  עמודות: {list(df.columns)}")
    print(f"  שורות לפני: {len(df)}  ·  "
          f"2025: {(df.season == 2025).sum()}")

    have = set(df.loc[df.season == 2025, "club"])
    todo = [(n, v, c) for n, v, c in NEW if n not in have]
    dupe = [n for n, _, _ in NEW if n in have]
    if dupe:
        print(f"\n  ⚠️ כבר קיימים ולא ייכתבו: {' · '.join(dupe)}")
    if not todo:
        print("\n  ✅ כל השמונה כבר בקובץ. אין מה לעשות.")
        return 0

    rows = []
    for name, net, code in todo:
        r = {c: pd.NA for c in df.columns}
        r["season"] = 2025
        r["club"] = name
        r["net_eur"] = net
        if "source" in df.columns:
            r["source"] = SOURCE
        if "kind" in df.columns:
            r["kind"] = "net"
        rows.append(r)

    out = pd.concat([df, pd.DataFrame(rows)[df.columns]],
                    ignore_index=True)

    # ------------------------------------------------ בקרות לפני כתיבה
    print("\n  בקרות:")
    n25 = int((out.season == 2025).sum())
    ok_n = n25 == 20
    print(f"    2025 אחרי ההוספה: {n25}  (צפוי 20)  "
          f"{'✅' if ok_n else '❌'}")
    d = out[out.season == 2025].club.duplicated().sum()
    print(f"    כפילויות ב-2025: {d}  {'✅' if d == 0 else '❌'}")
    miss = out.net_eur.isna().sum()
    print(f"    net_eur ריק (כל העונות): {miss}")
    if not ok_n or d:
        print("\n  ❌ בקרה נכשלה. לא נכתב דבר.")
        return 1

    bak = CSV.with_suffix(".csv.bak")
    shutil.copy2(CSV, bak)
    out.to_csv(CSV, index=False, encoding="utf-8-sig")
    print(f"\n  גיבוי:  {bak.name}")
    print(f"  נכתב:   {CSV.name}  ({len(df)} → {len(out)} שורות)")

    print("\n  " + "-" * 60)
    print("  להריץ עכשיו, בסדר הזה:")
    print("    1. season_heterogeneity.py   → 2025 צפוי 0.799 · n=20")
    print("    2. wins_conversion.py        → צפוי +2.03 · n=38")
    print("    3. ratio_2025.py             → בקרת השחזור אמורה לעבור")
    print("  אם אחד מהם לא חוזר — יש הפרש נוסף בין מה שרץ אז לעכשיו.")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())