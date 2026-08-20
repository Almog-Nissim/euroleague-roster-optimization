"""
usage_power_check.py — האם יש מספיק שונות כדי לזהות עקומת usage.

בדיקת כוח, לא אמידה. רצה **לפני** כל רגרסיה. אם היא נופלת,
היום נעצר כאן ופונקציית המטרה החדשה נבנית אחרת לגמרי.

השאלה: אחרי ניכוי ממוצע השחקן וממוצע העונה, כמה שונות נשארת
ב-usage בתוך אותו שחקן? בלי שונות פנימית אין מה לזהות — כל מה
שיימדד יהיה הבדלים *בין* שחקנים, וזה בדיוק מה שאפקטים קבועים
אמורים לנקות.

תחזית נעולה (קלוד)
------------------
ס"ת פנימי < 1.5 נק' אחוז -> אין זיהוי, עוצרים.
1.5-3.0 -> זיהוי חלש, null יהיה חסר-כוח ולא ראיה לאפס.
> 3.0  -> זיהוי סביר. אני צופה 2.5-4.0, כלומר עובר בקושי.

⚠️ הבדיקה יכולה לבטל את שתי התחזיות על השיפוע. אם אין זיהוי,
השאלה לא נסגרת לטובת אף אחד מאיתנו.

מדדים
-----
usage = (FGA + 0.44·FTA + TOV) · (דקות_קבוצה/5) /
        (דקות_שחקן · (FGA+0.44·FTA+TOV)_קבוצה)
TS%   = PTS / (2 · (FGA + 0.44·FTA))

⚠️ שני האגפים חולקים את FGA+0.44·FTA — שיפוע שלילי מכני גם בלי
עקומה. הפיצול אי-זוגי/זוגי הוא מה שיפריד ביניהם.

הרצה:  python src/usage_power_check.py --min-minutes 300
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import load_boxscores, repo_root  # noqa: E402
from verify_boxscores import parse_minutes  # noqa: E402


def build_player_season(bx: pd.DataFrame, min_minutes: float) -> pd.DataFrame:
    d = bx.copy()
    pid = d["Player_ID"].astype(str).str.strip().str.upper()
    d = d[~pid.isin(["TOTAL", "TEAM", "NAN", ""])]

    for c in ["Points", "FieldGoalsAttempted2", "FieldGoalsAttempted3",
              "FreeThrowsAttempted", "Turnovers"]:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)

    d["min_num"] = d["Minutes"].apply(parse_minutes)
    d["FGA"] = d["FieldGoalsAttempted2"] + d["FieldGoalsAttempted3"]
    d["poss_used"] = d["FGA"] + 0.44 * d["FreeThrowsAttempted"] + d["Turnovers"]

    tm = (d.groupby(["Season", "Gamecode", "Team"])
            .agg(tm_poss=("poss_used", "sum"), tm_min=("min_num", "sum"))
            .reset_index())
    d = d.merge(tm, on=["Season", "Gamecode", "Team"], how="left")

    ps = (d.groupby(["Season", "Player_ID", "Team"])
            .agg(minutes=("min_num", "sum"), poss=("poss_used", "sum"),
                 pts=("Points", "sum"), fga=("FGA", "sum"),
                 fta=("FreeThrowsAttempted", "sum"),
                 tm_poss=("tm_poss", "sum"), tm_min=("tm_min", "sum"),
                 games=("Gamecode", "nunique"))
            .reset_index())

    ps = ps[ps["minutes"] >= min_minutes].copy()
    ps["usage"] = 100 * (ps["poss"] * (ps["tm_min"] / 5)) / (ps["minutes"] * ps["tm_poss"])
    denom = 2 * (ps["fga"] + 0.44 * ps["fta"])
    ps["ts"] = np.where(denom > 0, 100 * ps["pts"] / denom, np.nan)
    return ps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--min-minutes", type=float, default=300)
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")

    bx = load_boxscores(args.root, verbose=True)
    ps = build_player_season(bx, args.min_minutes)

    print("\n" + "=" * 74)
    print(f"בדיקת כוח — {len(ps):,} תצפיות שחקן-עונה-מועדון (>= {args.min_minutes:.0f} דק')")
    print("=" * 74)

    print("\nusage גולמי:")
    print(ps["usage"].describe().to_string())
    print("\nTS% גולמי:")
    print(ps["ts"].describe().to_string())

    ps["usage_dm"] = ps["usage"] - ps.groupby("Player_ID")["usage"].transform("mean")
    ps["usage_dm"] = ps["usage_dm"] - ps.groupby("Season")["usage_dm"].transform("mean")

    counts = ps.groupby("Player_ID").size()
    multi = counts[counts >= 2].index
    inner = ps[ps["Player_ID"].isin(multi)]

    sd_within = float(inner["usage_dm"].std())
    sd_between = float(ps.groupby("Player_ID")["usage"].mean().std())
    sd_total = float(ps["usage"].std())

    print("\n" + "=" * 74)
    print("התוצאה")
    print("=" * 74)
    print(f"  שחקנים עם 2+ עונות    : {len(multi):,}")
    print(f"  תצפיות שתורמות לזיהוי : {len(inner):,}")
    print(f"  ס\"ת בין שחקנים        : {sd_between:.2f} נק' אחוז")
    print(f"  ס\"ת בתוך שחקן         : {sd_within:.2f} נק' אחוז")
    print(f"  יחס פנימי/כולל        : {sd_within / sd_total:.3f}")

    print("\n  מספר עונות לשחקן:")
    print(counts.value_counts().sort_index().to_string())

    print("\n" + "-" * 74)
    if sd_within < 1.5:
        print("  🔴 מתחת ל-1.5 — אין זיהוי. היום נעצר כאן.")
        print("     פונקציית המטרה החדשה לא יכולה להישען על עקומת usage")
        print("     שנאמדת מהדאטה שלנו. צריך לבנות אותה אחרת.")
        return 1
    if sd_within < 3.0:
        print("  ⚠️ 1.5-3.0 — זיהוי חלש. אפשר להמשיך, אבל כל אומדן יגיע")
        print("     עם רווח סמך רחב, ו-null יהיה חסר-כוח ולא ראיה לאפס.")
        return 0
    print("  ✅ מעל 3.0 — שונות פנימית מספקת. המשך לפיצול אי-זוגי/זוגי.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())