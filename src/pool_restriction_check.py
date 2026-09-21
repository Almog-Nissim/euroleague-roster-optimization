"""
pool_restriction_check.py  (ADR 0006, לפני v1.0)
-----------------------------------------------
האם ה-38/38 הוא תוצר של ההגבלה למאגר?

`club_side` משאיר בצד המועדון רק שחקנים שנמצאים במאגר ושיש להם עמדה.
השאר — בעיקר עולים חדשים בלי עונת יורוליג קודמת — יוצאים גם מהניקוד
וגם מהתקציב. על הנייר זה סימטרי: גם המנוע לא יכול לקנות אותם.

**אבל** הדקות שהם שיחקו בפועל נעלמות מצד המועדון, ו-`score_actual`
ממלא אותן ב-`REPL = 0.127`. אם הם היו טובים, המועדון נענש, והיתרון
של המנוע מנופח. זה מה שנמדד כאן.

    q_club_pool = ADR 0006: רק שחקני המאגר, השאר ב-REPL
    q_club_full = אותו דבר + השחקנים שיצאו, על הדקות וה-ppm שלהם בפועל

`q_club_full` הוא **חסם עליון** על הענישה: המועדון מקבל קרדיט על
שחקנים שהכסף שלהם לא נכנס לתקציב של המנוע. אם היתרון שורד את זה,
הוא שורד.

תחזיות, ננעלו לפני ההרצה (קלוד; אלמוג לא נתן):
    חציון נתח הדקות שאבד להגבלה          10%–20%
    חציון adv_F אחרי זיכוי מלא           0.10–0.16   (היום 0.189)
    שיעור ניצחון אחרי זיכוי מלא          ≥ 30/38

הרצה:  python src/pool_restriction_check.py
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import optimizer_backtest as ob                                # noqa: E402
import roster_optimizer as ro                                  # noqa: E402
import scoring                                                 # noqa: E402
from paths import PROCESSED_DIR                                # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER                       # noqa: E402
from league_backtest import build_pool, club_side, REPL, SEASONS  # noqa: E402

SEP = "=" * 78
SPEC = PROCESSED_DIR / "usage_constrained_shape.csv"
OUT = PROCESSED_DIR / "pool_restriction_check.csv"

PRED_LOST = (0.10, 0.20)
PRED_ADV = (0.10, 0.16)
PRED_WIN = 30


def main() -> int:
    print(SEP)
    print("pool_restriction_check — האם ה-38/38 הוא תוצר של ההגבלה למאגר?")
    print(SEP, flush=True)

    spec = pd.read_csv(SPEC).set_index(["season", "club"])
    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    rows = []
    for train_max, test in SEASONS:
        with contextlib.redirect_stdout(io.StringIO()):
            cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        gmax = float(ps[ps.season == test].games.max())
        for club in sorted(split[split.season == test].club.unique()):
            keep, lost = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER or (test, club) not in spec.index:
                continue
            keep = keep.copy()
            keep["min_actual"] = keep.min_per_game * keep.games / gmax
            lost = lost.copy()
            lost["min_actual"] = lost.min_per_game * lost.games / gmax
            lost["ppm_true"] = lost.ppm

            q_pool, used_pool, _ = scoring.score_actual(
                keep, "ppm_true", "min_actual", REPL)
            both = pd.concat([keep[["ppm_true", "min_actual"]],
                              lost[["ppm_true", "min_actual"]]])
            q_full, used_full, _ = scoring.score_actual(
                both, "ppm_true", "min_actual", REPL)

            s = spec.loc[(test, club)]
            q_plan = float(s.q_cap_shape_plan)
            lost_min = float(lost.min_actual.sum())
            rows.append(dict(
                season=test, club=club,
                n_keep=len(keep), n_lost=len(lost),
                lost_minutes=lost_min,
                lost_share=lost_min / max(used_full, 1e-9),
                lost_ppm_wmean=(float(np.average(lost.ppm_true,
                                                 weights=lost.min_actual))
                                if lost_min > 0 else np.nan),
                q_club_pool=q_pool, q_club_full=q_full,
                handicap=q_full / q_pool - 1,
                adv_F_pool=q_plan / q_pool - 1,
                adv_F_full=q_plan / q_full - 1,
                adv_F_spec=float(s.adv_cap_F_shape)))

    d = pd.DataFrame(rows)
    d.to_csv(OUT, index=False)

    print("\n" + SEP + "\nהתוצאה\n" + SEP)
    print(f"  עונות-מועדון                    : {len(d)}")
    print(f"  שחקנים שיצאו, חציון לעונה       : {d.n_lost.median():.0f}"
          f"  (טווח {d.n_lost.min()}–{d.n_lost.max()})")
    print(f"  נתח הדקות שאבד, חציון          : {d.lost_share.median():.1%}"
          f"  (מקסימום {d.lost_share.max():.1%})")
    print(f"  ppm של מי שיצא, ממוצע משוקלל   : {d.lost_ppm_wmean.median():.3f}"
          f"   מול REPL {REPL}")
    print(f"  הענישה על המועדון (q_full/q_pool): חציון {d.handicap.median():+.1%}")
    print(f"\n  adv_F, ההגבלה כמו בספק         : {d.adv_F_pool.median():.4f}"
          f"   (שחזור: {d.adv_F_spec.median():.4f})")
    print(f"  adv_F, מועדון מזוכה במלואו      : {d.adv_F_full.median():.4f}")
    win = int((d.adv_F_full > 0).sum())
    print(f"  שיעור ניצחון, מזוכה במלואו      : {win}/{len(d)}")

    print("\n" + SEP + "\nguards\n" + SEP)
    g1 = len(d) == 38
    g2 = float((d.adv_F_pool - d.adv_F_spec).abs().max()) < 1e-6
    print(f"  {'✅' if g1 else '❌'} 38 עונות-מועדון: {len(d)}")
    print(f"  {'✅' if g2 else '❌'} adv_F בהגבלה משחזר את הספק בדיוק: "
          f"max|Δ| {float((d.adv_F_pool - d.adv_F_spec).abs().max()):.1e}")

    print("\n" + SEP + "\nמול התחזיות שננעלו\n" + SEP)
    ls, af = float(d.lost_share.median()), float(d.adv_F_full.median())
    for name, ok, v in [
        ("נתח דקות שאבד [0.10, 0.20]", PRED_LOST[0] <= ls <= PRED_LOST[1], f"{ls:.3f}"),
        ("adv_F מזוכה [0.10, 0.16]", PRED_ADV[0] <= af <= PRED_ADV[1], f"{af:.4f}"),
        (f"ניצחון ≥ {PRED_WIN}/38", win >= PRED_WIN, f"{win}/38"),
    ]:
        print(f"  {'✅' if ok else '❌'} {name:<28} -> {v}")

    print("\n  ⚠️ q_club_full הוא חסם עליון על הענישה: המועדון מזוכה על שחקנים")
    print("     שהשכר שלהם לא נכנס לתקציב של המנוע.")
    print(f"\n  נשמר: {OUT.name}")
    return 0 if (g1 and g2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
