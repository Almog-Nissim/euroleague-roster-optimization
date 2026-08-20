"""
dump_rosters.py — לשמור את הסגלים שהמנוע בנה, ואת הסגלים האמיתיים.

למה נפרד ולא שינוי ב-league_backtest.py
---------------------------------------
`league_backtest_results.csv` מכיל סיכום בלבד: 38 שורות עם
q_club / q_eng / adv. **זהות השחקנים והקצאת הדקות מעולם לא נכתבו
לדיסק**, ולכן אי אפשר לחשב את ממוצע ה-usage של הסגל שנבנה.

הסקריפט הזה מייבא את אותן פונקציות ומריץ את אותה לולאה, וכותב רק
את הסגלים. `league_backtest_results.csv` **אינו נוגע** — אין סיכון
ש-q_eng יזוז בגלל שינוי שנועד להוסיף פלט.

מה לא ידוע ולכן נמדד
--------------------
`score_rows` מחזירה שלושה ערכים ושניים מהם מושלכים בקוד המקורי
(`q_club, _, _`). סביר שהקצאת הדקות שם — אבל **לא מנחשים**. הסקריפט
בודק את מבנה שני הערכים הנוספים ומדווח מה מצא, ומחלץ דקות רק אם
מצא מערך באורך הסגל.

בלי דקות אמיתיות אפשר עדיין לחשב usage לא-משוקלל, אבל זה מספר אחר —
בדיוק הפער שהקונטרריאן הצביע עליו בין 0.512 ל-123.7.

הרצה:  python src/dump_rosters.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from paths import PROCESSED_DIR  # noqa: E402
import optimizer_backtest as ob  # noqa: E402
from roster_membership_audit import score_rows  # noqa: E402
from optimise_consistent import optimise_v2  # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER  # noqa: E402
from league_backtest import build_pool, club_side, REPL, SEASONS  # noqa: E402

OUT = PROCESSED_DIR / "engine_rosters.csv"
_reported = {"done": False}


def extract_minutes(extra, n: int, label: str):
    """
    מחלץ דקות משני הערכים הנוספים של score_rows — רק אם נמצא מערך
    באורך הסגל. מדווח פעם אחת מה נמצא בפועל.
    """
    found = None
    for i, v in enumerate(extra):
        kind = type(v).__name__
        length = len(v) if hasattr(v, "__len__") else None
        if not _reported["done"]:
            print(f"    score_rows[{i + 1}]: {kind}"
                  + (f" באורך {length}" if length is not None else "")
                  + (f"  דוגמה: {np.asarray(v).ravel()[:3]}"
                     if length not in (None, 0) else ""))
        if found is None and length == n:
            try:
                arr = np.asarray(v, dtype=float).ravel()
                if arr.shape[0] == n:
                    found = arr
            except (TypeError, ValueError):
                pass

    if not _reported["done"]:
        if found is None:
            print(f"    ⚠️ לא נמצא מערך דקות באורך {n} ({label}). "
                  f"ה-usage יחושב לא-משוקלל.")
        else:
            print(f"    ✅ נמצא מערך באורך {n} — סכום {found.sum():.1f}")
            print("       (אם הסכום ~200, אלה הדקות)")
        _reported["done"] = True
    return found


def collect(df: pd.DataFrame, minutes, season, club, side) -> list[dict]:
    out = []
    for i, (_, r) in enumerate(df.iterrows()):
        out.append({
            "season": season, "club": club, "side": side,
            "player_code": str(r["pc"]),
            "ppm_true": float(r.get("ppm_true", np.nan)),
            "avail_true": float(r.get("avail_true", np.nan)),
            "cost": float(r.get("cost", np.nan)),
            "position": r.get("position", None),
            "minutes_alloc": float(minutes[i]) if minutes is not None else np.nan,
        })
    return out


def main() -> int:
    print("=" * 74)
    print("dump_rosters — שמירת הסגלים בלבד. התוצאות הקיימות לא נוגעות.")
    print("=" * 74)

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    rows: list[dict] = []
    for train_max, test in SEASONS:
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        gmax = float(ps[ps.season == test].games.max())
        clubs = sorted(split[split.season == test].club.unique())
        print(f"\nעונה {test} — {len(clubs)} מועדונים, מאגר {len(cand)}")

        for club in clubs:
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                continue
            B = float(keep.cost.sum())

            q_club, *extra_c = score_rows(keep, "ppm_true", "avail_true", REPL)
            min_club = extract_minutes(extra_c, len(keep), "מועדון")

            sel, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
            if sel is None:
                continue
            eng = cand[sel]
            q_eng, *extra_e = score_rows(eng, "ppm_true", "avail_true", REPL)
            min_eng = extract_minutes(extra_e, len(eng), "מנוע")

            rows += collect(keep, min_club, test, club, "club")
            rows += collect(eng, min_eng, test, club, "engine")
            print(f"  {club:<6} מועדון {len(keep):>3} · מנוע {len(eng):>3} · "
                  f"q {q_club:6.1f} -> {q_eng:6.1f}")

    if not rows:
        print("\n🔴 לא נאסף כלום.")
        return 1

    d = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT, index=False)

    print("\n" + "=" * 74)
    print("סיכום")
    print("=" * 74)
    print(f"  {len(d):,} שורות · {d.groupby(['season', 'club']).ngroups} עונות-מועדון")
    print(f"  סגל מנוע  : {int((d.side == 'engine').sum()):,} שורות")
    print(f"  סגל מועדון: {int((d.side == 'club').sum()):,} שורות")
    have_min = d["minutes_alloc"].notna().mean()
    print(f"  דקות הוקצו: {have_min:.0%} מהשורות")

    if have_min > 0:
        tm = d.groupby(["season", "club", "side"])["minutes_alloc"].sum()
        print("\n  סכום דקות לסגל (צפוי 200 אם אלה דקות):")
        print(f"    חציון {tm.median():.1f} · טווח {tm.min():.1f} .. {tm.max():.1f}")

    print(f"\n  נשמר: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())