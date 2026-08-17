"""
roster_optimizer.py  (Day 6)
----------------------------
המנוע.

    max  sum( avail(i) * ppm(i) * m(i) )
        sum m(i) <= 200          (5 על הפרקט * 40 דקות)
        m(i) <= 32 * x(i)        (המרבי שנצפה ב-2025: 31.0)
        sum cost(i)*x(i) <= B
        MIN_ROSTER <= sum x(i) <= 16
        אילוצי עמדות

--------------------------------------------------------------------
שני תיקונים מההרצה הקודמת
--------------------------------------------------------------------
**1. זמינות במקום שרידות.** מודל השרידות עונה על "האם יהיה בליגה
ב-t+1", וזה מערבב סיכון חיצוני עם ההחלטה שלנו להחתים. כאן משמש
avail = שיעור המשחקים החזוי (availability_model.py), שנמדד ישירות.
כיול 0.054, OOS פער +0.013.

**2. הדירוג עובר למונטה קרלו.** הפונקציה שממטבים אינה זו שמודדים:
היא מכפילה כל שחקן בזמינותו ומתעלמת מכך שכשמישהו נעדר **הדקות
עוברות לשחקן הבא**. לכן היא מתמחרת בחסר את הערך של עומק.

התיקון אינו לנסח מחדש את המטרה - זה היה הופך אותה ללא-ליניארית
ו-PuLP לא היה פותר. במקום זה: **סווייפ על MIN_ROSTER, וכל תוצאה
מדורגת לפי המונטה קרלו ולא לפי הפונקציה הדטרמיניסטית.** העומק
נקבע מהדאטה, לא מהצהרה.

--------------------------------------------------------------------
🔴 מה עדיין פלסטר
--------------------------------------------------------------------
1. ppm הוא פיגור מוכווץ. **אין מודל תפוקה** ואין אומדן פיזור סביבו.
   המונטה קרלו מודד רק את אי-ודאות הזמינות - היחידה שנאמדה.
2. הסקלה של מכבי מוחלת על כל המועמדים. ההטיה נמדדה: יחס חציוני
   1.40 מול השכר בפועל, ו-0.73/1.40 בין 2024 ל-2025.

הרצה:
    python src/availability_model.py     (חייב לרוץ קודם)
    python src/roster_optimizer.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pulp
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR

# ---------------- פרמטרים מוצהרים ----------------
DEMO_SEASON = 2025
TARGET_CLUB = "TEL"
COST_FEATURES = ["pir_lag_shrunk", "el_seasons"]
AVAIL_FEATURES = ["min_pg_lag", "frac_lag", "age_c", "log_gap"]
AGE_CENTER = 27.0

MINUTES_PER_GAME = 200.0      # 5 * 40
MAX_MIN_PLAYER = 32.0         # נצפה מרבי 31.0
MAX_ROSTER = 16
ROSTER_SWEEP = range(8, 17)   # MIN_ROSTER שנבדק
POS_FLOOR = {"G": 2, "F": 1, "C": 1}          # חברות בסגל

# גבולות על **חלוקת הדקות**, לא על חברות בסגל.
# בלעדיהם האופטימייזר נתן לסנטרים 64% מהדקות; אף קבוצה מ-20
# הקבוצות ב-2025 לא עברה 28.2%. הטווח כאן הוא המינימום והמקסימום
# שנצפו בפועל - לא הצהרה, מדידה.
#           מינ%   מקס%     (מתוך סך דקות הקבוצה, עונת 2025)
POS_MIN_SHARE = {"G": 0.163, "F": 0.146, "C": 0.043}
POS_MAX_SHARE = {"G": 0.698, "F": 0.794, "C": 0.282}
K_PPM = 450.0

# רמת מחליף. קבוצה **חייבת** להעמיד חמישה על הפרקט - היא לא יכולה
# לשחק 4 מול 5. כשהסגל לא מספיק, הדקות החסרות מתמלאות בשחקן ברמת
# מחליף (עשירון תחתון של ppm), לא באפס.
#
# בלי זה עומק לעולם לא משתלם: סגל דק "מרוויח" מכך שהוא פשוט משחק
# פחות דקות, וזו אינה אפשרות במשחק אמיתי.
REPLACEMENT_SWEEP = [1, 5, 10, 25]   # אחוזוני ppm — ציר רגישות שני
REPLACEMENT_PCTL = 10                # ברירת מחדל לדיווח

# ליבה נעולה: שחקנים שכבר חתומים במועדון היעד.
# הנימוק אינו רגשי - ישראלים הם מצרך נדרש (מכסת מקומיים בליגה
# המקומית), והמודל אינו יודע על הליגה המקומית בכלל. בלי הנעילה
# הוא מוחק אותם, וזו אינה החלטה אפשרית עבור מכבי.
#
# ולשחקן חתום **העלות ידועה** - אין סיבה להשתמש בתחזית המודל.
LOCK_ISRAELI = True

GAMES_PER_SEASON = 38
N_DRAWS = 300
SEED = 7
# -------------------------------------------------

SEP = "=" * 74


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


# ================= קלט =================
def build_pool():
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})
    pos = pd.read_csv(PROCESSED_DIR / "player_positions.csv",
                      dtype={"player_code": str})
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})

    # ---- עלות ----
    cal_all = anch[anch.usage == "calibrate"].copy()
    agg = cal_all.groupby(["club", "season"]).salary_mid.agg(["sum", "size"])
    agg.columns = ["payroll", "n"]
    agg["mean_salary"] = agg.payroll / agg.n
    cal = cal_all[cal_all.player_code.notna()].merge(
        agg, left_on=["club", "season"], right_index=True)
    cal["log_rel"] = np.log(cal.salary_mid / cal.mean_salary)
    dc = cal.merge(feat, on=["player_code", "season"], how="inner",
                   suffixes=("", "_f")).dropna(
        subset=COST_FEATURES + ["log_rel"])
    cm = sm.OLS(dc.log_rel, sm.add_constant(dc[COST_FEATURES].astype(float))
                ).fit(cov_type="cluster", cov_kwds={"groups": dc.player_code})
    smear = float(np.mean(np.exp(cm.resid)))
    ref = agg.loc[(TARGET_CLUB, DEMO_SEASON)]
    B, mean_sal = float(ref.payroll), float(ref.mean_salary)

    # ---- זמינות ----
    gmax = ps.groupby("season").games.max().rename("gmax")
    p2 = ps.merge(gmax, left_on="season", right_index=True)
    p2["frac"] = p2.games / p2.gmax
    p2 = p2.sort_values(["player_code", "season"])
    g = p2.groupby("player_code", sort=False)
    p2["frac_lag"] = g.frac.shift(1)
    p2["min_pg_lag"] = g.min_per_game.shift(1)
    p2["season_lag"] = g.season.shift(1)
    p2["age_c"] = p2.age - AGE_CENTER
    p2["gap"] = p2.season - p2.season_lag
    p2["log_gap"] = np.log(p2.gap)
    tr = p2[p2.gap.notna() & (p2.gap >= 1) & p2.frac_lag.notna() &
            (p2.season <= 2024)]
    am = sm.GLM(np.column_stack([tr.games, tr.gmax - tr.games]),
                sm.add_constant(tr[AVAIL_FEATURES].astype(float)),
                family=sm.families.Binomial()).fit()

    # ---- המאגר ----
    pool = feat[feat.season == DEMO_SEASON].merge(
        pos[["player_code", "position"]], on="player_code", how="left")
    X = sm.add_constant(pool[COST_FEATURES].astype(float),
                        has_constant="add")
    pool["cost"] = np.exp(cm.predict(X)) * smear * mean_sal

    prev = (p2[p2.season < DEMO_SEASON].sort_values(["player_code", "season"])
            .groupby("player_code").tail(1).set_index("player_code"))
    ax = pd.DataFrame({
        "min_pg_lag": pool.player_code.map(prev.min_per_game),
        "frac_lag": pool.player_code.map(prev.frac),
        "age_c": pool.age.astype(float) - AGE_CENTER,
        "log_gap": np.log(
            (DEMO_SEASON - pool.player_code.map(prev.season)).clip(lower=1))})
    n_imp = int(ax.frac_lag.isna().sum())
    ax["min_pg_lag"] = ax.min_pg_lag.fillna(prev.min_per_game.median())
    ax["frac_lag"] = ax.frac_lag.fillna(prev.frac.median())
    ax["log_gap"] = ax.log_gap.fillna(0.0)
    pool["avail"] = am.predict(sm.add_constant(ax, has_constant="add"))
    pool["avail_imputed"] = ax.index.isin(ax.index[n_imp:]) & False
    pool.loc[pool.player_code.map(prev.frac).isna(), "avail_imputed"] = True

    # ---- PIR לדקה: מודל, לא פיגור ----
    # עד יום 6 זה היה pir_lag_raw/min_lag מוכווץ - כלומר הנחה
    # שהתפוקה הבאה שווה למשוקללת של הקודמות, **בלי אומדן פיזור**.
    # production_model.py נותן גם ppm_hat וגם ppm_sd, והשני הוא
    # מה שהמונטה קרלו היה חסר.
    prod = pd.read_csv(PROCESSED_DIR / "player_production.csv",
                       dtype={"player_code": str})
    pool = pool.merge(prod[["player_code", "ppm_hat", "ppm_sd"]],
                      on="player_code", how="left")
    n_noprod = int(pool.ppm_hat.isna().sum())
    # מי שאין לו מודל: נופל חזרה לפיגור המוכווץ, עם פיזור המקסימום
    minutes_tot = pool.min_lag * pool.games_lag
    league_ppm = float((pool.pir_lag_raw * pool.games_lag).sum() /
                       minutes_tot.sum())
    raw = pool.pir_lag_raw / pool.min_lag.replace(0, np.nan)
    w = minutes_tot / (minutes_tot + K_PPM)
    fallback = w * raw.fillna(league_ppm) + (1 - w) * league_ppm
    pool["ppm"] = pool.ppm_hat.fillna(fallback)
    pool["ppm_sd"] = pool.ppm_sd.fillna(prod.ppm_sd.max())

    # ---- ליבה נעולה + עלות בפועל לחתומים ----
    tel = anch[(anch.club == TARGET_CLUB) & (anch.season == DEMO_SEASON)]
    signed = tel[tel.player_code.notna()].set_index("player_code")
    in_pool = pool.player_code.isin(signed.index)
    pool["signed"] = in_pool
    pool["cost_model"] = pool.cost
    pool.loc[in_pool, "cost"] = pool.loc[in_pool, "player_code"].map(
        signed.salary_mid)
    pool["is_israeli"] = pool.player_code.map(signed.is_israeli).fillna(0)

    isr_all = tel[tel.is_israeli == 1]
    isr_out = isr_all[~isr_all.player_code.isin(set(pool.player_code))]
    lock_offset = float(isr_out.salary_mid.sum())

    h("קלט")
    print(f"  עלות   : n={int(cm.nobs)} R2={cm.rsquared:.3f} | "
          f"Duan={smear:.4f} | שכר ממוצע {mean_sal:,.0f} | B={B:,.0f}")
    print(f"  זמינות : n={int(am.nobs)} | "
          f"frac_lag={am.params['frac_lag']:.3f} "
          f"min_pg_lag={am.params['min_pg_lag']:.4f}")
    print(f"  מאגר   : {len(pool)} | ללא עמדה {pool.position.isna().sum()} | "
          f"זמינות משוערכת ל-{n_imp} (אין עונה צמודה קודמת)")
    print(f"  avail  : חציון {pool.avail.median():.3f} | "
          f"טווח {pool.avail.min():.3f}-{pool.avail.max():.3f}")
    print(f"  ppm    : חציון {pool.ppm.median():.4f} | "
          f"טווח {pool.ppm.min():.4f}-{pool.ppm.max():.4f} | "
          f"ללא מודל: {n_noprod}")
    print(f"  ppm_sd : חציון {pool.ppm_sd.median():.4f} "
          f"(CV {pool.ppm_sd.median() / pool.ppm.median():.0%})")
    print(f"  חתומים : {int(in_pool.sum())} מתוך {len(signed)} — "
          f"עלותם היא החוזה בפועל, לא תחזית")
    print(f"  ישראלים: {int(pool.is_israeli.sum())} במאגר | "
          f"{len(isr_out)} מחוץ למאגר ({lock_offset:,.0f} מחויב מראש)")
    out = pool.dropna(subset=["cost", "ppm", "position"]).reset_index(
        drop=True)
    return out, B, lock_offset


# ================= אופטימיזציה =================
def optimise(pool, budget, min_roster, locked=None, budget_offset=0.0):
    """locked: אינדקסים שחייבים להיבחר. budget_offset: תקציב שכבר
    מחויב לשחקנים חתומים שאינם במאגר (אין להם פיצ'רים)."""
    n = len(pool)
    p = pulp.LpProblem("roster", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(n)]
    m = [pulp.LpVariable(f"m{i}", lowBound=0, upBound=MAX_MIN_PLAYER)
         for i in range(n)]
    val = (pool.avail * pool.ppm).values

    p += pulp.lpSum(val[i] * m[i] for i in range(n))
    p += pulp.lpSum(m) <= MINUTES_PER_GAME
    for i in range(n):
        p += m[i] <= MAX_MIN_PLAYER * x[i]
    p += pulp.lpSum(pool.cost.values[i] * x[i]
                    for i in range(n)) <= budget - budget_offset
    for i in (locked or []):
        p += x[i] == 1
    p += pulp.lpSum(x) <= MAX_ROSTER
    p += pulp.lpSum(x) >= min_roster
    for ps_, fl in POS_FLOOR.items():
        idx = pool.index[pool.position == ps_]
        p += pulp.lpSum(x[i] for i in idx) >= fl
        # גבולות דקות - הטווח שנצפה על פני 20 הקבוצות
        p += pulp.lpSum(m[i] for i in idx) <= \
            POS_MAX_SHARE[ps_] * MINUTES_PER_GAME
        p += pulp.lpSum(m[i] for i in idx) >= \
            POS_MIN_SHARE[ps_] * MINUTES_PER_GAME

    p.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[p.status] != "Optimal":
        return None, None
    sel = np.array([x[i].value() > 0.5 for i in range(n)])
    mins = np.array([m[i].value() or 0.0 for i in range(n)])
    return sel, mins


# ================= מונטה קרלו =================
def simulate(ppm_hat, ppm_sd, avail, positions, repl_ppm, rng,
             draws=N_DRAWS, games=GAMES_PER_SEASON):
    """הסגל הוא ההחלטה. שני דברים מתגלים אחריה.

    **תפוקה** — נדגמת פעם אחת לעונה: ppm ~ N(ppm_hat, ppm_sd).
    השחקן הוא מה שהוא לאורך העונה; מה שלא ידענו הוא מה הוא.

    **זמינות** — נדגמת בכל משחק בנפרד.

    הסדר הזה הוא מה שנותן לעומק ערך: אם הכוכב מתגלה כפחות טוב
    ממה שחשבנו, צריך למי להעביר את הדקות. הפונקציה הדטרמיניסטית
    לא יודעת על אף אחד משני הדברים.

    המאמן מקצה דקות לפי מה שהוא **רואה** בעונה, כלומר לפי ppm
    שנדגם - לא לפי התחזית מלפני העונה. מי שנופל מתחת לרמת מחליף
    לא מקבל דקות כלל.
    """
    n = len(ppm_hat)
    caps = {g: POS_MAX_SHARE[g] * MINUTES_PER_GAME for g in POS_MAX_SHARE}
    out = np.empty(draws)
    short_tot = 0.0
    repl_tot = 0.0

    for k in range(draws):
        true = rng.normal(ppm_hat, ppm_sd)          # פעם אחת לעונה
        order = np.argsort(-true)
        pp, av = true[order], avail[order]
        pos = np.asarray(positions)[order]
        ok = pp > repl_ppm                          # מתחת לזה - ספסל

        a = (rng.random((games, n)) < av) & ok
        total_left = np.full(games, MINUTES_PER_GAME)
        grp_left = {g: np.full(games, caps[g]) for g in caps}
        q = np.zeros(games)
        used = np.zeros(games)
        for j in range(n):
            g = pos[j]
            take = np.minimum(np.minimum(MAX_MIN_PLAYER, total_left),
                              grp_left[g]) * a[:, j]
            q += take * pp[j]
            used += take
            total_left -= take
            grp_left[g] -= take

        gap = MINUTES_PER_GAME - used
        q += gap * repl_ppm
        out[k] = q.mean()
        short_tot += (gap > 1e-6).mean()
        repl_tot += gap.mean() / MINUTES_PER_GAME

    return out, short_tot / draws, repl_tot / draws


# ================= דיווח =================
def scenarios(pool, budget, lock_offset):
    """שני תרחישים, אותו תקציב:

      חופשי  — האופטימייזר בוחר את כל 16
      נעול   — הישראלים החתומים מוכרחים להיכנס

    ההפרש ביניהם הוא **המחיר של הליבה הישראלית** ביחידות איכות.
    הוא לא בהכרח חיובי לרעה: אם הוא קטן, הליבה כמעט חינם.
    """
    isr = list(pool.index[pool.is_israeli == 1])
    return [("חופשי", [], 0.0),
            ("נעול (ליבה ישראלית)", isr, lock_offset)]


def sweep(pool, budget, lock_offset):
    rng = np.random.default_rng(SEED)
    repls = {q: float(np.percentile(pool.ppm, q))
             for q in REPLACEMENT_SWEEP}

    h("סווייפ — גודל סגל × רמת מחליף × ליבה נעולה")
    print("  רמות מחליף: " + " · ".join(
        f"p{q}={v:.3f}" for q, v in repls.items()))

    results = {}
    for label, locked, offset in scenarios(pool, budget, lock_offset):
        rows, solved = [], {}
        for mr in ROSTER_SWEEP:
            sel, mins = optimise(pool, budget, mr, locked, offset)
            if sel is None:
                continue
            solved[mr] = (sel, mins)
            r = pool[sel]
            row = {"MIN": mr, "n": int(sel.sum())}
            for q, rv in repls.items():
                qs, short, rs = simulate(r.ppm.values, r.ppm_sd.values,
                                         r.avail.values, r.position.values,
                                         rv, rng)
                row[f"p{q}"] = round(float(np.median(qs)), 1)
            rows.append(row)
        if not rows:
            print(f"\n  [{label}] אין פתרון בשום גודל סגל")
            continue
        t = pd.DataFrame(rows).set_index("MIN")
        print(f"\n  --- {label} ---")
        print(t.to_string())
        best_mr = int(t[f"p{REPLACEMENT_PCTL}"].idxmax())
        results[label] = (best_mr, float(t[f"p{REPLACEMENT_PCTL}"].max()),
                          *solved[best_mr])

    print("\n" + "-" * 70)
    if len(results) == 2:
        (mf, qf, _, _), (ml, ql, _, _) = results.values()
        print(f"  חופשי : MIN={mf} | איכות {qf:.1f}")
        print(f"  נעול  : MIN={ml} | איכות {ql:.1f}")
        print(f"\n  **מחיר הליבה הישראלית: {ql - qf:+.1f} "
              f"({ql / qf - 1:+.1%})**")
        if ql / qf - 1 > -0.05:
            print("  קטן מ-5% — הליבה כמעט חינם. הטענה ש'המודל מוחק")
            print("  את הישראלים כי הם לא שווים' אינה מדויקת.")
        else:
            print("  מעל 5% — הליבה עולה איכות ממשית. זה מספר שאפשר")
            print("  להציג למקבל החלטות, לא טענה.")
    key = "נעול (ליבה ישראלית)" if LOCK_ISRAELI else "חופשי"
    return results[key]


def report(pool, sel, mins, budget, label):
    r = pool[sel].assign(minutes=mins[sel]).sort_values(
        "minutes", ascending=False)
    h(label)
    print(f"{'שחקן':<24}{'עמ':>4}{'גיל':>5}{'עלות':>12}"
          f"{'ppm':>8}{'זמינות':>9}{'דקות':>8}")
    for t in r.itertuples():
        print(f"{str(t.player_name)[:23]:<24}{t.position:>4}{int(t.age):>5}"
              f"{t.cost:>12,.0f}{t.ppm:>8.3f}{t.avail:>9.2f}"
              f"{t.minutes:>8.1f}")
    played = int((r.minutes > 0.01).sum())
    print(f"\n  {len(r)} שחקנים | מקבלים דקות {played} | "
          f"ספסל {len(r) - played}")
    print(f"  עלות {r.cost.sum():,.0f}/{budget:,.0f} "
          f"({r.cost.sum() / budget:.0%})")
    print("  סגל   : " + " · ".join(
        f"{k}={int((r.position == k).sum())}" for k in POS_FLOOR))
    print("  דקות  : " + " · ".join(
        f"{k}={r.minutes[r.position == k].sum():.0f} "
        f"({r.minutes[r.position == k].sum() / MINUTES_PER_GAME:.0%}, "
        f"תקרה {POS_MAX_SHARE[k]:.0%})" for k in POS_FLOOR))
    return r


def benchmark(pool):
    """בלי בנצ'מרק אין למספר משמעות."""
    real = pool[pool.team.astype(str).str.contains(TARGET_CLUB, na=False)]
    if real.empty:
        return None
    rng = np.random.default_rng(SEED)
    repl = float(np.percentile(pool.ppm, REPLACEMENT_PCTL))
    q, short, rs = simulate(real.ppm.values, real.ppm_sd.values,
                            real.avail.values, real.position.values,
                            repl, rng)
    h(f"בנצ'מרק — הסגל האמיתי של {TARGET_CLUB} {DEMO_SEASON}")
    print(f"  {len(real)} שחקנים | עלות לפי המודל {real.cost.sum():,.0f}")
    print(f"  MC חציון {np.median(q):.1f} | p5 {np.percentile(q, 5):.1f} | "
          f"משחקים חסרים {short:.0%} | דקות מחליף {rs:.0%}")
    print("  🔴 העלות כאן היא של המודל, לא בפועל. ההטיה נמדדה: 1.40.")
    return float(np.median(q))


def main():
    print(SEP + "\nמנוע ההקצאה — זמינות מדודה, דירוג לפי מונטה קרלו\n" + SEP)
    pool, budget, lock_offset = build_pool()
    mr, qmc, sel, mins = sweep(pool, budget, lock_offset)
    r = report(pool, sel, mins, budget,
               f"הסגל הנבחר (MIN_ROSTER={mr}, "
               f"{'ליבה נעולה' if LOCK_ISRAELI else 'חופשי'})")
    qb = benchmark(pool)
    if qb:
        print(f"\n  אופטימייזר {qmc:.1f} מול {TARGET_CLUB} בפועל {qb:.1f}  "
              f"({qmc / qb - 1:+.1%})")
    h("תזכורת")
    print("  המונטה קרלו מפיץ **שני** מקורות: תפוקה (עונתית)")
    print("  וזמינות (לכל משחק). מה שעדיין לא נספר: שגיאת האמידה")
    print("  של avail עצמו (MAE 0.187), והטיית הסקלה בעלות (1.40).")
    print(SEP)


if __name__ == "__main__":
    main()