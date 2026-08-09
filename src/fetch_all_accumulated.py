import os
import time

from euroleague_api.player_stats import PlayerStats

import paths


def fetch_all_accumulated_data(seasons):
    """Fetch accumulated regular-season player stats and write to data/raw."""
    client = PlayerStats()

    print("--- Starting Accumulated Data Fetch ---")
    print(f"Target directory: {paths.RAW_DIR}\n")

    ok, failed = [], []

    for season in seasons:
        out_path = os.path.join(paths.RAW_DIR, f"accumulated_rs_{season}.csv")

        print(f"Fetching accumulated data for season {season} (Phase: RS)...")
        try:
            df = client.get_player_stats_single_season(
                endpoint='traditional',
                season=season,
                statistic_mode='Accumulated',
                phase_type_code='RS'
            )

            if df is None or df.empty:
                raise ValueError("API returned an empty frame")

            df.to_csv(out_path, index=False)

            written = os.path.getsize(out_path)
            print(f"[SUCCESS] Season {season} saved. Shape: {df.shape}")
            print(f"          -> {os.path.abspath(out_path)} ({written:,} bytes)")
            ok.append(season)

            time.sleep(3)  # politeness delay; see Difficulty 4

        except Exception as e:
            print(f"[ERROR] Failed on season {season}: {type(e).__name__}: {e}")
            failed.append(season)

    print(f"\n--- Done. ok={ok}  failed={failed} ---")
    if failed:
        raise RuntimeError(f"Fetch incomplete for seasons: {failed}")


if __name__ == "__main__":
    fetch_all_accumulated_data(seasons=[2016, 2025])