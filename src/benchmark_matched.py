"""
benchmark_matched.py  (Day 7)
-----------------------------
ההשוואה מול המועדון, כששני הצדדים מוגדרים במפורש.

--------------------------------------------------------------------
מה תיקן הקובץ הזה
--------------------------------------------------------------------
roster_membership_audit הראה שהבנצ'מרק של מכבי 2024 חסר חמישה
מתוך שנים-עשר עוגני השכר — ובהם ג'יילן הורד (30.6 דק', 17.5 PIR)
ולוויי רנדולף (27.7 דק', 12.2 PIR), שני בעלי הדקות הגבוהות ביותר
במועדון. הם נשרו מהמאגר כי **אין להם עונת יורוליג קודמת**, ולכן
אין להם pir_lag.

זו אינה תקלת דאטה. זו הגדרה של הבעיה:

    האופטימייזר יכול לבחור **רק** שחקנים ששיחקו ביורוליג
    בעונה הקודמת. מכבי לא הייתה כפופה לאילוץ הזה.

לכן יש שתי השוואות תקפות, והן אומרות דברים שונים:

  **מוגבל-מאגר** — המועדון מצומצם לשחקנים שהיו בהישג ידו של
    המנוע, והתקציב הוא השכר שלהם בלבד. שואל: *בהינתן אותה
    קבוצת מועמדים ואותו כסף, מי מקצה טוב יותר?*

  **מלא** — המועדון בסגלו האמיתי, והתקציב הוא כל השכר.
    שואל: *האם המנוע היה מנצח את המועדון בעולם האמיתי?*
    כאן המנוע נושא מגבלה שהמועדון לא נשא, וזה נאמר במפורש.

לדווח רק את הראשונה זה לנפח את המנוע. לדווח רק את השנייה זה
להאשים אותו במגבלה שהיא של הדאטה. שתיהן מודפסות.

הרצה:
    python src/benchmark_matched.py
"""

import io
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR
import roster_optimizer as ro
import optimizer_backtest as ob
from roster_membership_audit import score_rows

SCENARIOS = [("TEL", 2023, 2024), ("HTA", 2024, 2025)]
SEP = "=" * 78


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def best_roster(cand, budget):
    """הסגל הטוב ביותר לפי המודל, על פני כל גדלי הסגל האפשריים.

    הבחירה נעשית **לפי המודל בלבד** — לפי ppm ו-avail החזויים.
    לבחור לפי הניקוד האמיתי זה להציץ בעונת המבחן, וזה היה הופך
    את כל הבקטסט לחסר ערך.
    """
    best = None
    for mr in range(6, 17):
        sel, mins = ro.optimise(cand, budget, mr)
        if sel is None:
            continue
        r = cand[sel]
        qp, _, _ = score_rows(r, "ppm", "avail",
                              float(np.percentile(cand.ppm.values,
                                                  ro.REPLACEMENT_PCTL)))
        if best is None or qp > best[0]:
            best = (qp, r)
    return best


def run(club, train_max, test, feat, anch, pos, ps, posmap):
    ob.TRAIN_MAX, ob.TEST, ob.TARGET_CLUB = train_max, test, club
    with contextlib.redirect_stdout(io.StringIO()):
        cm, smear, agg, am, pm, PF, lagged = ob.fit_models(ps, feat, anch)
        cand = ob.build(lagged, feat, pos, cm, smear, agg, am, pm, PF,
                        ob.scale_for(anch, club, test))
    cand["ppm_true"] = cand.pir_per_game / cand.min_per_game
    cand["avail_true"] = cand.frac

    a = anch[(anch.club == club) & (anch.season == test)]
    acodes = set(a.player_code.dropna().astype(str))
    in_cand = set(cand.player_code.astype(str))

    gmax = float(ps[ps.season == test].games.max())
    sr = ps[(ps.season == test) & (ps.min_per_game > 0)].copy()
    sr["pc"] = sr.player_code.astype(str)
    sr["ppm_true"] = sr.pir_per_game / sr.min_per_game
    sr["avail_true"] = sr.games / gmax
    sr["position"] = sr.pc.map(posmap)

    rt = float(np.percentile(cand.ppm_true.values, ro.REPLACEMENT_PCTL))
    rp = float(np.percentile(cand.ppm.values, ro.REPLACEMENT_PCTL))

    # --- שני הבנצ'מרקים ---
    club_pool = cand[cand.player_code.astype(str).isin(acodes)]
    club_full = sr[sr.pc.isin(acodes) & sr.position.notna()]

    B_pool = float(a[a.player_code.astype(str).isin(in_cand)].salary_mid.sum())
    B_full = float(a.salary_mid.sum())

    q_pool, u_pool, _ = score_rows(club_pool, "ppm_true", "avail_true", rt)
    q_full, u_full, _ = score_rows(club_full, "ppm_true", "avail_true", rt)

    lost = a[~a.player_code.astype(str).isin(in_cand)]

    h(f"{club} {test}   (אימון <= {train_max})")
    print(f"  מאגר מועמדים: {len(cand)}  |  עוגני שכר למועדון: {len(a)}  "
          f"|  מהם במאגר: {len(acodes & in_cand)}")
    print(f"  🔴 מחוץ להישג יד המנוע: {len(lost)} שחקנים = "
          f"{float(lost.salary_mid.sum()):,.0f} "
          f"({float(lost.salary_mid.sum()) / B_full:.0%} מהשכר)")
    print(f"  רמת החלפה: מציאות {rt:.4f} | מודל {rp:.4f}")

    rows = []
    for label, bench_q, budget, nb in [
        ("מוגבל-מאגר", q_pool, B_pool, len(club_pool)),
        ("מלא", q_full, B_full, len(club_full)),
    ]:
        best = best_roster(cand, budget)
        if best is None:
            rows.append((label, budget, nb, bench_q, None, None, None, None))
            continue
        qp, r = best
        qt, _, _ = score_rows(r, "ppm_true", "avail_true", rt)
        rows.append((label, budget, nb, bench_q, len(r), qp, qt,
                     qt / bench_q - 1))

    print(f"\n  {'השוואה':<14}{'תקציב':>13}{'n מועדון':>10}{'מועדון':>9}"
          f"{'n מנוע':>8}{'מנוע-מודל':>11}{'מנוע-מציאות':>13}"
          f"{'קללה':>9}{'מול המועדון':>13}")
    out = {}
    for lab, b, nb, bq, nr, qp, qt, adv in rows:
        if nr is None:
            print(f"  {lab:<14}{b:>13,.0f}{nb:>10}{bq:>9.1f}   אין פתרון")
            continue
        print(f"  {lab:<14}{b:>13,.0f}{nb:>10}{bq:>9.1f}{nr:>8}"
              f"{qp:>11.1f}{qt:>13.1f}{qt / qp - 1:>+8.1%}{adv:>+12.1%}")
        out[lab] = dict(budget=b, bench=bq, n=nr, model=qp, real=qt,
                        curse=qt / qp - 1, adv=adv)
    return out


def main():
    print(SEP)
    print("ההשוואה מול המועדון — שני הצדדים מוגדרים במפורש")
    print("הבחירה תמיד לפי המודל. הניקוד תמיד לפי מה שקרה.")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position

    res = {}
    for club, tr, te in SCENARIOS:
        res[club] = run(club, tr, te, feat, anch, pos, ps, posmap)

    h("קריאה")
    for club in res:
        for lab, d in res[club].items():
            print(f"  {club:<5}{lab:<14}מול המועדון {d['adv']:>+7.1%}   "
                  f"קללת המנצח {d['curse']:>+7.1%}")
    print("\n  'קללה' = כמה איבד המנוע במעבר מהמודל למציאות.")
    print("  'מול המועדון' = ניקוד-מציאות של המנוע חלקי זה של המועדון.")
    print("\n  השורה 'מוגבל-מאגר' היא ההשוואה ההוגנת לאלגוריתם.")
    print("  השורה 'מלא' היא ההשוואה ההוגנת למועדון.")
    print(SEP)


if __name__ == "__main__":
    main()
