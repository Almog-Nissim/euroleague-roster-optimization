"""
id_seam.py — התפר בין הבוקסקורים ל-player_season, ברמת השחקן.

מה שהשער הראה
-------------
  as-is                       0 חפיפה  (0.0%)
  digits, no leading zeros  963 חפיפה  (89.6%)

`player_season` שומר קוד מספרי, הבוקסקור שומר `P` ואחריו תווים.
הם לא נפגשים גולמית. והנרמול ה"מנצח" הופך את `PAAX` ו-`PABN`
למחרוזת **ריקה** — 8.7% מהשורות מתמוטטות למפתח אחד.

1,157 מזהים בבוקסקור · 1,045 ב-player_season · 963 נפגשים.
**194 לא נמצאים.**

זו אותה משפחה של הבאג מיום 9: `lstrip('P')` שהשאיר `'012099'`,
"חפיפה 6 במקום 263, פעם חמישית".

מה שהסקריפט קובע
----------------
האם 194 השחקנים חסרים מ-`player_season`, או יושבים שם תחת קוד
אחר. יש שם מלא בשני הצדדים, אז זה ניתן להכרעה.

⚠️ התאמת שם היא **אבחון**, לא פתרון. אם היא מצליחה, המסקנה היא
שצריך טבלת מיפוי מפורשת — לא להטמיע התאמת שם בצינור.

הרצה:  python src/id_seam.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import load_boxscores, repo_root, resolve  # noqa: E402
from verify_boxscores import parse_minutes  # noqa: E402

OUT_REL = "data/processed/id_seam_unmatched.csv"


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def norm_num(s: pd.Series) -> pd.Series:
    """ספרות בלבד, בלי אפסים מובילים. מחזיר '' למזהה אלפאנומרי."""
    return s.astype(str).str.replace(r"\D", "", regex=True).str.lstrip("0")


def norm_name(s: pd.Series) -> pd.Series:
    """'LAZIC, BRANKO' -> 'LAZIC BRANKO'. סדר המילים לא משתנה."""
    return (s.astype(str).str.upper().str.strip()
            .str.replace(r"[^A-Z ]", " ", regex=True)
            .str.replace(r"\s+", " ", regex=True).str.strip())


def find_col(df: pd.DataFrame, *cands):
    lower = {c.lower(): c for c in df.columns}
    for c in cands:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--player-season", default="data/processed/player_season.csv")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")

    bx = load_boxscores(args.root, verbose=False)
    pid = bx["Player_ID"].astype(str).str.strip()
    bx = bx[~pid.str.upper().isin(["TEAM", "TOTAL", "NAN", ""])].copy()
    bx["Player_ID"] = bx["Player_ID"].astype(str).str.strip()
    bx["min_num"] = bx["Minutes"].apply(parse_minutes)

    players = (bx.groupby("Player_ID")
                 .agg(name=("Player", "first"),
                      minutes=("min_num", "sum"),
                      rows=("Player_ID", "size"),
                      seasons=("Season", "nunique"),
                      first_season=("Season", "min"),
                      last_season=("Season", "max"))
                 .reset_index())
    total_minutes = players["minutes"].sum()
    print(f"בוקסקור: {len(players):,} שחקנים · {total_minutes:,.0f} דקות")

    ps_path = resolve(args.player_season)
    ps = pd.read_csv(ps_path, dtype=str, low_memory=False)
    code_col = find_col(ps, "player_code", "player_id", "code")
    name_col = find_col(ps, "player", "player_name", "name", "full_name")
    print(f"player_season: {ps_path.name} · קוד={code_col} · שם={name_col}")
    if code_col is None:
        print(f"🔴 לא זוהתה עמודת קוד. עמודות: {list(ps.columns)}")
        return 1

    ps_codes = ps[code_col].astype(str).str.strip()

    # ---------------------------------------------------------- A
    hdr("A. מי לא נמצא, וכמה דקות הוא שווה")

    players["norm"] = norm_num(players["Player_ID"])
    players["is_alnum"] = players["norm"].eq("")
    ps_norm = set(norm_num(ps_codes).unique()) - {""}

    players["matched"] = players["norm"].isin(ps_norm) & ~players["is_alnum"]

    matched = players[players["matched"]]
    unmatched = players[~players["matched"]]

    print(f"  נמצאו       : {len(matched):,} שחקנים · "
          f"{matched['minutes'].sum() / total_minutes:.1%} מהדקות")
    print(f"  לא נמצאו    : {len(unmatched):,} שחקנים · "
          f"{unmatched['minutes'].sum() / total_minutes:.1%} מהדקות")
    print(f"    מהם אלפאנומריים: {int(unmatched['is_alnum'].sum()):,}")
    print(f"    מהם מספריים    : {int((~unmatched['is_alnum']).sum()):,}")

    print("\n  ⚠️ שיעור הדקות חשוב יותר משיעור השחקנים — שחקן שוליים")
    print("     שנעדר עולה פחות משחקן מפתח שנעדר.")

    if len(unmatched):
        print("\n  עשרת החסרים עם הכי הרבה דקות:")
        print(unmatched.nlargest(10, "minutes")[
            ["Player_ID", "name", "minutes", "seasons", "first_season", "last_season"]
        ].to_string(index=False))

    # ---------------------------------------------------------- B
    hdr("B. האם הם שם תחת קוד אחר — התאמה לפי שם")

    if name_col is None:
        print("  ⚠️ אין עמודת שם ב-player_season. אי אפשר להכריע.")
        print(f"     עמודות: {list(ps.columns)}")
        return 0

    ps_by_name = (ps.assign(_n=norm_name(ps[name_col]), _c=ps_codes)
                    .dropna(subset=["_n"]).drop_duplicates("_n")
                    .set_index("_n")["_c"].to_dict())

    unmatched = unmatched.copy()
    unmatched["name_norm"] = norm_name(unmatched["name"])
    unmatched["code_by_name"] = unmatched["name_norm"].map(ps_by_name)

    recovered = unmatched[unmatched["code_by_name"].notna()]
    truly_missing = unmatched[unmatched["code_by_name"].isna()]

    print(f"  נמצאו לפי שם  : {len(recovered):,} · "
          f"{recovered['minutes'].sum() / total_minutes:.1%} מהדקות")
    print(f"  חסרים באמת    : {len(truly_missing):,} · "
          f"{truly_missing['minutes'].sum() / total_minutes:.1%} מהדקות")

    if len(recovered):
        print("\n  דוגמאות למיפוי שהתגלה:")
        print(recovered.nlargest(10, "minutes")[
            ["Player_ID", "name", "code_by_name", "minutes"]].to_string(index=False))
        print("\n  🔴 כלומר השחקנים קיימים — הקוד שונה. צריך טבלת מיפוי.")

    if len(truly_missing):
        print("\n  החסרים באמת, לפי דקות:")
        print(truly_missing.nlargest(10, "minutes")[
            ["Player_ID", "name", "minutes", "seasons", "first_season", "last_season"]
        ].to_string(index=False))
        print("\n  לפי עונה ראשונה:")
        print(truly_missing.groupby("first_season").size().to_string())

    # ---------------------------------------------------------- C
    hdr("C. מה זה אומר")

    share = (unmatched["minutes"].sum() / total_minutes) if total_minutes else 0
    if share < 0.01:
        print(f"  ✅ {share:.1%} מהדקות. שולי.")
    elif share < 0.05:
        print(f"  ⚠️ {share:.1%} מהדקות. לא שולי — מאגר השחקנים חסר.")
    else:
        print(f"  🔴 {share:.1%} מהדקות חסרות מ-player_season.")
        print("     המאגר הוא הבסיס לבנצ'מרק ולמודל הזמינות.")

    out = resolve(OUT_REL)
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["Player_ID", "name", "minutes", "rows", "seasons",
            "first_season", "last_season", "is_alnum", "code_by_name"]
    unmatched[[c for c in cols if c in unmatched.columns]].to_csv(out, index=False)
    print(f"\n  נשמר: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())