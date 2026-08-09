"""
build_team_season.py
--------------------
בונה את טבלת קבוצה-עונה מקבצי accumulated_rs_{season}.csv.

תיקוני יום 2, לפי סדר הגילוי:
  1. SEASONS מורחב ל-2016..2025 — עידן הפורמט המחזורי, ללא 2021
  2. pd.to_numeric עם ספירת אובדן — מונע שרשור מחרוזות ב-sum()
  3. minutes_coverage חד-כיווני במקום minutes_flag עם abs().
     הארכות רק מוסיפות, ולכן רק חוסר מעיד על אובדן.
  4. סינון קבוצה-עונה מתחת ל-COVERAGE_MIN + קובץ ביקורת מלא
  5. הוסרה שורת ה-Ellipsis המיותרת
  6. team_games נלקח מ-standings לכל קבוצה בנפרד, לא max() ברמת הליגה.
     עונה קטועה (2019) או לוח מעוות (2021) מייצרים מספרים שונים
     לקבוצות שונות, ומספר יחיד היה מסתיר את זה.
  7. תקנון z תוך-עונתי. pir_per_round אינו בר-השוואה בין עונות:
     BAS 2025 צברה 92.5 עם win_pct 0.34, OLY 2016 צברה 83.7 עם 0.63.
     16 קבוצות ב-2016 מול 20 ב-2025 מזיזות את כל הפיזור.

מיקום: src/build_team_season.py
"""

import os
import time
import pandas as pd

from paths import RAW_DIR, PROCESSED_DIR
from euroleague_api.standings import Standings

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", None)

# ----------------------------------------------------------------------
# הגדרות
# ----------------------------------------------------------------------
SEASONS = list(range(2016, 2026))    # 2016-17 .. 2025-26
COVID_SEASONS = {2019}               # עונת 2019-20 נקטעה
EXCLUDED_SEASONS = {2021}            # קבוצות רוסיות הוצאו — לוח לא אחיד
MINUTES_PER_GAME = 200               # 5 שחקנים x 40 דקות

# כיסוי דקות מינימלי לקבוצה-עונה.
# מתחתיו, sum_pir מודד סגל חלקי בעוד הניצחונות נצברו עם הסגל המלא.
# חד-כיווני: כיסוי מעל 1.0 = הארכות, תקין.
# הסף נבחר לפני שנבדק אילו קבוצות נופלות בו.
COVERAGE_MIN = 0.00

# עמודות בקובץ השחקנים
TEAM_COL   = "player.team.code"
VAL_COL    = "pir"
MIN_COL    = "minutesPlayed"
PLAYER_COL = "player.code"
GAMES_COL  = "gamesPlayed"

# עמודות ב-standings — שמות מפורשים, אין זיהוי היוריסטי.
# gamesWon ולא winPercentage (זו מחרוזת בפורמט "64.7%").
ST_TEAM_COL  = "club.code"
ST_WINS_COL  = "gamesWon"
ST_GAMES_COL = "gamesPlayed"

REQUIRED_COLS = [TEAM_COL, VAL_COL, MIN_COL, PLAYER_COL, GAMES_COL]
NUMERIC_COLS  = [VAL_COL, MIN_COL, GAMES_COL]


# ----------------------------------------------------------------------
def load_season(season):
    """קורא קובץ עונה, מוודא סכמה, וממיר עמודות מספריות עם ספירת אובדן."""
    path = os.path.join(RAW_DIR, f"accumulated_rs_{season}.csv")
    if not os.path.exists(path):
        print(f"[SKIP] {season}: קובץ חסר -> {path}")
        return None

    df = pd.read_csv(path)

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        print(f"[FAIL] {season}: עמודות חסרות {missing}")
        print(f"       עמודות שכן קיימות: {df.columns.tolist()}")
        return None

    # המרה מספרית מפורשת. בלעדיה, עמודה שחוזרת כמחרוזת גורמת ל-sum()
    # לשרשר טקסט במקום לחבר, והשגיאה תיזרק הרבה במורד הזרם.
    # errors="coerce" לבדו הופך כשל רועש לשקט — ולכן סופרים את האובדן.
    for c in NUMERIC_COLS:
        before = df[c].notna().sum()
        df[c] = pd.to_numeric(df[c], errors="coerce")
        lost = before - df[c].notna().sum()
        if lost:
            print(f"   [WARN] {season}: {lost} ערכים ב-{c} לא המירו למספר")

    return df


def drop_traded_players(df, season):
    """
    שחקן שעבר קבוצה באמצע העונה מקבל קוד משורשר ('OLY;PAR').
    ה-endpoint מחזיר שורה אחת לשחקן לעונה ואינו מפרק את הדקות בין הקבוצות.
    השמטה היא הפחות-שגוי: כל זקיפה תמציא מספר שאינו בדאטה.
    מגבלה ידועה — ראה README/Limitations.
    """
    total_min = df[MIN_COL].sum()
    is_traded = df[TEAM_COL].astype(str).str.contains(";", na=False)

    n_traded   = int(is_traded.sum())
    min_traded = float(df.loc[is_traded, MIN_COL].sum())
    pct        = (min_traded / total_min * 100) if total_min else 0.0

    if n_traded:
        flag = "  <-- מעל 3%, בדוק ידנית" if pct > 3 else ""
        print(f"   traded players: {n_traded} שחקנים | "
              f"{min_traded:,.1f} דקות | {pct:.2f}% מהעונה{flag}")

    return df.loc[~is_traded].copy(), n_traded, pct


def fetch_standings(season, probe_round, verbose_schema=False):
    """
    מחזיר טבלת ליגה עם ניצחונות ומספר משחקים לכל קבוצה בנפרד.
    probe_round משמש רק כפרמטר לשאילתה; המספר האמיתי נקרא מהתשובה.
    """
    try:
        st = Standings().get_standings(season=season, round_number=probe_round)
    except Exception as e:
        print(f"[ERROR] {season}: כשל במשיכת standings -> {e}")
        return None

    if verbose_schema:
        print(f"   [standings schema] {st.columns.tolist()}")

    missing = [c for c in (ST_TEAM_COL, ST_WINS_COL, ST_GAMES_COL) if c not in st.columns]
    if missing:
        print(f"[FAIL] {season}: עמודות חסרות ב-standings {missing}")
        print(f"       עמודות: {st.columns.tolist()}")
        return None

    out = st[[ST_TEAM_COL, ST_WINS_COL, ST_GAMES_COL]].rename(
        columns={ST_TEAM_COL: "team", ST_WINS_COL: "wins", ST_GAMES_COL: "team_games"}
    )
    out["team"]       = out["team"].astype(str).str.strip()
    out["wins"]       = pd.to_numeric(out["wins"], errors="coerce")
    out["team_games"] = pd.to_numeric(out["team_games"], errors="coerce")

    # בדיקת אחידות לוח המשחקים — הבדיקה שפסלה את 2021
    vals = sorted(out["team_games"].dropna().unique().tolist())
    if len(vals) > 1:
        print(f"   [WARN] {season}: לוח לא אחיד — team_games = {vals}")
        print(out.loc[out["team_games"] != max(vals), ["team", "team_games", "wins"]]
                 .to_string(index=False))
    else:
        print(f"   לוח אחיד: {int(vals[0])} משחקים לכל קבוצה")

    return out


def aggregate_teams(df):
    """אגרגציה של סטטיסטיקות שחקנים לרמת קבוצה."""
    return (
        df.groupby(TEAM_COL)
          .agg(sum_pir=(VAL_COL, "sum"),
               total_minutes=(MIN_COL, "sum"),
               n_players=(PLAYER_COL, "nunique"))
          .reset_index()
          .rename(columns={TEAM_COL: "team"})
    )


def zscore_within_season(master, source_col, target_col):
    """
    כמה סטיות תקן הקבוצה מעל/מתחת לממוצע של העונה שלה.
    מנטרל בו-זמנית מספר קבוצות, אורך עונה, וקצב משחק משתנה.
    ddof=0 כי זו אוכלוסייה שלמה — כל קבוצות העונה בטבלה, אין דגימה.
    """
    master[target_col] = (
        master.groupby("season")[source_col]
              .transform(lambda s: (s - s.mean()) / s.std(ddof=0))
    )
    return master


# ----------------------------------------------------------------------
def build():
    print("=" * 74)
    print("BUILD TEAM-SEASON DATASET")
    print(f"seasons={SEASONS[0]}..{SEASONS[-1]} | excluded={sorted(EXCLUDED_SEASONS)} "
          f"| coverage_min={COVERAGE_MIN:.0%}")
    print("=" * 74)

    frames, audit, coverage_log = [], [], []

    for i, season in enumerate(SEASONS):
        if season in EXCLUDED_SEASONS:
            print(f"\n--- Season {season} --- [EXCLUDED] קבוצות רוסיות הוצאו, לוח לא אחיד")
            continue

        print(f"\n--- Season {season} ---")

        df = load_season(season)
        if df is None:
            continue

        df, n_traded, pct_traded = drop_traded_players(df, season)
        team_stats = aggregate_teams(df)

        # probe_round רק כדי לשאול; team_games האמיתי מגיע מהתשובה
        probe_round = int(df[GAMES_COL].max())
        st = fetch_standings(season, probe_round, verbose_schema=(i == 0))
        if st is None:
            continue

        merged = team_stats.merge(st, on="team", how="left")

        n_missing = int(merged["wins"].isna().sum())
        if n_missing:
            lost = merged.loc[merged["wins"].isna(), "team"].tolist()
            print(f"   [WARN] {season}: {n_missing}/{len(merged)} קבוצות בלי התאמה -> {lost}")
            print(f"          קודים ב-standings: {sorted(st['team'].dropna().tolist())}")
            if n_missing == len(merged):
                print(f"   [FAIL] {season}: המיזוג נכשל לגמרי. קודי הקבוצות לא תואמים.")
                continue
        merged = merged.dropna(subset=["wins", "team_games"]).copy()

        # --- נרמול לפי מספר המשחקים של אותה קבוצה ---
        merged["team_games"]       = merged["team_games"].astype(int)
        merged["expected_minutes"] = merged["team_games"] * MINUTES_PER_GAME
        merged["minutes_coverage"] = merged["total_minutes"] / merged["expected_minutes"]
        merged["pir_per_round"]    = merged["sum_pir"] / merged["team_games"]
        merged["win_pct"]          = merged["wins"]    / merged["team_games"]
        merged["season"]           = season
        merged["is_covid_season"]  = int(season in COVID_SEASONS)

        coverage_log.append(merged[["season", "team", "total_minutes", "expected_minutes",
                                    "minutes_coverage", "team_games", "n_players"]].copy())

        # --- סינון כיסוי: כלל כללי, לא רשימה ידנית של קבוצות ---
        below = merged["minutes_coverage"] < COVERAGE_MIN
        if below.any():
            print(f"   [DROP] {int(below.sum())} קבוצות מתחת ל-{COVERAGE_MIN:.0%} כיסוי:")
            print(merged.loc[below, ["team", "total_minutes", "minutes_coverage", "n_players"]]
                        .sort_values("minutes_coverage")
                        .to_string(index=False,
                                   formatters={"minutes_coverage": "{:.1%}".format}))
        final = merged.loc[~below].copy()

        if final.empty:
            print(f"   [FAIL] {season}: כל הקבוצות נפלו בסינון הכיסוי")
            continue

        frames.append(final)
        audit.append({"season": season, "teams": len(final),
                      "games": int(final["team_games"].max()),
                      "traded_players": n_traded, "traded_pct": round(pct_traded, 2),
                      "dropped_coverage": int(below.sum())})
        print(f"   [OK] {len(final)} קבוצות")

        time.sleep(2)

    if not frames:
        print("\n[FAIL] לא נבנתה אף עונה.")
        return

    master = pd.concat(frames, ignore_index=True)
    master = zscore_within_season(master, "pir_per_round", "pir_z")
    master = zscore_within_season(master, "win_pct",       "win_pct_z")

    master = master[["season", "team", "sum_pir", "pir_per_round", "pir_z",
                     "wins", "win_pct", "win_pct_z", "team_games", "n_players",
                     "total_minutes", "expected_minutes", "minutes_coverage",
                     "is_covid_season"]]
    master = master.sort_values(["season", "win_pct"], ascending=[True, False])

    out = os.path.join(PROCESSED_DIR, "team_season.csv")
    master.to_csv(out, index=False)

    cov = pd.concat(coverage_log, ignore_index=True).sort_values("minutes_coverage")
    cov_out = os.path.join(PROCESSED_DIR, "coverage_audit.csv")
    cov.to_csv(cov_out, index=False)

    # ------------------------------------------------------------------
    print("\n" + "=" * 74)
    print("AUDIT")
    print("=" * 74)
    print(pd.DataFrame(audit).to_string(index=False))

    print(f"\n[SUCCESS] {out}  ({len(master)} שורות)")
    print(f"[SUCCESS] {cov_out}  ({len(cov)} שורות, כולל שנפלו)")

    # שפיות התקנון: ממוצע z לכל עונה חייב להיות 0 וסטייה 1
    chk = master.groupby("season")[["pir_z", "win_pct_z"]].agg(["mean", "std"]).round(3)
    print("\n--- בדיקת שפיות: z לכל עונה (mean≈0, std≈1) ---")
    print(chk.to_string())

    print("\n--- 5 החזקות ביותר לפי pir_z, על פני כל התקופה ---")
    print(master.nlargest(5, "pir_z")[
        ["season", "team", "pir_per_round", "pir_z", "win_pct", "win_pct_z"]
    ].to_string(index=False))

    print("\n--- 5 החלשות ביותר ---")
    print(master.nsmallest(5, "pir_z")[
        ["season", "team", "pir_per_round", "pir_z", "win_pct", "win_pct_z"]
    ].to_string(index=False))

    print("\n--- כיסוי דקות: 5 הנמוכים ביותר ---")
    print(cov.head(5).to_string(index=False,
                                formatters={"minutes_coverage": "{:.1%}".format}))


if __name__ == "__main__":
    build()