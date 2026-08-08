import os
import time
from euroleague_api.player_stats import PlayerStats


def fetch_all_accumulated_data():
    # כל העונות הרלוונטיות לפרויקט
    seasons = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]

    output_dir = os.path.join("data", "raw")
    os.makedirs(output_dir, exist_ok=True)

    # אתחול הקליינט
    client = PlayerStats()

    print("--- Starting Accumulated Data Fetch ---")

    for season in seasons:
        out_path = os.path.join(output_dir, f"accumulated_rs_{season}.csv")

        print(f"Fetching accumulated data for season {season} (Phase: RS)...")
        try:
            # התיקון: הוספת endpoint='traditional' כפרמטר חובה
            df = client.get_player_stats_single_season(
                endpoint='traditional',
                season=season,
                statistic_mode='Accumulated',
                phase_type_code='RS'
            )

            df.to_csv(out_path, index=False)
            print(f"[SUCCESS] Season {season} saved. Shape: {df.shape}")

            # 3 שניות של המתנה מנומסת
            time.sleep(3)

        except Exception as e:
            print(f"[ERROR] Failed on season {season}: {e}")


if __name__ == "__main__":
    fetch_all_accumulated_data()