"""
fix_positions.py  (Day 9)
-------------------------
**סקריפט אחד, עצמאי, שסוגר את בעיית העמדות בלי העברות קבצים.**

הבעיה: הקובץ נשלח בצ'אט, נוחת ב-Downloads, ולא מגיע לתיקייה
שהקוד קורא ממנה. `league_backtest` ממשיך לקרוא את הישן **בשקט**,
מדלג על 11 מועדונים, ומדפיס תוצאה שנראית תקינה.

מה הוא עושה:
  1. מאתר את `positions_missing.xlsx` בכל מקום סביר
  2. קורא את `player_positions.csv` הנוכחי
  3. מוסיף רק קודים שעדיין אינם שם
  4. כותב **בדיוק לנתיב שהקוד קורא ממנו**
  5. מאמת ומדפיס כמה דקות נשארו בלי עמדה

**אידמפוטנטי.** הרצה שנייה לא משנה דבר ולא נופלת.
אינו תלוי בשום קובץ אחר חוץ מ-`paths.py`.

הרצה:
    python src/fix_positions.py
"""

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR, ROOT_DIR

VALID = {"G", "F", "C"}
POSCSV = PROCESSED_DIR / "player_positions.csv"
SEARCH = [PROCESSED_DIR.parent / "manual", PROCESSED_DIR.parent, ROOT_DIR,
          PROCESSED_DIR, Path.home() / "Downloads", Path.home() / "Desktop"]
SEP = "=" * 70


def find_xlsx():
    hits = []
    for d in SEARCH:
        if d.exists():
            hits += [f for f in d.glob("*ositions_missing*.xlsx")
                     if not f.name.startswith("~$")]
    return max(hits, key=lambda p: p.stat().st_mtime) if hits else None


def main():
    print(SEP)
    print(f"יעד: {POSCSV}")
    pos = pd.read_csv(POSCSV, dtype={"player_code": str})
    print(f"מצב נוכחי: {len(pos)} שורות")

    x = find_xlsx()
    if x is None:
        print("\n⛔ לא נמצא positions_missing.xlsx. חיפשתי ב:")
        for d in SEARCH:
            print(f"   {d}")
        print("\n   הורד אותו מהצ'אט ושים באחת התיקיות האלה. אין צורך")
        print("   לשנות שם או להעביר לתיקייה מסוימת — הסקריפט ימצא.")
        sys.exit(1)
    print(f"נמצא גיליון: {x}")

    df = pd.read_excel(x, sheet_name=0, dtype={"player_code": str})
    df["player_code"] = df.player_code.astype(str).str.strip()
    df["position"] = (df.position.astype(str).str.strip().str.upper()
                      .replace({"NAN": None, "": None, "NONE": None}))
    filled = df[df.position.notna()]
    bad = filled[~filled.position.isin(VALID)]
    if len(bad):
        raise ValueError("עמדה לא חוקית: " + ", ".join(
            f"{r.player_code}={r.position!r}" for r in bad.itertuples()))
    print(f"בגיליון: {len(df)} שורות, מהן {len(filled)} מולאו")

    have = set(pos.player_code)
    new = filled[~filled.player_code.isin(have)]
    print(f"חדשים להוספה: {len(new)}   (כבר קיימים: {len(filled)-len(new)})")

    if len(new):
        out = pd.concat(
            [pos[["player_code", "player_name", "position"]],
             new[["player_code", "player_name", "position"]]],
            ignore_index=True)
        out.to_csv(POSCSV, index=False)
        print(f"נכתב: {len(pos)} -> {len(out)} שורות")
    else:
        out = pos
        print("אין מה להוסיף — הקובץ כבר מעודכן.")

    print("\n" + SEP)
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    known, ok = set(out.player_code), True
    for s in (2024, 2025):
        t = ps[(ps.season == s) & (ps.min_per_game > 0)].copy()
        t["mt"] = t.min_per_game * t.games
        m = t[~t.player_code.isin(known)]
        share = m.mt.sum() / t.mt.sum()
        ok &= share < 0.001
        print(f"  {s}: {len(m):3d} שחקנים ללא עמדה, {share:6.1%} מהדקות")
    st = POSCSV.stat()
    print(f"\n  הקובץ בדיסק: {len(out)} שורות, {st.st_size:,} בייט, עודכן "
          f"{time.strftime('%H:%M:%S', time.localtime(st.st_mtime))}")
    print(SEP)
    print("✅ אפשר להריץ league_backtest ואז why_100." if ok else
          "⛔ עדיין חסר. שלח לי את הפלט הזה.")
    print(SEP)


if __name__ == "__main__":
    main()