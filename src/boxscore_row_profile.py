"""
boxscore_row_profile.py — ממה מורכבת שורה בקובץ בוקסקור קיים.

למה
---
המשיכה החדשה מחזירה 23.65 שורות למשחק. הקבצים הקיימים: 27.74
(2016) ו-27.85 (2017). פער של ~4 שורות למשחק, כלומר 2 לכל קבוצה.

ההשערה: הקבצים הקיימים כוללים שורות סיכום קבוצה, והפרסר החדש
קורא רק את `PlayersStats`. **לא מתקנים לפי השערה** — מודדים.

הסקריפט מפרק שורות של משחק אחד ומראה בדיוק מה יש שם.

הרצה:  python src/boxscore_row_profile.py
       python src/boxscore_row_profile.py --season 2020
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import find_boxscores, repo_root  # noqa: E402


# 🔴 תבנית המזהה מוגדרת **פעם אחת**. קודם היא הופיעה בשלושה מקומות
# ואחד מהם לא עודכן — הספירה סיננה לפי תבנית אחת והדוגמאות לפי
# אחרת, כך שהמספר והרשימה תיארו קבוצות שונות.
#
# ומדוע התבנית אינה `^P\d+$`: כ-19% מהמזהים ב-2016 נושאים אותיות —
# PLUO, PARN, PCHX, PJPF. אלה שחקנים אמיתיים.
ID_PATTERN = r"^P[A-Za-z0-9]+$"


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--root", default=None)
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")
    files = find_boxscores(args.root, verbose=False)
    if not files:
        raise SystemExit("🔴 לא נמצאו קבצי בוקסקור.")

    season = args.season or sorted(files)[0]
    if season not in files:
        raise SystemExit(f"🔴 אין קובץ לעונה {season}. קיימות: {sorted(files)}")

    path = files[season]
    df = pd.read_csv(path, dtype={"Gamecode": str, "Player_ID": str}, low_memory=False)
    print(f"קובץ: {path}\nשורות: {len(df):,}  משחקים: {df['Gamecode'].nunique():,}")
    print(f"שורות למשחק: {len(df) / df['Gamecode'].nunique():.2f}")

    # ---------------------------------------------------------- A
    hdr("A. משחק אחד, כל השורות")

    gc = df["Gamecode"].iloc[0]
    one = df[df["Gamecode"] == gc]
    print(f"gamecode {gc} — {len(one)} שורות\n")

    cols = [c for c in ["Home", "Team", "Player_ID", "Player", "Dorsal",
                        "IsStarter", "IsPlaying", "Minutes", "Points", "Valuation"]
            if c in one.columns]
    print(one[cols].to_string(index=False))

    # ---------------------------------------------------------- B
    hdr("B. שורות למשחק לפי קבוצה")

    if "Team" in df.columns:
        per = df.groupby(["Gamecode", "Team"]).size()
        print(per.describe().to_string())
        print(f"\n  ערכים נפוצים: {dict(per.value_counts().head(5))}")

    # ---------------------------------------------------------- C
    hdr("C. שורות שאינן שחקן")

    pid = df["Player_ID"].astype(str).str.strip()
    name = df.get("Player", pd.Series([""] * len(df))).astype(str).str.strip()

    print("  Player_ID שאינם מתחילים ב-P ואחריו תווים:")
    is_pid = pid.str.match(ID_PATTERN, na=False)
    odd_id = df[~is_pid]
    if len(odd_id):
        print(f"    {len(odd_id):,} שורות ({len(odd_id) / df['Gamecode'].nunique():.2f} למשחק)")
        print(f"    ערכים: {sorted(pid[~is_pid].unique())[:15]}")
    else:
        print("    אין — כל המזהים בפורמט תקין")

    print("\n  שמות חשודים (Total / Team / ריק):")
    odd_name = df[name.str.upper().str.contains("TOTAL|TEAM", na=False) | name.eq("")]
    if len(odd_name):
        print(f"    {len(odd_name):,} שורות ({len(odd_name) / df['Gamecode'].nunique():.2f} למשחק)")
        print(f"    ערכים: {sorted(name[name.str.upper().str.contains('TOTAL|TEAM', na=False) | name.eq('')].unique())[:15]}")
    else:
        print("    אין")

    non_player = df[(~pid.str.match(ID_PATTERN, na=False))
                    | name.str.upper().str.contains("TOTAL|TEAM", na=False)]
    if len(non_player):
        print(f"\n  דוגמאות ({len(non_player) / df['Gamecode'].nunique():.2f} למשחק):")
        print(non_player[cols].head(8).to_string(index=False))

    # ---------------------------------------------------------- D
    hdr("D. המסקנה")

    n_games = df["Gamecode"].nunique()
    total_ratio = len(df) / n_games
    player_ratio = (len(df) - len(non_player)) / n_games

    print(f"  שורות למשחק — הכול      : {total_ratio:.2f}")
    print(f"  שורות למשחק — שחקנים    : {player_ratio:.2f}")
    print(f"  שורות למשחק — לא שחקנים : {len(non_player) / n_games:.2f}")
    print("\n  המשיכה החדשה מחזירה 23.65.")

    if abs(player_ratio - 23.65) < 1.0:
        print("  ✅ תואם ל'שחקנים בלבד'. הפרסר החדש תקין — הקבצים הישנים")
        print("     כוללים שורות סיכום, והשאלה היא אם לשחזר אותן.")
    elif abs(total_ratio - 23.65) < 1.0:
        print("  ⚠️ תואם ל'הכול'. אז ההסבר אינו שורות סיכום.")
    else:
        print(f"  🔴 לא תואם לאף אחד מהשניים. הפער אינו שורות סיכום —")
        print(f"     חסרות ~{total_ratio - 23.65:.1f} שורות למשחק ממקור אחר.")
        print("     בדוק אם שחקנים עם DNP נשמטים בפרסר החדש.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())