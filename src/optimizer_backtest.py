"""
optimizer_backtest.py  (Day 6)
------------------------------
המבחן החוץ-מדגמי של **המנוע כולו**, לא של רכיב בודד.

--------------------------------------------------------------------
מה הוא בודק, ולמה זה לא נבדק עד עכשיו
--------------------------------------------------------------------
המונטה קרלו במנוע מגריל  ppm ~ N(ppm_hat, ppm_sd)  - כלומר ממורכז
סביב **אותו אומדן שבחר את השחקן**.

אבל האופטימייזר בוחר בדיוק את מי שה-ppm_hat שלו גבוה, וזה כולל
את מי ששגיאת האמידה שלו חיובית. **קללת המנצח.** בעולם האמיתי הם
נסוגים לממוצע, והמונטה קרלו לא יכול לראות את זה - הוא מעריך את
הבחירות באותו מודל שעשה אותן.

זה בדיוק הכשל שתפסנו במבחן הפועל ביום 5, ברמה אחת מעל.

--------------------------------------------------------------------
המבנה
--------------------------------------------------------------------
    אימון:  כל המודלים על עונות יעד <= TRAIN_MAX
    בחירה:  האופטימייזר בונה סגל לעונת TEST
    ניקוד:  לפי מה ש**באמת קרה** ב-TEST -
            ppm בפועל, שיעור המשחקים בפועל.
            **אף מודל לא נוגע בצד הניקוד.**

הבנצ'מרק: הסגל האמיתי של מועדון היעד באותה עונה, מנוקד באותה
פונקציה בדיוק.

--------------------------------------------------------------------
מה זה עדיין לא בודק
--------------------------------------------------------------------
- ה-20 סגלים האמיתיים מממשים 100% בהגדרה; סגל האופטימייזר לא
- מאגר המועמדים הוא כל מי ששיחק ביורוליג. מכבי לא יכלה להחתים
  את כולם - זמינות בשוק, תחרות, ורצון השחקן אינם במודל
- התקציב מושווה, אבל **הסקלה** של העלות עדיין של מודל

הרצה:
    python src/audits/optimizer_backtest.py
"""

import io
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROCESSED_DIR
import roster_optimizer as ro

TRAIN_MAX = 2023
TEST = 2024
TARGET_CLUB = "TEL"
SEP = "=" * 74


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def load_all():
    return (pd.read_csv(PROCESSED_DIR / f, dtype={"player_code": str})
            for f in ("player_features.csv", "salary_anchors.csv",
                      "player_positions.csv", "player_season.csv"))


def fit_models(ps, feat, anch):
    """כל המודלים על עונות יעד <= TRAIN_MAX. אין הצצה ל-TEST.

    ⚠️ המפרטים חייבים להיות זהים לאלה של roster_optimizer, אחרת
    הבקטסט בודק מודל אחר מזה שרץ. נבדק מפורשות למטה.
    """
    cal_all = anch[(anch.usage == "calibrate") & (anch.season <= TRAIN_MAX)]
    agg = cal_all.groupby(["club", "season"]).salary_mid.agg(["sum", "size"])
    agg.columns = ["payroll", "n"]
    agg["mean_salary"] = agg.payroll / agg.n
    cal = cal_all[cal_all.player_code.notna()].merge(
        agg, left_on=["club", "season"], right_index=True)
    cal["log_rel"] = np.log(cal.salary_mid / cal.mean_salary)
    dc = cal.merge(feat, on=["player_code", "season"], how="inner",
                   suffixes=("", "_f")).dropna(
        subset=ro.COST_FEATURES + ["log_rel"])
    cm = sm.OLS(dc.log_rel,
                sm.add_constant(dc[ro.COST_FEATURES].astype(float))).fit()
    smear = float(np.mean(np.exp(cm.resid)))

    gmax = ps.groupby("season").games.max().rename("gmax")
    p2 = ps.merge(gmax, left_on="season", right_index=True)
    p2["frac"] = p2.games / p2.gmax
    p2 = p2[p2.min_per_game > 0].copy()
    p2["ppm"] = p2.pir_per_game / p2.min_per_game
    p2["minutes_tot"] = p2.min_per_game * p2.games
    p2 = p2.sort_values(["player_code", "season"])
    g = p2.groupby("player_code", sort=False)
    for c, o in [("frac", "frac_lag"), ("min_per_game", "min_pg_lag"),
                 ("ppm", "ppm_lag"), ("minutes_tot", "mins_lag"),
                 ("season", "season_lag")]:
        p2[o] = g[c].shift(1)
    p2["el_seasons_lag"] = g.cumcount()
    p2["age_c"] = p2.age - ro.AGE_CENTER
    # תיקון יום 6: הפער נכנס כמשתנה ולא כמסנן. בלי זה הקובץ הזה
    # מתאמן על מפרט אחר מזה של המנוע - וההשוואה חסרת ערך.
    p2["gap"] = p2.season - p2.season_lag
    p2["log_gap"] = np.log(p2.gap)
    lagged = p2[p2.gap.notna() & (p2.gap >= 1) &
                p2.ppm_lag.notna()].copy()
    league = float((lagged.ppm_lag * lagged.mins_lag).sum() /
                   lagged.mins_lag.sum())
    w = lagged.mins_lag / (lagged.mins_lag + ro.K_PPM)
    lagged["ppm_lag_shrunk"] = w * lagged.ppm_lag + (1 - w) * league

    tr = lagged[lagged.season <= TRAIN_MAX]
    am = sm.GLM(np.column_stack([tr.games, tr.gmax - tr.games]),
                sm.add_constant(tr[ro.AVAIL_FEATURES].astype(float)),
                family=sm.families.Binomial()).fit()
    PF = ["ppm_lag_shrunk", "min_pg_lag", "age_c",
          "el_seasons_lag", "log_gap"]
    pm = sm.WLS(tr.ppm, sm.add_constant(tr[PF].astype(float)),
                weights=tr.minutes_tot).fit()

    missing = set(ro.AVAIL_FEATURES) - set(tr.columns)
    if missing:
        raise ValueError(
            f"פיצ'רי זמינות חסרים בבקטסט: {missing}. "
            "המנוע עודכן והקובץ הזה לא.")
    print(f"  עלות   : n={int(cm.nobs)} R2={cm.rsquared:.3f}")
    print(f"  זמינות : n={int(am.nobs)}")
    print(f"  תפוקה  : n={int(pm.nobs)} R2={pm.rsquared:.3f}")
    return cm, smear, agg, am, pm, PF, lagged


def scale_for(anch, club, season):
    """הסקלה (שכר ממוצע) של מועדון היעד בעונת המבחן.

    לא ניתן לקחת אותה מ-agg: agg מכיל רק שורות calibrate, כלומר
    מכבי. הפועל היא usage='test' ואינה שם. והתקציב ממילא נתון -
    הוא אילוץ, לא תחזית - ולכן גם הסקלה שלו נתונה.
    """
    t = anch[(anch.club == club) & (anch.season == season)]
    if t.empty:
        raise ValueError(f"אין עוגנים ל-{club} {season}")
    return float(t.salary_mid.sum() / len(t))


def build(lagged, feat, pos, cm, smear, agg, am, pm, PF, mean_salary):
    cand = lagged[lagged.season == TEST].copy()
    cand = cand.drop(columns=[c for c in ("team",) if c in cand.columns])
    cand = cand.merge(feat[feat.season == TEST][
        ["player_code", "pir_lag_shrunk", "el_seasons", "team"]],
        on="player_code", how="inner")
    cand = cand.merge(pos[["player_code", "position"]], on="player_code",
                      how="left").dropna(subset=["position"])

    X = sm.add_constant(cand[ro.COST_FEATURES].astype(float),
                        has_constant="add")
    cand["cost"] = np.exp(cm.predict(X)) * smear * mean_salary
    cand["avail"] = am.predict(sm.add_constant(
        cand[ro.AVAIL_FEATURES].astype(float), has_constant="add"))
    cand["ppm"] = pm.predict(sm.add_constant(cand[PF].astype(float)))
    cand["ppm_sd"] = 0.0
    # --- מה שבאמת קרה. לא נכנס לשום מודל. ---
    cand["ppm_true"] = cand.ppm            # יוחלף מיד
    return cand.reset_index(drop=True)


def score(r, ppm_col, avail_col, repl=None):
    """ניקוד לפי מה שבאמת קרה. חלוקת דקות חמדנית תחת תקרות עמדה.

    זו אותה פונקציה שמדרגת את שני הצדדים - אחרת ההשוואה חסרת ערך.

    --- תיקון יום 6, אחרי backtest_diagnostics ---
    הגרסה הקודמת עצרה כשנגמרו השחקנים, ולא כשנגמרו הדקות. סגל של
    7 שחקנים מילא 167 דקות מתוך 200 וקיבל ניקוד נמוך **בגלל גודלו
    ולא בגלל איכותו**. זו בדיוק הבעיה שכבר טופלה ב-roster_optimizer
    ולא כאן, ולכן שני הצדדים לא נוקדו באותה סרגל.

    repl = ppm ברמת החלפה. הדקות שנשארות ממולאות בו. קבוצה לא
    משחקת 4 על 5, וגם לא 200 דקות עם 7 שחקנים.
    """
    ppm = r[ppm_col].values
    av = r[avail_col].values
    pos = r.position.values
    order = np.argsort(-ppm)
    caps = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
            for g in ro.POS_MAX_SHARE}
    left = ro.MINUTES_PER_GAME
    q = 0.0
    for j in order:
        g = pos[j]
        take = min(ro.MAX_MIN_PLAYER, left, caps[g]) * av[j]
        take = max(take, 0.0)
        q += take * ppm[j]
        left -= take
        caps[g] -= take
    if repl is not None and left > 0:
        q += left * repl              # מילוי ברמת החלפה
    return q


def repl_level(cand, col):
    """רמת החלפה: אחוזון REPLACEMENT_PCTL של אותה עמודה שמנוקדת.

    חייב להיות מאותה עמודה - רמת החלפה לפי המודל ורמת החלפה לפי
    המציאות אינן אותו מספר, ולערבב ביניהן זה להשוות שני סרגלים.
    """
    return float(np.percentile(cand[col].values, ro.REPLACEMENT_PCTL))


def fair_budget(cand, anch, club, season, cm, smear, mean_salary):
    """התקציב שמולו מושווה המנוע — כולל אומדן למי שאין לו שכר.

    --- למה זה נדרש ---
    בגרסה הקודמת התקציב היה סכום השכר של **העוגנים בלבד**, אבל
    המועדון נוקד על **כל** שחקניו במאגר. במכבי 2024 זה אומר ששני
    שחקנים - אחד מהם ג'ורדן לויד עם 22.8 דקות למשחק - נספרו
    בתפוקה ולא בעלות. הם היו חינם.

    שתי הדרכים לתקן אינן שקולות:
      - לצמצם את המועדון למתומחרים -> ארטיפקט גודל סגל (נמדד: 167
        דקות בלבד). מחליף הטיה בהטיה.
      - לאמוד את השכר החסר במודל העלות -> משתמש **רק** בפיצ'רים
        (pir_lag, el_seasons), לעולם לא בשכר של עונת המבחן.

    השנייה נבחרה. היא מגדילה את התקציב, כלומר **מיטיבה עם המנוע**,
    ולכן מדווחים גם את הישן וגם את החדש.
    """
    a = anch[(anch.club == club) & (anch.season == season)]
    priced = set(a.player_code)
    mine = cand[cand.team.astype(str).str.contains(club, na=False)]
    known = float(a[a.player_code.isin(set(cand.player_code))].salary_mid.sum())
    miss = mine[~mine.player_code.isin(priced)]
    imputed = float(miss.cost.sum()) if len(miss) else 0.0
    return known, imputed, miss


def main():
    print(SEP)
    print(f"BACKTEST של המנוע — אימון <= {TRAIN_MAX}, מבחן {TEST}")
    print("הניקוד לפי מה שבאמת קרה. אף מודל לא נוגע בו.")
    print(SEP)

    feat, anch, pos, ps = load_all()
    h("1. אימון")
    cm, smear, agg, am, pm, PF, lagged = fit_models(ps, feat, anch)

    h("2. מאגר המועמדים")
    cand = build(lagged, feat, pos, cm, smear, agg, am, pm, PF,
                 scale_for(anch, TARGET_CLUB, TEST))
    # התוצאה בפועל
    cand["ppm_true"] = cand.pir_per_game / cand.min_per_game
    cand["avail_true"] = cand.frac
    print(f"  {len(cand)} מועמדים לעונת {TEST}")
    print(f"  ppm חזוי חציון {cand.ppm.median():.4f} | "
          f"בפועל {cand.ppm_true.median():.4f}")
    print(f"  זמינות חזויה {cand.avail.median():.3f} | "
          f"בפועל {cand.avail_true.median():.3f}")

    tel = anch[(anch.club == TARGET_CLUB) & (anch.season == TEST)]
    real = cand[cand.team.astype(str).str.contains(TARGET_CLUB, na=False)]
    known, imputed, miss = fair_budget(cand, anch, TARGET_CLUB, TEST,
                                       cm, smear, None)
    B_old = known
    B_fair = known + imputed
    B_full = float(tel.salary_mid.sum())
    print(f"\n  תקציב {TARGET_CLUB} {TEST}:")
    print(f"    מלא (כל העוגנים)      {B_full:>14,.0f}")
    print(f"    שכר ידוע במאגר        {known:>14,.0f}")
    print(f"    אומדן ל-{len(miss)} ללא שכר      {imputed:>14,.0f}")
    for t in miss.itertuples():
        print(f"      {str(t.player_name)[:26]:<28}"
              f"{t.cost:>12,.0f}   {t.min_per_game:.1f} דק'")
    print(f"    תקציב מושווה מתוקן    {B_fair:>14,.0f}")

    rt = repl_level(cand, "ppm_true")
    rp = repl_level(cand, "ppm")
    print(f"\n  רמת החלפה (אחוזון {ro.REPLACEMENT_PCTL}): "
          f"לפי המציאות {rt:.4f} | לפי המודל {rp:.4f}")

    h("3. התוצאה")
    q_real_true = score(real, "ppm_true", "avail_true", rt)
    q_real_pred = score(real, "ppm", "avail", rp)
    print(f"  {TARGET_CLUB} בפועל ({len(real)} שחקנים, מילוי החלפה):")
    print(f"    ניקוד לפי המודל   {q_real_pred:>8.1f}")
    print(f"    ניקוד לפי המציאות {q_real_true:>8.1f}")

    print(f"\n{'תקציב':<24}{'n':>4}{'לפי המודל':>12}{'לפי המציאות':>14}"
          f"{'קללת המנצח':>14}{'מול מכבי':>12}")
    for lab, b in [("מלא", B_full), ("ידוע בלבד (ישן)", B_old),
                   ("מושווה מתוקן", B_fair)]:
        best = None
        for mr in range(6, 17):
            sel, mins = ro.optimise(cand, b, mr)
            if sel is None:
                continue
            r = cand[sel]
            qp = score(r, "ppm", "avail", rp)
            if best is None or qp > best[0]:
                best = (qp, r)
        if best is None:
            print(f"{lab:<24}{'—':>4}   אין פתרון")
            continue
        qp, r = best
        qt = score(r, "ppm_true", "avail_true", rt)
        print(f"{lab:<24}{len(r):>4}{qp:>12.1f}{qt:>14.1f}"
              f"{qt / qp - 1:>+13.1%}{qt / q_real_true - 1:>+11.1%}")

    h("4. קריאה")
    print("  'קללת המנצח' = כמה ירד הניקוד כשעוברים מהמודל למציאות.")
    print("  אם הוא שלילי וגדול, האופטימייזר בוחר שחקנים ששגיאת")
    print("  האמידה שלהם חיובית - ובעולם האמיתי הם נסוגים לממוצע.")
    print("\n  השורה הקובעת: **מושווה מתוקן**. רק בה שני הצדדים")
    print("  נספרים על אותו כסף ומשחקים אותן 200 דקות.")
    print("\n  השורה 'ידוע בלבד' היא מה שדווח קודם. היא נשארת כדי")
    print("  שיהיה אפשר לראות כמה מהמספר נבע מהחלטת ספירה ולא")
    print("  מהמנוע.")
    print(SEP)


if __name__ == "__main__":
    main()