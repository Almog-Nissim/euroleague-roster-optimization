"""
check_files.py  (Day 9)
-----------------------
**איזה קבצים אצלך מעודכנים ואיזה לא.**

זו הפעם הרביעית היום שהרצה נופלת לא בגלל תוכן אלא בגלל שקובץ
שנשלח בצ'אט לא הגיע ל-src, או הגיע בגרסה ישנה. השגיאות נראות
כמו באגים:

    ModuleNotFoundError: No module named 'newcomer_pool'
    ModuleNotFoundError: No module named 'final_fix'
    TypeError: optimise_v3() got an unexpected keyword argument 'repl'
    (וגם: player_positions.csv הישן, ש**לא** זרק שגיאה כלל)

הסקריפט בודק לכל קובץ סימן היכר שקיים רק בגרסה העדכנית.

הרצה:
    python src/check_files.py
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
SEP = "=" * 74

# קובץ -> מחרוזת שחייבת להופיע בגרסה העדכנית
MARKS = {
    "league_backtest.py":       "build_newcomer_rows",
    "newcomer_pool.py":         "el_seasons_lag == 1",
    "minute_profile.py":        "repl=0.0",
    "why_100.py":               "score_realistic",
    "crowding.py":              "def _alloc",
    "crowding_extrapolation.py": "def check_convexity",
    "cost_reality.py":          "מנוע=n",
    "salary_market.py":         "ISHWAINWRIGHT",
    "depth_value.py":           "lost_x_depth",
    "final_fix.py":             "def prune",
    "score_to_wins.py":         "slope_ci",
    "stochastic_avail.py":      "def sim_score",
}

print(SEP)
print(f"תיקייה: {SRC}")
print(SEP)
missing, stale, ok = [], [], []
for f, mark in MARKS.items():
    p = SRC / f
    if not p.exists():
        missing.append(f)
        print(f"  ⛔ חסר לגמרי     {f}")
        continue
    txt = p.read_text(encoding="utf-8", errors="ignore")
    if mark not in txt:
        stale.append(f)
        print(f"  ⚠️ גרסה ישנה     {f}   (חסר: {mark!r})")
    else:
        ok.append(f)
        print(f"  ✅ מעודכן        {f}")

print(SEP)
print(f"  מעודכנים {len(ok)} · ישנים {len(stale)} · חסרים {len(missing)}")
if stale or missing:
    print("\n  בקש ממני לשלוח מחדש:")
    for f in missing + stale:
        print(f"    {f}")
else:
    print("\n  ✅ הכל מעודכן.")
print(SEP)