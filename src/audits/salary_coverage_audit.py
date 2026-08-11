"""
Task 0, Day 4 - salary anchor coverage audit.

Cross-checks published 2025-26 salary anchors against player_season.csv for
Maccabi (TEL) and Hapoel (HTA). Answers three questions:
  1. how many anchors map to a player who actually logged EuroLeague minutes
  2. which rostered players have no anchor  (=> team total understates payroll)
  3. which anchors have no minutes         (=> list covers domestic-league squad)

Raises on failure. Does not print SUCCESS unless every assert passed.
Lesson from Day 3: build_all_seasons.py printed "Failed asserts: 1" and then
[SUCCESS] on the next line, and overwrote a verified dataset.
"""
import sys
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paths import PROCESSED_DIR

MIN_MATCH_RATE = 0.80
CLUB_CODES = {"TEL": "Maccabi Tel Aviv", "HTA": "Hapoel Tel Aviv"}
SEASON = 2025


def load(players_path: Path, anchors_path: Path):
    pl = pd.read_csv(players_path, dtype={"player_code": str})
    an = pd.read_csv(anchors_path, dtype={"player_code": str})
    # player_code formatting is not stable across builds (leading zeros
    # appear in some versions). Normalise both sides before any join.
    for df in (pl, an):
        df["player_code"] = (df.player_code
                             .astype("string")
                             .str.strip()
                             .str.lstrip("0")
                             .replace("", pd.NA))

    pl = pl[pl.season == SEASON].copy()
    pl["clubs"] = pl.team.str.split(";")
    return pl, an


def audit_club(pl: pd.DataFrame, an: pd.DataFrame, club: str) -> dict:
    roster = pl[pl.clubs.apply(lambda x: club in x)]
    anchors = an[an.club == club]

    roster_codes = set(roster.player_code)
    anchor_codes = set(anchors.player_code.dropna())

    matched = roster_codes & anchor_codes
    mins_no_anchor = roster_codes - anchor_codes
    anchor_no_mins = anchors[anchors.player_code.isna()]

    rate = len(matched) / len(anchors) if len(anchors) else 0.0

    print(f"\n{'='*66}\n{club} - {CLUB_CODES[club]}  ({SEASON}-26)\n{'='*66}")
    print(f"roster (played EuroLeague) : {len(roster_codes):>3}")
    print(f"published anchors          : {len(anchors):>3}")
    print(f"matched                    : {len(matched):>3}   ({rate:.1%})")

    if mins_no_anchor:
        print(f"\n-- minutes, no salary anchor ({len(mins_no_anchor)}) --")
        sub = roster[roster.player_code.isin(mins_no_anchor)]
        print(sub[["player_code", "player_name", "games", "min_per_game"]]
              .sort_values("min_per_game", ascending=False).to_string(index=False))

    if len(anchor_no_mins):
        print(f"\n-- salary anchor, no EuroLeague minutes ({len(anchor_no_mins)}) --")
        print(anchor_no_mins[["player_name_he", "salary_usd_mid", "notes"]].to_string(index=False))

    payroll_all = anchors.salary_usd_mid.sum()
    payroll_matched = anchors[anchors.player_code.isin(matched)].salary_usd_mid.sum()
    print(f"\npublished payroll (all anchors)   : ${payroll_all:,.0f}")
    print(f"payroll of EuroLeague-active only : ${payroll_matched:,.0f}"
          f"  ({payroll_matched/payroll_all:.1%})")

    return {"club": club, "rate": rate, "matched": len(matched),
            "anchors": len(anchors), "roster": len(roster_codes),
            "mins_no_anchor": len(mins_no_anchor), "anchor_no_mins": len(anchor_no_mins)}


def measurement_error(an: pd.DataFrame):
    """Task 2 - is the disagreement between sources concentrated at the bottom?"""
    d = an[an.is_range == 1].copy()
    print(f"\n{'='*66}\nSOURCE DISAGREEMENT\n{'='*66}")
    print(f"{len(d)} of {len(an)} anchors differ between the two published lists\n")
    print(d[["player_name_el", "club", "salary_usd_low", "salary_usd_high", "rel_spread"]]
          .sort_values("rel_spread", ascending=False).to_string(index=False))

    an = an.copy()
    an["tier"] = pd.cut(an.salary_usd_mid,
                        [0, 400_000, 800_000, 1_500_000, 10_000_000],
                        labels=["<400k", "400-800k", "800k-1.5M", ">1.5M"])
    g = an.groupby("tier", observed=True).agg(
        n=("salary_usd_mid", "size"),
        n_disagree=("is_range", "sum"),
        mean_rel_spread=("rel_spread", "mean"),
        max_rel_spread=("rel_spread", "max"),
    ).round(4)
    print(f"\n-- relative spread by salary tier --\n{g.to_string()}")


def main():
    players_path = PROCESSED_DIR / "player_season.csv"
    anchors_path = PROCESSED_DIR / "salary_anchors.csv"

    # path guard - fail loudly and say where we looked, not "file not found"
    for pth in (players_path, anchors_path):
        if not pth.exists():
            raise SystemExit(f"missing input: {pth.resolve()}")

    print(f"reading from {PROCESSED_DIR.resolve()}")
    pl, an = load(players_path, anchors_path)

    results = [audit_club(pl, an, c) for c in CLUB_CODES]
    measurement_error(an)

    failed = [r for r in results if r["rate"] < MIN_MATCH_RATE]
    print(f"\n{'='*66}")
    if failed:
        for r in failed:
            print(f"FAIL {r['club']}: match rate {r['rate']:.1%} < {MIN_MATCH_RATE:.0%}")
        raise SystemExit("coverage gate failed - anchors not usable")
    print(f"[OK] all clubs above {MIN_MATCH_RATE:.0%} match gate")



if __name__ == "__main__":
    main()