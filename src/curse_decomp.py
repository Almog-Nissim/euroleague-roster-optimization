"""
curse_decomp.py  (Day 7)
------------------------
מפרק את קללת המנצח לשני מקורות, ומודד את הטיית הבחירה ישירות.

--------------------------------------------------------------------
השאלה
--------------------------------------------------------------------
benchmark_matched הראה שהפער הגדול של יום 6 בין שני התרחישים
(+21.2% מול -0.5%) היה **ארטיפקט של הגדרת הבנצ'מרק**. בהשוואה
המלאה שני התרחישים מסכימים: +9.4% ו-+11.2%.

מה שנשאר לא מוסבר הוא קללת המנצח: -6.2% מול -11.9%.

הניקוד הוא  Σ דקות(i) · avail(i) · ppm(i), ולכן יש בדיוק שני
מקורות לפער בין המודל למציאות:

    ppm חזוי  != ppm בפועל
    avail חזוי != avail בפועל

הפירוק מבודד כל אחד מהם: מנקדים את **אותו סגל** ארבע פעמים,
בכל צירוף של חזוי/בפועל. ההפרש בין הצירופים הוא התרומה.

--------------------------------------------------------------------
הטיית הבחירה
--------------------------------------------------------------------
קללת המנצח היא טענה על **בחירה**, לא על דיוק כללי: המודל אמור
לטעות לשני הכיוונים במאגר כולו, אבל לטעות **כלפי מעלה** דווקא
על מי שנבחר. לכן שגיאת התחזית נמדדת פעמיים — על הנבחרים ועל
המאגר — וההפרש ביניהם הוא הטיית הבחירה.

אם השגיאה על הנבחרים שווה לזו של המאגר, אין קללת מנצח; יש
מודל לא מדויק. אלה שני ליקויים שונים עם שני תיקונים שונים.

הרצה:
    python src/curse_decomp.py
"""

import io
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster_optimizer as ro
import optimizer_backtest as ob
from roster_membership_audit import score_rows
from benchmark_matched import best_roster

SCENARIOS = [("TEL", 2023, 2024), ("HTA", 2024, 2025)]
SEP = "=" * 78


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def main():
    print(SEP)
    print("פירוק קללת המנצח — ppm מול זמינות, ובחירה מול מאגר")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    summary = []

    for club, train_max, test in SCENARIOS:
        ob.TRAIN_MAX, ob.TEST, ob.TARGET_CLUB = train_max, test, club
        with contextlib.redirect_stdout(io.StringIO()):
            cm, smear, agg, am, pm, PF, lagged = ob.fit_models(ps, feat, anch)
            cand = ob.build(lagged, feat, pos, cm, smear, agg, am, pm, PF,
                            ob.scale_for(anch, club, test))
        cand["ppm_true"] = cand.pir_per_game / cand.min_per_game
        cand["avail_true"] = cand.frac

        a = anch[(anch.club == club) & (anch.season == test)]
        B_full = float(a.salary_mid.sum())
        rt = float(np.percentile(cand.ppm_true.values, ro.REPLACEMENT_PCTL))
        rp = float(np.percentile(cand.ppm.values, ro.REPLACEMENT_PCTL))

        qp, r = best_roster(cand, B_full)

        h(f"{club} {test}  —  סגל נבחר: {len(r)} שחקנים, תקציב "
          f"{B_full:,.0f}")

        # --- פירוק: אותו סגל, ארבעה צירופים ---
        q_pp, _, _ = score_rows(r, "ppm", "avail", rp)          # מודל מלא
        q_tp, _, _ = score_rows(r, "ppm_true", "avail", rt)     # ppm אמיתי
        q_pt, _, _ = score_rows(r, "ppm", "avail_true", rp)     # avail אמיתי
        q_tt, _, _ = score_rows(r, "ppm_true", "avail_true", rt)

        print(f"  {'ppm':<10}{'avail':<10}{'ניקוד':>9}")
        print(f"  {'חזוי':<10}{'חזוי':<10}{q_pp:>9.1f}   (המודל)")
        print(f"  {'בפועל':<10}{'חזוי':<10}{q_tp:>9.1f}")
        print(f"  {'חזוי':<10}{'בפועל':<10}{q_pt:>9.1f}")
        print(f"  {'בפועל':<10}{'בפועל':<10}{q_tt:>9.1f}   (המציאות)")

        d_ppm = q_tp - q_pp
        d_av = q_pt - q_pp
        d_tot = q_tt - q_pp
        inter = d_tot - d_ppm - d_av
        print(f"\n  קללה כוללת            {d_tot:>+8.1f}  "
              f"({d_tot / q_pp:>+6.1%})")
        print(f"    מתוכה — שגיאת ppm   {d_ppm:>+8.1f}  "
              f"({d_ppm / abs(d_tot) if d_tot else 0:>6.0%} מהפער)")
        print(f"    מתוכה — שגיאת זמינות{d_av:>+8.1f}  "
              f"({d_av / abs(d_tot) if d_tot else 0:>6.0%} מהפער)")
        print(f"    אינטראקציה          {inter:>+8.1f}")

        # --- הטיית בחירה: נבחרים מול מאגר ---
        def bias(df, pred, true):
            e = df[true].values - df[pred].values
            return float(np.mean(e)), float(np.mean(np.abs(e)))

        sel_p, sel_a = bias(r, "ppm", "ppm_true")
        pool_p, pool_a = bias(cand, "ppm", "ppm_true")
        sel_v, sel_va = bias(r, "avail", "avail_true")
        pool_v, pool_va = bias(cand, "avail", "avail_true")

        print(f"\n  {'':<14}{'הטיה (בפועל-חזוי)':>20}{'MAE':>10}")
        print(f"  {'ppm נבחרים':<14}{sel_p:>20.4f}{sel_a:>10.4f}")
        print(f"  {'ppm מאגר':<14}{pool_p:>20.4f}{pool_a:>10.4f}")
        print(f"  {'→ הטיית בחירה':<14}{sel_p - pool_p:>20.4f}")
        print(f"  {'זמינות נבחרים':<14}{sel_v:>20.4f}{sel_va:>10.4f}")
        print(f"  {'זמינות מאגר':<14}{pool_v:>20.4f}{pool_va:>10.4f}")
        print(f"  {'→ הטיית בחירה':<14}{sel_v - pool_v:>20.4f}")

        if sel_p < pool_p:
            print("\n  ✅ קללת מנצח אמיתית ב-ppm: הנבחרים מאכזבים יותר")
            print("     מהמאגר. הבחירה עצמה מטה כלפי מעלה.")
        else:
            print("\n  ⚠️ אין הטיית בחירה ב-ppm — השגיאה על הנבחרים אינה")
            print("     גרועה מזו של המאגר. זה לא קללת מנצח אלא אי-דיוק.")

        summary.append(dict(club=club, curse=d_tot / q_pp,
                            share_ppm=d_ppm / d_tot if d_tot else np.nan,
                            share_av=d_av / d_tot if d_tot else np.nan,
                            sel_bias_ppm=sel_p - pool_p,
                            sel_bias_av=sel_v - pool_v,
                            n=len(r)))

    h("השוואה בין התרחישים")
    s = pd.DataFrame(summary)
    print(s.to_string(index=False,
                      float_format=lambda v: f"{v:.4f}"))
    print("\n  אם חלוקת המקורות שונה בין התרחישים, 'קללת המנצח' אינה")
    print("  תופעה אחת אלא שם לשתי בעיות נפרדות.")
    print(SEP)


if __name__ == "__main__":
    main()
