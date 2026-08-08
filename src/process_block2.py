import os
import pandas as pd


# 1. פונקציית עזר לפירסוס דקות
def parse_minutes(min_val):
    if pd.isna(min_val):
        return 0.0
    val_str = str(min_val).strip()
    if ':' in val_str:
        parts = val_str.split(':')
        return int(parts[0]) + int(parts[1]) / 60.0
    try:
        return float(val_str)
    except ValueError:
        return 0.0


def run_block2():
    input_path = os.path.join("data", "raw", "boxscore_player_2022.csv")
    df = pd.read_csv(input_path)

    # ניקוי שורות סיכום קבוצתיות (Team/Total)
    initial_rows = len(df)
    df = df[~df['Player'].isin(['Team', 'Total', 'TEAM', 'TOTAL'])]

    print("\n--- 1. Minutes Parsing & Verification ---")
    df['Minutes_Parsed'] = df['Minutes'].apply(parse_minutes)
    max_mins = df['Minutes_Parsed'].max()
    print(f"Parsed Minutes Max (Single Player): {max_mins:.2f}")

    print("\n--- 2. Actual Participation Filter (Minutes > 0) ---")
    # התיקון: סינון לפי דקות בפועל במקום דגל IsPlaying
    df_played = df[df['Minutes_Parsed'] > 0].copy()

    # חישוב מתמטי לאימות (צפי ל-10 עד 12 שחקנים לקבוצה-משחק)
    total_games = df_played.groupby(['Gamecode', 'Team']).ngroups
    avg_players_per_team_game = len(df_played) / total_games if total_games > 0 else 0

    print(f"Rows after filtering DNP (Minutes > 0): {len(df_played)}")
    print(f"Average players participating per team-game: {avg_players_per_team_game:.2f}")

    print("\n--- 3. Quick Sanity Checks ---")
    print(f"Unique Players: {df_played['Player_ID'].nunique()}")
    print(f"Unique Teams: {df_played['Team'].nunique()} (Expected: 18)")

    print("\n--- 4. Phase Filtering & Aggregation ---")
    # מניעת מעגליות: רק עונה סדירה
    df_rs = df_played[df_played['Phase'] == 'RS'].copy()

    # אגרגציה לקבוצה-עונה
    team_season = df_rs.groupby('Team').agg({
        'Points': 'sum',
        'Valuation': 'sum',
        'Minutes_Parsed': 'sum',
        'Turnovers': 'sum'
    }).reset_index()

    output_dir = os.path.join("data", "processed")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "team_season_2022.csv")

    # שמירה (דורס את הקובץ השגוי הקודם)
    team_season.to_csv(out_path, index=False)

    print(f"\n[SUCCESS] Saved corrected dataset to: {out_path}")


if __name__ == "__main__":
    run_block2()