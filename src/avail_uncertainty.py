"""
avail_uncertainty.py  (Day 7 -> 8)
----------------------------------
מפיץ את אי-ודאות **הזמינות** למונטה קרלו.

--------------------------------------------------------------------
מה חסר היום
--------------------------------------------------------------------
ב-`roster_optimizer.simulate` הזמינות מוגרלת משחק-משחק:

    a = (rng.random((games, n)) < av) & ok

אבל `av` נחשב **ידוע במדויק**. שחקן שהמודל חזה לו 0.64 מוגרל
כאילו זה באמת השיעור שלו. ה-MAE של מודל הזמינות הוא 0.13-0.22.

`curse_decomp` (יום 7) הראה שזה אינו פרט: **כל** ההפרש שנשאר בין
מכבי להפועל הוא זמינות. הטיית הבחירה בזמינות הייתה +0.088 אצל
מכבי ו-−0.117 אצל הפועל, בעוד הטיית ה-ppm כמעט זהה בשניהם
(−0.048 מול −0.040). ה-ppm כבר נושא אי-ודאות בסימולציה; הזמינות
לא.

--------------------------------------------------------------------
המודל: בטא-בינומי
--------------------------------------------------------------------
    p_i  ~  Beta( ממוצע = av_i ,  שונות = rho · av_i(1-av_i) )   פעם לעונה
    a_ij ~  Bernoulli( p_i )                                     כל משחק

`rho` נאמד מהדאטה ולא נבחר: מחשבים שארית פירסון לכל תצפית,

    r = (frac - p̂) / sqrt( p̂(1-p̂) / n )

ומקבלים פיזור-יתר phi = mean(r²). בבטא-בינומי מתקיים
phi = 1 + (n-1)·rho, ולכן rho = (phi-1)/(n-1).

phi = 1 בדיוק פירושו שאין אי-ודאות מעבר לבינומית, ואז הקובץ הזה
מיותר. phi >> 1 פירושו שהשיעור עצמו אינו ידוע.

--------------------------------------------------------------------
תחזיות — נרשמו לפני ההרצה
--------------------------------------------------------------------
זו נקודת הכשל של יום 7: שלושה קבצים חדשים הורצו בלי אף תחזית
שנרשמה מראש, בניגוד ל-`Oos_hapoel` ול-`backtest_diagnostics`.
"""

# ====================================================================
# ננעל ב-17.8.2026, לפני שהורצה ולו שורה אחת. אין לערוך בדיעבד.
# ====================================================================
PRED_ALMOG_SCORE = "down_small"      # ירידה עד 3%
PRED_ALMOG_DEPTH = "depth_gains"     # 16 משתפר מול 12

PRED_CLAUDE_SCORE = "down_3_to_6"
PRED_CLAUDE_SCORE_WHY = (
    "אסימטריה: כששחקן מתגלה פחות זמין, דקותיו עוברות לשחקן גרוע "
    "יותר. כשהוא מתגלה זמין יותר, הרווח אפס — 200 הדקות כבר "
    "מלאות. ולכן שונות סביב תוחלת קבועה מורידה את התוחלת."
)
PRED_CLAUDE_DEPTH = "depth_gains_but_under_2pct"
PRED_CLAUDE_DEPTH_WHY = (
    "12 שחקנים x 32 דקות x 0.78 זמינות = ~300 דקות זמינות מול 200 "
    "נדרשות. גם סגל של 12 הוא כבר עודף קיבולת. עומק עוזר רק בזנב "
    "שבו רבים נעדרים בו-זמנית, והזנב הזה נדיר. אם אלמוג צודק "
    "והאפקט גדול — הזנב שכיח יותר משאני חושב."
)

# כלל הכרעה, נוסח לפני ההרצה:
DEPTH_MEANINGFUL_MIN = 0.02   # שינוי ביחס 16/12 מתחת לזה = רעש
SCORE_SMALL_MAX = 0.03        # הגבול בין "ירידה מעטה" ל"ירידה גדולה"
# ====================================================================

import io
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster_optimizer as ro
import optimizer_backtest as ob
import club_rosters as cr
from optimise_consistent import optimise_v2
from final_day7 import prep, MIN_LEGAL_ROSTER

SEP = "=" * 78
N_DRAWS = 400
SEED = 20260817


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def estimate_rho(ps, feat, anch, train_max):
    """פיזור-היתר של מודל הזמינות, בשיטת המומנטים.

    מוחזר גם phi כדי שיהיה אפשר לראות אם בכלל יש מה להפיץ.
    """
    with contextlib.redirect_stdout(io.StringIO()):
        cm, smear, agg, am, pm, PF, lagged = ob.fit_models(ps, feat, anch)
    tr = lagged[lagged.season <= train_max].copy()
    p = am.predict(sm.add_constant(tr[ro.AVAIL_FEATURES].astype(float),
                                   has_constant="add"))
    n = tr.gmax.values
    frac = tr.games.values / n
    var = np.maximum(p * (1 - p) / n, 1e-12)
    r2 = ((frac - p) ** 2) / var
    phi = float(np.mean(r2))
    nbar = float(np.mean(n))
    rho = max((phi - 1.0) / (nbar - 1.0), 0.0)
    return phi, rho, float(np.abs(frac - p).mean()), len(tr)


def simulate_av(ppm_hat, ppm_sd, avail, positions, repl_ppm, rng,
                rho, draws=N_DRAWS, games=ro.GAMES_PER_SEASON):
    """כמו ro.simulate, אבל שיעור הזמינות עצמו נדגם פעם לעונה.

    rho=0 -> זהה לחלוטין להתנהגות הקיימת. זה מה שהופך את ההשוואה
    לנקייה: אותו קוד, אותו זרע, פרמטר אחד משתנה.
    """
    n = len(ppm_hat)
    caps = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
            for g in ro.POS_MAX_SHARE}
    out = np.empty(draws)
    short_tot = 0.0
    av0 = np.clip(np.asarray(avail, float), 1e-4, 1 - 1e-4)

    for k in range(draws):
        true = rng.normal(ppm_hat, ppm_sd)
        if rho > 0:
            # Beta עם ממוצע av ושונות rho*av*(1-av)
            conc = max(1.0 / rho - 1.0, 1e-6)
            p_true = rng.beta(av0 * conc, (1 - av0) * conc)
        else:
            p_true = av0
        order = np.argsort(-true)
        pp, av = true[order], p_true[order]
        pos = np.asarray(positions)[order]
        ok = pp > repl_ppm

        a = (rng.random((games, n)) < av) & ok
        total_left = np.full(games, ro.MINUTES_PER_GAME)
        grp_left = {g: np.full(games, caps[g]) for g in caps}
        q = np.zeros(games)
        used = np.zeros(games)
        for j in range(n):
            g = pos[j]
            take = np.minimum(np.minimum(ro.MAX_MIN_PLAYER, total_left),
                              grp_left[g]) * a[:, j]
            q += take * pp[j]
            used += take
            total_left -= take
            grp_left[g] -= take
        gap = ro.MINUTES_PER_GAME - used
        q += gap * repl_ppm
        out[k] = q.mean()
        short_tot += (gap > 1e-6).mean()
    return out, short_tot / draws


def main():
    print(SEP)
    print("הפצת אי-ודאות הזמינות למונטה קרלו")
    print("תחזיות ננעלו לפני ההרצה — ראו ראש הקובץ")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()

    h("1. כמה אי-ודאות יש בכלל")
    phi, rho, mae, n = estimate_rho(ps, feat, anch, 2023)
    print(f"  n = {n} תצפיות")
    print(f"  MAE ברמת שחקן          {mae:.3f}")
    print(f"  פיזור-יתר phi          {phi:.2f}   (1.0 = אין)")
    print(f"  מתאם תוך-מחלקתי rho    {rho:.4f}")
    print(f"  ס\"ת של השיעור סביב 0.78: "
          f"{np.sqrt(rho * 0.78 * 0.22):.3f}")
    if phi < 1.2:
        print("  ⚠️ phi קרוב ל-1 — אין פיזור-יתר, ואין מה להפיץ.")

    h("2. אותו סגל, עם ובלי")
    rng_seed = SEED
    rows = []
    for club, train_max, test in [("TEL", 2023, 2024), ("HTA", 2024, 2025)]:
        cand = prep(club, train_max, test, feat, anch, pos, ps)
        r = cr.roster_df(club, test)
        B = float(r.salary.dropna().sum()) + cr.budget_only_total(club, test)
        # ppm_sd אינו בבקטסט — נגזר משגיאת התחזית של המאגר
        sd = float(np.std(cand.ppm_true.values - cand.ppm.values))
        print(f"\n  {club} {test}  ·  ppm_sd = {sd:.3f}  ·  "
              f"rho = {rho:.4f}")
        print(f"  {'סגל':>5}{'ללא אי-ודאות':>15}{'עם':>10}"
              f"{'שינוי':>9}{'חוסר דקות':>12}")
        for mr in (MIN_LEGAL_ROSTER, 14, 16):
            sel, _ = optimise_v2(cand, B, mr)
            if sel is None:
                continue
            rr = cand[sel]
            args = (rr.ppm.values, np.full(len(rr), sd), rr.avail.values,
                    rr.position.values, 0.127)
            q0, s0 = simulate_av(*args, np.random.default_rng(rng_seed),
                                 rho=0.0)
            q1, s1 = simulate_av(*args, np.random.default_rng(rng_seed),
                                 rho=rho)
            m0, m1 = float(np.median(q0)), float(np.median(q1))
            print(f"  {len(rr):>5}{m0:>15.1f}{m1:>10.1f}"
                  f"{m1 / m0 - 1:>+8.1%}{s1:>11.1%}")
            rows.append(dict(club=club, n=len(rr), base=m0, unc=m1,
                             delta=m1 / m0 - 1, short=s1))

    h("3. הכרעת התחזיות")
    df = pd.DataFrame(rows)
    worst = float(df.delta.min())
    print(f"  ירידת הניקוד: מ-{df.delta.max():+.1%} עד {worst:+.1%}")
    verdict_score = ("down_small" if abs(worst) <= SCORE_SMALL_MAX
                     else "down_3_to_6" if abs(worst) <= 0.06
                     else "down_large")
    print(f"  -> {verdict_score}")
    print(f"     אלמוג ניבא  {PRED_ALMOG_SCORE}")
    print(f"     קלוד ניבא   {PRED_CLAUDE_SCORE}")

    print()
    for club in df.club.unique():
        s = df[df.club == club].set_index("n")
        if 12 in s.index and 16 in s.index:
            r0 = s.loc[16, "base"] / s.loc[12, "base"]
            r1 = s.loc[16, "unc"] / s.loc[12, "unc"]
            print(f"  {club}: יחס 16/12 — ללא {r0:.3f} | עם {r1:.3f} | "
                  f"שינוי {r1 / r0 - 1:+.2%}")
            if abs(r1 / r0 - 1) < DEPTH_MEANINGFUL_MIN:
                print(f"     -> מתחת ל-{DEPTH_MEANINGFUL_MIN:.0%}, "
                      "כלומר רעש. אלמוג ניבא רווח לעומק.")
            elif r1 > r0:
                print("     -> עומק הרוויח. **אלמוג צדק.**")
            else:
                print("     -> עומק הפסיד. שנינו טעינו בכיוון.")
    print(SEP)


if __name__ == "__main__":
    main()
