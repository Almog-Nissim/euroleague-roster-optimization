"""
optimise_consistent.py  (Day 7)
-------------------------------
מיישר את פונקציית המטרה של האופטימייזר לפונקציה שמנקדת אותו.

--------------------------------------------------------------------
הבאג
--------------------------------------------------------------------
ניקוד **המודל**, על הסגל שהמודל עצמו בחר, אינו מונוטוני ב-
MIN_ROSTER:

    mr      7      8      9     10     11     12
    ניקוד 117.5  119.2  118.7  117.5  119.6  118.4

זה בלתי אפשרי. `min_roster` הוא אילוץ מהדק — הערך האופטימלי
חייב לרדת או להישאר. אלא אם ממטבים דבר אחד ומודדים אחר.

--------------------------------------------------------------------
מה בדיוק שונה
--------------------------------------------------------------------
ב-`roster_optimizer.optimise`:

    max  Σ avail(i)·ppm(i)·m(i)
         Σ m(i) <= 200
         m(i)   <= 32·x(i)

ב-`score` (וב-`score_rows`):

    take(i) = min(32, נותר, תקרת_עמדה) · avail(i)
    נותר   -= take(i)

**ההבדל:** ה-LP מגביל את **סכום הדקות** ל-200, אבל מעריך אותן
בזמינות. הניקוד מגביל את סכום הדקות **המשוקללות בזמינות** ל-200.

בניקוד, שחקן שזמין ב-80% תופס 25.6 דקות ולא 32. לכן סגל של 7
מכסה 165 דקות בפועל, בעוד ה-LP משוכנע שחילק 200 מלאות. המנוע
בוחר סגל שאופטימלי לעולם שהמדידה לא מכירה — ו**זו בדיוק אותה
משפחה של יום 6 סעיף 7**, רק ברמה הדטרמיניסטית ולא מול המונטה
קרלו.

--------------------------------------------------------------------
איזה מהשניים נכון
--------------------------------------------------------------------
**הניקוד.** קבוצה חייבת להעמיד 200 דקות ב**כל** משחק, כולל
במשחקים שבהם שחקן נעדר. אם שחקן זמין ב-80% מהמשחקים ומשחק 32
דקות בכל אחד מהם, תרומתו הממוצעת לעונה היא 25.6 דקות — והשאר
חייבות להיות משוחקות על ידי מישהו.

לכן משתנה ההחלטה מוגדר מחדש:

    e(i) = דקות **צפויות לאורך העונה**  (ולא דקות במשחק שבו שיחק)

    max  Σ ppm(i)·e(i)
         Σ e(i) <= 200
         e(i)   <= 32·avail(i)·x(i)

עכשיו המטרה זהה לניקוד באופן מדויק, וה-LP מונוטוני באילוץ.

⚠️ **זו החלטת מודל, לא תיקון סינטקטי.** היא משנה את הסגל שהמנוע
בוחר: שחקן פגיע נעשה פחות אטרקטיבי, כי התקרה שלו מתכווצת. זה
הכיוון הנכון — אבל הוא כיוון, ולכן שתי הגרסאות רצות זו לצד זו
ומדווחות יחד.

הרצה:
    python src/optimise_consistent.py
"""

import io
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pulp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster_optimizer as ro
import optimizer_backtest as ob
from roster_membership_audit import score_rows

SEP = "=" * 78


def optimise_v2(pool, budget, min_roster, locked=None, budget_offset=0.0):
    """זהה ל-ro.optimise פרט להגדרת משתנה הדקות.

    e(i) הן דקות צפויות לעונה: e(i) <= 32·avail(i)·x(i),
    והמטרה היא Σ ppm(i)·e(i) — בלי הכפלה נוספת בזמינות, כי היא
    כבר בתוך התקרה. זהה בדיוק ל-score_rows.
    """
    n = len(pool)
    p = pulp.LpProblem("roster_v2", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(n)]
    e = [pulp.LpVariable(f"e{i}", lowBound=0) for i in range(n)]
    ppm = pool.ppm.values
    av = pool.avail.values
    cost = pool.cost.values

    p += pulp.lpSum(ppm[i] * e[i] for i in range(n))
    p += pulp.lpSum(e) <= ro.MINUTES_PER_GAME
    for i in range(n):
        p += e[i] <= ro.MAX_MIN_PLAYER * av[i] * x[i]
    p += pulp.lpSum(cost[i] * x[i]
                    for i in range(n)) <= budget - budget_offset
    for i in (locked or []):
        p += x[i] == 1
    p += pulp.lpSum(x) <= ro.MAX_ROSTER
    p += pulp.lpSum(x) >= min_roster
    for ps_, fl in ro.POS_FLOOR.items():
        idx = pool.index[pool.position == ps_]
        p += pulp.lpSum(x[i] for i in idx) >= fl
        p += pulp.lpSum(e[i] for i in idx) <= \
            ro.POS_MAX_SHARE[ps_] * ro.MINUTES_PER_GAME
        p += pulp.lpSum(e[i] for i in idx) >= \
            ro.POS_MIN_SHARE[ps_] * ro.MINUTES_PER_GAME

    p.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[p.status] != "Optimal":
        return None, None
    sel = np.array([x[i].value() > 0.5 for i in range(n)])
    mins = np.array([e[i].value() or 0.0 for i in range(n)])
    return sel, mins


def monotone_check(cand, budget, repl, label, fn):
    print(f"\n  {label}")
    print(f"  {'mr':>4}{'n':>4}{'ניקוד מודל':>12}{'ניקוד מציאות':>14}"
          f"{'דקות':>9}")
    prev, viol = None, 0
    for mr in range(7, 17):
        sel, mins = fn(cand, budget, mr)
        if sel is None:
            print(f"  {mr:>4}   אין פתרון")
            continue
        r = cand[sel]
        qp, used, _ = score_rows(r, "ppm", "avail", repl)
        qt, _, _ = score_rows(r, "ppm_true", "avail_true", repl)
        bad = prev is not None and qp > prev + 1e-6
        viol += bad
        print(f"  {mr:>4}{len(r):>4}{qp:>12.1f}{qt:>14.1f}{used:>9.1f}"
              + ("   🔴 עלה" if bad else ""))
        prev = qp
    print(f"  -> הפרות מונוטוניות: {viol}")
    return viol


def main():
    print(SEP)
    print("יישור פונקציית המטרה לפונקציית הניקוד")
    print(SEP)

    import club_rosters as cr
    feat, anch, pos, ps = ob.load_all()
    ob.TRAIN_MAX, ob.TEST, ob.TARGET_CLUB = 2023, 2024, "TEL"
    with contextlib.redirect_stdout(io.StringIO()):
        cm, smear, agg, am, pm, PF, lagged = ob.fit_models(ps, feat, anch)
        cand = ob.build(lagged, feat, pos, cm, smear, agg, am, pm, PF,
                        ob.scale_for(anch, "TEL", 2024))
    cand["ppm_true"] = cand.pir_per_game / cand.min_per_game
    cand["avail_true"] = cand.frac
    r = cr.roster_df("TEL", 2024)
    B = float(r.salary.dropna().sum())
    repl = 0.127

    print(f"\n  TEL 2024 · תקציב {B:,.0f} · רמת מחליף {repl}")
    v1 = monotone_check(cand, B, repl, "גרסה נוכחית (ro.optimise)",
                        lambda c, b, m: ro.optimise(c, b, m))
    v2 = monotone_check(cand, B, repl, "גרסה מיושרת (optimise_v2)",
                        lambda c, b, m: optimise_v2(c, b, m))

    print(f"\n{SEP}")
    if v2 == 0 and v1 > 0:
        print("  ✅ היישור פתר את אי-המונוטוניות. המטרה והניקוד")
        print("     הם עכשיו אותה פונקציה, וסווייפ העומק תקף.")
    elif v2 > 0:
        print("  🔴 עדיין יש הפרות — היישור אינו מלא. לא לדווח סווייפ.")
    print(SEP)


if __name__ == "__main__":
    main()
