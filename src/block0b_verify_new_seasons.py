# src/block0b_verify_new_seasons.py
"""Schema + structure verification for newly fetched seasons 2016, 2025."""
import os
import pandas as pd
import paths

# שמות העמודות מיובאים מהמקור שכבר עובד — לא משוכפלים
from build_team_season import (
    TEAM_COL, VAL_COL, MIN_COL, PLAYER_COL, GAMES_COL, REQUIRED_COLS
)

REF_SEASON = 2024
FILE_FMT   = "accumulated_rs_{}.csv"
EXPECTED   = {2016: (16, 30), 2024: (18, 34), 2025: (20, 38)}  # season: (teams, rounds)


def load(season):
    path = os.path.join(paths.RAW_DIR, FILE_FMT.format(season))
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path}\navailable: {sorted(os.listdir(paths.RAW_DIR))}"
        )
    return pd.read_csv(path)


ref_cols = set(load(REF_SEASON).columns)
print(f"reference {REF_SEASON}: {len(ref_cols)} columns\n")

for season in (2016, 2025):
    df = load(season)
    cols = set(df.columns)
    teams_exp, rounds_exp = EXPECTED[season]

    print(f"{'='*62}\nSEASON {season}\n{'='*62}")

    print(f"[schema] width {len(cols)} vs ref {len(ref_cols)}")
    print(f"[schema] missing vs ref : {sorted(ref_cols - cols) or 'none'}")
    print(f"[schema] extra   vs ref : {sorted(cols - ref_cols) or 'none'}")

    absent = [c for c in REQUIRED_COLS if c not in cols]
    if absent:
        print(f"  !! required columns absent: {absent}")
        print(f"  actual: {sorted(cols)}")
        continue

    # המרה מספרית עם ספירת אובדן — הבדיקה מסעיף 4
    for c in (VAL_COL, MIN_COL, GAMES_COL):
        before = df[c].notna().sum()
        df[c] = pd.to_numeric(df[c], errors="coerce")
        lost = before - df[c].notna().sum()
        print(f"[numeric] {c}: {lost} values failed to convert"
              + ("   <-- INVESTIGATE" if lost else ""))

    codes  = df[TEAM_COL].astype(str)
    multi  = codes.str.contains(";", na=False)
    single = codes[~multi]

    print(f"\n[teams] unique single codes: {single.nunique()}  (expect {teams_exp})")
    print(f"[teams] {sorted(single.unique())}")

    max_gp = df[GAMES_COL].max()
    print(f"\n[rounds] max {GAMES_COL}: {max_gp}  (expect {rounds_exp})")
    if max_gp != rounds_exp:
        print("  !! MISMATCH — schedule irregularity, investigate before aggregating")

    base  = teams_exp * rounds_exp * 200
    total = df[MIN_COL].sum()
    print(f"[minutes] total {total:,.0f} vs base {base:,} "
          f"({100*(total-base)/base:+.2f}%)  [OT only adds; negative = data loss]")

    per_team = df.loc[~multi].groupby(TEAM_COL)[MIN_COL].sum()
    exp_team = rounds_exp * 200
    deficit  = (exp_team - per_team).sort_values(ascending=False)
    print(f"[minutes] per-team expected {exp_team:,}; worst deficits:")
    print(deficit.head(3).to_string())

    print(f"\n[pir] total {df[VAL_COL].sum():,.0f}   players {df[PLAYER_COL].nunique()}")
    print(f"[multi-team] {multi.sum()} rows, {df.loc[multi, MIN_COL].sum():,.0f} min "
          f"({100*df.loc[multi, MIN_COL].sum()/total:.2f}%)\n")