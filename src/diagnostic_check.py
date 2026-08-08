import os
import pandas as pd


def run_diagnostics(season=2022):
    print(f"--- Diagnostics for Season {season} ---")

    # 1. בדיקת כפילויות ב-Valuation (ברצלונה מול מונאקו)
    final_path = os.path.join("data", "processed", f"team_season_{season}_final.csv")
    if os.path.exists(final_path):
        df_final = pd.read_csv(final_path)
        dupes = df_final['Valuation'].duplicated(keep=False)
        dupe_count = dupes.sum()

        print("\n[1] Valuation Duplicates Check:")
        if dupe_count > 0:
            print(f"Found {dupe_count} rows with duplicated Valuation:")
            print(df_final.loc[dupes, ['Team', 'Valuation', 'Minutes', 'Wins']].to_string(index=False))
        else:
            print("No duplicated Valuations found. (If you saw them before, check your eyes or the previous output!)")

    # 2. הערכת נזק: חישוב אחוז הדקות של שחקנים שעברו קבוצה
    raw_path = os.path.join("data", "raw", f"accumulated_rs_{season}.csv")
    if os.path.exists(raw_path):
        df_raw = pd.read_csv(raw_path)

        team_cols = [c for c in df_raw.columns if 'team' in c.lower() or 'club' in c.lower()]
        min_cols = [c for c in df_raw.columns if 'minute' in c.lower() or 'duration' in c.lower()]

        if team_cols and min_cols:
            team_col = team_cols[0]
            min_col = min_cols[0]

            # איתור שורות עם נקודה-פסיק
            traded_mask = df_raw[team_col].astype(str).str.contains(';')

            traded_mins = df_raw.loc[traded_mask, min_col].sum()
            total_mins = df_raw[min_col].sum()
            pct_dropped = (traded_mins / total_mins) * 100

            print("\n[2] Traded Players (Dropped Minutes) Impact:")
            print(f"Total Minutes in Season: {total_mins:.2f}")
            print(f"Minutes by Traded Players: {traded_mins:.2f}")
            print(f"Percentage of Dropped Minutes: {pct_dropped:.3f}%")

            print("\nTraded Players Breakdown:")
            # הצגת השחקנים עצמם כדי להבין במי מדובר
            player_col = [c for c in df_raw.columns if 'player' in c.lower() or 'name' in c.lower()][0]
            print(df_raw.loc[traded_mask, [player_col, team_col, min_col, 'Valuation']].to_string(index=False))


if __name__ == "__main__":
    run_diagnostics(2022)