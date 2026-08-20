"""
dilution_test.py — האם עומק המאגר מסביר את הפער ברוויה.

השאלה
-----
הרוויה נמדדה ב-21M ל-2024 (מאגר 295) וב-29M ל-2025 (מאגר 335).
פער של 8M. שלושה הסברים מתחרים:

    א. עומק מאגר   — יותר מה לקנות, הרוויה נדחית
    ב. התייקרות    — 20 קבוצות רודפות אחרי אותם שחקנים,
                     הבינוניים מתייקרים, כל שחקן עולה יותר
    ג. שגיאת תמחור — מודל העלות כויל על מכבי בלבד (n=18)
                     ואינו יודע שהשוק התחרותי

**המבחן הזה מבודד את (א) בלבד.** אם דילול 2025 ל-295 מחזיר את
הרוויה ל-21M, ההסבר הפשוט מספיק. אם היא כמעט לא זזה, (ב) ו-(ג)
נשארים על השולחן וצריך למדוד אותם בנפרד.

⚠️ שלוש הסתייגויות שנרשמות לפני ההרצה
--------------------------------------
1. **דילול אינו הרחבת ליגה.** ההרחבה הוסיפה שחקנים באיכות ממוצעת
   נמוכה יותר; דילול מוריד טובים וגרועים באותה מידה. לכן הדילול
   פוגע במאגר **יותר** מהמציאות, והוא חסם עליון על האפקט.
2. **הדילול משכבת לפי עמדה**, כדי לשמור על היתכנות POS_FLOOR
   ו-POS_MIN_SHARE. זה בכוונה: המבחן על **גודל** המאגר, לא על
   הרכבו. דילול אקראי לגמרי היה מערבב את שני הדברים.
3. **זרע יחיד אינו מדידה.** מריצים S זרעים ומדווחים חציון וטווח.
   אם הטווח רחב מ-4M, גודל המאגר אינו מסביר יציב.

תחזיות שננעלו לפני ההרצה
------------------------
    2025 מדולל ל-295   אלמוג: 25M        ·  קלוד: 24-29M
    2024 מדולל ל-260   אלמוג: —          ·  קלוד: 18-21M
    כמה מ-8M ייסגרו    קלוד: פחות ממחצית (כלומר רוויה > 25M)
    השיפוע עד הרוויה   קלוד: יעלה אחרי דילול

אלמוג חוזה בדיוק מחצית (29->25). זה הגבול, ולכן מבחן טוב.

הרצה:
    python src/dilution_test.py --scale 1.0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import optimizer_backtest as ob  # noqa: E402
from paths import PROCESSED_DIR  # noqa: E402
from budget_curve import find_saturation, MIN_ROSTER  # noqa: E402
from league_backtest import build_pool, SEASONS  # noqa: E402
from usage_constrained import optimise_capped, attach_usage  # noqa: E402
import optimise_consistent as oc  # noqa: E402

SEP = "=" * 78
# כמה לדלל כל עונה. 2025 -> גודל המאגר של 2024 = המבחן המרכזי.
TARGETS = {2024: [260], 2025: [295, 260]}


def hdr(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def dilute(cand: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """
    דילול משוכבת לפי עמדה — שומר על הפרופורציות ועל היתכנות.
    מבודד גודל מאגר מהרכב מאגר.

    🔴 reset_index הכרחי. optimise_capped בונה את משתני ה-LP לפי
    מיקום (`range(n)`) אבל שולף עמדות לפי תווית האינדקס
    (`pool.index[pool.position == ps_]`). בפול המלא התווית שווה
    למיקום ולכן זה עובד; אחרי דילול התוויות מקוריות ו-x[i] חורג.
    זהו "מזהה אינו מספר" בווריאנט של אינדקס — הפעם השביעית
    בפרויקט.
    """
    if n >= len(cand):
        return cand.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    frac = n / len(cand)
    keep = []
    for _, g in cand.groupby("position"):
        k = max(1, int(round(len(g) * frac)))
        keep.append(rng.choice(g.index.values, size=min(k, len(g)),
                               replace=False))
    return cand.loc[np.concatenate(keep)].reset_index(drop=True)


def curve(cand, budgets_rel, budgets_m):
    """עקומה על q_lp בלבד. אין צורך ב-score_rows כאן."""
    # שומר סף: optimise_capped מניח שהתווית שווה למיקום.
    assert list(cand.index) == list(range(len(cand))), \
        "אינדקס המאגר אינו 0..n-1 — optimise_capped ייפול על x[i]"
    rows = []
    for b_rel, b_m in zip(budgets_rel, budgets_m):
        sel, _ = optimise_capped(cand, b_rel, MIN_ROSTER)
        if sel is None:
            continue
        rows.append({"budget_m": b_m, "q_lp": oc.LAST.get("obj", np.nan)})
    return pd.DataFrame(rows)


def slope_to_sat(d: pd.DataFrame, sat: float) -> float:
    pre = d[d.budget_m <= sat].sort_values("budget_m")
    if len(pre) < 2:
        return np.nan
    span = float(pre.budget_m.iloc[-1] - pre.budget_m.iloc[0])
    return float(pre.q_lp.iloc[-1] - pre.q_lp.iloc[0]) / span


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, required=True)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--lo", type=float, default=10.0)
    ap.add_argument("--hi", type=float, default=36.0)
    ap.add_argument("--step", type=float, default=1.0)
    ap.add_argument("--usage",
                    default="data/processed/usage_curve_results_min0.csv")
    args = ap.parse_args()

    budgets_m = np.arange(args.lo, args.hi + 1e-9, args.step)
    budgets_rel = budgets_m / args.scale

    hdr("מבחן הדילול — האם גודל המאגר מסביר את הפער ברוויה")
    print(f"  {len(budgets_m)} נקודות תקציב · {args.seeds} זרעים")
    print("  תחזיות: 2025->295  אלמוג 25M · קלוד 24-29M")
    print("          קלוד בנוסף: הדילול יסגור פחות ממחצית מ-8M\n")

    feat, anch, pos, ps = ob.load_all()
    upath = Path(args.usage)
    if not upath.is_absolute():
        upath = Path(__file__).resolve().parents[1] / upath

    out, base = [], {}
    for train_max, test in SEASONS:
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        cand = attach_usage(cand, upath, test)

        d0 = curve(cand, budgets_rel, budgets_m)
        _, s0 = find_saturation(d0)
        base[test] = (len(cand), s0, slope_to_sat(d0, s0) if s0 else np.nan)
        print(f"\n  עונה {test} · מאגר {len(cand)} · "
              f"רוויה בסיס {s0}M · שיפוע {base[test][2]:.2f}")

        for n in TARGETS.get(test, []):
            sats, slopes = [], []
            for s in range(args.seeds):
                sub = dilute(cand, n, seed=1000 * test + s)
                d = curve(sub, budgets_rel, budgets_m)
                _, sat = find_saturation(d)
                if sat:
                    sats.append(sat)
                    slopes.append(slope_to_sat(d, sat))
                print(f"    ->{n}  זרע {s}  n={len(sub)}  "
                      f"רוויה {sat}M", flush=True)
            if not sats:
                print(f"    ->{n}  לא זוהתה רוויה באף זרע")
                continue
            a = np.array(sats, float)
            out.append({"season": test, "target": n, "n_seeds": len(a),
                        "sat_median": float(np.median(a)),
                        "sat_min": float(a.min()), "sat_max": float(a.max()),
                        "sat_base": s0, "slope_median": float(np.median(slopes)),
                        "slope_base": base[test][2]})

    if not out:
        print("\n🔴 אין תוצאות.")
        return 1
    r = pd.DataFrame(out)

    hdr("התוצאה")
    for _, x in r.iterrows():
        spread = x.sat_max - x.sat_min
        print(f"\n  {int(x.season)}  {int(base[x.season][0])} -> "
              f"{int(x.target)} שחקנים")
        print(f"    רוויה : {x.sat_base:.0f}M -> חציון {x.sat_median:.0f}M "
              f"(טווח {x.sat_min:.0f}-{x.sat_max:.0f})")
        print(f"    שיפוע : {x.slope_base:.2f} -> {x.slope_median:.2f} נק'/M")
        if spread > 4:
            print(f"    🔴 פיזור {spread:.0f}M בין זרעים — גודל המאגר")
            print("       אינו מסביר יציב. המספר אינו קביל.")

    hdr("מול התחזיות")
    key = r[(r.season == 2025) & (r.target == 295)]
    if len(key):
        k = key.iloc[0]
        gap = base[2025][1] - base[2024][1]
        closed = base[2025][1] - k.sat_median
        print(f"  הפער המקורי        : {gap:.0f}M "
              f"({base[2024][1]:.0f} מול {base[2025][1]:.0f})")
        print(f"  2025 מדולל ל-295   : {k.sat_median:.0f}M")
        print(f"  🔴 נסגר             : {closed:.0f}M מתוך {gap:.0f}M "
              f"({closed / gap:.0%})")
        print(f"\n    אלמוג 25M      "
              f"{'✅' if abs(k.sat_median - 25) <= 0.5 else '❌'}")
        print(f"    קלוד 24-29M    "
              f"{'✅' if 24 <= k.sat_median <= 29 else '❌'}")
        print(f"    קלוד 'פחות ממחצית'  "
              f"{'✅' if closed < gap / 2 else '❌'}")
        print()
        if closed >= 0.7 * gap:
            print("  ⇒ **עומק המאגר מסביר את רוב הפער.** ההסברים על")
            print("     מחירים והתייקרות אינם נדרשים.")
        elif closed <= 0.3 * gap:
            print("  ⇒ **עומק המאגר אינו ההסבר.** הפער נובע ממחירים —")
            print("     או התייקרות אמיתית, או שגיאת תמחור של המודל")
            print("     שכויל על מכבי בלבד. שניהם דורשים מבחן נפרד.")
        else:
            print("  ⇒ **שני מנגנונים פועלים.** עומק המאגר מסביר חלק,")
            print("     והשאר הוא מחירים. לא ניתן להכריע ביניהם כאן.")

    print("\n  ⚠️ הדילול פוגע במאגר יותר מהרחבת ליגה אמיתית — הוא")
    print("     מוריד טובים וגרועים באותה מידה. חסם עליון על האפקט.")

    p = PROCESSED_DIR / "dilution_test.csv"
    r.to_csv(p, index=False)
    print(f"\n  נשמר: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())