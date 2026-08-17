"""
fetch_phases.py  (Day 8)
------------------------
מושך את מיפוי gamecode -> Phase לעונה. **בקשה אחת בלבד.**

למה זה נחוץ: `fetch_boxscores.py` v2 משתמש בנקודת קצה של משחק
בודד, וזו **אינה מחזירה את עמודת Phase** — בניגוד לנקודת הקצה
העונתית ששימשה ל-2024. בלי Phase אי אפשר לסנן לעונה סדירה,
ו-`player_season` נבנה מ-RS בלבד.

זה באג בקובץ v2, והתיקון הזה משלים אותו בלי למשוך שוב 402 משחקים.

הרצה:
    python src/fetch_phases.py 2025
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import RAW_DIR
from euroleague_api.boxscore_data import BoxScoreData

for s in (sys.argv[1:] or ["2025"]):
    gc = BoxScoreData(competition="E").get_gamecodes_season(int(s))
    cols = {c.lower(): c for c in gc.columns}
    code = cols.get("gamecode") or cols.get("game_code") or cols.get("gamenumber")
    ph = cols.get("phase") or cols.get("round")
    out = gc[[code, ph]].copy()
    out.columns = ["Gamecode", "Phase"]
    p = RAW_DIR / f"gamecode_phase_{s}.csv"
    out.to_csv(p, index=False)
    print(f"[{s}] {len(out)} משחקים -> {p.name}")
    print(out.Phase.value_counts().to_string())
