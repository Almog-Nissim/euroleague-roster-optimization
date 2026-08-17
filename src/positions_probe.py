"""
positions_probe.py  (Day 6, task 0)  -- גרסה 2
----------------------------------------------
האם euroleague_api מחזיר עמדת שחקן?

גרסה 1 נעצרה באמצע: הפילטר שלה תפס גם פונקציות שמושכות משחק-משחק
(330 קריאות לעונה, ~1.7 שניות לכל אחת). היא היתה שורפת את כל
ה-timebox ומעמיסה על ה-API על פונקציה שממילא לא מחזירה עמדה.

הגרסה הזו לא מנחשת. מיפוי החבילה נעשה מראש בהסתכלות על החתימות:

  get_player_stats_single_season(endpoint, season)   <- קריאה אחת
  get_players_boxscore_stats_single_season(season)   <- 330 קריאות

--------------------------------------------------------------------
מה שכבר ידוע לפני ההרצה
--------------------------------------------------------------------
בחבילה אין endpoint של סגל, רשימת שחקנים או פרופיל. היא כולה
דאטת משחקים: box score, play-by-play, shots, standings, schedule,
game metadata. אין get_roster ואין get_players.

לכן מרחב החיפוש כולו הוא ארבעת ה-endpoints של player_stats:
traditional, advanced, misc, scoring - ועוד box score של משחק אחד.

התחזית: אף אחד מהם לא מחזיר עמדה. traditional כבר משמש ב-
fetch_all_accumulated.py, ו-player_season.csv אינו מכיל עמדה -
כלומר לפחות אחד מהחמישה כבר הופרך בעקיפין.
--------------------------------------------------------------------

תקציב קריאות: 6. סטופר: 20 דקות. שניהם קשיחים.

הרצה:
    python src/audits/positions_probe.py
"""

import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROCESSED_DIR

SEASON = 2024
TIMEBOX_SEC = 20 * 60
MAX_CALLS = 6
POLITE_SLEEP = 3          # אותה השהיה כמו ב-fetch_all_accumulated.py

ENDPOINTS = ["traditional", "advanced", "misc", "scoring"]

# 'dorsal' הוסר: בספרדית זה מספר החולצה, לא העמדה. הוא נכנס לכאן
# בטעות והפיל את ההרצה הראשונה - הסקריפט הכריז POSITIONS = AVAILABLE
# על העמודה [2, 3, 5, 7, 9, 10, 15, 19].
POS_COL_PAT = re.compile(r"(position|^pos$|_pos$|pos_|role)", re.I)

# שדה עמדה שכל ערכיו ספרות אינו שדה עמדה. התאמה לפי שם לבדה
# אינה מספיקה - היא מה שהכשילה את ההרצה הראשונה.
NUMERIC_REJECT_FRAC = 0.5
POS_VALUE_PAT = re.compile(
    r"^\s*(g|f|c|pg|sg|sf|pf|guard|forward|center|centre)\s*$", re.I)

_calls = 0
_t0 = None


def budget(where):
    """שני התקציבים נבדקים יחד. חריגה באחד מהם עוצרת."""
    left_t = TIMEBOX_SEC - (time.time() - _t0)
    left_c = MAX_CALLS - _calls
    if left_t <= 0:
        stop(f"נגמר הזמן ב-{where}")
    if left_c <= 0:
        stop(f"נגמר תקציב הקריאות ב-{where}")
    return left_t, left_c


def stop(why):
    print(f"\n[STOP] {why}")
    print("POSITIONS = UNAVAILABLE")
    print("מועבר כפריט דאטה. לא ממשיכים לחפש.")
    sys.exit(0)


def scan_for_position(df, label):
    """שני מבחנים: שם עמודה, וערכים שנראים כמו עמדה.

    השני קיים כי עמודה בשם 'category' יכולה להכיל G/F/C.
    """
    by_name = []
    for c in df.columns:
        if not POS_COL_PAT.search(str(c)):
            continue
        s = df[c].dropna().astype(str).head(300)
        num_frac = s.str.fullmatch(r"\d+").mean() if len(s) else 0.0
        if num_frac > NUMERIC_REJECT_FRAC:
            print(f"    [נדחה] {c}: {num_frac:.0%} מהערכים ספרות "
                  f"({list(s.unique()[:6])}). מספר, לא עמדה.")
            continue
        by_name.append(c)

    by_value = []
    for c in df.columns:
        try:
            s = df[c].dropna().astype(str).head(300)
        except Exception:
            continue
        if s.empty or s.nunique() > 8:
            continue
        frac = s.apply(lambda x: bool(POS_VALUE_PAT.match(x))).mean()
        if frac > 0.7:
            by_value.append((c, sorted(s.unique().tolist())[:8]))

    if not (by_name or by_value):
        return None

    print(f"\n  [HIT] {label}")
    for c in by_name:
        print(f"    לפי שם : {c} -> "
              f"{list(df[c].dropna().astype(str).unique()[:8])}")
    for c, vals in by_value:
        print(f"    לפי ערך: {c} -> {vals}")
    return (by_name + [c for c, _ in by_value])[0]


def probe_player_stats():
    global _calls
    from euroleague_api.player_stats import PlayerStats
    client = PlayerStats()
    found = []

    print("\n" + "=" * 74)
    print(f"player_stats - ארבעה endpoints, קריאה אחת לכל אחד")
    print("=" * 74)

    for ep in ENDPOINTS:
        left_t, left_c = budget(f"endpoint={ep}")
        try:
            df = client.get_player_stats_single_season(
                endpoint=ep, season=SEASON,
                statistic_mode="Accumulated", phase_type_code="RS")
            _calls += 1
        except Exception as e:
            print(f"  [FAIL] {ep}: {type(e).__name__}: {str(e)[:70]}")
            continue

        if df is None or df.empty:
            print(f"  [ריק]  {ep}")
            continue

        print(f"  [OK]   {ep:<14} {df.shape}  "
              f"[{int(left_t)}s, {left_c} קריאות נותרו]")
        print(f"         עמודות: {list(df.columns)[:14]}")
        col = scan_for_position(df, f"player_stats/{ep}")
        if col:
            found.append((f"player_stats/{ep}", df, col))
        time.sleep(POLITE_SLEEP)
    return found


def extract_gamecode(gc):
    """מזהי משחק אינם בהכרח מספרים.

    'E2024_1' הוא מזהה מורכב: E + עונה + _ + מספר משחק. int() עליו
    זורק. זה בדיוק באג 1 מיום 4 - הנחה שמזהה הוא מספר - והפעם הוא
    היה בקוד הזה. לכן: לא מנחשים, מסתכלים.

    סדר החיפוש:
      1. עמודה בשם gamecode/game_code שהיא כבר מספרית
      2. אותה עמודה כמחרוזת -> החלק שאחרי '_'
      3. כל עמודה מספרית שנראית כמו מספר משחק
    """
    cand = [c for c in gc.columns
            if re.search(r"game_?code", str(c), re.I)]
    for c in cand:
        s = gc[c].dropna()
        if s.empty:
            continue
        v = s.iloc[0]
        if isinstance(v, (int,)) or str(v).isdigit():
            return int(v)
        m = re.search(r"_(\d+)$", str(v))
        if m:
            return int(m.group(1))
    for c in gc.columns:
        s = pd.to_numeric(gc[c], errors="coerce").dropna()
        if len(s) and s.min() >= 1 and s.max() < 100000:
            return int(s.iloc[0])
    return None


def probe_boxscore():
    """box score של משחק *אחד*. שתי קריאות: gamecodes + משחק.

    לא get_players_boxscore_stats_single_season - זו שמושכת 330.
    """
    global _calls
    from euroleague_api.boxscore_data import BoxScoreData
    client = BoxScoreData()

    print("\n" + "=" * 74)
    print("box score - משחק אחד בלבד")
    print("=" * 74)

    budget("gamecodes")
    try:
        gc = client.get_gamecodes_season(SEASON)
        _calls += 1
    except Exception as e:
        print(f"  [FAIL] gamecodes: {type(e).__name__}: {str(e)[:70]}")
        return []
    if gc is None or gc.empty:
        print("  [ריק] אין gamecodes")
        return []

    print(f"  gamecodes: {gc.shape} | עמודות: {list(gc.columns)}")
    print(gc.head(2).to_string())

    code = extract_gamecode(gc)
    if code is None:
        print("  [SKIP] לא זוהה gamecode מספרי. box score מדולג.")
        return []
    print(f"  gamecode שנבחר: {code!r}")

    budget("boxscore")
    try:
        df = client.get_players_boxscore_stats(season=SEASON, gamecode=code)
        _calls += 1
    except Exception as e:
        print(f"  [FAIL] boxscore: {type(e).__name__}: {str(e)[:70]}")
        return []

    print(f"  [OK] gamecode={code} {df.shape}")
    print(f"       עמודות: {list(df.columns)[:14]}")
    col = scan_for_position(df, f"boxscore/{code}")
    return [(f"boxscore/{code}", df, col)] if col else []


def coverage(df, pos_col):
    """שדה שקיים ב-40% מהשורות אינו שדה שאפשר לבנות עליו אילוץ סגל."""
    print("\n" + "=" * 74)
    print("כיסוי מול player_season.csv")
    print("=" * 74)
    try:
        ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                         dtype={"player_code": str})
    except FileNotFoundError:
        print("  [SKIP] player_season.csv לא נמצא")
        return

    code_col = next((c for c in df.columns
                     if re.search(r"player[_.]?(code|id)|^code$", str(c),
                                  re.I)), None)
    if code_col is None:
        print("  [FAIL] אין עמודת קוד שחקן - אי אפשר להצליב")
        return

    api = df[[code_col, pos_col]].copy()
    api[code_col] = api[code_col].astype(str).str.strip().str.upper()
    api = api.dropna(subset=[pos_col]).drop_duplicates(code_col)
    ours = set(ps.player_code.dropna().astype(str).str.strip().str.upper())
    cov = len(ours & set(api[code_col])) / max(1, len(ours))

    print(f"  שחקנים אצלנו : {len(ours)}")
    print(f"  עם עמדה      : {cov:.1%}")
    if cov < 0.90:
        print("  [WARN] מתחת ל-90%. אילוץ סגל על שדה חלקי נותן")
        print("  לאופטימייזר דלת אחורית דרך מי שאין לו עמדה.")


def main():
    global _t0
    _t0 = time.time()
    print("=" * 74)
    print("משימה 0 - עמדות שחקנים")
    print(f"  timebox {TIMEBOX_SEC // 60} דק' · תקציב {MAX_CALLS} קריאות")
    print("  תחזית: אף endpoint לא מחזיר עמדה")
    print("=" * 74)

    try:
        import euroleague_api  # noqa: F401
    except ImportError:
        print("  [FAIL] euroleague_api לא מותקן:")
        print("  & \"<python.exe>\" -m pip install euroleague-api")
        sys.exit(1)

    found = probe_player_stats() + probe_boxscore()

    print("\n" + "=" * 74)
    print("תוצאה")
    print("=" * 74)
    print(f"  קריאות שהצליחו: {_calls}/{MAX_CALLS} · "
          f"זמן: {time.time() - _t0:.0f}s/{TIMEBOX_SEC}s")

    # "לא נמצאה עמדה" ו"לא הצלחנו לבדוק" הן שתי תוצאות שונות.
    # בלי ההפרדה הזו, כשל רשת נראה בדיוק כמו הפרכה - והפריט
    # היה נסגר בלי שנבדק. זה בדיוק הדפוס של הבאגים השקטים מיום 3.
    if _calls == 0:
        print("\n  POSITIONS = UNKNOWN")
        print("  אף קריאה לא הצליחה. זו לא הפרכה - זו אי-בדיקה.")
        print("  בדוק חיבור/פרוקסי והרץ שוב. הפריט נשאר פתוח.")
        sys.exit(2)

    if not found:
        print(f"\n  POSITIONS = UNAVAILABLE  ({_calls} מקורות נבדקו בפועל)")
        print("  התחזית אושרה. אין שדה עמדה באף מקור שנבדק,")
        print("  ואין בחבילה endpoint של סגל או פרופיל שחקן.")
        print("\n  מסקנה: זו לא בעיה של חיפוש - זו תכונה של החבילה.")
        print("  היא דאטת משחקים בלבד. הפריט נסגר כאן ולא נדחה שוב.")
        print("\n  ליום 7, כפריט דאטה: מקור עמדות חיצוני.")
        print("  RealGM · Proballers · גיליונות סגל של המועדונים.")
        print("  דרישה: קוד או שם שניתן להצליב, כיסוי מעל 90%.")
        print("\n  ל-Limitations: אילוץ הסגל ב-PuLP הוא ספירה בלבד")
        print("  (<=16). האופטימייזר יכול להרכיב חמישה סנטרים.")
    else:
        print(f"\n  POSITIONS = AVAILABLE ({len(found)} מקורות)")
        for src, _, col in found:
            print(f"    {src} -> {col}")
        src, df, col = found[0]
        coverage(df, col)
    print("=" * 74)


if __name__ == "__main__":
    main()