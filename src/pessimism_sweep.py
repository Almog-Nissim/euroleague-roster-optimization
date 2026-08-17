"""
pessimism_sweep.py  (Day 6)
---------------------------
האם בחירה פסימית מתקנת את קללת המנצח?

--------------------------------------------------------------------
🔴 גרסה 2 — מה השתנה ולמה
--------------------------------------------------------------------
גרסה 1 החזירה עקומה שטוחה לחלוטין ודיווחתי ש"הפסימיות נדחית".
backtest_diagnostics הראה ששתי הנחות שם היו שגויות:

1. **הגודל היה לא נכון.** ענשתי לפי ה**שארית** (השונות האמיתית
   בין שחקנים סביב התוחלת). אבל קללת המנצח נובעת משגיאת
   ה**אמידה**. הענשה לפי השארית מענישה כישרון אמיתי.

2. **הציר היה מנוון.** השארית נגזרה ממשתנה יחיד - דקות - וכל
   המועמדים הטובים שיחקו הרבה דקות. מקדם השונות בקרב 15
   המובילים: 12.7% (TEL), 7.1% (HTA). חיסור קבוע אינו משנה דירוג.

כלומר "העקומה שטוחה" לא היה ממצא על הפסימיות אלא על המבחן.

גרסה 2 מענישה לפי se_mean של ה-WLS, שגדל עם מינוף - גיל חריג,
פער עונות, מעט עונות יורוליג - ולא רק עם מיעוט דקות:

    ppm_selection = ppm_hat - lambda * ppm_se

ומדפיסה **כמה שחקנים באמת הוחלפו** בכל lambda. אם התשובה אפס,
הסווייפ לא בדק כלום - וזה נאמר במפורש ולא מוסתר מאחורי עקומה.

בנוסף: הניקוד עובר מילוי ברמת החלפה, והתקציב המושווה כולל אומדן
לשחקנים שאין להם שכר - שני תיקונים מ-optimizer_backtest.

**הרעיון אינו "להיות זהיר".** הוא שהתוחלת של הערך המתקבל,
בהינתן שנבחרת, נמוכה מהאומדן - וההפרש גדל עם השונות. הענשה
פרופורציונלית ל-sd היא התיקון הראשון-סדר.

--------------------------------------------------------------------
🔴 מגבלת התוקף - קראו לפני שקובעים lambda
--------------------------------------------------------------------
יש לנו **עונת מבחן אחת** (2024). מודל העלות דורש עוגנים, והם
מתחילים ב-2023 - ולכן אי אפשר לאמן על <=2022.

לכן lambda שייבחר כאן **מותאם לעונה בודדת**. זה לא כיול, זו
התאמה. מה שכן תקף:
  - **צורת העקומה**. אם היא שטוחה, lambda לא משנה וזה ממצא.
  - **הכיוון**. אם כל lambda>0 עדיף על 0, הפסימיות עוזרת גם אם
    הערך המדויק לא נקבע.

עונת 2025 אינה משמשת לאימות - היא עונת הדמו, וכיול עליה הורס
אותה. זו החלטה סגורה מיום 4.

הרצה:
    python src/audits/pessimism_sweep.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROCESSED_DIR
import roster_optimizer as ro
import optimizer_backtest as bt

LAMBDAS = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]

# שני תרחישי מבחן. הפועל 25/26 היא usage='test' ומעולם לא שימשה
# לכיול, לאימון או לכל דבר אחר - ולכן היא מבחן שני אמיתי:
# מועדון אחר, עונה אחרת, סגל שלא נגענו בו.
#
# מכבי 25/26 **אינה** נבדקת. היא עונת הדמו, וכיול עליה הורס
# אותה. החלטה סגורה מיום 4.
SCENARIOS = [("TEL", 2023, 2024), ("HTA", 2024, 2025)]
SEP = "=" * 74


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def add_sd(cand, lagged):
    """[גרסה 1 - נשמרת לתיעוד] ppm_sd מהטרוסקדסטיות: log|שארית| ~ log(דקות).

    🔴 backtest_diagnostics הראה שהציר הזה **מנוון**: בקרב 15
    המובילים מקדם השונות הוא 12.7% (TEL) ו-7.1% (HTA), כי כולם
    שיחקו הרבה דקות. חיסור lambda*sd מקבוצה שה-sd שלה כמעט זהה
    הוא חיסור קבוע - והוא אינו משנה דירוג.

    ובנוסף: זו **השארית**, לא שגיאת האמידה. ראו add_se למטה.
    """
    tr = lagged[lagged.season <= bt.TRAIN_MAX]
    PF = ["ppm_lag_shrunk", "min_pg_lag", "age_c", "el_seasons_lag"]
    m = sm.WLS(tr.ppm, sm.add_constant(tr[PF].astype(float)),
               weights=tr.minutes_tot).fit()
    r = tr.ppm - m.predict(sm.add_constant(tr[PF].astype(float)))
    d = tr[tr.min_pg_lag > 0].copy()
    d["a"] = np.abs(r[d.index])
    sd_m = sm.OLS(np.log(d.a.clip(lower=1e-4)),
                  sm.add_constant(np.log(d.min_pg_lag))).fit()
    cand = cand.copy()
    cand["ppm_sd"] = np.exp(sd_m.predict(sm.add_constant(
        np.log(cand.min_pg_lag.clip(lower=1.0))))) * 1.2533
    return cand


def add_se(cand, pm, PF):
    """[גרסה 2 - זו שנבדקת] שגיאת **האמידה** של התחזית, se_mean.

    --------------------------------------------------------------
    למה זה הגודל הנכון
    --------------------------------------------------------------
    קללת המנצח נובעת מכך שהאופטימייזר בוחר את מי ש-ppm_hat שלו
    גבוה, כולל את מי ששגיאת ה**אמידה** שלו חיובית. אלה נסוגים.

    השארית היא משהו אחר לגמרי: היא שונות אמיתית בין שחקנים סביב
    התוחלת. שחקן שבאמת טוב מהתחזית אינו טעות שצריך להעניש - הוא
    בדיוק מה שמחפשים. הענשה לפי השארית מענישה כישרון.

    בגרסה 1 השתמשתי בשארית. זו הייתה טעות מושגית, ולא רק ציר
    חלש.

    --------------------------------------------------------------
    ולמה דווקא לזה יש פיזור
    --------------------------------------------------------------
    se_mean גדל עם **מינוף** - כמה חריג הוא הצירוף של הפיצ'רים
    ביחס למדגם האימון. שחקן בן 36, שחקן עם פער של 3 עונות, שחקן
    בעונת יורוליג ראשונה: לכולם se גדול, גם אם שיחקו 30 דקות.

    זה בדיוק המידע שהציר הקודם לא הכיל.
    """
    cand = cand.copy()
    X = sm.add_constant(cand[PF].astype(float), has_constant="add")
    pr = pm.get_prediction(X)
    cand["ppm_se"] = np.asarray(pr.se_mean)
    return cand


def run_scenario(club, train_max, test, feat, anch, pos, ps):
    bt.TRAIN_MAX, bt.TEST, bt.TARGET_CLUB = train_max, test, club
    h(f"תרחיש: {club} {test}  (אימון <={train_max})")
    cm, smear, agg, am, pm, PF, lagged = bt.fit_models(ps, feat, anch)
    cand = bt.build(lagged, feat, pos, cm, smear, agg, am, pm, PF,
                    bt.scale_for(anch, club, test))
    cand["ppm_true"] = cand.pir_per_game / cand.min_per_game
    cand["avail_true"] = cand.frac
    cand = add_sd(cand, lagged)          # הציר הישן, להשוואה
    cand = add_se(cand, pm, PF)          # הציר שנבדק

    known, imputed, miss = bt.fair_budget(cand, anch, club, test,
                                          cm, smear, None)
    B_fair = known + imputed
    rt = bt.repl_level(cand, "ppm_true")
    rp = bt.repl_level(cand, "ppm")
    real = cand[cand.team.astype(str).str.contains(bt.TARGET_CLUB, na=False)]
    q_real = bt.score(real, "ppm_true", "avail_true", rt)

    print(f"  מועמדים: {len(cand)} | תקציב מושווה {B_fair:,.0f} "
          f"({known:,.0f} ידוע + {imputed:,.0f} אומדן) | "
          f"המועדון בפועל {q_real:.1f}")

    # --- האם לציר החדש יש פיזור שלציר הישן לא היה? ---
    top = cand.nlargest(15, "ppm")
    print(f"\n  פיזור בקרב 15 המובילים (מקדם שונות):")
    print(f"    ppm_sd  (שארית, הישן) : {top.ppm_sd.std() / top.ppm_sd.mean():>6.1%}"
          f"   ממוצע {top.ppm_sd.mean():.4f}")
    print(f"    ppm_se  (אמידה, החדש): {top.ppm_se.std() / top.ppm_se.mean():>6.1%}"
          f"   ממוצע {top.ppm_se.mean():.4f}")
    print(f"    הפרש ppm בין מקום 1 ל-15: "
          f"{top.ppm.max() - top.ppm.min():.4f}")
    if top.ppm_se.std() / top.ppm_se.mean() < 0.15:
        print("    🔴 גם הציר החדש מנוון. הסווייפ למטה לא בודק כלום.")

    print(f"\n{'lambda':>7}{'n':>4}{'לפי המודל':>12}{'לפי המציאות':>14}"
          f"{'קללה':>10}{'מול המועדון':>13}{'חילופים':>10}")
    rows = []
    base = cand.ppm.copy()
    ref = None
    for lam in LAMBDAS:
        c = cand.copy()
        c["ppm"] = base - lam * c.ppm_se          # דירוג פסימי
        best = None
        for mr in range(6, 17):
            sel, mins = ro.optimise(c, B_fair, mr)
            if sel is None:
                continue
            qp = bt.score(c[sel], "ppm", "avail", rp)
            if best is None or qp > best[0]:
                best = (qp, sel)
        if best is None:
            continue
        sel = best[1]
        codes = set(cand.loc[sel, "player_code"])
        if ref is None:
            ref = codes
        swaps = len(ref - codes)
        r = cand[sel]                              # ניקוד לפי המציאות
        qt = bt.score(r, "ppm_true", "avail_true", rt)
        qm = bt.score(r, "ppm", "avail", rp)
        rows.append({"lambda": lam, "n": int(sel.sum()),
                     "model": qm, "true": qt, "swaps": swaps,
                     "curse": qt / qm - 1, "vs": qt / q_real - 1})
        print(f"{lam:>7.2f}{int(sel.sum()):>4}{qm:>12.1f}{qt:>14.1f}"
              f"{qt / qm - 1:>+12.1%}{qt / q_real - 1:>+10.1%}"
              f"{swaps:>10d}")

    if rows and max(r["swaps"] for r in rows) == 0:
        print("\n  🔴 אף שחקן לא הוחלף באף lambda. הסווייפ לא בדק")
        print("  את הפסימיות - הוא הריץ שבע פעמים את אותו סגל.")

    return pd.DataFrame(rows)


def main():
    print(SEP)
    print("סווייפ פסימיות — שני תרחישי מבחן בלתי תלויים")
    print(SEP)
    feat, anch, pos, ps = bt.load_all()
    out = {}
    for club, tr, te in SCENARIOS:
        out[f"{club} {te}"] = run_scenario(club, tr, te, feat, anch,
                                           pos, ps)

    h("השוואה בין התרחישים")
    print(f"{'lambda':>7}" + "".join(f"{k:>16}" for k in out))
    for lam in LAMBDAS:
        line = f"{lam:>7.2f}"
        for k, t in out.items():
            r = t[t["lambda"] == lam]
            line += (f"{r.iloc[0]['vs']:>+15.1%} " if len(r)
                     else f"{'—':>16}")
        print(line)

    print("\n  שני התרחישים אינם חולקים מועדון, עונה, או סגל.")
    agree = []
    for lam in LAMBDAS:
        v = [t[t["lambda"] == lam]["vs"].iloc[0]
             for t in out.values() if len(t[t["lambda"] == lam])]
        if len(v) == len(out) and all(x > 0 for x in v):
            agree.append(lam)
    if agree:
        print(f"  ✅ lambda שחיובי **בשניהם**: {agree}")
        print("  זה אימות, לא התאמה - התרחיש השני לא שימש לבחירה.")
    else:
        print("  🔴 אין lambda שחיובי בשני התרחישים.")
        print("  הממצא מהתרחיש הראשון **לא אומת**. אין לקבע ערך.")

    t = list(out.values())[0]
    h("קריאה — התרחיש הראשון")
    best = t.loc[t["true"].idxmax()]
    print(f"  שיא לפי המציאות: lambda={best['lambda']:.2f} | "
          f"{best['true']:.1f} | מול מכבי {best['vs']:+.1%}")
    zero = t[t["lambda"] == 0].iloc[0]
    print(f"  ללא פסימיות    : lambda=0.00 | "
          f"{zero['true']:.1f} | מול מכבי {zero['vs']:+.1%}")
    gain = best["true"] / zero["true"] - 1
    print(f"\n  רווח מהפסימיות: {gain:+.1%}")

    spread = (t["true"].max() - t["true"].min()) / t["true"].mean()
    print(f"  פיזור העקומה  : {spread:.1%}")
    if spread < 0.05:
        print("\n  העקומה שטוחה. **lambda אינו משנה** - וזה ממצא:")
        print("  קללת המנצח אינה נובעת מהבדלי שונות בין מועמדים.")
    elif best["lambda"] > 0 and (t[t["lambda"] > 0]["true"] >
                                 zero["true"]).all():
        print("\n  **כל lambda>0 עדיף על 0.** הכיוון תקף גם אם הערך")
        print("  המדויק מותאם לעונה בודדת.")
    else:
        print("\n  העקומה אינה מונוטונית. עם עונת מבחן אחת אי אפשר")
        print("  להבחין בין אופטימום אמיתי לרעש.")

    print("\n  🔴 עונת מבחן אחת. lambda שנבחר כאן מותאם אליה,")
    print("  ואינו מכויל. הצורה והכיוון תקפים; המספר לא.")
    print(SEP)


if __name__ == "__main__":
    main()