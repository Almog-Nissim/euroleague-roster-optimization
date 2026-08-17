"""
v0_degeneracy_audit.py  (Day 6)
-----------------------
שלד מקצה לקצה. **מכוער בכוונה. נועד להיזרק.**

מטרתו אינה תוצאה - היא לגלות את התפרים בין הרכיבים לפני שכל אחד
מהם מלוטש בנפרד.

--------------------------------------------------------------------
הנימוק
--------------------------------------------------------------------
באג ה-share ישב בקוד יומיים. הוא עבר ניתוח רגישות ל-k, השמטת
עונה, מבחן טאוטולוגיה ובדיקת סימנים - ולא נראה. הוא התגלה רק
כשהמודל פגש סגל שני.

באגים מהסוג הזה חיים **בתפרים בין רכיבים**, והם בלתי נראים כל עוד
הרכיבים לא נפגשים. הקובץ הזה מכריח אותם להיפגש היום.

--------------------------------------------------------------------
מה כאן אמיתי ומה פלסטר - קראו לפני שמסתכלים על מספר כלשהו
--------------------------------------------------------------------
אמיתי:
  - מודל העלות: המפרט הסגור של יום 5 על log_rel
  - מודל השרידות: המפרט הסגור של יום 3
  - עמדות: 100% כיסוי, אילוץ שנגזר מהסגלים בפועל
  - אילוץ התקציב והספירה

🔴 פלסטר v0 - כל אחד מאלה יוחלף:
  1. pir_hat = pir_lag_shrunk גולמי. **אין מודל תפוקה.**
     זה מניח שהתפוקה בעונה הבאה שווה למשוקללת של הקודמות.
  2. expected_games = P(survive) * G_REF. מודל השרידות מנבא
     *נוכחות בעונה הבאה*, לא מספר משחקים. G_REF הוא קבוע מוצהר.
  3. אי-הוודאות על התפוקה היא CV מוצהר. **אין לה אומדן.**
     זה הפער הגדול ביותר בפרויקט, והמונטה קרלו כאן מדגים מנגנון
     ולא מודד אי-ודאות אמיתית.
  4. mean_salary_ref של מכבי מוחל על כל המועמדים.

**אף מספר בקובץ הזה אינו תוצאה של הפרויקט.**
--------------------------------------------------------------------

הרצה:
    pip install pulp
    python src/audits/v0_degeneracy_audit.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pulp
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROCESSED_DIR

# ---------------- פרמטרים מוצהרים ----------------
DEMO_SEASON = 2025
TARGET_CLUB = "TEL"
COST_FEATURES = ["pir_lag_shrunk", "el_seasons"]
AGE_CENTER = 27.0

MAX_ROSTER = 16
POS_FLOOR = {"G": 2, "F": 1, "C": 1}      # נגזר מהסגלים בפועל, יום 6

# תקרת דקות: 5 שחקנים על הפרקט * 40 דקות = 200 דקות-שחקן למשחק.
# ההחלטה הזו כבר נרשמה ביום 4 ("12 = לכל מפגש, מובלע בדקות") ולא
# יושמה. בלעדיה, שחקן ה-16 מוסיף תפוקה בחינם - אין שום דבר שמתחרה
# על הפרקט, והאופטימייזר קונה 16 שחקני רוטציה זולים.
MINUTES_CAP = 200.0

G_REF = 30                                 # 🔴 פלסטר 2
PIR_CV = 0.25                              # 🔴 פלסטר 3
N_DRAWS = 200
SEED = 7
# -------------------------------------------------

SEP = "=" * 74


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


# ============ 1. עלות ============
def cost_side():
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})

    cal_all = anch[anch.usage == "calibrate"].copy()
    agg = cal_all.groupby(["club", "season"]).salary_mid.agg(["sum", "size"])
    agg.columns = ["payroll", "n"]
    agg["mean_salary"] = agg.payroll / agg.n

    cal = cal_all[cal_all.player_code.notna()].merge(
        agg, left_on=["club", "season"], right_index=True)
    cal["log_rel"] = np.log(cal.salary_mid / cal.mean_salary)
    d = cal.merge(feat, on=["player_code", "season"], how="inner",
                  suffixes=("", "_f")).dropna(subset=COST_FEATURES + ["log_rel"])

    X = sm.add_constant(d[COST_FEATURES].astype(float))
    m = sm.OLS(d.log_rel, X).fit(cov_type="cluster",
                                 cov_kwds={"groups": d.player_code})
    smear = float(np.mean(np.exp(m.resid)))
    sigma = float(np.std(m.resid, ddof=len(m.params)))

    # התקציב והסקלה של עונת הדמו אצל מועדון היעד
    ref = agg.loc[(TARGET_CLUB, DEMO_SEASON)]
    B, N_ref, mean_sal = ref.payroll, int(ref.n), ref.mean_salary

    h("1. אגף העלות")
    print(f"  כיול: n={int(m.nobs)} | R2={m.rsquared:.3f} | sigma={sigma:.3f}")
    for f in COST_FEATURES:
        print(f"    {f:<18}{m.params[f]:>9.4f}  p={m.pvalues[f]:.3f}")
    print(f"  Duan={smear:.4f}")
    print(f"\n  סקלת עונת הדמו ({TARGET_CLUB} {DEMO_SEASON}):")
    print(f"    תקציב B      = {B:>12,.0f}")
    print(f"    גודל סגל N   = {N_ref:>12}")
    print(f"    שכר ממוצע    = {mean_sal:>12,.0f}   <- cost = rel * זה")
    print("\n  🔴 הנחה: הסקלה של מכבי מוחלת על כל 228 המועמדים.")
    return m, smear, sigma, B, mean_sal


# ============ 2. זמינות ============
def survival_side():
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    last = ps.season.max()
    src = ps[ps.season < last].copy()
    alive = set(zip(ps.player_code, ps.season))
    src["survived"] = [(c, s + 1) in alive
                       for c, s in zip(src.player_code, src.season)]
    src["survived"] = src.survived.astype(int)
    src["age_c"] = src.age - AGE_CENTER
    src["age_c2"] = src.age_c ** 2

    cols = ["min_per_game", "age_c", "age_c2"]
    m = sm.Logit(src.survived, sm.add_constant(src[cols])).fit(
        disp=0, cov_type="cluster", cov_kwds={"groups": src.player_code})

    h("2. אגף הזמינות")
    print(f"  n={int(m.nobs)} | שרידות בפועל={src.survived.mean():.1%}")
    for c in cols:
        print(f"    {c:<16}{m.params[c]:>9.4f}  p={m.pvalues[c]:.3f}")
    print(f"\n  🔴 המודל מנבא *נוכחות בעונה הבאה*, לא מספר משחקים.")
    print(f"     expected_games = P(survive) * G_REF={G_REF} (קבוע מוצהר)")
    return m, ps


# ============ 3. הרכבת המועמדים ============
def build_pool(cost_m, smear, ps, surv_m, mean_sal):
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    pos = pd.read_csv(PROCESSED_DIR / "player_positions.csv",
                      dtype={"player_code": str})

    pool = feat[feat.season == DEMO_SEASON].merge(
        pos[["player_code", "position"]], on="player_code", how="left")

    # --- עלות ---
    X = sm.add_constant(pool[COST_FEATURES].astype(float),
                        has_constant="add")
    pool["log_rel_hat"] = cost_m.predict(X)
    pool["rel_hat"] = np.exp(pool.log_rel_hat) * smear
    pool["cost"] = pool.rel_hat * mean_sal

    # --- זמינות: מנבאים מהעונה האחרונה שקדמה לעונת הדמו ---
    prev = (ps[ps.season < DEMO_SEASON]
            .sort_values(["player_code", "season"])
            .groupby("player_code").tail(1)
            .set_index("player_code"))
    pool["min_prev"] = pool.player_code.map(prev.min_per_game)
    pool["age_prev"] = pool.player_code.map(prev.age)

    miss = pool.min_prev.isna()
    if miss.any():
        pool.loc[miss, "min_prev"] = prev.min_per_game.median()
        pool.loc[miss, "age_prev"] = pool.loc[miss, "age"] - 1

    sx = pd.DataFrame({
        "min_per_game": pool.min_prev.astype(float),
        "age_c": pool.age_prev.astype(float) - AGE_CENTER})
    sx["age_c2"] = sx.age_c ** 2
    pool["p_survive"] = surv_m.predict(sm.add_constant(sx,
                                                       has_constant="add"))
    pool["exp_games"] = pool.p_survive * G_REF

    # --- תפוקה: 🔴 פלסטר ---
    pool["pir_hat"] = pool.pir_lag_shrunk
    pool["value"] = pool.pir_hat * pool.exp_games

    h("3. מאגר המועמדים")
    print(f"  {len(pool)} שחקנים | ללא עמדה: {pool.position.isna().sum()} | "
          f"ללא עונה קודמת: {int(miss.sum())}")
    print(f"  עלות   : חציון {pool.cost.median():>10,.0f} | "
          f"מקס {pool.cost.max():>11,.0f}")
    print(f"  ערך    : חציון {pool.value.median():>10.1f} | "
          f"מקס {pool.value.max():>11.1f}")
    print(f"  יעילות : ערך לכל מיליון $ — חציון "
          f"{(pool.value / (pool.cost / 1e6)).median():.1f}")
    return pool.dropna(subset=["cost", "value", "position"]).reset_index(
        drop=True)


# ============ 4. האופטימייזר ============
def solve(pool, budget, cost=None, value=None, quiet=True):
    cost = pool.cost.values if cost is None else cost
    value = pool.value.values if value is None else value

    p = pulp.LpProblem("roster", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(len(pool))]

    p += pulp.lpSum(value[i] * x[i] for i in range(len(pool)))
    p += pulp.lpSum(cost[i] * x[i] for i in range(len(pool))) <= budget
    p += pulp.lpSum(x) <= MAX_ROSTER
    for pos, floor in POS_FLOOR.items():
        idx = pool.index[pool.position == pos]
        p += pulp.lpSum(x[i] for i in idx) >= floor
    if MINUTES_CAP:
        p += pulp.lpSum(pool.min_prev.values[i] * x[i]
                        for i in range(len(pool))) <= MINUTES_CAP

    p.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[p.status] != "Optimal":
        if not quiet:
            print(f"  [FAIL] {pulp.LpStatus[p.status]}")
        return None
    return np.array([int(round(v.value())) for v in x], dtype=bool)


def report_roster(pool, sel, budget):
    r = pool[sel].sort_values("value", ascending=False)
    h("4. הסגל שנבחר")
    print(f"{'שחקן':<24}{'עמ':>4}{'גיל':>5}{'עלות':>12}"
          f"{'P(שרידות)':>11}{'PIR':>7}{'ערך':>9}")
    for t in r.itertuples():
        print(f"{str(t.player_name)[:23]:<24}{t.position:>4}{int(t.age):>5}"
              f"{t.cost:>12,.0f}{t.p_survive:>11.2f}"
              f"{t.pir_hat:>7.1f}{t.value:>9.1f}")
    print(f"\n  נבחרו {sel.sum()}/{MAX_ROSTER} | "
          f"עלות {r.cost.sum():,.0f} מתוך {budget:,.0f} "
          f"({r.cost.sum() / budget:.0%}) | ערך {r.value.sum():.0f}")
    print("  עמדות: " + " · ".join(
        f"{k}={int((r.position == k).sum())} (רצפה {v})"
        for k, v in POS_FLOOR.items()))
    return r


# ============ 5. מונטה קרלו ============
def monte_carlo(pool, budget, sigma):
    rng = np.random.default_rng(SEED)
    n = len(pool)
    picks = np.zeros(n)
    totals, costs, fails = [], [], 0

    for _ in range(N_DRAWS):
        c = pool.rel_hat.values * np.exp(rng.normal(0, sigma, n))
        c *= (pool.cost.values / pool.rel_hat.values)          # חזרה לדולרים
        alive = rng.random(n) < pool.p_survive.values          # ברנולי
        pir = pool.pir_hat.values * np.exp(
            rng.normal(0, PIR_CV, n))                          # 🔴 CV מוצהר
        v = pir * alive * G_REF

        sel = solve(pool, budget, cost=c, value=v)
        if sel is None:
            fails += 1
            continue
        picks += sel
        totals.append(v[sel].sum())
        costs.append(c[sel].sum())

    h("5. מונטה קרלו")
    print(f"  {N_DRAWS} הגרלות | נכשלו: {fails}")
    print(f"  🔴 אי-הוודאות על התפוקה היא CV={PIR_CV} מוצהר, לא נאמד.")
    print(f"     המונטה קרלו כאן מדגים מנגנון ולא מודד אי-ודאות.\n")
    ok = N_DRAWS - fails
    print(f"  ערך כולל : חציון {np.median(totals):.0f} | "
          f"טווח {np.percentile(totals, 5):.0f}-"
          f"{np.percentile(totals, 95):.0f}")
    print(f"  עלות     : חציון {np.median(costs):,.0f} | "
          f"ניצול {np.median(costs) / budget:.0%}")

    pool = pool.copy()
    pool["freq"] = picks / max(1, ok)
    top = pool.sort_values("freq", ascending=False).head(20)
    print(f"\n  שכיחות בחירה (20 הראשונים):")
    print(f"{'שחקן':<24}{'עמ':>4}{'שכיחות':>9}{'עלות':>12}")
    for t in top.itertuples():
        print(f"{str(t.player_name)[:23]:<24}{t.position:>4}"
              f"{t.freq:>9.2f}{t.cost:>12,.0f}")
    core = int((pool.freq >= 0.80).sum())
    print(f"\n  גרעין יציב (נבחרים ב->=80% מההגרלות): {core}")
    print(f"  נבחרו אי פעם: {int((pool.freq > 0).sum())} מתוך {len(pool)}")
    return pool


def degeneracy_check(pool, cost_m):
    """התפר החמור ביותר, והוא אנליטי ולא אמפירי.

        ערך(i)  = PIR * משחקים          -> **ליניארי** ב-PIR
        עלות(i) = exp(b1*PIR) * סקלה    -> **מעריכי** ב-PIR

    ולכן:
        d/dPIR [ ln(ערך/עלות) ] = 1/PIR - b1 = 0   ->   PIR* = 1/b1

    מעל הסף הזה היעילות יורדת מונוטונית, והאופטימייזר **לעולם**
    לא יקנה שחקן-על. זה לא באג מספרי - זה מבנה. שום אילוץ לא
    מתקן אותו, רק שינוי בהגדרת הערך.
    """
    b1 = float(cost_m.params["pir_lag_shrunk"])
    h("6. בדיקת ניוון — ערך ליניארי מול עלות מעריכית")
    print(f"  b1 = {b1:.4f}  ->  PIR* = 1/b1 = {1 / b1:.2f}")
    print(f"  מעל PIR={1 / b1:.1f} היעילות יורדת מונוטונית.")
    print(f"  טווח PIR במאגר: {pool.pir_hat.min():.1f}-"
          f"{pool.pir_hat.max():.1f} | חציון {pool.pir_hat.median():.1f}")

    b = pool.assign(eff=pool.value / pool.cost * 1e6,
                    bucket=pd.cut(pool.pir_hat, [0, 5, 7, 9, 11, 99]))
    t = b.groupby("bucket", observed=True).agg(
        n=("eff", "size"), יעילות=("eff", "median")).round(1)
    print(f"\n  ערך למיליון $ לפי דלי PIR:")
    print(t.to_string())
    peak = t.יעילות.idxmax()
    print(f"\n  שיא היעילות: דלי {peak}")
    print("  🔴 אם השיא אינו בדלי העליון, האופטימייזר מעדיף")
    print("     בינוניות על מצוינות - וזו תכונה של הגדרת הערך.")


def seam_checks(pool, r, budget):
    """התפרים - זו הסיבה שהקובץ הזה קיים."""
    h("7. בדיקות תפר")
    ok = True

    used = r.cost.sum() / budget
    print(f"  [א] ניצול תקציב: {used:.0%}")
    if used < 0.60:
        print("      🔴 האופטימייזר לא מנצל את התקציב. סימן שהעלויות")
        print("      החזויות נמוכות מדי ביחס לסקלה - התפר בין rel לדולרים.")
        ok = False
    else:
        print("      התקציב נצרך. הסקלה סבירה.")

    # האם המודל מתמחר את מכבי בפועל נכון?
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})
    real = anch[(anch.club == TARGET_CLUB) & (anch.season == DEMO_SEASON)]
    j = pool.merge(real[["player_code", "salary_mid"]], on="player_code")
    if len(j):
        ratio = (j.cost / j.salary_mid).median()
        print(f"\n  [ב] מודל מול שכר בפועל אצל {TARGET_CLUB} "
              f"(n={len(j)}): יחס חציוני {ratio:.2f}")
        if not 0.7 <= ratio <= 1.4:
            print("      🔴 הסקלה מוטה. cost אינו בסדר גודל של דולרים אמיתיים.")
            ok = False
        else:
            print("      סדר הגודל נכון.")

    print(f"\n  [ג] מי האילוץ הפעיל?")
    print(f"      ספירה : {len(r):>6}/{MAX_ROSTER}")
    print(f"      תקציב : {r.cost.sum():>10,.0f}/{budget:,.0f}")
    print(f"      דקות  : {r.min_prev.sum():>6.1f}/{MINUTES_CAP}")
    binding = []
    if len(r) >= MAX_ROSTER:
        binding.append("ספירה")
    if r.cost.sum() >= budget * 0.98:
        binding.append("תקציב")
    if MINUTES_CAP and r.min_prev.sum() >= MINUTES_CAP * 0.98:
        binding.append("דקות")
    print(f"      פעילים: {', '.join(binding) if binding else 'אף אחד'}")
    if len(binding) > 1:
        print("      הערה: כמה אילוצים נחתכים יחד. זה לא בהכרח באג,")
        print("      אבל זה אומר שהפתרון רגיש לכל אחד מהם.")

    print(f"\n  [ד] יחידות: value = PIR/משחק * משחקים = PIR מצטבר")
    print(f"      cost = דולרים. הפונקציה היא max ערך תחת אילוץ דולרי -")
    print(f"      היחידות לא מתערבבות. ✔")

    print("\n" + ("  [סיכום] כל התפרים עברו." if ok else
                  "  [סיכום] 🔴 יש תפר שבור. זו התוצאה של הקובץ הזה."))
    return ok


def main():
    print(SEP)
    print("v0 — שלד מקצה לקצה. מכוער בכוונה. נועד להיזרק.")
    print("אף מספר כאן אינו תוצאה של הפרויקט.")
    print(SEP)

    cost_m, smear, sigma, budget, mean_sal = cost_side()
    surv_m, ps = survival_side()
    pool = build_pool(cost_m, smear, ps, surv_m, mean_sal)

    sel = solve(pool, budget, quiet=False)
    if sel is None:
        raise RuntimeError("האופטימייזר לא מצא פתרון - בדוק אילוצים")
    r = report_roster(pool, sel, budget)
    monte_carlo(pool, budget, sigma)
    degeneracy_check(pool, cost_m)
    seam_checks(pool, r, budget)


if __name__ == "__main__":
    main()