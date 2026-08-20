"""
team_games.py — המכנה האמיתי של מודל הזמינות, לכל מועדון-עונה.

למה זה קיים
-----------
זמינות = `משחקים / משחקים_אפשריים`. המכנה נראה כמו קבוע והוא לא:

  · 2016-2017 — 30 מחזורי RS (16 קבוצות)
  · 2019-2024 — 34 מחזורים (18 קבוצות)
  · 2025      — 38 מחזורים (20 קבוצות)
  · 2019      — נעצרה אחרי 28. **כל המועדונים באותה מידה**
  · 2021      — 28 משחקים בוטלו. **מועדונים ספציפיים**

ההבדל בין שתי השורות האחרונות הוא כל העניין. ב-2019 המכנה יורד
לכולם — הטיה ברמה, שלא משנה דירוג. ב-2021 הוא יורד למועדונים
מסוימים בלבד, ולכן שתי תצפיות באותה עונה נמדדות על בסיסים שונים.
זו אותה משפחה של "שני צדי ההשוואה חייבים לתאר את אותם אנשים".

מה שנבנה
--------
`data/processed/team_season_games.csv` — לכל (עונה, מועדון):
משחקים ששוחקו לפי Phase, ומספר המחזורים שנקבעו לו בפועל.

⚠️ הגדרת "שוחק": `Played == 'result'`. זה **לא** ניחוש — סעיף D
ב-index_audit הראה הפרדה מלאה מול הבוקסקורים (כל result נמצא,
אף suspended לא). הסקריפט מאמת את זה שוב בכל הרצה, ועוצר אם
ההפרדה נשברה.

הרצה:  python src/team_games.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import find_boxscores, repo_root, resolve  # noqa: E402

PLAYED_VALUE = "result"
RS_LABELS = {"RS", "REGULARSEASON", "REGULAR"}
OUT_REL = "data/processed/team_season_games.csv"


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def verify_played_definition(idx: pd.DataFrame, root) -> bool:
    """
    לא מניחים ש-'result' == שוחק. מאמתים מול הבוקסקורים בכל הרצה.
    """
    hdr("אימות ההגדרה: Played == 'result' פירושו שוחק")

    files = find_boxscores(root, verbose=False)
    seasons = [s for s in sorted(idx["Season"].unique()) if int(s) in files]
    if not seasons:
        print("  ⚠️ אין בוקסקורים להשוואה — ההגדרה לא אומתה.")
        return False

    played_flag = idx["Played"].astype(str).str.lower().str.strip() == PLAYED_VALUE
    bad = 0
    for season in seasons:
        bx = pd.read_csv(files[int(season)], dtype={"Gamecode": str}, low_memory=False)
        codes = set(bx["Gamecode"].astype(str).str.strip())
        sub = idx[idx["Season"] == season]
        in_bx = sub["Gamecode"].isin(codes)
        flag = played_flag.loc[sub.index]
        mism = int((in_bx != flag).sum())
        bad += mism
        print(f"  {season}: {mism} אי-התאמות מתוך {len(sub)}")

    if bad == 0:
        print("\n  ✅ ההפרדה מלאה. מותר להשתמש בשדה גם לעונות בלי בוקסקור.")
        return True
    print(f"\n  🔴 {bad} אי-התאמות — ההגדרה נשברה. אל תסמוך על השדה.")
    return False


def build(idx: pd.DataFrame) -> pd.DataFrame:
    played = idx[idx["Played"].astype(str).str.lower().str.strip() == PLAYED_VALUE].copy()

    long = pd.concat([
        played.assign(Team=played["HomeTeam"]),
        played.assign(Team=played["AwayTeam"]),
    ], ignore_index=True)
    long = long[long["Team"].notna()]

    long["PhaseNorm"] = (long["Phase"].astype(str).str.upper()
                         .str.replace(r"[^A-Z]", "", regex=True))
    long["is_rs"] = long["PhaseNorm"].isin(RS_LABELS)

    out = (long.groupby(["Season", "Team"])
               .agg(games_played=("Gamecode", "nunique"),
                    games_rs=("is_rs", "sum"))
               .reset_index())
    out["games_playoff"] = out["games_played"] - out["games_rs"]

    # כמה משחקי RS *נקבעו* לאותו מועדון, כולל אלה שלא שוחקו
    sched = pd.concat([idx.assign(Team=idx["HomeTeam"]),
                       idx.assign(Team=idx["AwayTeam"])], ignore_index=True)
    sched = sched[sched["Team"].notna()]
    sched["PhaseNorm"] = (sched["Phase"].astype(str).str.upper()
                          .str.replace(r"[^A-Z]", "", regex=True))
    sched_rs = (sched[sched["PhaseNorm"].isin(RS_LABELS)]
                .groupby(["Season", "Team"])["Gamecode"].nunique()
                .rename("rs_scheduled").reset_index())

    out = out.merge(sched_rs, on=["Season", "Team"], how="left")
    out["rs_missing"] = out["rs_scheduled"] - out["games_rs"]
    return out.sort_values(["Season", "Team"]).reset_index(drop=True)


def check_per_team_total(tab: pd.DataFrame, idx: pd.DataFrame) -> list[str]:
    """
    בדיקה נגזרת: בליגה של T קבוצות עם סבב כפול, כל מועדון משחק
    בדיוק `2·(T−1)` משחקי RS. 16 -> 30 · 18 -> 34 · 20 -> 38.

    נוספה אחרי ש-`AwayTeam` יצא ריק ב-index וכל מועדון נספר רק
    במשחקי הבית שלו. כל המספרים יצאו חצי, והטבלה נראתה סבירה.
    הבדיקה הזו הייתה צועקת על 15 מול 30 בשורה הראשונה.
    """
    problems = []
    print("\n" + "=" * 74)
    print("בדיקה נגזרת: משחקי RS שנקבעו לכל מועדון = 2·(T−1)")
    print("=" * 74)

    for season in sorted(tab["Season"].unique()):
        sub = idx[idx["Season"] == season]
        teams = pd.unique(pd.concat([sub["HomeTeam"], sub["AwayTeam"]]).dropna().astype(str))
        n_teams = len(teams)
        expected = 2 * (n_teams - 1)
        observed = tab.loc[tab["Season"] == season, "rs_scheduled"]
        mx = int(observed.max()) if len(observed) else 0
        ok = mx == expected
        print(f"  {season}: {n_teams} קבוצות · צפוי {expected} · נצפה מקס {mx}  "
              f"{'✅' if ok else '🔴'}")
        if not ok:
            problems.append(f"{season}: מקס {mx} מול {expected} הצפויים"
                            + (" — נספר צד אחד בלבד?" if mx * 2 == expected else ""))
    return problems


def report(tab: pd.DataFrame) -> None:
    hdr("משחקי RS ששוחקו — לפי עונה")
    summary = (tab.groupby("Season")["games_rs"]
                 .agg(["count", "min", "max", "mean"])
                 .rename(columns={"count": "מועדונים", "min": "מינ'",
                                  "max": "מקס", "mean": "ממוצע"}))
    summary["ממוצע"] = summary["ממוצע"].round(1)
    summary["אחיד?"] = ["✅" if a == b else "🔴"
                        for a, b in zip(summary["מינ'"], summary["מקס"])]
    print(summary.to_string())

    uneven = summary[summary["מינ'"] != summary["מקס"]]
    if not len(uneven):
        print("\n  ✅ בכל עונה כל המועדונים שיחקו אותו מספר משחקי RS.")
        return

    print("\n" + "=" * 74)
    print("🔴 עונות שבהן המכנה שונה בין מועדונים")
    print("=" * 74)
    print("  משמעות: שתי תצפיות באותה עונה נמדדות על בסיסים שונים.")
    print("  זו הטיה שמשתנה בין קבוצות, לא הטיה ברמה.\n")

    for season in uneven.index:
        sub = tab[(tab["Season"] == season) & (tab["rs_missing"] > 0)]
        print(f"  --- {season} ---")
        if len(sub):
            print(sub[["Team", "games_rs", "rs_scheduled", "rs_missing"]]
                  .sort_values("rs_missing", ascending=False)
                  .to_string(index=False))
        print()

    print("  פעולה: avaliabillity_model.py חייב לקחת את המכנה מהטבלה")
    print("  הזו לפי (עונה, מועדון), ולא מקבוע או ממקסימום עונתי.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--index", default="data/processed/game_index.csv")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")
    path = resolve(args.index)
    if not path.exists():
        raise SystemExit(f"🔴 לא נמצא {path}. הרץ game_index.py קודם.")

    idx = pd.read_csv(path, dtype={"Gamecode": str}, low_memory=False)
    idx["Gamecode"] = idx["Gamecode"].astype(str).str.strip()
    print(f"נטען: {path}  ({len(idx):,} שורות)")

    verified = verify_played_definition(idx, args.root)

    tab = build(idx)
    structural = check_per_team_total(tab, idx)
    if structural:
        print("\n🔴 הספירה לכל מועדון אינה עקבית עם מבנה הליגה:")
        for p in structural:
            print(f"   · {p}")
        print("\n  הטבלה **לא נשמרה**. בדוק את HomeTeam/AwayTeam ב-game_index.csv")
        print("  והרץ את game_index.py מחדש.")
        return 2

    report(tab)

    out = resolve(OUT_REL)
    out.parent.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out, index=False)
    print(f"\n✅ נשמר: {out}  ({len(tab)} שורות מועדון-עונה)")

    if not verified:
        print("\n⚠️ ההגדרה של 'שוחק' לא אומתה מול הבוקסקורים. הטבלה חשודה.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())