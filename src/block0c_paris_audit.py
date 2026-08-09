import os, pandas as pd, paths
from build_team_season import TEAM_COL, MIN_COL, PLAYER_COL, GAMES_COL

df = pd.read_csv(os.path.join(paths.RAW_DIR, "accumulated_rs_2025.csv"))
df[MIN_COL] = pd.to_numeric(df[MIN_COL], errors="coerce")
codes = df[TEAM_COL].astype(str)
multi = codes.str.contains(";", na=False)

print(df.loc[multi, [PLAYER_COL, TEAM_COL, MIN_COL, GAMES_COL]]
        .sort_values(MIN_COL, ascending=False).to_string(index=False))

for team in ("PAR", "OLY"):
    drop = multi & codes.str.split(";").apply(lambda p: team in p)
    kept = df.loc[codes.eq(team), MIN_COL].sum()
    print(f"\n{team}: kept {kept:,.0f} | deficit {7600-kept:,.0f} | "
          f"dropped-with-{team} {df.loc[drop, MIN_COL].sum():,.0f} "
          f"({drop.sum()} players) | residual {7600-kept-df.loc[drop, MIN_COL].sum():,.0f}")