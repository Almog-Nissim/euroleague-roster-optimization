"""
check_positions.py  (Day 9)
---------------------------
בדיקה של שורה אחת: **איזה קובץ עמדות התוכנית באמת קוראת.**

`league_backtest` דיווח פעמיים על אותם 100 שחקנים חסרים אחרי
שהקובץ המעודכן נשלח. יש שלוש אפשרויות, והסקריפט הזה מכריע
ביניהן בלי לנחש:

  1. הקובץ לא הוחלף במקום הנכון
  2. Windows שמר אותו כ-`player_positions (1).csv`
  3. `paths.py` מצביע לתיקייה אחרת ממה שחשבנו

הרצה:
    python src/check_positions.py
"""

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR, ROOT_DIR

P = PROCESSED_DIR / "player_positions.csv"

print("=" * 70)
print(f"שורש הפרויקט : {ROOT_DIR}")
print(f"תיקיית processed: {PROCESSED_DIR}")
print(f"הקובץ שנקרא  : {P}")
print(f"קיים          : {P.exists()}")
if P.exists():
    st = P.stat()
    print(f"גודל          : {st.st_size:,} בייט")
    print(f"עודכן לאחרונה : "
          f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}")
    d = pd.read_csv(P, dtype={"player_code": str})
    print(f"שורות         : {len(d)}      <-- צריך להיות 684, לא 545")
print("=" * 70)

print("\nכל קובץ שנראה כמו קובץ עמדות בסביבה:")
seen = set()
for base in [ROOT_DIR, PROCESSED_DIR, PROCESSED_DIR.parent,
             Path.home() / "Downloads", Path.home() / "Desktop"]:
    if not base.exists():
        continue
    for f in sorted(base.glob("*osition*")):
        if f.is_file() and f not in seen:
            seen.add(f)
            n = ""
            if f.suffix == ".csv":
                try:
                    n = f"  ({len(pd.read_csv(f))} שורות)"
                except Exception:
                    n = "  (לא נקרא)"
            print(f"  {f}{n}")

print("\n" + "=" * 70)
if P.exists() and len(pd.read_csv(P)) >= 684:
    print("✅ הקובץ הנכון במקום. אפשר להריץ league_backtest.")
else:
    print("⛔ הקובץ שנקרא הוא הישן.")
    print(f"   העתק את player_positions.csv בן 684 השורות בדיוק לכאן:")
    print(f"   {P}")
    print("   לחלופין — הרץ  python src/positions_merge.py  והוא")
    print("   ייצר אותו מחדש אצלך מהגיליון (הוא מחפש גם ב-Downloads).")
print("=" * 70)