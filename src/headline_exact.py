"""
headline_exact.py  (ADR 0006, follow-up)
----------------------------------------
הכותרת בלי פער אופטימליות. קיים כי אותו חישוב על אותו דאטה נתן
C = 0.1205 ואחר כך 0.1235 — הפער המוצהר 0.5% ו-CBC לא-דטרמיניסטי.
תוכנית הסגירה דורשת מספר סופי, ומספר שזז בין הרצות זהות אינו סופי.

מה נפתר מחדש, ומה לא
--------------------
    נפתר   : ה-LP המאולץ **עם** אילוץ הצורה, ב-gap = 0. 38 פתרונות.
    לא     : ה-LP בלי צורה. הוא דטרמיניסטי (תא A שוחזר בדיוק פעמיים),
             ווקטורי הדקות שלו כבר ב-shape_minutes.csv. שם גם יושבת
             הגרלת זמן הריצה — PAM 30,894 שניות, TEL 40,332.

guard של "מדויק"
----------------
    כל פתרון: sol_status == 1 (הוכח אופטימלי), לא 2 (אפשרי בלבד).
    `LpStatus == "Optimal"` אינו מספיק: CBC שנעצר על timeLimit עם
    פתרון אפשרי מדווח גם הוא Optimal. אם אחד לא הוכח — הכותרת אינה
    נטענת כמדויקת, ומדווח מי.

התחזיות ננעלו ב-ADR 0006, סעיף "Follow-up", לפני ההרצה.

הרצה:  python src/headline_exact.py
"""

from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import optimizer_backtest as ob                                # noqa: E402
import optimise_consistent as oc                               # noqa: E402
import scoring                                                 # noqa: E402
from paths import PROCESSED_DIR                                # noqa: E402
from roster_membership_audit import score_rows                 # noqa: E402
from usage_constrained import optimise_capped, attach_usage    # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER                       # noqa: E402
from league_backtest import build_pool, club_side, REPL, SEASONS  # noqa: E402

SEP = "=" * 78
TIME_LIMIT = 1800
USAGE_CSV = PROCESSED_DIR / "usage_curve_results_min0.csv"
PREV = PROCESSED_DIR / "usage_constrained_shape.csv"
OUT = PROCESSED_DIR / "headline_exact.csv"

# ננעלו ב-ADR 0006 לפני ההרצה
PRED_F = (0.184, 0.194)
PRED_DELTA = 0.005


def main() -> int:
    print(SEP)
    print("headline_exact — הכותרת ב-gap=0 · ADR 0006 follow-up")
    print(f"timeLimit {TIME_LIMIT}s לפתרון · guard: sol_status == 1")
    print(SEP, flush=True)

    caps = scoring.load_caps()
    prev = pd.read_csv(PREV).set_index(["season", "club"])
    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    rows, t0 = [], time.time()
    for train_max, test in SEASONS:
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        with contextlib.redirect_stdout(io.StringIO()):
            cand = attach_usage(cand, USAGE_CSV, test)
        gmax = float(ps[ps.season == test].games.max())
        clubs = sorted(split[split.season == test].club.unique())
        print(f"\n  עונה {test} — {len(clubs)} מועדונים", flush=True)
        print(f"  {'מועדון':<7}{'F מדויק':>10}{'F בפער':>10}{'Δ':>9}"
              f"{'status':>8}{'שנ':>7}", flush=True)

        for club in clubs:
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                continue
            keep = keep.copy()
            keep["min_actual"] = keep.min_per_game * keep.avail_true
            B = float(keep.cost.sum())

            q_greedy, _, _ = score_rows(keep, "ppm_true", "avail_true", REPL)
            q_actual, _, _ = scoring.score_actual(
                keep, "ppm_true", "min_actual", REPL)

            t1 = time.time()
            sel, mins = optimise_capped(cand, B, MIN_LEGAL_ROSTER, caps=caps,
                                        gap=0.0, time_limit=TIME_LIMIT)
            secs = time.time() - t1
            last = dict(oc.LAST)
            if sel is None:
                print(f"  {club:<7} ❌ אין פתרון ({last.get('status')})",
                      flush=True)
                rows.append(dict(season=test, club=club, secs=secs,
                                 status=last.get("status"), sol_status=-1))
                continue

            q_plan, _, e, clipped = scoring.score_planned(
                cand[sel], "ppm_true", "avail_true", mins[sel], REPL)
            F = q_plan / q_actual - 1
            E = q_plan / q_greedy - 1
            F_prev = float(prev.loc[(test, club), "adv_cap_F_shape"])
            ok = last.get("sol_status") == 1
            rows.append(dict(
                season=test, club=club, budget=B, secs=secs,
                status=last.get("status"), sol_status=last.get("sol_status"),
                lp_obj=last.get("obj"), q_plan=q_plan, q_club_actual=q_actual,
                q_club_greedy=q_greedy, adv_F_exact=F, adv_E_exact=E,
                adv_F_gap=F_prev, clipped=clipped, n=int(sel.sum())))
            print(f"  {club:<7}{F:>+10.2%}{F_prev:>+10.2%}{F-F_prev:>+9.2%}"
                  f"{'✅' if ok else '⚠️ 2':>8}{secs:>7.0f}", flush=True)
            pd.DataFrame(rows).to_csv(OUT, index=False)     # מצטבר

    d = pd.DataFrame(rows)
    d.to_csv(OUT, index=False)
    print(f"\n  זמן כולל: {(time.time()-t0)/60:.1f} דקות")

    print("\n" + SEP + "\nהתוצאה\n" + SEP)
    solved = d[d.sol_status.notna() & (d.sol_status != -1)]
    proven = int((d.sol_status == 1).sum())
    F_med = float(solved.adv_F_exact.median())
    E_med = float(solved.adv_E_exact.median())
    F_gap = float(solved.adv_F_gap.median())
    delta = F_med - F_gap
    win = float((solved.adv_F_exact > 0).mean())
    print(f"  adv_cap · F_shape מדויק : {F_med:.4f}")
    print(f"  adv_cap · E_shape מדויק : {E_med:.4f}")
    print(f"  מול ההרצה בפער 0.5%     : {F_gap:.4f}   Δ {delta:+.4f}")
    print(f"  שיעור ניצחון            : {win:.0%}  ({int((solved.adv_F_exact>0).sum())}/{len(solved)})")
    print(f"  זמן: חציון {d.secs.median():.0f}s · מקסימום {d.secs.max():.0f}s")

    print("\n" + SEP + "\nguards\n" + SEP)
    g1 = proven == len(d)
    g2 = len(solved) == 38
    print(f"  {'✅' if g1 else '❌'} כל הפתרונות הוכחו אופטימליים: {proven}/{len(d)}")
    if not g1:
        bad = d[d.sol_status != 1][["season", "club", "sol_status", "secs"]]
        print("     לא הוכחו — הכותרת **אינה** נטענת כמדויקת:")
        print(bad.to_string(index=False))
    print(f"  {'✅' if g2 else '❌'} 38 עונות-מועדון נפתרו: {len(solved)}")

    print("\n" + SEP + "\nמול התחזיות שננעלו\n" + SEP)
    preds = [
        ("F_shape מדויק", F_med, PRED_F, lambda v, r: r[0] <= v <= r[1]),
        ("|Δ| מול הרצת הפער", abs(delta), (0, PRED_DELTA),
         lambda v, r: v <= r[1]),
        ("פתרונות שנגעו ב-1800s", float((d.secs >= TIME_LIMIT - 5).sum()),
         (0, 0), lambda v, r: v == 0),
        ("שיעור ניצחון", win, (1.0, 1.0), lambda v, r: v == 1.0),
    ]
    for name, v, r, f in preds:
        print(f"  {'✅' if f(v, r) else '❌'} {name:<24} {r} -> {v:.4f}")

    print(f"\n  נשמר: {OUT}")
    return 0 if (g1 and g2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
