import os
import pandas as pd
from euroleague_api.boxscore_data import BoxScoreData


def fetch_season_data(season: int):
    print(f"Fetching boxscore data for season {season}...")

    try:
        # יצירת אובייקט של המחלקה החדשה
        boxscore_client = BoxScoreData()

        # שימוש במתודה הייעודית לעונה בודדת שהתגלתה בדיאגנוסטיקה
        df = boxscore_client.get_players_boxscore_stats_single_season(season=season)

        # הדפסת המידע הנדרש לבדיקת תקינות הנתונים
        print("\n--- Data Overview ---")
        print(f"Shape: {df.shape}")
        print("\nColumns:")
        print(df.columns.tolist())
        print("\nFirst 5 rows (sample):")
        print(df.head(5))

        # הגדרת נתיב השמירה בתיקיית data/raw
        output_dir = os.path.join("data", "raw")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"boxscore_player_{season}.csv")

        # שמירת הקובץ
        df.to_csv(output_path, index=False)
        print(f"\n[SUCCESS] Data successfully saved to: {output_path}")

    except Exception as e:
        print(f"\n[ERROR] Failed to fetch data for season {season}: {e}")


if __name__ == "__main__":
    fetch_season_data(2022)