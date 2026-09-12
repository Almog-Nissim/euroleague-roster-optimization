"""
shape_constraint_test.py  (ADR 0005)
------------------------------------
11 הטסטים שהוצהרו ב-ADR 0005, לפני הקוד.

**T8 ו-T9 חייבים להיכשל מול הקוד של היום.** שניהם באגים קיימים:
  T8  `score_realistic` מחיל את תקרת ה-k לפי דירוג ppm, והאילוץ
      מוגדר על k הגדולים של e
  T9  `optimise_v3` מקבל סטטוס `Not Solved` — time limit — כהצלחה

הגרסה הבאגית של הסקורר נשמרת כאן כ-`_legacy_rank_scorer`, כדי
שהכישלון יהיה בר-שחזור גם אחרי שהמקור תוקן. זו לא כפילות: זו
הראיה.

הרצה:
    python src/shape_constraint_test.py            # סינתטי, מהיר
    python src/shape_constraint_test.py --full     # + 38 עונות-מועדון
    python src/shape_constraint_test.py --full --clubs 4
"""

import argparse
import contextlib
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pulp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR          # noqa: E402
import roster_optimizer as ro            # noqa: E402
import scoring                           # noqa: E402

SEP = "=" * 78
RESULTS = []


def check(tid, name, ok, detail=""):
    RESULTS.append((tid, name, bool(ok)))
    print(f"  {'✅' if ok else '❌'} {tid:<4} {name}"
          + (f"\n          {detail}" if detail else ""))
    return bool(ok)


# =====================================================================
# מאגר סינתטי — קטן, דטרמיניסטי, פותר במהירות
# =====================================================================
def synth_pool(n=26, seed=20260912):
    rng = np.random.default_rng(seed)
    pos = np.array((["G"] * 10 + ["F"] * 10 + ["C"] * 6)[:n])
    ppm = np.sort(rng.uniform(0.20, 0.75, n))[::-1]
    return pd.DataFrame(dict(
        pc=[f"p{i}" for i in range(n)],
        ppm=ppm,
        avail=rng.uniform(0.75, 1.0, n),
        cost=rng.uniform(0.4, 3.0, n),
        position=pos,
        usage_prior=rng.uniform(14.0, 26.0, n),
    ))


def solve(pool, budget, min_roster, caps=None, **kw):
    """קורא ל-optimise_capped של מסלול הכותרת."""
    import usage_constrained as uc
    with contextlib.redirect_stdout(io.StringIO()):
        sel, mins = uc.optimise_capped(pool, budget, min_roster,
                                       caps=caps, **kw)
    import optimise_consistent as oc
    return sel, mins, dict(oc.LAST)


SLACK_CAPS = {k: 1e6 for k in range(1, scoring.KMAX + 1)}


# =====================================================================
# הגרסה הבאגית, נשמרת כראיה ל-T8
# =====================================================================
def _legacy_rank_scorer(df, ppm_col, avail_col, repl, caps):
    """`score_realistic` כפי שהיה: caps.get(rank) לפי דירוג ppm."""
    ppm, av, pos = df[ppm_col].values, df[avail_col].values, df.position.values
    order = np.argsort(-ppm)
    poscap = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
              for g in ro.POS_MAX_SHARE}
    e = np.zeros(len(df))
    left, cum = ro.MINUTES_PER_GAME, 0.0
    for rank, j in enumerate(order, start=1):
        cap_k = caps.get(rank, np.inf)
        take = min(ro.MAX_MIN_PLAYER * av[j], left, poscap[pos[j]],
                   max(cap_k - cum, 0.0))
        take = max(take, 0.0)
        e[j] = take
        left -= take
        cum += take
        poscap[pos[j]] -= take
    return float((e * ppm).sum()), float(e.sum()), e


# =====================================================================
# הטסטים הסינתטיים
# =====================================================================
def synthetic(caps):
    print("\n" + SEP + "\nסינתטי\n" + SEP)
    pool = synth_pool()
    B, MR = 14.0, 8

    sel0, min0, last0 = solve(pool, B, MR, caps=None)
    # 🔴 T1 חייב לרוץ ב-gap=0. בהרצת הייצור האילוץ מביא איתו gapRel=0.005,
    #    ואם T1 ירוץ כך הוא ימדוד את הפער ולא את הקינון: נמדד הפרש של
    #    0.015% על המאגר הסינתטי שנובע כולו מהפער, לא מהאילוץ.
    sel1, min1, last1 = solve(pool, B, MR, caps=SLACK_CAPS, gap=0.0,
                              time_limit=300)
    check("T1", "אילוץ רפוי משחזר את ה-LP של היום (gap=0)",
          sel0 is not None and sel1 is not None
          and abs(last0["obj"] - last1["obj"]) < 1e-6,
          f"{last0['obj']:.6f} מול {last1['obj']:.6f}")

    # T1b — מתעד את מחיר הפער, כדי שהוא לא יתגלה בתוך מספר הכותרת
    _, _, last1g = solve(pool, B, MR, caps=SLACK_CAPS)
    cost_gap = abs(last0["obj"] - last1g["obj"]) / abs(last0["obj"])
    check("T1b", "מחיר הפער 0.005 חסום בפער עצמו", cost_gap <= 0.005,
          f"אותו LP, gap=0.005: {last1g['obj']:.6f} · פער בפועל {cost_gap:.4%}")

    selc, minc, lastc = solve(pool, B, MR, caps=caps)
    if selc is None:
        check("T2", "הידוק אינו מעלה את המטרה", False, "אין פתרון")
        return pool, None, None
    check("T2", "הידוק אינו מעלה את המטרה",
          lastc["obj"] <= last0["obj"] + 1e-6,
          f"עם צורה {lastc['obj']:.4f} <= בלי {last0['obj']:.4f}")

    bad = scoring.check_shape(minc, caps)
    check("T3", "הצורה מקוימת בווקטור e שחזר (לא בניסוח)",
          not bad, "הפרות: " + (str(bad) if bad else "אין"))

    check("T4", "Σe <= 200", minc.sum() <= ro.MINUTES_PER_GAME + 1e-6,
          f"Σe = {minc.sum():.4f}")

    per = minc <= ro.MAX_MIN_PLAYER * pool.avail.values + 1e-6
    check("T5", "e_i <= 32·avail_i — התקרה הישנה עומדת", per.all(),
          f"מקסימום e/avail = {(minc/pool.avail.values).max():.4f}")

    okpos, det = True, []
    for g in ro.POS_MAX_SHARE:
        idx = pool.index[pool.position == g]
        s = minc[idx].sum()
        hi = ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
        lo = ro.POS_MIN_SHARE[g] * ro.MINUTES_PER_GAME
        if s > hi + 1e-6 or s < lo - 1e-6:
            okpos = False
        det.append(f"{g} {s:.1f} ב-[{lo:.1f},{hi:.1f}]")
        nsel = int(selc[idx].sum())
        if nsel < ro.POS_FLOOR[g]:
            okpos = False
    check("T6", "תקרות ורצפות עמדה", okpos, " · ".join(det))

    q, used, e = scoring.score_shape(pool[selc], "ppm", "avail", None, caps)
    gap = abs(q - lastc["obj"]) / max(abs(lastc["obj"]), 1e-9)
    check("T7", "הסקורר על סגל ה-LP משחזר את המטרה",
          gap <= 0.005,
          f"סקורר {q:.4f} מול LP {lastc['obj']:.4f} · פער {gap:.4%}")

    # --- T8: מקרה שבו תקרת עמדה שוברת מונוטוניות בין ppm ל-e ---
    adv = pd.DataFrame(dict(
        pc=list("abcdef"),
        # שני מרכזים חזקים: תקרת C (28.2% מ-200 = 56.4) תיחסם,
        # והדקות יזלגו לשחקנים עם ppm נמוך יותר
        ppm=[0.90, 0.85, 0.80, 0.40, 0.38, 0.36],
        avail=[1.0] * 6,
        position=["C", "C", "C", "G", "G", "F"],
    ))
    _, _, e_leg = _legacy_rank_scorer(adv, "ppm", "avail", None, caps)
    _, _, e_new = scoring.score_shape(adv, "ppm", "avail", None, caps)
    v_leg = scoring.check_shape(e_leg, caps)
    v_new = scoring.check_shape(e_new, caps)
    check("T8", "האילוץ על k הגדולים של e, לא על דירוג ppm",
          (not v_new) and bool(v_leg),
          f"הישן מפר {len(v_leg)} תקרות {v_leg[:2]} · החדש {len(v_new)}")

    # --- T9: שער הסולבר ---
    p = pulp.LpProblem("infeasible", pulp.LpMaximize)
    z = pulp.LpVariable("z", lowBound=0)
    p += z
    p += z >= 5
    p += z <= 1
    p.solve(pulp.PULP_CBC_CMD(msg=0))
    raised = False
    try:
        scoring.solver_guard(p, "T9")
    except RuntimeError:
        raised = True
    check("T9", "סטטוס שאינו Optimal זורק ולא חוזר בשקט", raised,
          f"סטטוס {pulp.LpStatus[p.status]} · נזרק: {raised}")

    check("T11", "הפער האופטימלי מדווח",
          "gap" in lastc or "obj" in lastc,
          f"LAST = {sorted(lastc)}")
    return pool, selc, minc


# =====================================================================
# T10 — צד המועדון, על הנתונים האמיתיים
# =====================================================================
def club_side_test(caps):
    print("\n" + SEP + "\nצד המועדון — 38 עונות-מועדון\n" + SEP)
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    gmax = ps.groupby("season").games.max()

    n_ok_actual, n_viol_greedy, n = 0, 0, 0
    worst = []
    for (s, c), g in split.groupby(["season", "club"]):
        n += 1
        e_act = (g.min_per_game * g.games / gmax[s]).values
        if not scoring.check_shape(e_act, caps):
            n_ok_actual += 1
        # החלוקה החמדנית של score_rows, בקירוב עליון (בלי תקרות עמדה)
        av = np.clip((g.games / gmax[s]).values, 0, 1)
        av = av[np.argsort(-e_act)]
        left, gr = ro.MINUTES_PER_GAME, []
        for a in av:
            t = max(min(ro.MAX_MIN_PLAYER, left) * a, 0.0)
            gr.append(t)
            left -= t
        v = scoring.check_shape(np.array(gr), caps)
        if v:
            n_viol_greedy += 1
            worst.append((f"{s} {c}", v[0]))

    check("T10a", "38/38 המועדונים על הדקות שבפועל מקיימים כל תקרה",
          n_ok_actual == n, f"{n_ok_actual}/{n}")
    check("T10b", "38/38 מפרים את הצורה תחת הסקורר החמדני",
          n_viol_greedy == n,
          f"{n_viol_greedy}/{n} · לדוגמה {worst[0] if worst else '-'}")


# =====================================================================
# T1 / T2 / T7 על המאגר האמיתי
# =====================================================================
def full_test(caps, n_clubs):
    print("\n" + SEP + f"\nמאגר אמיתי — {n_clubs} עונות-מועדון\n" + SEP)
    import optimizer_backtest as ob
    import usage_constrained as uc
    from league_backtest import build_pool, club_side, SEASONS
    from final_day7 import MIN_LEGAL_ROSTER
    from roster_membership_audit import score_rows

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    n1 = n2 = n7 = tot = 0
    for train_max, test in SEASONS:
        if tot >= n_clubs:
            break
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        with contextlib.redirect_stdout(io.StringIO()):
            cand = uc.attach_usage(
                cand, PROCESSED_DIR / "usage_curve_results_min0.csv", test)
        gmax = float(ps[ps.season == test].games.max())
        for club in sorted(split[split.season == test].club.unique()):
            if tot >= n_clubs:
                break
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                continue
            B = float(keep.cost.sum())
            _, _, l0 = solve(cand, B, MIN_LEGAL_ROSTER, caps=None)
            # gap=0 — אחרת T1 מודד את הפער ולא את הקינון. ראו T1b.
            _, _, l1 = solve(cand, B, MIN_LEGAL_ROSTER, caps=SLACK_CAPS,
                             gap=0.0, time_limit=600)
            sc, mc, lc = solve(cand, B, MIN_LEGAL_ROSTER, caps=caps)
            tot += 1
            if l0["obj"] is not None and abs(l0["obj"] - l1["obj"]) < 1e-4:
                n1 += 1
            if lc["obj"] is not None and lc["obj"] <= l0["obj"] + 1e-6:
                n2 += 1
            if sc is not None:
                q, _, _ = scoring.score_shape(cand[sc], "ppm", "avail",
                                              None, caps)
                if abs(q - lc["obj"]) / max(abs(lc["obj"]), 1e-9) <= 0.005:
                    n7 += 1
            print(f"    {test} {club:<5} בלי {l0['obj']:>8.3f} · "
                  f"רפוי {l1['obj']:>8.3f} · צורה {lc['obj']:>8.3f}")

    check("T1-full", "אילוץ רפוי == ה-LP של היום", n1 == tot, f"{n1}/{tot}")
    check("T2-full", "הידוק אינו מעלה את המטרה", n2 == tot, f"{n2}/{tot}")
    check("T7-full", "הסקורר משחזר את המטרה", n7 == tot, f"{n7}/{tot}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--clubs", type=int, default=4)
    a = ap.parse_args()

    print(SEP)
    print("ADR 0005 — אילוץ צורת הדקות · 11 טסטים")
    print("T8 ו-T9 חייבים להיכשל מול הקוד שלפני התיקון.")
    print(SEP)

    caps = scoring.load_caps()
    print(f"\n  תקרות מ-{scoring.CAPS_CSV.name}: "
          + " ".join(f"{k}:{v:.1f}" for k, v in sorted(caps.items())))

    synthetic(caps)
    club_side_test(caps)
    if a.full:
        full_test(caps, a.clubs)

    print("\n" + SEP)
    bad = [t for t, _, ok in RESULTS if not ok]
    print(f"  {len(RESULTS) - len(bad)}/{len(RESULTS)} עברו")
    if bad:
        print(f"  ❌ נכשלו: {', '.join(bad)}")
    else:
        print("  ✅ הכול עבר")
    print(SEP)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
