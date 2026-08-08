"""
inspect_schema.py
-----------------
סקריפט אבחון בלבד. קורא קובץ אחד, מדפיס מה יש בו, לא כותב כלום.
מטרה: לזהות את שמות העמודות האמיתיות לפני שקובעים אותן בפייפליין.

הרצה: העבר ל-src/ והרץ. אם הקובץ יושב ישירות ב-PythonProject,
שנה את ROOT_DIR לשורה המסומנת למטה.
"""

import os
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 250)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)   # <-- אם הסקריפט לא ב-src/, החלף ל: ROOT_DIR = BASE_DIR
RAW_DIR = os.path.join(ROOT_DIR, "data", "raw")

SEASON = 2022
FILE_PATH = os.path.join(RAW_DIR, f"accumulated_rs_{SEASON}.csv")


def main():
    print(f"[DEBUG] ROOT_DIR = {ROOT_DIR}")
    print(f"[DEBUG] Looking for = {FILE_PATH}")

    if not os.path.exists(FILE_PATH):
        print("\n[FAIL] הקובץ לא נמצא. קבצים שכן קיימים ב-RAW_DIR:")
        if os.path.isdir(RAW_DIR):
            for f in sorted(os.listdir(RAW_DIR)):
                print("   -", f)
        else:
            print("   התיקייה עצמה לא קיימת. הנתיב שגוי.")
        return

    df = pd.read_csv(FILE_PATH)

    # ---------- 1. סכמה ----------
    print("\n" + "=" * 70)
    print("1. SCHEMA")
    print("=" * 70)
    print(f"Shape: {df.shape}")
    print("\nColumns (name | dtype | non-null | n_unique):")
    for c in df.columns:
        print(f"   {c:<32} | {str(df[c].dtype):<8} | {df[c].notna().sum():>5} | {df[c].nunique():>5}")

    # ---------- 2. מועמדות לעמודות המפתח ----------
    print("\n" + "=" * 70)
    print("2. CANDIDATE COLUMNS  (לבחירה ידנית - הסקריפט לא בוחר בשבילך)")
    print("=" * 70)

    patterns = {
        "TEAM":      ["team", "club"],
        "VALUATION": ["valuation", "pir", "performanceindex", "rating"],
        "MINUTES":   ["minute", "duration"],
        "PLAYER_ID": ["playerid", "player_id", "code"],
        "GAMES":     ["gamesplayed", "games"],
    }
    for role, keys in patterns.items():
        hits = [c for c in df.columns if any(k in c.lower().replace("_", "") for k in keys)]
        status = "OK" if len(hits) == 1 else ("NONE!" if not hits else "AMBIGUOUS")
        print(f"   {role:<10} [{status:^9}] -> {hits}")

    # ---------- 3. דגימה ----------
    print("\n" + "=" * 70)
    print("3. SAMPLE ROWS (first 5, all columns)")
    print("=" * 70)
    print(df.head(5).to_string())

    # ---------- 4. בדיקת שחקנים שעברו קבוצה ----------
    print("\n" + "=" * 70)
    print("4. TRADED-PLAYER CHECK (ערכי קבוצה משורשרים)")
    print("=" * 70)
    team_cands = [c for c in df.columns if "team" in c.lower() or "club" in c.lower()]
    if not team_cands:
        print("   לא נמצאה עמודת קבוצה. בדוק ידנית ברשימה למעלה.")
    for tc in team_cands:
        vals = df[tc].astype(str)
        weird = vals[vals.str.contains(r"[;,/]", regex=True, na=False)]
        print(f"   '{tc}': {df[tc].nunique()} ערכים ייחודיים | {len(weird)} שורות חשודות")
        if len(weird):
            print(f"      דוגמאות: {weird.unique()[:5].tolist()}")

    # ---------- 5. שפיות דקות ----------
    print("\n" + "=" * 70)
    print("5. MINUTES SANITY")
    print("=" * 70)
    min_cands = [c for c in df.columns if "minute" in c.lower()]
    for mc in min_cands:
        total = df[mc].sum()
        print(f"   '{mc}': sum={total:,.1f} | max_single={df[mc].max():,.1f}")
        print(f"      -> implied team-rounds = sum/200 = {total / 200:.1f}")
        print("      (צפוי: n_rounds * n_teams / 2 ... כלומר 34*18/2 = 306 לעונת 2022)")


if __name__ == "__main__":
    main()