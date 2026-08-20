"""
usage_constrained.py — הבנצ'מרק עם אילוץ הכדור, לצד הגרסה בלעדיו.

האילוץ
------
    Σ eᵢ · usageᵢ  ≤  20 · Σ eᵢ

שקול ל-`Σ eᵢ·(usageᵢ − 20) ≤ 0`. ליניארי לגמרי, בלי משתנים חדשים.
זו אותה משפחה של האילוץ שכבר קיים ב-optimise_v2:
`Σ eᵢ ≤ POS_MAX_SHARE·200` לכל עמדה — תקרה על צירוף דקות.

למה
---
`usage` הוא נתח ההחזקות מתוך אלה של הקבוצה. הממוצע המשוקלל-דקות
חייב להיות 20.0% — חמישה על המגרש, כדור אחד. **זהות, לא אמידה.**

נמדד: הסגל שהמנוע בנה יושב על 21.83% מול 20.03% של המועדון,
פער של +1.80 שנחצה כמעט שווה בשווה בין בחירה להקצאה.

וזו הפעם הרביעית באותה משפחה: תקרת 32 דקות נכונה לשחקן בודד
והמודל העמיד שמונה; רצפות עמדה נכונות לכל עמדה בנפרד ואף מועדון
לא נמצא במינימום של שלוש. **הקצה של כל מרווח בנפרד.**

⚠️ שתי הסתייגויות
------------------
1. `usage` נלקח מהעונה **הקודמת**, כי זה מה שידוע בזמן הבחירה.
   כלומר האילוץ אוכף שהסגל היה עומד בתקרה **אילו כל שחקן שמר על
   נתחו** — וזה בדיוק מה שאי אפשר. הוא נכון כאילוץ תכנוני, לא
   כניבוי.
2. למי שאין `usage` — עולים חדשים ו-112 שחקנים שאינם ב-
   player_season — מוצב 20.0%, כלומר ניטרלי. אותה לוגיקה של
   newcomer_pool: כיווץ מלא לממוצע הליגה למי שהמידע עליו אפסי.

תחזיות שננעלו לפני ההרצה
------------------------
    אובדן ניקוד   אלמוג ~7 נקודות   ·   קלוד 8-12
    שיעור ניצחון  קלוד 85-95%       (היום: 100%)

חסמים שחושבו קודם: 6.7 נקודות לפי β, 18.8 בסימולציה חמדנית.

הרצה:  python src/usage_constrained.py
"""

from __future__ import annotations

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

import roster_optimizer as ro  # noqa: E402
import optimizer_backtest as ob  # noqa: E402
from paths import PROCESSED_DIR  # noqa: E402
from roster_membership_audit import score_rows  # noqa: E402
import optimise_consistent as oc  # noqa: E402
from optimise_consistent import optimise_v2  # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER  # noqa: E402
from league_backtest import build_pool, club_side, REPL, SEASONS  # noqa: E402
from player_id import canonical  # noqa: E402

TARGET_USAGE = 20.0
SEP = "=" * 78


def hdr(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def optimise_capped(pool, budget, min_roster, cap=TARGET_USAGE):
    """
    `optimise_v2` בתוספת אילוץ אחד. כל השאר זהה — אם משהו כאן שונה
    מהמקור פרט לאילוץ, ההשוואה אינה תקפה.
    """
    n = len(pool)
    p = pulp.LpProblem("roster_capped", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(n)]
    e = [pulp.LpVariable(f"e{i}", lowBound=0) for i in range(n)]
    ppm = pool.ppm.values
    av = pool.avail.values
    cost = pool.cost.values
    usage = pool.usage_prior.values

    p += pulp.lpSum(ppm[i] * e[i] for i in range(n))
    p += pulp.lpSum(e) <= ro.MINUTES_PER_GAME
    for i in range(n):
        p += e[i] <= ro.MAX_MIN_PLAYER * av[i] * x[i]
    p += pulp.lpSum(cost[i] * x[i] for i in range(n)) <= budget
    p += pulp.lpSum(x) <= ro.MAX_ROSTER
    p += pulp.lpSum(x) >= min_roster
    for ps_, fl in ro.POS_FLOOR.items():
        idx = pool.index[pool.position == ps_]
        p += pulp.lpSum(x[i] for i in idx) >= fl
        p += pulp.lpSum(e[i] for i in idx) <= ro.POS_MAX_SHARE[ps_] * ro.MINUTES_PER_GAME
        p += pulp.lpSum(e[i] for i in idx) >= ro.POS_MIN_SHARE[ps_] * ro.MINUTES_PER_GAME

    # 🔴 האילוץ. Σ eᵢ·usageᵢ ≤ cap·Σ eᵢ
    p += pulp.lpSum((usage[i] - cap) * e[i] for i in range(n)) <= 0

    p.solve(pulp.PULP_CBC_CMD(msg=0))
    oc.LAST.clear()
    oc.LAST.update(status=pulp.LpStatus[p.status],
                   obj=pulp.value(p.objective), fn="capped")
    if pulp.LpStatus[p.status] != "Optimal":
        return None, None
    sel = np.array([x[i].value() > 0.5 for i in range(n)])
    mins = np.array([e[i].value() or 0.0 for i in range(n)])
    return sel, mins


def attach_usage(cand: pd.DataFrame, usage_path: Path, test: int) -> pd.DataFrame:
    """usage של העונה הקודמת. חסרים -> 20.0 (ניטרלי)."""
    use = pd.read_csv(usage_path, low_memory=False)
    use["key"] = use["Player_ID"].map(canonical)
    prior = (use[use.Season == test - 1].groupby("key")["usage"]
             .mean().rename("usage_prior"))
    cand = cand.copy()
    cand["key"] = cand["pc"].map(canonical)
    cand["usage_prior"] = cand["key"].map(prior)
    n_missing = int(cand["usage_prior"].isna().sum())
    cand["usage_prior"] = cand["usage_prior"].fillna(TARGET_USAGE)
    print(f"  usage מעונת {test - 1}: {len(cand) - n_missing}/{len(cand)} "
          f"נמצאו · {n_missing} הוצבו ל-{TARGET_USAGE:.0f}")
    return cand


def wusage(rows: pd.DataFrame, mins: np.ndarray) -> float:
    ok = mins > 0
    return float(np.average(rows["usage_prior"].values[ok], weights=mins[ok])) \
        if ok.any() else np.nan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--usage", default="data/processed/usage_curve_results_min0.csv")
    args = ap.parse_args()

    hdr("הבנצ'מרק עם אילוץ הכדור, לצד הגרסה בלעדיו")
    print("  תחזיות: אלמוג ~7 נקודות · קלוד 8-12 · ניצחון 85-95%")

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})
    upath = Path(args.usage)
    if not upath.is_absolute():
        upath = Path(__file__).resolve().parents[1] / upath

    rows = []
    for train_max, test in SEASONS:
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        cand = attach_usage(cand, upath, test)
        gmax = float(ps[ps.season == test].games.max())
        clubs = sorted(split[split.season == test].club.unique())
        print(f"\n  עונה {test} — {len(clubs)} מועדונים, מאגר {len(cand)}")
        print(f"  {'מועדון':<8}{'מועדון':>9}{'חופשי':>9}{'מאולץ':>9}"
              f"{'הפרש':>9}{'usage חופ':>11}{'usage מאו':>11}")

        for club in clubs:
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                continue
            B = float(keep.cost.sum())
            q_club, _, _ = score_rows(keep, "ppm_true", "avail_true", REPL)

            sel_f, min_f = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
            lp_free = oc.LAST.get("obj", np.nan)
            sel_c, min_c = optimise_capped(cand, B, MIN_LEGAL_ROSTER)
            lp_cap = oc.LAST.get("obj", np.nan)
            if sel_f is None or sel_c is None:
                print(f"  {club:<8}   אין פתרון"
                      + ("  (מאולץ)" if sel_c is None else ""))
                continue

            free, capped = cand[sel_f], cand[sel_c]
            q_free, _, _ = score_rows(free, "ppm_true", "avail_true", REPL)
            q_cap, _, _ = score_rows(capped, "ppm_true", "avail_true", REPL)

            u_free = wusage(free, min_f[sel_f])
            u_cap = wusage(capped, min_c[sel_c])

            rows.append(dict(season=test, club=club, budget=B, q_club=q_club,
                             q_free=q_free, q_cap=q_cap,
                             lp_free=lp_free, lp_cap=lp_cap,
                             n_free=int(sel_f.sum()), n_cap=int(sel_c.sum()),
                             u_free=u_free, u_cap=u_cap,
                             adv_free=q_free / q_club - 1,
                             adv_cap=q_cap / q_club - 1,
                             overlap=len(set(free.pc) & set(capped.pc))))
            print(f"  {club:<8}{q_club:>9.1f}{q_free:>9.1f}{q_cap:>9.1f}"
                  f"{q_cap - q_free:>+9.1f}{u_free:>11.2f}{u_cap:>11.2f}")

    d = pd.DataFrame(rows)
    if d.empty:
        print("\n🔴 אין תוצאות.")
        return 1

    hdr("התוצאה")
    loss = float((d.q_free - d.q_cap).mean())
    print(f"  n = {len(d)} עונות-מועדון\n")
    print(f"  ניקוד חופשי  : חציון {d.q_free.median():.1f}")
    print(f"  ניקוד מאולץ  : חציון {d.q_cap.median():.1f}")
    print(f"  🔴 אובדן ממוצע: {loss:.1f} נקודות "
          f"(טווח {(d.q_free - d.q_cap).min():.1f} .. "
          f"{(d.q_free - d.q_cap).max():.1f})")

    print(f"\n  usage משוקלל : חופשי {d.u_free.mean():.2f}%  ->  "
          f"מאולץ {d.u_cap.mean():.2f}%")
    print(f"  חפיפת הסגלים : {d.overlap.mean():.1f} מתוך {d.n_free.mean():.1f}")
    print(f"  גודל הסגל    : {d.n_free.mean():.1f}  ->  {d.n_cap.mean():.1f}")

    w_free = float((d.adv_free > 0).mean())
    w_cap = float((d.adv_cap > 0).mean())
    print(f"\n  שיעור ניצחון : {w_free:.1%}  ->  {w_cap:.1%}")
    print(f"  יתרון חציוני : {d.adv_free.median():+.1%}  ->  "
          f"{d.adv_cap.median():+.1%}")

    hdr("🔴 מבחן ה-LP — סגירת האנומליה של OLY")
    print("  אילוץ מהדק אינו יכול להעלות את ערך המטרה. זה חייב")
    print("  להתקיים ב-38 מתוך 38. אם לא — יש באג באילוץ.\n")
    print("  ⚠️ q_free ו-q_cap הם score_rows על ppm_true, ולהם מותר")
    print("     להתהפך: הם מודדים תוצאה, לא את מה שמוטב.\n")
    viol = d[d.lp_cap > d.lp_free + 1e-6]
    print(f"  הפרות: {len(viol)} מתוך {len(d)}")
    if len(viol):
        print("  🔴 באג באילוץ:")
        print(viol[["season", "club", "lp_free", "lp_cap"]].to_string(index=False))
    else:
        print("  ✅ אפס הפרות. **האילוץ תקין.**")
        gap = (d.lp_free - d.lp_cap)
        print(f"     עלות האילוץ ב-LP: חציון {gap.median():.2f} · "
              f"טווח {gap.min():.2f}..{gap.max():.2f}")

    flip = d[d.q_cap > d.q_free]
    print(f"\n  היפוכים ב-ppm_true: {len(flip)} מתוך {len(d)}"
          f"  ({len(flip) / len(d):.0%})")
    if len(flip):
        print("  אלה שגיאת ניבוי, לא באג. הגדול שבהם:")
        w = flip.assign(delta=flip.q_cap - flip.q_free).nlargest(3, "delta")
        print(w[["season", "club", "lp_free", "lp_cap",
                 "q_free", "q_cap", "delta"]].to_string(index=False))
        print(f"\n  ⇒ OLY אינו חריג יחיד אלא {len(flip)} מקרים מאותה")
        print("     משפחה. **המנוע ממטב על מנובא ונמדד על אמיתי,**")
        print("     ושגיאת הניבוי גדולה מעלות האילוץ.")

    hdr("מול התחזיות")
    print(f"  אובדן ניקוד — אלמוג ~7 · קלוד 8-12  ->  {loss:.1f}")
    print(f"    אלמוג {'✅' if 5.5 <= loss <= 8.5 else '❌'}   "
          f"קלוד {'✅' if 8 <= loss <= 12 else '❌'}")
    print(f"  שיעור ניצחון — קלוד 85-95%  ->  {w_cap:.1%}"
          f"   {'✅' if 0.85 <= w_cap <= 0.95 else '❌'}")
    print(f"\n  חסמים שחושבו קודם: 6.7 לפי β · 18.8 בסימולציה חמדנית")
    if 6.7 <= loss <= 18.8:
        print("  ✅ התוצאה בין שני החסמים, כצפוי.")
    else:
        print("  ⚠️ התוצאה **מחוץ** לטווח החסמים — יש מה להסביר.")

    out = PROCESSED_DIR / "usage_constrained_results.csv"
    d.to_csv(out, index=False)
    print(f"\n  נשמר: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())