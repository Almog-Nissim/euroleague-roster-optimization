"""
slack_sensitivity.py  (ADR 0005 run matrix b, מבוצע אחרי v1.0)
---------------------------------------------------------------
רגישות הכותרת למכפיל התקרות SLACK. **מדווחת, לא נבחרת** — SLACK=1.00
הוא הספציפיקציה (ADR 0005), והיא לא תשתנה לפי מה שיצא כאן.

סטייה מהמטריצה שהוצהרה ב-ADR 0005, מוצהרת לפני ההרצה
----------------------------------------------------
ADR 0005 הצהיר על `shape_run --slack`. מאז הכותרת עברה ל-ADR 0006,
וה-code review מצא ש-`--slack` שם (1) דורס את קבצי הכותרת המקומטים
בתת-מדגם, (2) מדווח את תאי C/D המחולקים-בדיעבד ולא את תא F, (3) פותר
בפער 0.5% — שההרצה המדויקת הראתה שמזיז עונת-מועדון בודדת עד 14 נקודות,
יותר מהאפקט שנמדד כאן, ו-(4) פותר גם את ה-LP בלי צורה, שם יושבת
הגרלת זמן הריצה (PAM, 8.6 שעות, נמצא בתת-המדגם).

לכן כאן: רק ה-LP המאולץ עם הצורה, gap=0, timeLimit 1800, guard על
sol_status==1, על 12 עונות-המועדון שהוצהרו, ניקוד לפי ADR 0006 (תא F).
SLACK=1.00 אינו נפתר שוב — הערך המדויק שלו הוא headline_exact.csv.

כלל, הוצהר לפני ההרצה
---------------------
    |Δ חציון F| ≤ 0.02 בשני המכפילים   ->  הכותרת עמידה ל-SLACK
    אחרת                                 ->  מדווח ב-caveat, לא בוחר
    פתרון שלא הוכח (sol_status≠1)         ->  מדווח בשמו, לא נספר

הרצה:  python src/slack_sensitivity.py
"""

from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import optimizer_backtest as ob                                # noqa: E402
import optimise_consistent as oc                               # noqa: E402
import scoring                                                 # noqa: E402
from paths import PROCESSED_DIR                                # noqa: E402
from usage_constrained import optimise_capped, attach_usage    # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER                       # noqa: E402
from league_backtest import build_pool, club_side, REPL, SEASONS  # noqa: E402
from shape_run import SUBSAMPLE_12                             # noqa: E402

SEP = "=" * 78
TIME_LIMIT = 1800
SLACKS = (0.95, 1.05)
USAGE_CSV = PROCESSED_DIR / "usage_curve_results_min0.csv"
BASE = PROCESSED_DIR / "headline_exact.csv"
OUT = PROCESSED_DIR / "shape_slack_sensitivity.csv"
ROBUST = 0.02

# ננעל לפני ההרצה. חציון F על 12 עונות-המועדון; ב-1.00 הוא 0.1385.
PRED = {
    "claude": {0.95: (0.118, 0.1385), 1.05: (0.1385, 0.158)},
    # אלמוג: "הידוק יורד בטיפה יותר מ-0.02, ריפוי עולה בטיפה יותר מ-0.02"
    "almog": {0.95: (0.1085, 0.1185), 1.05: (0.1585, 0.1685)},
}


def main() -> int:
    print(SEP)
    print("slack_sensitivity — הכותרת (תא F) מול מכפיל התקרות · gap=0")
    print(SEP, flush=True)

    base_caps = scoring.load_caps()
    base = pd.read_csv(BASE).set_index(["season", "club"])
    want = set(SUBSAMPLE_12)
    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    rows, t0 = [], time.time()
    for train_max, test in SEASONS:
        clubs = sorted(c for (s, c) in want if s == test)
        if not clubs:
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
            cand = attach_usage(cand, USAGE_CSV, test)
        gmax = float(ps[ps.season == test].games.max())
        print(f"\n  עונה {test}: {', '.join(clubs)}", flush=True)
        for club in clubs:
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            keep = keep.copy()
            keep["min_actual"] = keep.min_per_game * keep.avail_true
            B = float(keep.cost.sum())
            q_actual, _, _ = scoring.score_actual(
                keep, "ppm_true", "min_actual", REPL)
            b = base.loc[(test, club)]
            for sl in SLACKS:
                caps = scoring.slack_caps(base_caps, sl)
                t1 = time.time()
                try:
                    sel, mins = optimise_capped(
                        cand, B, MIN_LEGAL_ROSTER, caps=caps,
                        gap=0.0, time_limit=TIME_LIMIT)
                    err = None
                except RuntimeError as exc:          # sol_status == 2
                    sel, mins, err = None, None, str(exc)
                secs = time.time() - t1
                last = dict(oc.LAST)
                if sel is None:
                    print(f"  {club:<5} SLACK {sl:.2f}  ❌ "
                          f"{err or last.get('status')}", flush=True)
                    rows.append(dict(season=test, club=club, slack=sl,
                                     secs=secs, sol_status=last.get("sol_status"),
                                     proven=False))
                    continue
                q_plan, _, _, clipped = scoring.score_planned(
                    cand[sel], "ppm_true", "avail_true", mins[sel], REPL)
                F = q_plan / q_actual - 1
                rows.append(dict(
                    season=test, club=club, slack=sl, secs=secs,
                    sol_status=last.get("sol_status"),
                    proven=last.get("sol_status") == 1,
                    lp_obj=last.get("obj"), lp_obj_base=float(b.lp_obj),
                    adv_F=F, adv_F_base=float(b.adv_F_exact),
                    clipped=clipped, n=int(sel.sum())))
                print(f"  {club:<5} SLACK {sl:.2f}  F {F:+.2%}  "
                      f"(1.00: {b.adv_F_exact:+.2%})  "
                      f"{'✅' if last.get('sol_status') == 1 else '❌'}  "
                      f"{secs:.0f}s", flush=True)
                pd.DataFrame(rows).to_csv(OUT, index=False)   # מצטבר

    d = pd.DataFrame(rows)
    d.to_csv(OUT, index=False)
    print(f"\n  זמן כולל: {(time.time()-t0)/60:.1f} דקות")

    print("\n" + SEP + "\nהתוצאה — חציון F על 12 עונות-המועדון\n" + SEP)
    base12 = float(base.loc[[k for k in base.index if k in want],
                            "adv_F_exact"].median())
    print(f"  SLACK 1.00   {base12:.4f}   (headline_exact, לא נפתר שוב)")
    med = {}
    for sl in SLACKS:
        g = d[(d.slack == sl) & d.proven]
        med[sl] = float(g.adv_F.median()) if len(g) else float("nan")
        print(f"  SLACK {sl:.2f}   {med[sl]:.4f}   Δ {med[sl]-base12:+.4f}   "
              f"הוכחו {len(g)}/12 · ניצחון {int((g.adv_F>0).sum())}/{len(g)}")

    print("\n" + SEP + "\nguards\n" + SEP)
    proven = int(d.proven.sum())
    g1 = proven == len(SLACKS) * 12
    print(f"  {'✅' if g1 else '❌'} כל הפתרונות הוכחו: {proven}/{len(SLACKS)*12}")
    ok = d[d.proven]
    mono = (((ok.slack < 1) & (ok.lp_obj <= ok.lp_obj_base + 1e-6))
            | ((ok.slack > 1) & (ok.lp_obj >= ok.lp_obj_base - 1e-6)))
    g2 = bool(mono.all())
    print(f"  {'✅' if g2 else '❌'} ערך המטרה מונוטוני במכפיל (הידוק לא מעלה, "
          f"ריפוי לא מוריד): {int(mono.sum())}/{len(ok)}")

    print("\n" + SEP + "\nהכלל שהוצהר\n" + SEP)
    robust = all(abs(med[s] - base12) <= ROBUST for s in SLACKS)
    print(f"  {'✅ הכותרת עמידה ל-SLACK' if robust else '⚠️ רגיש — מדווח ב-caveat, לא בוחר'}"
          f"  (|Δ| ≤ {ROBUST} בשני המכפילים)")

    print("\n" + SEP + "\nמול התחזיות שננעלו\n" + SEP)
    for who, p in PRED.items():
        if p is None:
            print(f"  —  {who:<7} לא ניתנה תחזית")
            continue
        for sl, (a, b_) in p.items():
            hit = a <= med[sl] <= b_
            print(f"  {'✅' if hit else '❌'} {who:<7} SLACK {sl:.2f} "
                  f"[{a}, {b_}] -> {med[sl]:.4f}")

    print(f"\n  נשמר: {OUT.name}  ·  headline_exact.csv לא נגע")
    return 0 if (g1 and g2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
