"""
inspect_backtest.py — מה בדיוק יש ב-league_backtest_results.csv.

נכתב לפני הצירוף ולא אחריו. שש פעמים היום ניחשתי מבנה — שם קובץ,
תיקיית עבודה, טווחי משחקים, ערכי Played, שם שדה, מבנה מזהה — וכל
פעם זה עלה סבב. הפעם מודדים קודם.

מה שצריך לדעת כדי לחשב usage משוקלל-דקות לסגל שהמנוע בנה:
  · איזה עמודה מזהה שחקן, ובאיזה פורמט
  · איפה הדקות שהוקצו
  · איך מבדילים בין סגל המנוע לסגל המועדון
  · מה מגדיר עונה-מועדון אחת

הרצה:  python src/inspect_backtest.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import repo_root, resolve  # noqa: E402

CANDIDATES = [
    "data/processed/league_backtest_results.csv",
    "data/processed/backtest_results.csv",
    "data/processed/why_100_results.csv",
    "data/processed/usage_curve_results.csv",
]


def describe(path: Path) -> None:
    print("\n" + "=" * 74)
    print(path.name)
    print("=" * 74)

    if not path.exists():
        print("  לא קיים.")
        return

    df = pd.read_csv(path, low_memory=False)
    print(f"  {len(df):,} שורות · {len(df.columns)} עמודות\n")
    print(f"  עמודות: {list(df.columns)}\n")

    print("  שלוש שורות ראשונות:")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(df.head(3).to_string())

    print("\n  ערכים ייחודיים לעמודה (עד 8):")
    for c in df.columns:
        n = df[c].nunique(dropna=True)
        if n <= 8:
            vals = list(df[c].dropna().unique())
            print(f"    {c:<26} {n:>5}  {vals}")
        else:
            sample = list(df[c].dropna().unique()[:3])
            print(f"    {c:<26} {n:>5}  לדוגמה: {sample}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*", default=None)
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")
    for rel in (args.files or CANDIDATES):
        describe(resolve(rel))

    print("\n" + "=" * 74)
    print("מה שאני צריך כדי לכתוב את הצירוף")
    print("=" * 74)
    print("  1. עמודת מזהה שחקן בקובץ הבנצ'מרק — שם ופורמט")
    print("  2. עמודת הדקות שהוקצו לכל שחקן")
    print("  3. איך מסמנים סגל-מנוע מול סגל-מועדון")
    print("  4. מה מגדיר עונה-מועדון אחת (עונה + קוד מועדון)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())