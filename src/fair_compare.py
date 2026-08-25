"""fair_compare.py — יום 13. שני תיקונים לפני הפרונט.

====================================================================
א. ההשוואה מועדון ↔ מנוע — שתי כמויות שונות
====================================================================
`roster_sweep` מדפיס:

    OLY   תקציב 36.93 · ניקוד 125.0      score_rows על ppm_true (נצפה)
    מנוע ב-36.93       · ניקוד 142.90     q_LP     על ppm     (חזוי)

פער של 17.9 — **שרובו יחידות מדידה, לא יתרון.** הצגתן זו לצד זו
בממשק היא בדיוק הכשל של יום 11.

**התיקון:** לנקד את סגל המועדון באותה מטרה בדיוק — `optimise_v2`
עם `locked` = כל שחקני הסגל, תקציב = תקציבו. אותה פונקציה, אותה
הקצאת דקות, אותו `ppm` חזוי. הסגל כפוי, ההקצאה חופשית.

⚠️ זו טובה למועדון: הוא מקבל את הקצאת הדקות **האופטימלית** לסגלו,
   לא את זו שהמאמן בחר. הפער שיתקבל הוא **חסם תחתון** על יתרון
   המנוע — וזה הכיוון הנכון לטעות בו.

====================================================================
ב. רגישות למילוי זהות הכדור
====================================================================
`attach_usage` מוצא זהות ל-192 מתוך 335 שחקנים. **143 (43%)
מקבלים `TARGET_USAGE = 20` מומצא.**

והמילוי אינו אקראי: החסרים הם עולים חדשים ושחקנים שחזרו — בדיוק
מי שבפועל צורך 26–30%. שחקן עם 20 מומצא נראה לאילוץ **ניטרלי**
ועובר אותו בקלות.

⇒ **האילוץ כנראה רופף מדי, לא הדוק מדי.** אם כך, +2.03 הוא
  הערכת יתר.

**המבחן:** להריץ את המאולץ עם שלושה מילויים — 20 (הנוכחי), 24,
28 — ולראות כמה הכותרת זזה. אין דאטה לתקן, אבל יש דרך למדוד
כמה זה משנה.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""
PRED = {
    "1. פער מועדון↔מנוע אחרי התיקון": ("", "יקטן ל-40%–70% מ-17.9"),
    "2. מס' מועדונים שהמנוע מפסיד להם": ("", "0–2 מתוך 20"),
    "3. Δq_cap במילוי 28 מול 20":      ("", "−1.5 .. −5.0 יחידות"),
    "4. הכותרת עם מילוי 28":            ("", "+1.5 .. +1.9"),
}
FILLS = [20.0, 24.0, 28.0]
# ====================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import optimizer_backtest as ob                      # noqa: E402
from league_backtest import build_pool, club_side    # noqa: E402
from optimise_consistent import optimise_v2          # noqa: E402
import usage_constrained as ucm                      # noqa: E402
from roster_optimizer import PROCESSED_DIR           # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER              # noqa: E402
from player_id import canonical                      # noqa: E402

SEASON, TRAIN_MAX = 2025, 2024
SEP = "=" * 78


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def q_lp(pool, sel, mins):
    """ערך המטרה: Σ ppm(i)·e(i) על ppm החזוי. 0 הפרות מונוטוניות."""
    m = np.asarray(mins)[np.asarray(sel)]
    return float((pool[sel].ppm.values * m).sum())


def attach_usage_fill(cand, path, test, fill):
    """כמו attach_usage, אבל עם ערך מילוי נשלט."""
    use = pd.read_csv(path, low_memory=False)
    use["key"] = use["Player_ID"].map(canonical)
    prior = (use[use.Season == test - 1].groupby("key")["usage"]
             .mean().rename("usage_prior"))
    c = cand.copy()
    c["key"] = c["pc"].map(canonical)
    c["usage_prior"] = c["key"].map(prior)
    n_miss = int(c.usage_prior.isna().sum())
    c["usage_prior"] = c.usage_prior.fillna(fill)
    return c, n_miss


def main() -> int:
    print(SEP)
    print("fair_compare — השוואה הוגנת + רגישות למילוי הזהות")
    print("תחזיות ננעלו. ראו ראש הקובץ.")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    cand, _ = build_pool(SEASON, TRAIN_MAX, feat, anch, pos, ps)
    cand = cand.reset_index(drop=True)          # באג היישור, יום 12
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})
    gmax = float(ps[ps.season == SEASON].games.max())

    # ================================================== חלק א
    h("א. ההשוואה ההוגנת — אותה מטרה לשני הצדדים")
    print("  המועדון: optimise_v2 עם locked=כל הסגל, תקציב=תקציבו.")
    print("  המנוע:   optimise_v2 חופשי, אותו תקציב.\n")
    print(f"  {'מועדון':<7}{'תקציב':>7}{'סגל':>5}"
          f"{'מועדון(הוגן)':>13}{'מנוע':>9}{'פער':>8}{'פער %':>8}")
    rows = []
    for club in sorted(split[split.season == SEASON].club.unique()):
        keep, _ = club_side(cand, split, club, SEASON, gmax, posmap)
        if len(keep) < MIN_LEGAL_ROSTER:
            continue
        B = float(keep.cost.sum())

        # המועדון: אותו LP, סגלו נעול
        codes = set(keep.player_code.astype(str))
        lock = [i for i, c in enumerate(cand.player_code.astype(str))
                if c in codes]
        sc, mc = optimise_v2(cand, B, MIN_LEGAL_ROSTER, locked=lock)
        if sc is None:
            print(f"  {club:<7} ⚠️ לא פתיר עם הסגל נעול — מדולג")
            continue
        q_club_fair = q_lp(cand, sc, mc)

        # המנוע: אותו תקציב, בחירה חופשית
        se, me = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
        q_eng = q_lp(cand, se, me)

        gap = q_eng - q_club_fair
        rows.append(dict(club=club, budget=B, n=len(keep),
                         q_club_fair=q_club_fair, q_eng=q_eng,
                         gap=gap, gap_pct=gap / q_club_fair))
        print(f"  {club:<7}{B:>7.2f}{len(keep):>5}{q_club_fair:>13.1f}"
              f"{q_eng:>9.1f}{gap:>8.1f}{gap/q_club_fair:>8.1%}")

    R = pd.DataFrame(rows)
    print(f"\n  🔴 פער חציוני: {R.gap.median():.2f} יחידות "
          f"({R.gap_pct.median():.1%})")
    print(f"     מול 17.9 בהשוואה השבורה → "
          f"{R.gap.median()/17.9:.0%} ממנה")
    lose = int((R.gap < 0).sum())
    print(f"  מועדונים שהמנוע מפסיד להם: {lose}/{len(R)}")
    if lose:
        print(f"    {', '.join(R[R.gap < 0].club)}")

    # ================================================== חלק ב
    h("ב. רגישות למילוי זהות הכדור")
    upath = PROCESSED_DIR / "usage_curve_results_min0.csv"
    med_B = float(R.budget.median())
    print(f"  נבדק על תקציב חציוני {med_B:.2f} וכן על כל 20 המועדונים.\n")
    print(f"  {'מילוי':>7}{'חסרים':>8}{'q_cap@חציון':>13}"
          f"{'q_cap חציון(20)':>17}{'Δמול 20':>10}")
    base = None
    sens = []
    for fill in FILLS:
        cu, n_miss = attach_usage_fill(cand, upath, SEASON, fill)
        s1, m1 = ucm.optimise_capped(cu, med_B, MIN_LEGAL_ROSTER)
        q_med = q_lp(cu, s1, m1) if s1 is not None else np.nan
        qs = []
        for _, r in R.iterrows():
            s2, m2 = ucm.optimise_capped(cu, float(r.budget),
                                         MIN_LEGAL_ROSTER)
            if s2 is not None:
                qs.append(q_lp(cu, s2, m2) - r.q_club_fair)
        gap_med = float(np.median(qs)) if qs else np.nan
        if base is None:
            base = gap_med
        print(f"  {fill:>7.0f}{n_miss:>8}{q_med:>13.1f}"
              f"{gap_med:>17.2f}{gap_med-base:>10.2f}")
        sens.append(dict(fill=fill, n_missing=n_miss, q_at_median=q_med,
                         gap_median=gap_med, delta=gap_med - base))

    S = pd.DataFrame(sens)
    d28 = float(S[S.fill == 28].delta.iloc[0])
    print(f"\n  🔴 מעבר ממילוי 20 ל-28 מזיז את הפער ב-{d28:+.2f} יחידות")
    print(f"     ({d28/base:+.1%} מהפער)")

    # המרה גסה לניצחונות: אותו מקדם כמו wins_conversion
    K = 0.4338 * 0.6403          # s_partial × k
    print(f"\n  בהמרה לניצחונות (מקדם {K:.4f}):")
    for _, r in S.iterrows():
        print(f"    מילוי {r.fill:.0f}: פער {r.gap_median:>6.2f} יח' → "
              f"{K*r.gap_median:+.2f} ניצחונות")
    print("\n  ⚠️ המרה גסה — החציון כאן על הגדרה שונה מ-wins_conversion")
    print("     (מטרה חזויה מול score_rows נצפה). האינדיקציה היא")
    print("     ה**כיוון והסדר גודל**, לא המספר.")

    # ---------------------------------------------------- תחזיות
    h("ג. לוח התחזיות")
    actual = {
        "1. פער מועדון↔מנוע אחרי התיקון": f"{R.gap.median():.1f} "
                                          f"({R.gap.median()/17.9:.0%})",
        "2. מס' מועדונים שהמנוע מפסיד להם": f"{lose}/{len(R)}",
        "3. Δq_cap במילוי 28 מול 20": f"{d28:+.2f}",
        "4. הכותרת עם מילוי 28": f"{K*float(S[S.fill==28].gap_median.iloc[0]):+.2f}",
    }
    print(f"  {'מבחן':<34}{'אלמוג':>12}{'קלוד':>22}{'בפועל':>14}")
    for k, (a, c) in PRED.items():
        print(f"  {k:<34}{a:>12}{c:>22}{actual[k]:>14}")

    R.to_csv(PROCESSED_DIR / "fair_compare_clubs.csv", index=False)
    S.to_csv(PROCESSED_DIR / "usage_fill_sensitivity.csv", index=False)
    print(f"\n  נשמר: fair_compare_clubs.csv · usage_fill_sensitivity.csv")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())