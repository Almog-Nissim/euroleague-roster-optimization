"""
build_team_season.py
--------------------
בונה את טבלת קבוצה-עונה מקבצי accumulated_rs_{season}.csv.

תיקונים מול הגרסה הקודמת:
  1. שמות עמודות קבועים במפורש (אין יותר זיהוי אוטומטי עם [0])
  2. n_rounds נגזר מהדאטה ולא ממיפוי ידני
  3. נרמול: pir_per_round ו-win_pct  <-- אלה משתני הרגרסיה, לא הסכומים
  4. שחקנים שעברו קבוצה מסוננים ומדווחים באחוזים
  5. אזהרה רועשת אם מיזוג הניצחונות מפיל שורות
  6. נתיבים מ-paths.py

מיקום: src/build_team_season.py
הרצה ראשונה: השאר SEASONS = [2022] כדי להשוות מול team_season_2022_final.csv
"""

import os
import time
import pandas as pd

from paths import RAW_DIR, PROCESSED_DIR
from euroleague_api.standings import Standings

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", None)

# ----------------------------------------------------------------------
# הגדרות
# ----------------------------------------------------------------------
SEASONS = list(range(2017, 2025))
COVID_SEASONS = {2019}               # עונת 2019-20 נקטעה
EXCLUDED_SEASONS = {2021}            # קבוצות רוסיות הוצאו באמצע העונה - לוח משחקים לא אחיד
MINUTES_PER_GAME = 200

TEAM_COL   = "player.team.code"
VAL_COL    = "pir"
MIN_COL    = "minutesPlayed"
PLAYER_COL = "player.code"
GAMES_COL  = "gamesPlayed"

REQUIRED_COLS = [TEAM_COL, VAL_COL, MIN_COL, PLAYER_COL, GAMES_COL]


# ----------------------------------------------------------------------
def load_season(season):
    """קורא קובץ עונה ומוודא שהסכמה היא מה שציפינו לה."""
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

    return df


def drop_traded_players(df, season):
    """
    שחקנים שעברו קבוצה מקבלים קוד משורשר ('IST;ZAL') ולא ניתן לפצל
    את הדקות שלהם בין הקבוצות. מסננים ומדווחים אחוז.
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


def aggregate_teams(df, season):
    """אגרגציה לרמת קבוצה + בדיקת שפיות על סך הדקות."""
    team_stats = (
        df.groupby(TEAM_COL)
          .agg(sum_pir=(VAL_COL, "sum"),
               total_minutes=(MIN_COL, "sum"),
               n_players=(PLAYER_COL, "nunique"))
          .reset_index()
          .rename(columns={TEAM_COL: "team"})
    )

    # n_rounds נגזר מהדאטה, לא ממיפוי ידני
    n_rounds = int(df[GAMES_COL].max())
    expected_minutes = n_rounds * MINUTES_PER_GAME

    team_stats["n_rounds"] = n_rounds
    # סטייה מעל 10% = חשוד. הארכות מסבירות סטייה קטנה כלפי מעלה בלבד.
    team_stats["minutes_flag"] = (
        (team_stats["total_minutes"] - expected_minutes).abs() > expected_minutes * 0.10
    )

    n_flagged = int(team_stats["minutes_flag"].sum())
    print(f"   n_rounds={n_rounds} | expected_minutes/team={expected_minutes:,} | "
          f"teams={len(team_stats)} | flagged={n_flagged}")
    if n_flagged:
        print(team_stats.loc[team_stats["minutes_flag"],
                             ["team", "total_minutes", "n_players"]].to_string(index=False))

    return team_stats, n_rounds


def attach_wins(team_stats, season, n_rounds, verbose_schema=False):
    """מצרף ניצחונות מטבלת הליגה. מתריע רועשות אם המיזוג מפיל שורות."""
    try:
        st = Standings().get_standings(season=season, round_number=n_rounds)
    except Exception as e:
        print(f"[ERROR] {season}: כשל במשיכת standings -> {e}")
        return None
    if verbose_schema:
        print(f"   [standings schema] {st.columns.tolist()}")

        # שמות קבועים במפורש - אין זיהוי אוטומטי.
        # club.code מקביל ל-player.team.code בצד הסטטיסטיקות.
        # gamesWon ולא winPercentage (זו מחרוזת בפורמט "64.7%").
    ST_TEAM_COL = "club.code"
    ST_WINS_COL = "gamesWon"

    missing = [c for c in (ST_TEAM_COL, ST_WINS_COL) if c not in st.columns]
    if missing:
        print(f"[FAIL] {season}: עמודות חסרות ב-standings {missing}")
        print(f"       עמודות: {st.columns.tolist()}")
        return None

    wins = st[[ST_TEAM_COL, ST_WINS_COL]].rename(
        columns={ST_TEAM_COL: "team", ST_WINS_COL: "wins"}
    )
    wins["wins"] = pd.to_numeric(wins["wins"], errors="coerce")
    wins["team"] = wins["team"].astype(str).str.strip()
    team_stats["team"] = team_stats["team"].astype(str).str.strip()

    # אימות צולב: אורך העונה לפי standings מול מה שנגזר מהסטטיסטיקות
    if "gamesPlayed" in st.columns:
        gp = pd.to_numeric(st["gamesPlayed"], errors="coerce").max()
        if pd.notna(gp) and int(gp) != n_rounds:
            print(f"   [WARN] {season}: n_rounds={n_rounds} מהסטטיסטיקות "
                  f"אבל {int(gp)} ב-standings")

    merged = team_stats.merge(wins, on="team", how="left")

    n_missing = int(merged["wins"].isna().sum())
    if n_missing:
        lost = merged.loc[merged["wins"].isna(), "team"].tolist()
        print(f"   [WARN] {season}: {n_missing}/{len(merged)} קבוצות בלי ניצחונות -> {lost}")
        print(f"          קודים ב-standings: {sorted(wins['team'].dropna().unique().tolist())}")
        if n_missing == len(merged):
            print(f"   [FAIL] {season}: המיזוג נכשל לגמרי. קודי הקבוצות לא תואמים.")
            return None

    return merged.dropna(subset=["wins"]).copy()

# ----------------------------------------------------------------------
def build():
    print("=" * 70)
    print("BUILD TEAM-SEASON DATASET")
    print("=" * 70)

    frames, audit = [], []
    for i, season in enumerate(SEASONS):
        if season in EXCLUDED_SEASONS:
            print(f"\n--- Season {season} --- [EXCLUDED] קבוצות רוסיות הוצאו, לוח לא אחיד")
            continue

        print(f"\n--- Season {season} ---")
        ...

        df = load_season(season)
        if df is None:
            continue

        df, n_traded, pct_traded = drop_traded_players(df, season)
        team_stats, n_rounds = aggregate_teams(df, season)

        final = attach_wins(team_stats, season, n_rounds, verbose_schema=(i == 0))
        if final is None:
            continue

        # --- נרמול: אלה משתני הרגרסיה, לא הסכומים הגולמיים ---
        final["pir_per_round"] = final["sum_pir"] / final["n_rounds"]
        final["win_pct"]       = final["wins"]    / final["n_rounds"]

        final["season"]          = season
        final["is_covid_season"] = int(season in COVID_SEASONS)

        frames.append(final)
        audit.append({"season": season, "teams": len(final), "n_rounds": n_rounds,
                      "traded_players": n_traded, "traded_pct": round(pct_traded, 2)})
        print(f"   [OK] {len(final)} קבוצות")

        if len(SEASONS) > 1:
            time.sleep(2)

    if not frames:
        print("\n[FAIL] לא נבנתה אף עונה.")
        return

    master = pd.concat(frames, ignore_index=True)
    master = master[["season", "team", "sum_pir", "pir_per_round",
                     "wins", "win_pct", "n_rounds", "n_players",
                     "total_minutes", "is_covid_season",
                     "minutes_flag"]]
    master = master.sort_values(["season", "win_pct"], ascending=[True, False])

    out = os.path.join(PROCESSED_DIR, "team_season.csv")
    master.to_csv(out, index=False)

    print("\n" + "=" * 70)
    print("AUDIT")
    print("=" * 70)
    print(pd.DataFrame(audit).to_string(index=False))

    print(f"\n[SUCCESS] נשמר: {out}  ({len(master)} שורות)")
    print("\n--- TOP 5 ---")
    print(master.head(5).to_string(index=False))
    print("\n--- BOTTOM 5 ---")
    print(master.tail(5).to_string(index=False))


if __name__ == "__main__":
    build()