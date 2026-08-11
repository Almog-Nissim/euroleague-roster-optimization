"""
אימות ההרחבה: העונות 2022-2025 חייבות להיות זהות בין הקובץ
המאומת לבין המורחב. אם משהו זז - זה באג, לא שיפור.
"""
import sys
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import PROCESSED_DIR


OVERLAP = [2022, 2023, 2024, 2025]

old = pd.read_csv(PROCESSED_DIR / "player_season.csv", dtype={"player_code": str})
new = pd.read_csv(PROCESSED_DIR / "player_season_extended.csv", dtype={"player_code": str})

new_ov = new[new.season.isin(OVERLAP)]
print(f"old: {len(old)} שורות | new(overlap): {len(new_ov)} שורות")

if len(old) != len(new_ov):
    raise SystemExit(f"פער בספירת שורות: {len(old)} מול {len(new_ov)}")

a = old.groupby("season").agg(n=("player_code", "size"), pir=("sum_pir", "sum"),
                              minutes=("minutes", "sum"))
b = new_ov.groupby("season").agg(n=("player_code", "size"), pir=("sum_pir", "sum"),
                                 minutes=("minutes", "sum"))
d = (a - b).abs()
print("\nפער לפי עונה:")
print(d.to_string())

if d.max().max() > 1e-6:
    raise SystemExit("העונות החופפות אינן זהות - ההרחבה שינתה דאטה קיים")

print("\n[OK] 2022-2025 זהות. ההרחבה הוסיפה בלבד.")