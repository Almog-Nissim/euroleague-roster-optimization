"""
shape_run.py  (ADR 0005, שלב 4)
-------------------------------
ההרצה של אילוץ הצורה. **לא** נוגע ב-`usage_constrained_results.csv`:
קו הבסיס המקומט נשאר כמו שהוא, וההרצה מחשבת אותו מחדש בעצמה כ-guard
במקום להשחיל תוצאה חדשה על קובץ ישן.

טבלת ה-2x2 של ADR 0005
----------------------
                        q_club חמדני      q_club בפועל
    LP בלי צורה            תא A               תא B
    LP עם צורה             תא C               תא D

    A  קו הבסיס. חייב לשחזר adv_cap = 0.1414 — זה ה-guard
    B  רק המכנה השתנה
    C  רק ה-LP הידוק. זו הרגישות החד-צדדית של Q1
    D  **הספציפיקציה**

בלי ארבעת התאים אי אפשר לייחס את התזוזה לא למכנה ולא לאילוץ, ושתי
התזוזות בכיוונים מנוגדים.

צד המנוע
--------
    בלי צורה  ->  score_rows      (חמדני, תקרת 32 לשחקן)
    עם צורה   ->  scoring.score_shape  (LP מדויק תחת תקרות הצורה)

צד המועדון
----------
    חמדני     ->  score_rows      — מעניק לשישייה 177.0 במקום 125.7
    בפועל     ->  scoring.score_actual  — הדקות ששוחקו

הרצה:
    python src/shape_run.py                 # a: 38 עונות, 4 תאים
    python src/shape_run.py --slack         # b: רגישות על 12 המוצהרות
    python src/shape_run.py --clubs 4       # חתך קטן לבדיקת שפיות
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import roster_optimizer as ro                                  # noqa: E402
import optimizer_backtest as ob                                # noqa: E402
import optimise_consistent as oc                               # noqa: E402
import scoring                                                 # noqa: E402
from paths import PROCESSED_DIR                                # noqa: E402
from roster_membership_audit import score_rows                 # noqa: E402
from optimise_consistent import optimise_v2                   # noqa: E402
from minute_profile import optimise_v3                        # noqa: E402
from usage_constrained import optimise_capped, attach_usage    # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER                       # noqa: E402
from league_backtest import build_pool, club_side, REPL, SEASONS  # noqa: E402

SEP = "=" * 78
BASELINE_ADV_CAP = 0.1414        # ADR 0005, קו הבסיס המוצהר
USAGE_CSV = PROCESSED_DIR / "usage_curve_results_min0.csv"
OUT_MAIN = PROCESSED_DIR / "usage_constrained_shape.csv"
OUT_BIND = PROCESSED_DIR / "shape_binding.csv"
OUT_SLACK = PROCESSED_DIR / "shape_slack_sensitivity.csv"
OUT_MINS = PROCESSED_DIR / "shape_minutes.csv"

# תת-המדגם שהוצהר ב-ADR 0005 לפני ההרצה, בשמות
SUBSAMPLE_12 = [
    (2024, "MUN"), (2024, "PAR"), (2024, "IST"),
    (2024, "BAR"), (2024, "ZAL"), (2024, "BER"),
    (2025, "MCO"), (2025, "DUB"), (2025, "OLY"),
    (2025, "ULK"), (2025, "PAM"), (2025, "PRS"),
]


def hdr(t):
    print("\n" + SEP + f"\n{t}\n" + SEP, flush=True)


def binding_ks(mins, caps, rtol=1e-4):
    """אילו k נוגעים בתקרה. rtol יחסי, כי הפער האופטימלי 0.5%."""
    cum = scoring.top_k_sums(mins, scoring.KMAX)
    return [k for k in sorted(caps)
            if k <= scoring.KMAX and cum[k - 1] >= caps[k] * (1 - rtol)]


def one_club(cand, keep, caps, B):
    """ארבעת התאים לעונת-מועדון אחת. מחזיר dict או None."""
    r = {}

    # --- שני המכנים ---
    r["q_club_greedy"], _, _ = score_rows(keep, "ppm_true", "avail_true", REPL)
    r["q_club_actual"], r["club_used"], e_act = scoring.score_actual(
        keep, "ppm_true", "min_actual", REPL)
    r["club_top6"] = float(scoring.top_k_sums(e_act, 6)[5])

    # --- LP בלי צורה ---
    # 🔴 זמן לכל פתרון בנפרד. בהרצת ADR 0005 היה מד זמן אחד לארבעה
    #    פתרונות, ולכן ש-2024 TEL אכל 11.2 מ-12.8 השעות אפשר היה לייחס
    #    רק בדרך השלילה. לא שוב.
    _t = time.time()
    sel_f, min_f = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
    r["secs_free"], _t = time.time() - _t, time.time()
    r["lp_free"] = oc.LAST.get("obj", np.nan)
    sel_c, min_c = optimise_capped(cand, B, MIN_LEGAL_ROSTER)
    r["secs_cap"], _t = time.time() - _t, time.time()
    r["lp_cap"] = oc.LAST.get("obj", np.nan)
    if sel_f is None or sel_c is None:
        return None
    r["q_free"], _, _ = score_rows(cand[sel_f], "ppm_true", "avail_true", REPL)
    r["q_cap"], _, _ = score_rows(cand[sel_c], "ppm_true", "avail_true", REPL)
    r["n_free"], r["n_cap"] = int(sel_f.sum()), int(sel_c.sum())
    r["top6_cap"] = float(scoring.top_k_sums(min_c, 6)[5])

    # --- LP עם צורה ---
    # optimise_v3 עם repl=0.0 הוא בדיוק v2 + צורה: המטרה Σ(ppm−0)·e.
    _t = time.time()
    sel_fs, min_fs = optimise_v3(cand, B, MIN_LEGAL_ROSTER, caps, repl=0.0)
    r["secs_free_shape"], _t = time.time() - _t, time.time()
    r["lp_free_shape"] = oc.LAST.get("obj", np.nan)
    sel_cs, min_cs = optimise_capped(cand, B, MIN_LEGAL_ROSTER, caps=caps)
    r["secs_cap_shape"] = time.time() - _t
    r["lp_cap_shape"] = oc.LAST.get("obj", np.nan)
    if sel_fs is None or sel_cs is None:
        return None
    r["q_free_shape"], _, _ = scoring.score_shape(
        cand[sel_fs], "ppm_true", "avail_true", REPL, caps)
    r["q_cap_shape"], _, _ = scoring.score_shape(
        cand[sel_cs], "ppm_true", "avail_true", REPL, caps)
    r["n_free_shape"], r["n_cap_shape"] = int(sel_fs.sum()), int(sel_cs.sum())
    r["top6_cap_shape"] = float(scoring.top_k_sums(min_cs, 6)[5])
    r["bind_free"] = ",".join(map(str, binding_ks(min_fs, caps)))
    r["bind_cap"] = ",".join(map(str, binding_ks(min_cs, caps)))

    # --- ADR 0006: המנוע על הדקות שהוא תכנן, בלי הקצאה מחדש ---
    r["q_cap_plan"], r["plan_used"], e_pl, r["clipped"] = scoring.score_planned(
        cand[sel_c], "ppm_true", "avail_true", min_c[sel_c], REPL)
    r["q_cap_shape_plan"], r["plan_used_shape"], e_pls, r["clipped_shape"] = \
        scoring.score_planned(cand[sel_cs], "ppm_true", "avail_true",
                              min_cs[sel_cs], REPL)
    r["top6_plan_shape"] = float(scoring.top_k_sums(e_pls, 6)[5])

    # --- ארבעת התאים של ADR 0005 ---
    r["adv_cap_A"] = r["q_cap"] / r["q_club_greedy"] - 1
    r["adv_cap_B"] = r["q_cap"] / r["q_club_actual"] - 1
    r["adv_cap_C"] = r["q_cap_shape"] / r["q_club_greedy"] - 1
    r["adv_cap_D"] = r["q_cap_shape"] / r["q_club_actual"] - 1
    r["adv_free_A"] = r["q_free"] / r["q_club_greedy"] - 1
    r["adv_free_D"] = r["q_free_shape"] / r["q_club_actual"] - 1

    # --- ADR 0006: E = מכנה חמדני · F = הספציפיקציה ---
    r["adv_cap_E"] = r["q_cap_plan"] / r["q_club_greedy"] - 1
    r["adv_cap_F"] = r["q_cap_plan"] / r["q_club_actual"] - 1
    r["adv_cap_E_shape"] = r["q_cap_shape_plan"] / r["q_club_greedy"] - 1
    r["adv_cap_F_shape"] = r["q_cap_shape_plan"] / r["q_club_actual"] - 1

    # 🔴 וקטורי הדקות נשמרים הפעם. ADR 0006 נאלץ להריץ 152 פתרונות
    #    מחדש רק כי הם לא נשמרו בהרצה של ADR 0005. לא פעמיים.
    r["_mins"] = [
        dict(side="cap_noshape", pc=str(pc), e_lp=float(a), e_scored=float(b),
             ppm_true=float(c), avail_true=float(d))
        for pc, a, b, c, d in zip(cand[sel_c].pc, min_c[sel_c], e_pl,
                                  cand[sel_c].ppm_true, cand[sel_c].avail_true)
    ] + [
        dict(side="cap_shape", pc=str(pc), e_lp=float(a), e_scored=float(b),
             ppm_true=float(c), avail_true=float(d))
        for pc, a, b, c, d in zip(cand[sel_cs].pc, min_cs[sel_cs], e_pls,
                                  cand[sel_cs].ppm_true, cand[sel_cs].avail_true)
    ] + [
        dict(side="club", pc=str(pc), e_lp=float(a), e_scored=float(a),
             ppm_true=float(c), avail_true=float(d))
        for pc, a, c, d in zip(keep.pc, keep.min_actual,
                               keep.ppm_true, keep.avail_true)
    ]
    return r


def run(caps, n_clubs, only=None, label="spec"):
    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    rows, mins_rows, t0 = [], [], time.time()
    for train_max, test in SEASONS:
        clubs = sorted(split[split.season == test].club.unique())
        if only is not None:
            clubs = [c for c in clubs if (test, c) in only]
        if not clubs or len(rows) >= n_clubs:
            continue
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        with contextlib.redirect_stdout(io.StringIO()):
            cand = attach_usage(cand, USAGE_CSV, test)
        gmax = float(ps[ps.season == test].games.max())
        print(f"\n  עונה {test} — {len(clubs)} מועדונים, מאגר {len(cand)}",
              flush=True)
        print(f"  {'מועדון':<7}{'A':>9}{'B':>9}{'C':>9}{'D':>9}{'F':>9}"
              f"{'n':>5}{'קוצץ':>7}{'binding':>11}{'שנ':>6}", flush=True)

        for club in clubs:
            if len(rows) >= n_clubs:
                break
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                continue
            keep = keep.copy()
            keep["min_actual"] = keep.min_per_game * keep.avail_true
            B = float(keep.cost.sum())
            t1 = time.time()
            try:
                r = one_club(cand, keep, caps, B)
            except RuntimeError as exc:       # שער הסולבר, T9
                print(f"  {club:<7} ❌ {exc}", flush=True)
                continue
            if r is None:
                print(f"  {club:<7} אין פתרון", flush=True)
                continue
            r.update(season=test, club=club, budget=B, secs=time.time() - t1)
            for m in r.pop("_mins", []):
                mins_rows.append(dict(season=test, club=club, **m))
            rows.append(r)
            # 🔴 כתיבה מצטברת. ההרצה של ADR 0005 לקחה 12.8 שעות, ולו
            #    קרסה בשעה ה-12 לא היה נשאר דבר.
            pd.DataFrame(rows).to_csv(OUT_MAIN, index=False)
            pd.DataFrame(mins_rows).to_csv(OUT_MINS, index=False)
            print(f"  {club:<7}{r['adv_cap_A']:>+9.2%}{r['adv_cap_B']:>+9.2%}"
                  f"{r['adv_cap_C']:>+9.2%}{r['adv_cap_D']:>+9.2%}"
                  f"{r['adv_cap_F_shape']:>+9.2%}"
                  f"{r['n_cap_shape']:>5}{r['clipped_shape']:>7.1f}"
                  f"{r['bind_cap']:>11}{r['secs']:>6.0f}", flush=True)

    print(f"\n  זמן כולל: {(time.time()-t0)/60:.1f} דקות", flush=True)
    return pd.DataFrame(rows)


def report(d):
    hdr("טבלת ה-2x2 — חציון מעל עונות-המועדון")
    cells = {k: float(d[f"adv_cap_{k}"].median()) for k in "ABCD"}
    print(f"  {'':<16}{'q_club חמדני':>16}{'q_club בפועל':>16}")
    print(f"  {'LP בלי צורה':<16}{cells['A']:>+16.2%}{cells['B']:>+16.2%}")
    print(f"  {'LP עם צורה':<16}{cells['C']:>+16.2%}{cells['D']:>+16.2%}")

    hdr("ה-guard על קו הבסיס")
    ok_base = abs(cells["A"] - BASELINE_ADV_CAP) <= 0.002
    print(f"  {'✅' if ok_base else '❌'} תא A משחזר את 0.1414 — "
          f"{cells['A']:.4f} (סבילות 0.002)")
    if not ok_base:
        print("     🔴 בלי זה אין ל-2x2 provenance. עצור והסבר לפני כל מסקנה.")

    hdr("ADR 0006 — המנוע על הדקות שתכנן")
    E = float(d.adv_cap_E.median())
    F = float(d.adv_cap_F.median())
    Es = float(d.adv_cap_E_shape.median())
    Fs = float(d.adv_cap_F_shape.median())
    print(f"  {'':<20}{'המנוע מחולק מחדש':>20}{'המנוע על תוכניתו':>20}")
    print(f"  {'מכנה חמדני':<20}{cells['A']:>+20.2%}{E:>+20.2%}")
    print(f"  {'מכנה בפועל':<20}{cells['B']:>+20.2%}{F:>+20.2%}")
    print(f"\n  ואותו דבר עם אילוץ הצורה:")
    print(f"  {'מכנה חמדני':<20}{cells['C']:>+20.2%}{Es:>+20.2%}")
    print(f"  {'מכנה בפועל':<20}{cells['D']:>+20.2%}{Fs:>+20.2%}   <- הספציפיקציה")
    print(f"\n  עלות הקציצה: חציון {d.clipped_shape.median():.1f} דקות מ-200 "
          f"({d.clipped_shape.median()/2:.1f}%) · מקסימום {d.clipped_shape.max():.1f}")
    qdrop_num = 1 - float((d.q_cap_shape_plan / d.q_cap_shape).median())
    print(f"  q_cap יורד במעבר להקצאה-לפי-תוכנית: {qdrop_num:.2%}")

    hdr("הפירוק שנדרש בכלל ההחלטה")
    print(f"  מהמכנה בלבד      A -> B  : {cells['B']-cells['A']:>+8.2%}")
    print(f"  מהאילוץ בלבד     A -> C  : {cells['C']-cells['A']:>+8.2%}")
    print(f"  ADR 0005 spec    A -> D  : {cells['D']-cells['A']:>+8.2%}  (נעצר)")
    print(f"  מהורדת הבדיעבד   A -> E  : {E-cells['A']:>+8.2%}")
    print(f"  ADR 0006 spec    A -> Fs : {Fs-cells['A']:>+8.2%}")
    move = Fs / cells["A"] - 1 if cells["A"] else np.nan
    print(f"\n  הספציפיקציה (Fs) מול קו הבסיס: {move:+.1%}")
    if move > 0.50:
        v = "🔴 עולה מעל 50% -> STOP. חוזרים לגריל לפני שמשהו נכתב."
    elif move > 0:
        v = "עולה -> מדווח **רק** עם הפירוק שלמעלה."
    elif move > -0.20:
        v = "יורד פחות מ-20% -> הכותרת עומדת, CV ו-LinkedIn ללא שינוי."
    elif move > -0.60:
        v = "יורד 20%-60% -> הכותרת עומדת, ומצוינת עם אילוץ הצורה בכל מקום."
    else:
        v = "יורד מעל 60% -> הכותרת הקודמת בטלה. המספר החדש הוא הכותרת."
    neg = float((d.adv_cap_F_shape <= 0).mean())
    if neg > 0.5:
        v = f"🔴 adv_cap<=0 ב-{neg:.0%} -> אין טענה. סעיפים 4 ו-5 נכתבים מחדש."
    print(f"  לפי הכלל המוצהר: {v}")
    if move > 0.50:
        print("  ⚠️ זו העצירה ה**שנייה** על אותה מטריקה (ADR 0005 עצר על D).")
        print("     לפי השורה האחרונה בכלל של ADR 0006: הבעיה במטריקה ולא")
        print("     בקונבנציה. מדווחים 0.1414 עם הקונבנציה שלו, השאר ל-v2.")
    print("\n  ⚠️ תאי B ו-D נעצרו ב-ADR 0005 ואינם מדווחים כתוצאה.")

    hdr("מול התחזיות שננעלו")
    qdrop = 1 - float((d.q_club_actual / d.q_club_greedy).median())
    preds = [
        ("0005 adv_cap צורה+חמדני", cells["C"], 0.09, 0.13, "קלוד"),
        ("0005 adv_cap צורה+בפועל", cells["D"], 0.15, 0.21, "קלוד"),
        ("0005 q_club יורד", qdrop, 0.04, 0.09, "קלוד"),
        ("0005 גודל הסגל", float(d.n_cap_shape.median()), 13, 15, "קלוד"),
        ("0006 q_cap יורד", qdrop_num, 0.11, 0.18, "קלוד"),
        ("0006 adv_cap תא F+צורה", Fs, 0.09, 0.17, "קלוד"),
        ("0006 adv_cap תא E", E, 0.02, 0.09, "קלוד"),
        ("0006 דקות שנקצצו", float(d.clipped_shape.median()), 20, 32, "קלוד"),
        ("0006 שיעור ניצחון F", float((d.adv_cap_F_shape > 0).mean()),
         0.75, 0.95, "קלוד"),
    ]
    for name, got, lo, hi, who in preds:
        ok = lo <= got <= hi
        print(f"  {'✅' if ok else '❌'} {who:<6}{name:<26}"
              f"[{lo:g}, {hi:g}]  ->  {got:.4f}")

    hdr("אילו k היו binding")
    allk = [int(k) for s in d.bind_cap.fillna("") for k in s.split(",") if k]
    vc = pd.Series(allk).value_counts().sort_index()
    for k in range(1, scoring.KMAX + 1):
        share = vc.get(k, 0) / len(d)
        print(f"  k={k}  {vc.get(k, 0):>3}/{len(d)}  {share:>6.0%}")
    dead = [k for k in (5, 7) if vc.get(k, 0) == 0]
    print(f"\n  k=5/k=7 שלא נגעו באף פתרון: {dead or 'אין — K_USED לא יצטמצם'}")
    return cells, ok_base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clubs", type=int, default=999)
    ap.add_argument("--slack", action="store_true")
    a = ap.parse_args()

    caps = scoring.load_caps()
    print(SEP)
    print("ADR 0005 שלב 4 — הרצת אילוץ הצורה")
    print("התחזיות ננעלו ב-ADR 0005. הן לא נוגעות בקוד הזה.")
    print(SEP)
    print("  תקרות: " + " ".join(f"{k}:{v:.1f}" for k, v in sorted(caps.items())))

    if a.slack:
        hdr("רגישות SLACK — 12 עונות-המועדון שהוצהרו")
        out = []
        for s in (0.95, 1.00, 1.05):
            cs = scoring.slack_caps(caps, s)
            print(f"\n  --- SLACK = {s:.2f} ---", flush=True)
            d = run(cs, 999, only=set(SUBSAMPLE_12), label=f"slack{s}")
            if d.empty:
                continue
            out.append(dict(slack=s, n=len(d),
                            adv_cap_C=float(d.adv_cap_C.median()),
                            adv_cap_D=float(d.adv_cap_D.median()),
                            n_roster=float(d.n_cap_shape.median()),
                            top6=float(d.top6_cap_shape.median())))
        r = pd.DataFrame(out)
        r.to_csv(OUT_SLACK, index=False)
        print("\n" + r.to_string(index=False))
        print(f"\n  נשמר: {OUT_SLACK}")
        print("  ⚠️ מדווח, לא נבחר. SLACK=1.00 הוא הספציפיקציה.")
        return 0

    d = run(caps, a.clubs)
    if d.empty:
        print("\n🔴 אין תוצאות.")
        return 1
    cells, ok_base = report(d)

    d.to_csv(OUT_MAIN, index=False)
    long = []
    for _, r in d.iterrows():
        for side in ("free", "cap"):
            for k in str(r[f"bind_{side}"] or "").split(","):
                if k:
                    long.append(dict(season=r.season, club=r.club,
                                     side=side, k=int(k)))
    pd.DataFrame(long).to_csv(OUT_BIND, index=False)
    print(f"\n  נשמר: {OUT_MAIN}\n  נשמר: {OUT_BIND}")
    print(f"  ⚠️ usage_constrained_results.csv לא נגע. קו הבסיס שמור.")
    return 0 if ok_base else 1


if __name__ == "__main__":
    raise SystemExit(main())
