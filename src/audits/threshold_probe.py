"""
threshold_probe.py
------------------
מאיזו כמות דקות למשחק הופך pir_per_game לאות יציב?

השיטה: חלוקה לדליים לפי min_per_game בעונה t, ובכל דלי — מתאם בין
pir_per_game בעונה t לבין pir_per_game בעונה t+1 של אותו שחקן.
דלי שבו המתאם קורס = מדגם קטן מדי מכדי לאמוד ממנו.

המפרט המושהה בלבד. מתאם בו-זמני היה טאוטולוגי.
המיזוג על season+1 חוסם פערים מבנית — זוג לא רצוף לא מוצא בן זוג.

הרצה: python src/audits/threshold_probe.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
import pandas as pd
from paths import PROCESSED_DIR

# גבולות הדליים — נכתבו לפני ההרצה
BUCKETS = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 45)]
MIN_N = 15   # מתחתיו המתאם עצמו רועש ולא מדווח


def main():
    df = pd.read_csv(os.path.join(PROCESSED_DIR, "player_season.csv"))

    # שחקן שעבר קבוצה מקבל שורה אחת עם סכומים תקינים — נשאר בפנים.
    # מה שמעורפל אצלו הוא שיוך המועדון, לא התפוקה.
    cur = df[["player_code", "season", "min_per_game", "pir_per_game",
              "games", "age"]].copy()
    nxt = df[["player_code", "season", "pir_per_game", "games"]].rename(
        columns={"pir_per_game": "pir_next", "games": "games_next"})

    cur["season_next"] = cur["season"] + 1
    pairs = cur.merge(nxt, left_on=["player_code", "season_next"],
                      right_on=["player_code", "season"],
                      suffixes=("", "_y"))

    print("=" * 66)
    print("THRESHOLD PROBE — יציבות pir_per_game בין עונות")
    print("=" * 66)

    trans = pairs.groupby("season").size()
    print(f"\nזוגות: {len(pairs)}")
    print(trans.to_string())

    # --- שרידות לפי דלי: מי בכלל שרד לעונה הבאה ---
    print("\n--- שרידות לעונה הבאה, לפי דקות למשחק ---")
    src = df[df["season"] < df["season"].max()].copy()
    survived = set(zip(pairs["player_code"], pairs["season"]))
    src["survived"] = [(c, s) in survived
                       for c, s in zip(src["player_code"], src["season"])]
    rows = []
    for lo, hi in BUCKETS:
        m = src["min_per_game"].between(lo, hi, inclusive="left")
        if m.sum():
            rows.append({"bucket": f"{lo}-{hi}", "n": int(m.sum()),
                         "survival": round(src.loc[m, "survived"].mean(), 3)})
    print(pd.DataFrame(rows).to_string(index=False))

    # --- יציבות האות ---
    print("\n--- מתאם pir_per_game: t מול t+1 ---")
    rows = []
    for lo, hi in BUCKETS:
        m = pairs["min_per_game"].between(lo, hi, inclusive="left")
        sub = pairs.loc[m]
        if len(sub) < MIN_N:
            rows.append({"bucket": f"{lo}-{hi}", "n": len(sub),
                         "pearson": None, "spearman": None,
                         "pir_mean": None, "pir_sd": None})
            continue
        rows.append({
            "bucket":   f"{lo}-{hi}",
            "n":        len(sub),
            "pearson":  round(sub["pir_per_game"].corr(sub["pir_next"]), 3),
            "spearman": round(sub["pir_per_game"].corr(sub["pir_next"],
                                                       method="spearman"), 3),
            "pir_mean": round(sub["pir_per_game"].mean(), 2),
            "pir_sd":   round(sub["pir_per_game"].std(), 2),
        })
    print(pd.DataFrame(rows).to_string(index=False))

    print("\nהערה: המתאם מחושב על שורדים בלבד. בדליים הנמוכים השרידות")
    print("נמוכה, ולכן המתאם שם מתאר תת-קבוצה נבחרת — לא את הדלי כולו.")


if __name__ == "__main__":
    main()