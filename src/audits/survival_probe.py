"""
survival_probe.py
-----------------
שרידות לעונה הבאה על שני צירים: דקות למשחק וגיל.

"שרידה" = לשחקן יש שורה בעונה t+1. הגדרה גסה: היא מאחדת פרישה,
מעבר ל-NBA, ירידה לליגה אחרת ועונה שלמה של פציעה לאותה תצפית.
מה שהיא כן מודדת נכון הוא בדיוק מה שהאופטימייזר צריך —
האם השחקן ייצר ערך ביורוליג בעונה הבאה, או אפס.

הצירים אינם עצמאיים: צעירים מקבלים פחות דקות. לכן מוצגים
שני שוליים ואז טבלה מוצלבת — השוליים לבדם מטעים.

הרצה: python src/audits/survival_probe.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
import pandas as pd
from paths import PROCESSED_DIR

AGE_BINS   = [0, 23, 27, 31,33, 35, 99]
AGE_LABELS = ["<23", "23-26", "27-30", "31-32","33-34", "35+"]

MIN_BINS   = [0, 10, 20, 99]
MIN_LABELS = ["<10", "10-20", "20+"]

MIN_CELL = 20   # מתחתיו התא רועש מכדי לקרוא ממנו


def main():
    df = pd.read_csv(os.path.join(PROCESSED_DIR, "player_season.csv"))

    last = df["season"].max()
    src = df[df["season"] < last].copy()
    alive = set(zip(df["player_code"], df["season"]))
    src["survived"] = [(c, s + 1) in alive
                       for c, s in zip(src["player_code"], src["season"])]

    src["age_bin"] = pd.cut(src["age"], AGE_BINS, labels=AGE_LABELS, right=False)
    src["min_bin"] = pd.cut(src["min_per_game"], MIN_BINS, labels=MIN_LABELS,
                            right=False)

    print("=" * 66)
    print(f"SURVIVAL PROBE | מקור: {sorted(src['season'].unique())} | "
          f"{len(src)} שחקן-עונה")
    print("=" * 66)

    print(f"\nשרידות כללית: {src['survived'].mean():.1%}")

    print("\n--- שוליים: גיל בלבד ---")
    print(src.groupby("age_bin", observed=True)
             .agg(n=("survived", "size"),
                  survival=("survived", "mean"),
                  min_pg=("min_per_game", "mean"))
             .round(3).to_string())

    print("\n--- שוליים: דקות בלבד ---")
    print(src.groupby("min_bin", observed=True)
             .agg(n=("survived", "size"),
                  survival=("survived", "mean"),
                  age=("age", "mean"))
             .round(3).to_string())

    print("\n--- מוצלב: שרידות ---")
    cross = src.pivot_table(index="age_bin", columns="min_bin",
                            values="survived", aggfunc="mean", observed=True)
    print(cross.round(3).to_string())

    print("\n--- מוצלב: גודל התא ---")
    cnt = src.pivot_table(index="age_bin", columns="min_bin",
                          values="survived", aggfunc="size", observed=True)
    print(cnt.to_string())

    thin = (cnt < MIN_CELL).sum().sum()
    print(f"\nתאים מתחת ל-{MIN_CELL} תצפיות: {int(thin)} מתוך {cnt.size} "
          f"— אין לקרוא מהם.")

    print("\n--- יציבות: שרידות לפי עונת מקור ---")
    print(src.groupby("season")
             .agg(n=("survived", "size"), survival=("survived", "mean"))
             .round(3).to_string())


if __name__ == "__main__":
    main()