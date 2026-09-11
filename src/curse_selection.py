"""curse_selection.py — הטיית הבחירה על 38 עונות-מועדון, בשני מפרטי
מודל העלות. שלב 1 של תוכנית יום 15.

--------------------------------------------------------------------
השאלה
--------------------------------------------------------------------
`curse_decomp` (יום 7) מדד את זה על **שני** תרחישים. הקפיצה של
adv_cap מ-6.5% ל-17.2% אחרי הריפיט מחייבת מדידה על כל המדגם,
ובשני המפרטים, אחרת אין למה להשוות.

    הטיית_בחירה = ממוצע(ppm_חזוי − ppm_נצפה) על הנבחרים
                − ממוצע(ppm_חזוי − ppm_נצפה) על כל המאגר

מדווח כאחוז מ-ppm הממוצע במאגר. אפס = המודל לא מדויק אבל אינו
מוטה בבחירה. חיובי = הוא טועה כלפי מעלה **דווקא** על מי שנבחר.

--------------------------------------------------------------------
⚠️ מה זה לא מודד
--------------------------------------------------------------------
המדד הזה בודק ערוץ אחד: תפוקה שהוערכה ביתר. הוא **אינו** בודק
את הערוץ השני — שגיאת תמחור לפי סוג שחקן. adv נמדד על ppm_נצפה
בשני הצדדים, ולכן קללת המנצח מקטינה אותו ולא מנפחת אותו; מה
שיכול לנפח אותו הוא מחיר כוכבים נמוך מדי, שנותן למנוע ארביטראז'
שמועדון אמיתי לא יכול לממש. זה נמדד בנפרד.

--------------------------------------------------------------------
פרמטרים מוצהרים
--------------------------------------------------------------------
ממוצע לא משוקלל על הנבחרים (משוקלל-דקות מדווח לצידו).
המאגר = כל שורה עם ppm_נצפה מוגדר, כלומר מי ששיחק דקה אחת לפחות.

חיזויים שננעלו לפני ההרצה:
    הטיית בחירה, ישן    קלוד 10-15%   אלמוג 12-16%
    הטיית בחירה, חדש    קלוד 17-24%   אלמוג 20-25%
    יחס חדש/ישן         קלוד 1.4-1.9  אלמוג 1.25-2.08
    נתח הקפיצה שמוסבר   קלוד < 50%    אלמוג >= 40%

הרצה:
    COST_SPEC=club_relative python src/curse_selection.py
    COST_SPEC=market        python src/curse_selection.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import optimizer_backtest as ob  # noqa: E402
from paths import PROCESSED_DIR  # noqa: E402
from league_backtest import build_pool, club_side, REPL, SEASONS  # noqa: E402
from optimise_consistent import optimise_v2  # noqa: E402
from usage_constrained import optimise_capped, attach_usage  # noqa: E402
from roster_membership_audit import score_rows  # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER  # noqa: E402

SEP = "=" * 80
USAGE_PATH = PROCESSED_DIR / "usage_curve_results_min0.csv"


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def main() -> int:
    print(SEP)
    print(f"curse_selection — הטיית בחירה על 38 עונות-מועדון · מפרט "
          f"{ob.COST_SPEC}")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    rows = []
    for train_max, test in SEASONS:
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        cand = cand.reset_index(drop=True)
        cand = attach_usage(cand, USAGE_PATH, test)
        gmax = float(ps[ps.season == test].games.max())

        ok = cand.ppm_true.notna() & np.isfinite(cand.ppm_true)
        pool = cand[ok]
        pool_err = float((pool.ppm - pool.ppm_true).mean())
        pool_ppm = float(pool.ppm_true.mean())

        for club in sorted(split[split.season == test].club.unique()):
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                continue
            B = float(keep.cost.sum())
            q_club = float(score_rows(keep, "ppm_true", "avail_true", REPL)[0])

            out = dict(season=test, club=club, budget=B, q_club=q_club,
                       pool_err=pool_err, pool_ppm=pool_ppm)
            for tag, fn in [("free", optimise_v2), ("cap", optimise_capped)]:
                sel, mins = fn(cand, B, MIN_LEGAL_ROSTER)
                if sel is None:
                    out[f"sel_err_{tag}"] = np.nan
                    continue
                r = cand[sel]
                r = r[r.ppm_true.notna() & np.isfinite(r.ppm_true)]
                m = np.asarray(mins)[np.asarray(sel)][
                    (cand[sel].ppm_true.notna()
                     & np.isfinite(cand[sel].ppm_true)).values]
                err = (r.ppm - r.ppm_true)
                out[f"sel_err_{tag}"] = float(err.mean())
                out[f"sel_err_w_{tag}"] = (float(np.average(err, weights=m))
                                           if m.sum() > 0 else np.nan)
                out[f"q_true_{tag}"] = float(
                    score_rows(r, "ppm_true", "avail_true", REPL)[0])
                out[f"q_pred_{tag}"] = float(
                    score_rows(r, "ppm", "avail_true", REPL)[0])
            rows.append(out)
            print(f"  {test} {club:<5} B={B:>6.2f}", end="\r")

    d = pd.DataFrame(rows)
    for tag in ("free", "cap"):
        d[f"bias_{tag}"] = (d[f"sel_err_{tag}"] - d.pool_err) / d.pool_ppm
        d[f"bias_w_{tag}"] = (d[f"sel_err_w_{tag}"] - d.pool_err) / d.pool_ppm
        d[f"adv_{tag}"] = d[f"q_true_{tag}"] / d.q_club - 1
        d[f"adv_ideal_{tag}"] = d[f"q_pred_{tag}"] / d.q_club - 1
        d[f"curse_pp_{tag}"] = d[f"adv_ideal_{tag}"] - d[f"adv_{tag}"]

    h(f"התוצאה — מפרט {ob.COST_SPEC} · n={len(d)}")
    print(f"  {'':<26}{'חופשי':>12}{'מאולץ':>12}")
    for lbl, k in [("הטיית בחירה (חציון)", "bias"),
                   ("הטיית בחירה משוקללת", "bias_w"),
                   ("יתרון נמדד", "adv"),
                   ("יתרון לו התחזית התממשה", "adv_ideal"),
                   ("עלות הקללה (נק' אחוז)", "curse_pp")]:
        print(f"  {lbl:<26}{d[f'{k}_free'].median():>11.1%}"
              f"{d[f'{k}_cap'].median():>12.1%}")
    print(f"\n  שגיאת ppm במאגר: " + " · ".join(
        f"{int(s)}: {g.pool_err.iloc[0]:+.4f} מתוך ppm {g.pool_ppm.iloc[0]:.4f}"
        for s, g in d.groupby("season")))

    out = PROCESSED_DIR / f"curse_selection_{ob.COST_SPEC}.csv"
    d.to_csv(out, index=False)
    print(f"\n  נשמר: {out.name}")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
