"""מבחן אי-תלות באינדקס — יום 12.

חמש פונקציות LP בונות משתנים לפי **מיקום** (`range(n)`) ושולפות
קבוצות לפי **תווית** (`pool.index[...]`). כל עוד `build_pool` מחזיר
RangeIndex רציף השניים זהים והקוד עובד. הרציפות הזו נשמרת בשורה
אחת (`league_backtest.build_pool`), 130 שורות מהפונקציות שתלויות בה,
ואף בדיקה לא ידעה שהיא קיימת.

המבחן מריץ כל פונקציה פעמיים — על המאגר הטבעי, ועל אותו מאגר עם
אינדקס מעורבב ולא רציף — ודורש **תוצאה זהה**.

    python src/index_invariance_test.py            # אחרי התיקון
    python src/index_invariance_test.py --expect-fail   # להדגמת הבאג

הרצה: TEST=2025, TRAIN_MAX=2024, תקציב = חציון המאגר.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import roster_optimizer as ro                     # noqa: E402
import optimise_consistent as oc                  # noqa: E402
import usage_constrained as uc                    # noqa: E402
import league_backtest as lb                      # noqa: E402
import optimizer_backtest as ob                   # noqa: E402

TEST, TRAIN_MAX = 2025, 2024
BUDGET = 20.0
MIN_ROSTER = 12
SEED = 11


def scramble(df: pd.DataFrame, rng, mode: str = "sparse") -> pd.DataFrame:
    """אותן שורות, באותו סדר — רק תוויות אינדקס אחרות.

    שני מצבים, ורק אחד מהם מסוכן:

    sparse  — תוויות גדולות ודלילות (10, 18, 26, ...). זה מה שמייצר
              סינון בוליאני או `drop`. `x[label]` חורג מהרשימה,
              ולכן הכשל **רועש**: IndexError. זה מה שקרה ל-`dilute`.

    permuted — תוויות שהן פרמוטציה של 0..n-1. זה מה שמייצר
              `sort_values` בלי `reset_index`. כל תווית חוקית
              כמיקום, אין שגיאה, והפתרון פשוט **שגוי בשקט**.
              זה התרחיש שצריך לתפוס.
    """
    out = df.copy()
    n = len(df)
    if mode == "sparse":
        labels = rng.choice(np.arange(10, 10 + 8 * n, 8), size=n,
                            replace=False)
    elif mode == "permuted":
        labels = rng.permutation(n)
    else:
        raise ValueError(mode)
    out.index = pd.Index(labels, name=mode)
    assert not out.index.equals(pd.RangeIndex(n))
    return out


def compare(name, fn, cand, rng, mode="sparse") -> bool:
    try:
        sel_a, min_a = fn(cand)
        sel_b, min_b = fn(scramble(cand, rng, mode))
    except Exception as e:
        print(f"  {name:<24}❌  {type(e).__name__}: {e}")
        return False

    if sel_a is None or sel_b is None:
        print(f"  {name:<24} אין פתרון באחד הצדדים")
        return False

    same_sel = bool(np.array_equal(np.asarray(sel_a), np.asarray(sel_b)))
    dmin = float(np.max(np.abs(np.asarray(min_a, float)
                               - np.asarray(min_b, float))))
    ok = same_sel and dmin < 1e-6
    n_a, n_b = int(np.sum(sel_a)), int(np.sum(sel_b))
    flag = "✅" if ok else "❌"
    print(f"  {name:<24}{flag}  n {n_a}/{n_b}   "
          f"סגל זהה: {same_sel}   Δדקות מרבי: {dmin:.2e}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect-fail", action="store_true",
                    help="0 אם המבחן נכשל — להדגמת הבאג לפני התיקון")
    args = ap.parse_args()

    print("=" * 68)
    print("מבחן אי-תלות באינדקס — חמש פונקציות LP")
    print("=" * 68)

    rng = np.random.default_rng(SEED)
    feat, anch, pos, ps = ob.load_all()
    with contextlib.redirect_stdout(io.StringIO()):
        cand, _info = lb.build_pool(TEST, TRAIN_MAX, feat, anch, pos, ps)

    upath = ro.PROCESSED_DIR / "usage_curve_results_min0.csv"
    if upath.exists():
        with contextlib.redirect_stdout(io.StringIO()):
            cand = uc.attach_usage(cand, upath, TEST)
        usrc = "אמיתי"
    else:
        # הקובץ נגזר מבוקסקורים ואינו בריפו. למבחן הזה נדרש רק
        # עמוד usage לא-קבוע שיפעיל את האילוץ — לא ערכיו הנכונים.
        r = cand.ppm.rank(pct=True).to_numpy()
        cand = cand.copy()
        cand["usage_prior"] = 12.0 + 16.0 * r
        usrc = "מסונתז (הקובץ חסר)"

    print(f"\n  מאגר {TEST}: {len(cand)} שחקנים · "
          f"אינדקס רציף במקור: {cand.index.equals(pd.RangeIndex(len(cand)))}")
    print(f"  תקציב {BUDGET} · MIN_ROSTER {MIN_ROSTER} · usage {usrc}\n")

    checks = [
        ("optimise_v2", lambda c: oc.optimise_v2(c, BUDGET, MIN_ROSTER)),
        ("optimise_capped", lambda c: uc.optimise_capped(
            c, BUDGET, MIN_ROSTER)),
        ("optimise (ro)", lambda c: ro.optimise(c, BUDGET, MIN_ROSTER)),
    ]

    # נעילה — הכשל החמור, כי הוא שקט: נועל את מי שבמיקום 7 במקום את
    # בעל התווית 7, בלי שגיאה.
    free_sel, _ = oc.optimise_v2(cand, BUDGET, MIN_ROSTER)
    unpicked = np.flatnonzero(~np.asarray(free_sel))
    # שלושה זולים שהפתרון החופשי **לא** בחר — כך שהנעילה מחייבת
    # ומשנה את התשובה. נעילה שלא מחייבת אינה מבחן.
    lock_pos = [int(i) for i in
                unpicked[np.argsort(cand.cost.to_numpy()[unpicked])][:3]]
    checks.append(
        ("optimise_v2 + locked", lambda c: oc.optimise_v2(
            c, BUDGET, MIN_ROSTER, locked=lock_pos)))

    results = []
    for mode, title in [("sparse", "א. תוויות דלילות (drop / סינון) — כשל רועש"),
                        ("permuted", "ב. תוויות מפורמטות (sort_values) — כשל שקט")]:
        print(f"  {title}")
        for nm, f in checks:
            results.append(compare(nm, f, cand, rng, mode))
        print()

    # אימות נפרד לנעילה: האם באמת נבחרו השלושה שביקשנו
    sel, _ = oc.optimise_v2(scramble(cand, rng, "permuted"), BUDGET,
                            MIN_ROSTER, locked=lock_pos)
    locked_held = bool(sel is not None and all(sel[i] for i in lock_pos))
    print(f"  {'הנעולים אכן נבחרו':<24}{'✅' if locked_held else '❌'}  "
          f"{len(lock_pos)} מיקומים")
    results.append(locked_held)

    ok = all(results)
    print("\n" + "-" * 68)
    print(f"  {sum(results)}/{len(results)} עברו")
    if args.expect_fail:
        print("  מצב --expect-fail: כישלון הוא התוצאה הצפויה")
        return 0 if not ok else 1
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())