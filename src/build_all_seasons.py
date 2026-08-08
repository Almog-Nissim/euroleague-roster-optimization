import os
import time
import pandas as pd
from euroleague_api.standings import Standings

# התיקון: הגדרת נתיבים אבסולוטית כדי למנוע בעיות של Working Directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")


def get_season_metadata(season):
    # הגדרת מספר המחזורים (n_rounds) בהתאם למבנה הליגה בכל עונה
    if season in [2017, 2018]:
        return 30
    elif season == 2019:
        return 28  # עונת הקורונה שנקטעה
    else:
        return 34


def build_final_dataset():
    print("--- Building Final Unified Dataset ---")
    seasons = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
    all_data = []

    for season in seasons:
        n_rounds = get_season_metadata(season)

        # שימוש בנתיב האבסולוטי המעודכן
        file_path = os.path.join(RAW_DIR, f"accumulated_rs_{season}.csv")

        if not os.path.exists(file_path):
            print(f"[SKIP] Missing raw data for season {season}. Looked at: {file_path}")
            continue

        df_players = pd.read_csv(file_path)

        # איתור דינמי של עמודות
        team_col = [c for c in df_players.columns if 'team' in c.lower() or 'club' in c.lower()][0]
        val_col = \
        [c for c in df_players.columns if 'valuation' in c.lower() or 'pir' in c.lower() or 'index' in c.lower()][0]
        min_col = [c for c in df_players.columns if 'minute' in c.lower() or 'duration' in c.lower()][0]

        # אגרגציה לרמת קבוצה ושינוי שמות העמודות לפי דרישת המודל
        team_stats = df_players.groupby(team_col).agg({
            val_col: 'sum',
            min_col: 'sum'
        }).reset_index().rename(columns={
            team_col: 'team',
            val_col: 'weighted_pir',
            min_col: 'total_minutes'
        })

        # === Assert דינמי לדקות משחק ===
        expected_mins = n_rounds * 200
        team_stats['assert_minutes_flag'] = False

        for idx, row in team_stats.iterrows():
            actual_mins = row['total_minutes']
            # אם הדקות חורגות ב-10% מהצפי (או חסרות), נסמן את השורה
            if abs(actual_mins - expected_mins) > (expected_mins * 0.1):
                team_stats.at[idx, 'assert_minutes_flag'] = True

        # משיכת טבלת הדירוג והניצחונות
        try:
            df_standings = Standings().get_standings(season=season, round_number=n_rounds)
            team_col_st = \
            [c for c in df_standings.columns if 'team' in c.lower() or 'club' in c.lower() or 'code' in c.lower()][0]
            wins_col = [c for c in df_standings.columns if 'win' in c.lower() or 'won' in c.lower()][0]

            df_wins = df_standings[[team_col_st, wins_col]].rename(columns={team_col_st: 'team', wins_col: 'wins'})

            # מיזוג הטבלאות וסינון קבוצות "רפאים" (שחקנים שעברו קבוצה)
            final_df = pd.merge(team_stats, df_wins, on='team', how='left')
            final_df = final_df.dropna(subset=['wins']).copy()

        except Exception as e:
            print(f"[ERROR] Could not process standings for season {season}: {e}")
            continue

        # הוספת עמודות התיעוד הנדרשות
        final_df['season'] = season
        final_df['n_rounds'] = n_rounds
        final_df['is_covid_season'] = 1 if season == 2019 else 0

        all_data.append(final_df)

        failed_asserts = final_df['assert_minutes_flag'].sum()
        print(f"[SUCCESS] Season {season} ready. Failed asserts: {failed_asserts}")

        time.sleep(2)  # מניעת עומס

    if all_data:
        master_df = pd.concat(all_data, ignore_index=True)

        # סידור ושמירת העמודות המדויקות למודל
        master_df = master_df[
            ['season', 'team', 'weighted_pir', 'wins', 'n_rounds', 'is_covid_season', 'assert_minutes_flag']]
        master_df = master_df.sort_values(by=['season', 'wins'], ascending=[False, False])

        os.makedirs(PROCESSED_DIR, exist_ok=True)
        out_path = os.path.join(PROCESSED_DIR, "team_season.csv")

        master_df.to_csv(out_path, index=False)
        print(f"\n[SUCCESS] Final master dataset saved to {out_path} ({len(master_df)} rows).")


if __name__ == "__main__":
    build_final_dataset()