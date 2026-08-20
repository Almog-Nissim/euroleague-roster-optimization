"""
index_audit.py — אילו משחקים באמת שוחקו, לפי אמת קרקע ולא לפי שדה.

למה זה קיים
-----------
`report_played` הקודם הדפיס "0 משוחקים" בכל עונה. זה שגוי — 2022
עברה אימות מול הבוקסקור ב-100%, כלומר כל 328 המשחקים שוחקו. הסיבה:
קידדתי רשימת ערכי-אמת (TRUE / PLAYED / FINAL) והשדה בפיד מכיל
ערך אחר. **ניחוש רביעי ברצף** אחרי שם הקובץ, תיקיית העבודה
וטווחי המשחקים.

הפתרון אינו לנחש טוב יותר. הסמנטיקה של `Played` אינה ידועה לנו,
אבל דבר אחד כן ידוע: **אם משחק מופיע בקובץ הבוקסקור, הוא שוחק.**
זו אמת קרקע שכבר בידינו.

ולמה זה משנה: הבדיקה המבנית (RS = T·(T−1)) **עברה** על 2019, כי
הלוח המתוכנן היה מלא — 18×17=306. רק הצלבה מול מה ששוחק בפועל
תחשוף שהעונה נעצרה אחרי 28 מחזורים.

מה שנבדק
--------
A. מה בכלל יש בשדה Played — ערכים, בלי פרשנות
B. index מול בוקסקור לכל עונה: הצטלבות, יתומים משני הצדדים
C. המחזור האחרון ששוחק — המכנה של מודל הזמינות
D. הצלבה: Played מול נוכחות בבוקסקור

הרצה:  python src/index_audit.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import find_boxscores, repo_root, resolve  # noqa: E402


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def load_index(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"🔴 לא נמצא {path}. הרץ game_index.py קודם.")
    idx = pd.read_csv(path, dtype={"Gamecode": str}, low_memory=False)
    idx["Gamecode"] = idx["Gamecode"].astype(str).str.strip()
    print(f"נטען: {path}  ({len(idx):,} שורות)")
    return idx


# ---------------------------------------------------------------- A
def describe_played(idx: pd.DataFrame) -> None:
    hdr("A. מה יש בשדה Played — ערכים בלבד, בלי פרשנות")

    if "Played" not in idx.columns:
        print("  אין עמודה Played.")
        return

    print(f"  ריקים: {int(idx['Played'].isna().sum()):,} מתוך {len(idx):,}")
    print(f"  טיפוס: {idx['Played'].dtype}")
    print("\n  ערכים ייחודיים:")
    print(idx["Played"].astype(str).value_counts(dropna=False).head(15).to_string())

    print("\n  לפי עונה:")
    print(pd.crosstab(idx["Season"], idx["Played"].astype(str)).to_string())

    if "Date" in idx.columns:
        d = pd.to_datetime(idx["Date"], errors="coerce", utc=True)
        print(f"\n  טווח תאריכים: {d.min()} .. {d.max()}")
        print(f"  תאריכים שלא נפרסרו: {int(d.isna().sum()):,}")


# ---------------------------------------------------------------- B
def crosscheck(idx: pd.DataFrame, root) -> pd.DataFrame:
    hdr("B. index מול בוקסקור — אמת הקרקע")

    files = find_boxscores(root, verbose=False)
    rows = []
    detail = {}

    for season in sorted(idx["Season"].unique()):
        season = int(season)
        idx_codes = set(idx.loc[idx["Season"] == season, "Gamecode"])

        if season not in files:
            rows.append({"Season": season, "index": len(idx_codes), "boxscore": None,
                         "משותפים": None, "רק ב-index": None, "רק בבוקסקור": None})
            continue

        bx = pd.read_csv(files[season], dtype={"Gamecode": str}, low_memory=False)
        bx_codes = set(bx["Gamecode"].astype(str).str.strip())

        both = idx_codes & bx_codes
        only_idx = idx_codes - bx_codes
        only_bx = bx_codes - idx_codes
        detail[season] = only_idx

        rows.append({"Season": season, "index": len(idx_codes), "boxscore": len(bx_codes),
                     "משותפים": len(both), "רק ב-index": len(only_idx),
                     "רק בבוקסקור": len(only_bx)})

    tab = pd.DataFrame(rows).set_index("Season")
    print(tab.to_string())

    print("\n  קריאה:")
    print("   · 'רק ב-index'    = מתוכנן ולא שוחק (או משיכה חלקית)")
    print("   · 'רק בבוקסקור'   = 🔴 חמור — משחק שאינו בלוח")
    print("   · boxscore ריק    = הקובץ עדיין לא נמשך")

    bad = tab[tab["רק בבוקסקור"].fillna(0) > 0]
    if len(bad):
        print(f"\n  🔴 {len(bad)} עונות עם משחקים שאינם בלוח — בדוק לפני שממשיכים.")

    for season, codes in detail.items():
        if not codes:
            continue
        sub = idx[(idx["Season"] == season) & (idx["Gamecode"].isin(codes))]
        print(f"\n  --- {season}: {len(codes)} משחקים ב-index בלבד ---")
        print("  לפי Phase:")
        print("   " + sub["Phase"].value_counts().to_string().replace("\n", "\n   "))
        rounds = pd.to_numeric(sub["Round"], errors="coerce").dropna()
        if len(rounds):
            print(f"  מחזורים: {int(rounds.min())} .. {int(rounds.max())}")
        if "Date" in sub.columns:
            d = pd.to_datetime(sub["Date"], errors="coerce", utc=True)
            if d.notna().any():
                print(f"  תאריכים: {d.min().date()} .. {d.max().date()}")

    return tab


# ---------------------------------------------------------------- C
def availability_denominator(idx: pd.DataFrame, root) -> None:
    hdr("C. המכנה של מודל הזמינות")
    print("  זמינות = משחקים / משחקים_אפשריים. אם המכנה נלקח כעונה")
    print("  מלאה בעונה שנקטעה, הזמינות מוערכת בחסר לכל שחקן.\n")

    files = find_boxscores(root, verbose=False)
    rows = []

    for season in sorted(idx["Season"].unique()):
        season = int(season)
        sub = idx[idx["Season"] == season]
        phase = sub["Phase"].astype(str).str.upper().str.replace(r"[^A-Z]", "", regex=True)
        rs = sub[phase.isin({"RS", "REGULARSEASON", "REGULAR"})]
        planned_rounds = pd.to_numeric(rs["Round"], errors="coerce").max()

        played_rounds, teams = None, None
        if season in files:
            bx = pd.read_csv(files[season], dtype={"Gamecode": str}, low_memory=False)
            bx_codes = set(bx["Gamecode"].astype(str).str.strip())
            rs_played = rs[rs["Gamecode"].isin(bx_codes)]
            played_rounds = pd.to_numeric(rs_played["Round"], errors="coerce").max()
            teams = len(pd.unique(pd.concat([rs["HomeTeam"], rs["AwayTeam"]]).dropna()))

        rows.append({"Season": season, "קבוצות": teams,
                     "מחזורים מתוכננים": planned_rounds,
                     "מחזורים ששוחקו": played_rounds})

    tab = pd.DataFrame(rows).set_index("Season")
    print(tab.to_string())

    cut = tab[(tab["מחזורים ששוחקו"].notna())
              & (tab["מחזורים ששוחקו"] < tab["מחזורים מתוכננים"])]
    if len(cut):
        print("\n  🔴 עונות שנקטעו:")
        for season, row in cut.iterrows():
            p, a = row["מחזורים מתוכננים"], row["מחזורים ששוחקו"]
            print(f"     {season}: {int(a)} מתוך {int(p)} — הטיה של {1 - a / p:.1%} במכנה")
        print("\n  פעולה: לאתר מאיפה avaliabillity_model.py לוקח את המכנה.")
    else:
        print("\n  ✅ אין עונה שנקטעה בין אלה שיש להן בוקסקור.")


# ---------------------------------------------------------------- D
def played_vs_truth(idx: pd.DataFrame, root) -> None:
    hdr("D. הצלבה: השדה Played מול נוכחות בבוקסקור")
    print("  אם יש התאמה מלאה, מותר להשתמש בשדה. אחרת — הבוקסקור קובע.\n")

    if "Played" not in idx.columns:
        print("  אין עמודה Played.")
        return

    files = find_boxscores(root, verbose=False)
    seasons = [s for s in sorted(idx["Season"].unique()) if int(s) in files]
    if not seasons:
        print("  אין עונות עם בוקסקור להשוואה.")
        return

    frames = []
    for season in seasons:
        bx = pd.read_csv(files[int(season)], dtype={"Gamecode": str}, low_memory=False)
        bx_codes = set(bx["Gamecode"].astype(str).str.strip())
        sub = idx[idx["Season"] == season].copy()
        sub["in_boxscore"] = sub["Gamecode"].isin(bx_codes)
        frames.append(sub)

    allsub = pd.concat(frames, ignore_index=True)
    print(pd.crosstab(allsub["Played"].astype(str), allsub["in_boxscore"]).to_string())
    print("\n  אם עמודה אחת ריקה לגמרי — השדה קבוע ואינו נושא מידע.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--index", default="data/processed/game_index.csv")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")
    idx = load_index(resolve(args.index))

    describe_played(idx)
    crosscheck(idx, args.root)
    availability_denominator(idx, args.root)
    played_vs_truth(idx, args.root)

    hdr("סיכום")
    print("  אמת הקרקע היא הבוקסקור. השדה Played נבדק, לא מונח.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())