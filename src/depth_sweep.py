"""
depth_sweep.py  (Day 7)
-----------------------
האם עומק משתלם — כפונקציה של רמת המחליף, לא תחת הנחה עליה.

--------------------------------------------------------------------
למה סווייפ ולא מספר
--------------------------------------------------------------------
יום 6, סעיף 8, מצא שסגל של 8 מנצח סגל של 16, וסימן מיד:

    "REPLACEMENT_PCTL = 10 היא הצהרה שאי אפשר למדוד...
     זה ציר רגישות, לא באג."

היום ניסיתי למדוד אותה, ואלמוג מסר שני מקרים אמיתיים ממכבי 24/25
(מאייר 0.243 חינם, קאבה 0.000) שממוצעם 0.122. אוכלוסיית הממלאים
בכל הליגה נותנת 0.127. התאמה יפה — **אבל היא לא יציבה**:

    <= 5 משחקים   ->  0.030
    <= 10 משחקים  ->  0.127
    <= 15 משחקים  ->  0.179

פי שישה בין הקצוות, לפי סף שאני בוחר. **לבחור 0.127 זה להחליף
מספר שרירותי אחד באחר**, ולהצהיר שמדדתי כשלמעשה בחרתי.

לכן הפלט אינו מספר אלא **נקודת המפנה**: מתחת לאיזו רמת מחליף
עומק מתחיל להשתלם. את הנקודה הזו אפשר להשוות לטווח הנמדד
ולהגיד משהו שלא תלוי בבחירת הסף.

--------------------------------------------------------------------
למה זה זול
--------------------------------------------------------------------
רמת המחליף **אינה נכנסת לאופטימיזציה** — `optimise()` לא מקבל
אותה. היא נכנסת רק ל**ניקוד**. לכן פותרים פעם אחת לכל גודל סגל,
ומנקדים על פני כל הרמות בחינם.

הרצה:
    python src/depth_sweep.py
"""

import io
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster_optimizer as ro
import optimizer_backtest as ob
from roster_membership_audit import score_rows
import club_rosters as cr
from replacement_level import load as load_repl, measure

SCENARIOS = [("TEL", 2023, 2024), ("HTA", 2024, 2025)]
REPL_GRID = [0.00, 0.03, 0.06, 0.09, 0.127, 0.16, 0.19, 0.22, 0.25]
ROSTER_SIZES = list(range(7, 17))
SEP = "=" * 78


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def club_benchmark(club, season, ps, posmap, repl):
    """הבנצ'מרק לפי הסגל המפורש של club_rosters, מנוקד על מה שקרה."""
    r = cr.roster_df(club, season)
    gmax = float(ps[ps.season == season].games.max())
    sr = ps[(ps.season == season) & (ps.min_per_game > 0)].copy()
    sr["pc"] = sr.player_code.astype(str)
    sr["ppm_true"] = sr.pir_per_game / sr.min_per_game
    sr["avail_true"] = sr.games / gmax
    sr["position"] = sr.pc.map(posmap)
    d = sr[sr.pc.isin(set(r.player_code)) & sr.position.notna()]
    q, used, filled = score_rows(d, "ppm_true", "avail_true", repl)
    return q, len(d), used


def main():
    print(SEP)
    print("האם עומק משתלם — כפונקציה של רמת המחליף")
    print(SEP)

    d = load_repl()
    lo, _ = measure(d, max_games=5)
    mid, _ = measure(d, max_games=10)
    hi, _ = measure(d, max_games=15)
    print(f"\n  הטווח הנמדד: {lo:.3f} (סף 5) .. {mid:.3f} (סף 10) .. "
          f"{hi:.3f} (סף 15)")
    print(f"  שני המקרים של מכבי (אלמוג): 0.122")

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position

    for club, train_max, test in SCENARIOS:
        ob.TRAIN_MAX, ob.TEST, ob.TARGET_CLUB = train_max, test, club
        with contextlib.redirect_stdout(io.StringIO()):
            cm, smear, agg, am, pm, PF, lagged = ob.fit_models(ps, feat, anch)
            cand = ob.build(lagged, feat, pos, cm, smear, agg, am, pm, PF,
                            ob.scale_for(anch, club, test))
        cand["ppm_true"] = cand.pir_per_game / cand.min_per_game
        cand["avail_true"] = cand.frac

        r = cr.roster_df(club, test)
        known = float(r.salary.dropna().sum())
        # אומדן מודל למי שאין לו שכר — רק מפיצ'רים, לעולם לא משכר המבחן
        miss = r[r.salary.isna()]
        imp = float(cand[cand.player_code.astype(str)
                    .isin(set(miss.player_code))].cost.sum())
        budget = known + imp + cr.budget_only_total(club, test)

        h(f"{club} {test}   תקציב {budget:,.0f}  "
          f"({known:,.0f} ידוע + {imp:,.0f} אומדן ל-{len(miss)} + "
          f"{cr.budget_only_total(club, test):,.0f} לא-רשומים)")

        # --- פתרון פעם אחת לכל גודל סגל ---
        sols = {}
        for mr in ROSTER_SIZES:
            sel, mins = ro.optimise(cand, budget, mr)
            if sel is not None:
                sols[mr] = cand[sel]
        if not sols:
            print("  אין פתרון")
            continue

        print(f"\n  {'repl':<8}" +
              "".join(f"{mr:>7}" for mr in sorted(sols)) +
              f"{'הטוב':>8}{'מועדון':>9}{'יתרון':>9}")
        rows = []
        for rp in REPL_GRID:
            bq, nb, _ = club_benchmark(club, test, ps, posmap, rp)
            line, best = {}, None
            for mr in sorted(sols):
                q, _, _ = score_rows(sols[mr], "ppm_true", "avail_true", rp)
                line[mr] = q
                if best is None or q > line[best]:
                    best = mr
            rows.append((rp, best, line[best], bq))
            mark = " <-- מדוד" if abs(rp - 0.127) < 1e-9 else ""
            print(f"  {rp:<8.3f}" +
                  "".join(f"{line[mr]:>7.1f}" for mr in sorted(sols)) +
                  f"{best:>8}{bq:>9.1f}{line[best] / bq - 1:>+8.1%}{mark}")

        print(f"\n  n המועדון בבנצ'מרק: {nb}")
        flips = [(a, b) for a, b in zip(rows, rows[1:])
                 if a[1] != b[1]]
        if flips:
            print("  🔴 נקודות מפנה בגודל הסגל האופטימלי:")
            for a, b in flips:
                print(f"     repl {a[0]:.3f} -> {b[0]:.3f} : "
                      f"סגל {a[1]} -> {b[1]}")
        else:
            print(f"  גודל הסגל האופטימלי קבוע ({rows[0][1]}) על פני "
                  "כל הטווח — הציר אינו מכריע כאן.")

    h("קריאה")
    print("  אם גודל הסגל האופטימלי מתהפך **בתוך** הטווח הנמדד")
    print("  (0.03-0.18), אי אפשר לענות על שאלת העומק בלי לקבוע")
    print("  את רמת המחליף — והתשובה של יום 6 ('8 עדיף על 16')")
    print("  הייתה תוצר של ההנחה, לא של הדאטה.")
    print("\n  אם הוא קבוע על פני כל הטווח, המסקנה חסינה והציר נסגר.")
    print(SEP)


if __name__ == "__main__":
    main()
