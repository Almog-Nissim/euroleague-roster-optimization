"""
stochastic_crn.py  (Day 9)
--------------------------
**אותו מבחן, בלי הבאג שאני שתלתי בו.**

--------------------------------------------------------------------
מה קרה בגרסה הקודמת
--------------------------------------------------------------------
`stochastic_avail` דיווח שני מספרים שסותרים זה את זה:

    הרווח מהמעבר מ-12 לגודל האופטימלי:  חציון +3.35%

    ניקוד ממוצע לפי גודל סגל:
      12: 122.06    13: 121.63    14: 120.74
      15: 120.96    16: 119.19

כל מועדון "הרוויח" 3.35%, ובממוצע גודל 12 הוא הטוב ביותר.

הסיבה: בחרתי לכל מועדון את **המקסימום מבין חמישה אומדנים
רועשים**. גם אם כל הגדלים שווים בדיוק, E[max של 5] גבוה
מהראשון ב-~1.16 סטיות תקן. עם ס"ת של ~3.5 נקודות זה בערך
4 נקודות — בדיוק מה שהתקבל.

**זו קללת המנצח**, התופעה שהפרויקט הזה נבנה כדי למדוד, ושתלתי
אותה בסקריפט שאמור להכריע בשאלה.

--------------------------------------------------------------------
שני התיקונים
--------------------------------------------------------------------
**א. מספרים אקראיים משותפים (CRN).** מגרילים מטריצת אקראיות
   **אחת** לכל המאגר, ומצמידים אותה ל**שחקן** ולא לסגל. כל
   הגדלים נבחנים על אותם משחקים בדיוק, עם אותן הגרלות זמינות
   לאותם שחקנים. ההפרש בין 12 ל-14 נובע רק ממי בסגל.

**ב. הכרעה לפי העקומה, לא לפי argmax.** מדווחים את ההפרש
   **המזווג** בין כל גודל ל-12, עם מבחן t מזווג ובוטסטרפ.
   `argmax` עדיין מדווח — אבל לצד ההטיה שלו, שנמדדת ישירות
   במבחן פלצבו.

**ג. מבחן פלצבו.** מנקדים את **אותו סגל של 12** פעמיים, עם
   שתי הגרלות שונות, ובוחרים את המקסימום. כל "רווח" שיוצא שם
   הוא הטיה טהורה — אין שום הבדל אמיתי בין שתי ההרצות.

--------------------------------------------------------------------
מה זה עדיין לא מתקן
--------------------------------------------------------------------
ה-LP ממטב תוחלת עם זמינות **קבועה**, ואנחנו מנקדים בזנב. המנוע
מעולם לא ניסה לבנות סגל עמיד להיעדרויות — הוא בנה סגל לתוחלת
ונבחן בסערה. זה כמו למדוד עמידות לגשם על מטרייה שתוכננה לשמש.

התיקון הזה דורש אופטימיזציה מבוססת סימולציה, וזה שינוי אמיתי.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
PRED_CLAUDE = dict(
    placebo="1.5% .. 3.5%   ההטיה הטהורה, בלי שום הבדל אמיתי",
    paired="כל הגדלים מעל 12 יצאו **שליליים** מזווגים",
    best_size="12 יישאר הטוב ביותר ברוב המכריע של המועדונים",
    verdict="גם עם זמינות סטוכסטית, עומק לא משתלם במודל הזה",
)
PRED_ALMOG = dict()
# ====================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR
import roster_optimizer as ro
import optimizer_backtest as ob
from league_backtest import build_pool, club_side, SEASONS
from optimise_consistent import optimise_v2
from final_day7 import MIN_LEGAL_ROSTER
from stochastic_avail import prune, measure_replacement

SEP = "=" * 96
SIMS = 400
SIZES = [12, 13, 14, 15, 16]


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def game_scores(ppm, p, U, repl):
    """ניקוד לכל משחק, בהינתן מטריצת אקראיות U קבועה מראש.

    U הוא (G, n) ומגיע **מהמאגר**, כלומר לשחקן מסוים יש אותה
    סדרת הגרלות בכל סגל שהוא נמצא בו. זה מה שהופך את ההשוואה
    בין הגדלים למזווגת.
    """
    o = np.argsort(-ppm)
    ppm, p, U = ppm[o], p[o], U[:, o]
    av = (U < p).astype(float)
    cap = av * ro.MAX_MIN_PLAYER
    before = np.cumsum(cap, axis=1) - cap
    mins = np.clip(ro.MINUTES_PER_GAME - before, 0.0,
                   ro.MAX_MIN_PLAYER) * av
    left = np.clip(ro.MINUTES_PER_GAME - mins.sum(axis=1), 0.0, None)
    return mins @ ppm + left * repl


def main():
    print(SEP)
    print("stochastic_crn — אותו מבחן, בלי ההטיה")
    print("תחזיות ננעלו. ראו ראש הקובץ.")
    print(SEP)

    repl = measure_replacement()["9-12"]
    print(f"\n  רמת מחליף = {repl:.3f}   סימולציות = {SIMS} עונות")

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    rows, placebo = [], []
    for train_max, test in SEASONS:
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        pool = prune(cand).reset_index(drop=True)
        gmax = float(ps[ps.season == test].games.max())
        G = int(gmax * SIMS)
        rng = np.random.default_rng(20260818 + test)
        # 🔴 מטריצה אחת לכל המאגר. השחקן במקום i מקבל את אותה
        #    סדרת הגרלות בכל סגל שבו הוא נמצא.
        U = rng.random((G, len(pool)))
        U2 = rng.random((G, len(pool)))       # להרצת הפלצבו
        h(f"עונה {test}   מאגר {len(pool)}   משחקים {gmax:.0f}   "
          f"הגרלות {G:,}")
        print(f"  {'מועדון':<7}{'מועדון':>9}" +
              "".join(f"{s:>9}" for s in SIZES) +
              "  |" + "".join(f"{'Δ'+str(s):>8}" for s in SIZES[1:]))
        om = ro.MAX_ROSTER
        for club in sorted(split[split.season == test].club.unique()):
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                continue
            B = float(keep.cost.sum())
            per_game, means = {}, {}
            for s in SIZES:
                ro.MAX_ROSTER = max(om, s)
                sel, _ = optimise_v2(pool, B, s)
                ro.MAX_ROSTER = om
                if sel is None:
                    continue
                idx = np.where(sel)[0]
                q = game_scores(pool.ppm_true.values[idx].astype(float),
                                pool.avail_true.values[idx].astype(float),
                                U[:, idx], repl)
                per_game[s] = q
                means[s] = float(q.mean())
            if 12 not in means:
                continue
            # פלצבו: אותו סגל של 12, הגרלה שנייה
            i12 = np.where(optimise_v2(pool, B, 12)[0])[0]
            q_b = game_scores(pool.ppm_true.values[i12].astype(float),
                              pool.avail_true.values[i12].astype(float),
                              U2[:, i12], repl)
            placebo.append(max(means[12], float(q_b.mean())) / means[12] - 1)

            d = {f"d{s}": (per_game[s] - per_game[12]).mean()
                 for s in SIZES[1:] if s in per_game}
            best = max(means, key=lambda k: means[k])
            rows.append(dict(season=test, club=club, best=best,
                             gain=means[best] / means[12] - 1,
                             **{f"m{k}": v for k, v in means.items()}, **d))
            print(f"  {club:<7}" +
                  "".join(f"{means.get(s, np.nan):>9.1f}" for s in SIZES) +
                  "  |" + "".join(f"{d.get('d'+str(s), np.nan):>+8.2f}"
                                  for s in SIZES[1:]))

    r = pd.DataFrame(rows)
    r.to_csv(PROCESSED_DIR / "stochastic_crn.csv", index=False)

    h("א. מבחן הפלצבו — ההטיה הטהורה")
    pl = np.array(placebo)
    print(f"  אותו סגל של 12, שתי הגרלות, בוחרים את המקסימום:")
    print(f"  'רווח' מדומה: חציון {np.median(pl):+.2%}   "
          f"ממוצע {pl.mean():+.2%}   מרבי {pl.max():+.2%}")
    print(f"  ומ-5 גדלים ההטיה גדולה יותר בערך פי 1.6.")
    print(f"  -> הרווח של +3.35% מההרצה הקודמת הוא ברובו זה.")

    h("ב. ההפרש המזווג מול גודל 12")
    print("  " + "גודל".rjust(6) + "הפרש ממוצע".rjust(14)
          + "סטיית תקן".rjust(12) + "t מזווג".rjust(10)
          + "p".rjust(9) + "חיובי".rjust(12))
    for s in SIZES[1:]:
        c = f"d{s}"
        v = r[c].dropna()
        t, p = stats.ttest_1samp(v, 0.0)
        print(f"  {s:>6}{v.mean():>+14.2f}{v.std():>9.2f}{t:>+10.2f}"
              f"{p:>9.4f}{int((v > 0).sum()):>12}/{len(v)}")

    h("ג. העקומה — ניקוד ממוצע לפי גודל")
    for s in SIZES:
        c = f"m{s}"
        print(f"    {s}: {r[c].mean():>7.2f}   "
              f"(מול 12: {r[c].mean()/r.m12.mean()-1:+.2%})")

    h("ד. argmax — לצד ההטיה שלו")
    print(f"  גודל נבחר: " + "  ".join(
        f"{k}:{v}" for k, v in r.best.value_counts().sort_index().items()))
    print(f"  ממוצע {r.best.mean():.2f}   "
          f"'רווח' חציוני {r.gain.median():+.2%}")
    print(f"  ההטיה מהפלצבו: {np.median(pl)*1.6:+.2%}")
    print(f"  -> רווח אמיתי משוער: "
          f"{r.gain.median() - np.median(pl)*1.6:+.2%}")

    h("מול התחזיות של קלוד")
    for k, v in PRED_CLAUDE.items():
        print(f"  {k:<12} {v}")
    print(SEP)


if __name__ == "__main__":
    main()