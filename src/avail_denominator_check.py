"""
avail_denominator_check.py — מה בדיוק המכנה של הזמינות, וכמה הוא מטה.

הרקע
----
`avaliabillity_model.py`:  frac(i,t) = games(i,t) / max_games(t)

המכנה ברמת **עונה**, לא ברמת **מועדון**. הנזק תלוי בשאלה אחת:

  תרחיש A — player_season הוא עונה סדירה בלבד
    max_games(t) = 30 / 34 / 38. נכון לרוב העונות.
    2019 נכונה גם היא (כולם שיחקו 28, והמקסימום נגזר מהדאטה).
    🔴 שבורה רק 2021: שחקני DYR/CSK/UNK יכלו לשחק 23-25
       ומקבלים מכנה 34. זמינות מושלמת = 0.68.

  תרחיש B — הדאטה כולל פלייאוף
    max_games(t) נקבע לפי קבוצת הפיינל-פור, ~41.
    🔴 **כל** העונות. שחקן בקבוצה שלא העפילה מקבל <=0.83
       בזמינות מושלמת. המכנה מתואם עם איכות הקבוצה —
       הזמינות מודדת הצלחה קבוצתית ולא בריאות.

ההכרעה בין A ל-B: האם המקסימום הנצפה עולה על אורך העונה הסדירה.

בשני התרחישים המכנה הנכון הוא **המשחקים שהקבוצה שיחקה בפועל**,
מתוך `team_season_games.csv`.

⚠️ הסתייגות שנשארת גם אחרי התיקון: שחקן שהצטרף באמצע עונה יכול
היה לשחק פחות משחקים מהקבוצה שלו. המכנה ברמת מועדון-עונה מטפל
בהסרות ובביטולים, לא בעיתוי חתימה.

הרצה:  python src/avail_denominator_check.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import repo_root, resolve  # noqa: E402


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def find_col(df: pd.DataFrame, *candidates: str):
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player-season", default="data/processed/player_season.csv")
    ap.add_argument("--team-games", default="data/processed/team_season_games.csv")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")

    ps_path, tg_path = resolve(args.player_season), resolve(args.team_games)
    if not ps_path.exists():
        raise SystemExit(f"🔴 לא נמצא {ps_path}")
    if not tg_path.exists():
        raise SystemExit(f"🔴 לא נמצא {tg_path}. הרץ team_games.py קודם.")

    ps = pd.read_csv(ps_path, low_memory=False)
    tg = pd.read_csv(tg_path, low_memory=False)
    print(f"נטען: {ps_path.name} ({len(ps):,}) · {tg_path.name} ({len(tg):,})")

    season_col = find_col(ps, "Season", "season")
    games_col = find_col(ps, "games", "games_played", "n_games", "GamesPlayed")
    team_col = find_col(ps, "Team", "team", "club", "Club", "team_code")

    print(f"\nעמודות שזוהו: עונה={season_col} · משחקים={games_col} · מועדון={team_col}")
    if season_col is None or games_col is None:
        print(f"🔴 לא זוהו עמודות חובה. עמודות בקובץ: {list(ps.columns)}")
        return 1

    # ---------------------------------------------------------- A/B
    hdr("A. תרחיש A או B — האם הדאטה כולל פלייאוף")

    obs = ps.groupby(season_col)[games_col].max().rename("מקס נצפה")
    rs_len = tg.groupby("Season")["rs_scheduled"].max().rename("אורך RS")
    all_len = tg.groupby("Season")["games_played"].max().rename("מקס כולל פלייאוף")

    cmp = pd.concat([obs, rs_len, all_len], axis=1)
    cmp["עודף מעל RS"] = cmp["מקס נצפה"] - cmp["אורך RS"]
    print(cmp.to_string())

    over = cmp["עודף מעל RS"].fillna(0)
    playoffs_included = bool((over > 1).any())

    if playoffs_included:
        print("\n  🔴 תרחיש B — הדאטה כולל פלייאוף.")
        print("     max_games(t) נקבע לפי הקבוצה שהעמיקה הכי הרבה.")
        print("     המכנה מתואם עם איכות הקבוצה בכל העונות.")
    else:
        print("\n  ✅ תרחיש A — עונה סדירה בלבד.")
        print("     max_games(t) שווה לאורך העונה. שבורה בעיקר 2021.")

    # ---------------------------------------------------------- B
    hdr("B. כמה זה מטה — מכנה עונתי מול מכנה מועדוני")

    if team_col is None:
        print("  ⚠️ אין עמודת מועדון ב-player_season. אי אפשר לכמת.")
        print(f"     עמודות: {list(ps.columns)}")
        print("     חלופה: player_club_season.csv")
        return 0

    denom_col = "games_played" if playoffs_included else "games_rs"
    print(f"  המכנה המועדוני שנבחר: {denom_col}\n")

    merged = ps.merge(
        tg.rename(columns={"Season": season_col, "Team": team_col})[[season_col, team_col, denom_col]],
        on=[season_col, team_col], how="left",
    )
    unmatched = int(merged[denom_col].isna().sum())
    if unmatched:
        print(f"  ⚠️ {unmatched:,}/{len(merged):,} שורות לא הותאמו למועדון-עונה.")
        print("     כנראה קודי מועדון שונים בין הקבצים — בדוק לפני שממשיכים.")
        bad = merged[merged[denom_col].isna()][team_col].dropna().unique()[:10]
        print(f"     קודים לדוגמה: {list(bad)}")

    merged["max_season"] = merged.groupby(season_col)[games_col].transform("max")
    ok = merged[denom_col].notna() & (merged[denom_col] > 0) & (merged["max_season"] > 0)
    m = merged[ok].copy()
    if not len(m):
        print("  🔴 אין שורות תקינות להשוואה.")
        return 1

    m["frac_now"] = m[games_col] / m["max_season"]
    m["frac_fixed"] = (m[games_col] / m[denom_col]).clip(upper=1.0)
    m["delta"] = m["frac_fixed"] - m["frac_now"]

    print(f"  זמינות נוכחית : ממוצע {m['frac_now'].mean():.4f}")
    print(f"  זמינות מתוקנת : ממוצע {m['frac_fixed'].mean():.4f}")
    print(f"  שינוי ממוצע   : {m['delta'].mean():+.4f}")
    print(f"  שינוי מקסימלי : {m['delta'].max():+.4f}")
    print(f"  שורות שזזו >0.05: {int((m['delta'].abs() > 0.05).sum()):,} מתוך {len(m):,}")

    print("\n  לפי עונה:")
    tab = m.groupby(season_col).agg(
        n=("delta", "size"), שינוי_ממוצע=("delta", "mean"), שינוי_מקס=("delta", "max"))
    print(tab.round(4).to_string())

    print("\n  עשרת המועדונים שהושפעו יותר מכל:")
    by_team = (m.groupby([season_col, team_col])["delta"].mean()
                 .sort_values(ascending=False).head(10))
    print(by_team.round(4).to_string())

    # ---------------------------------------------------------- C
    hdr("C. האם ההטיה מתואמת עם איכות הקבוצה")
    print("  אם כן, הזמינות מודדת בין השאר הצלחה קבוצתית ולא בריאות.\n")

    team_level = m.groupby([season_col, team_col]).agg(
        delta=("delta", "mean"), team_games=(denom_col, "first")).reset_index()
    if team_level["team_games"].nunique() > 1:
        r = team_level["delta"].corr(team_level["team_games"])
        print(f"  corr(תיקון , משחקי הקבוצה) = {r:+.3f}   n={len(team_level)}")
        if abs(r) > 0.3:
            print("\n  🔴 מתואם. המכנה הנוכחי נושא מידע על הקבוצה, לא על השחקן.")
        else:
            print("\n  ✅ מתאם חלש.")
    else:
        print("  כל הקבוצות שיחקו אותו מספר משחקים — אין מה לתאם.")

    hdr("מה לשנות")
    print("  frac(i,t) = games(i,t) / games_of_team(i,t)")
    print(f"  המכנה מ-team_season_games.csv, עמודה {denom_col}, לפי (עונה, מועדון).")
    print("\n  ⚠️ נשאר פתוח: שחקן שהצטרף באמצע עונה. המכנה המועדוני מטפל")
    print("     בהסרות ובביטולים, לא בעיתוי חתימה.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())