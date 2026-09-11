"""cost_market.py — מודל העלות של השוק. מממש ADR 0001, שלב 2 של
docs/refit-run-spec.md.

--------------------------------------------------------------------
מה מוחלף
--------------------------------------------------------------------
המפרט הישן:

    log(salary_i / squad_mean_club) ~ pir_lag_shrunk + el_seasons

נאמד על usage='calibrate', שהוא מכבי ת"א בלבד. β₁ = 0.2317 —
המועדון התלול ביותר מבין החמישה שנמדדו ביום 9.

המפרט כאן:

    log(salary_i) = α_club + γ_season + β₁·pir_lag_shrunk + β₂·el_seasons

אפקטים קבועים למועדון סופגים את **רמת** המחירים; β₁ נאמד בתוך
מועדון ומשותף לליגה. שחקני המאגר מתומחרים ב-α הממוצע, כלומר
במועדון ליגה ממוצע.

--------------------------------------------------------------------
פרמטרים מוצהרים — כל אחד הוא החלטה, לא ברירת מחדל
--------------------------------------------------------------------
**SALARY_MAX_SEASON = "test"**
    אילו תצפיות שכר מותרות לכיול. שתי אפשרויות:

    "train_max"  שכר עד עונת האימון בלבד — הכלל הישן ב-fit_models.
                 עבור עונת מבחן 2024 זה משאיר את TEL 2023 בלבד:
                 12 שורות, **מועדון אחד**. כלומר חצי מ-38 עונות-
                 המועדון היו מתומחרות במפרט חד-מועדוני וחציין
                 במפרט שוק, ו-adv_cap המאוחד היה מערבב שני מודלים.

    "test"       שכר עד עונת המבחן עצמה (ברירת המחדל כאן).
                 2025 -> 77 שורות / 14 מועדונים · 2024 -> 38 / 9.

    הנימוק ל-"test": שכר נקבע **לפני** העונה ואינו תוצאה שלה,
    והרגרסורים הם פיגור (pir_lag_shrunk מהעונה הקודמת). הניקוד
    (ppm_true, avail_true) אינו נוגע בשכר בשום שלב.
    ⚠️ מה שכן נכנס: מחירי העונה עצמה מגלמים ציפיות של השוק לגביה.
    זו הדלפה מדרגה שנייה, דרך שני מקדמים בלבד, ומדווחת.
    β₁ בשני הכללים מודפס בכל הרצה — ההפרש הוא גודל ההשפעה.

**PRICE_LEVEL = "mean_alpha"** — α ממוצע **לא משוקלל על פני
    מועדונים**. משוקלל-שורות היה נותן משקל למי שדלף ממנו יותר
    שכר לעיתונות, וזה לא "מועדון ממוצע".

**UNIT = "eur_millions"** — הפלט הוא מיליוני יורו.
    ⚠️ שינוי משמעות של ציר התקציב. במפרט הישן cost הוא יחס
    חסר-יחידות לשכר הממוצע במועדון הכיול (ראו CONTEXT.md).
    כאן α הוא רמת מחירים אמיתית ביורו, ולכן exp(α̅+βx) הוא מחיר
    ביורו. חלוקה ב-1e6 היא תצוגה בלבד ואינה משנה שום בחירה של
    ה-LP (סקלה אחידה על העלויות ועל התקציב).
    ⇒ הרשת 8–40 בסווייפ נקראת מעתה כ-8–40 מיליון יורו נטו, וזה
      בדיוק טווח תקציבי היורוליג. fit_eur הופך למבחן של רמת
      המחירים במקום למיפוי תצוגה (שלב 4 בספק).

**SEASON_DUMMY = True** — הכיול מערב עונות (2023/24/25 בעוגנים,
    2024/25 בחיצוני). איחוד בלי דמה לעונה מייחס אינפלציית שכר
    ל-β₁. המאגר מתומחר ברמת **עונת המבחן**.

--------------------------------------------------------------------
מקורות המדגם
--------------------------------------------------------------------
salary_anchors.csv     usage='calibrate' · קוד שחקן מאומת
salary_external_2025   usage='calibrate' · הצלבת שם מלא

התיוג עצמו נעשה ב-tag_external_usage.py (שלב 1, מקומט). כאן הוא
נקרא בלבד. ההצלבה, מיפוי המועדונים והכינויים מיובאים מ-
salary_market.py — מקור אמת אחד. שני מיפויי NAME2CODE כבר הפילו
כיול ב-13.8% ביום 12.

עונת שורה חיצונית היא `yr` ולא `season` — ADR 0003.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))

from paths import PROCESSED_DIR  # noqa: E402
import roster_optimizer as ro  # noqa: E402
import salary_market as smk  # noqa: E402

# ---------------- פרמטרים מוצהרים ----------------
SALARY_MAX_SEASON = "test"        # "test" | "train_max"
PRICE_LEVEL = "mean_alpha"
UNIT_DIVISOR = 1e6                # יורו -> מיליוני יורו
SEASON_DUMMY = True
MIN_ROWS = 25                     # מתחת לזה הכיול אינו מוגדר
# -------------------------------------------------

LAST_FIT: dict = {}               # פרובננס להדפסה/JSON, נכתב ב-build


# ============================ המדגם ============================
def _anchor_rows(anch: pd.DataFrame, max_season: int) -> pd.DataFrame:
    a = anch[(anch.usage == "calibrate") & anch.player_code.notna()].copy()
    a["salary"] = pd.to_numeric(a.salary_mid, errors="coerce")
    a = a[a.salary.notna() & (a.season <= max_season)]
    return pd.DataFrame({"player_code": a.player_code.astype(str),
                         "club": a.club.astype(str),
                         "season": a.season.astype(int),
                         "salary": a.salary.astype(float),
                         "src": "anchor"})


def _external_rows(ps: pd.DataFrame, max_season: int) -> tuple[pd.DataFrame, list]:
    """שורות calibrate מהקובץ החיצוני, עם קוד שחקן מאומת.

    ההצלבה זהה ל-salary_market.load_market, בהבדל אחד: מפת השמות
    נבנית מכל העונות ולא מ-2025 בלבד, כי כאן יש גם שורות yr=2024.
    שם שחקן אינו תלוי עונה; המפתח כן צריך להיות ייחודי.
    """
    notes = []
    s = pd.read_csv(PROCESSED_DIR / "salary_external_2025.csv")
    if "usage" not in s.columns:
        raise SystemExit(
            "ל-salary_external_2025.csv אין עמודת usage. שלב 1 של "
            "docs/refit-run-spec.md לא רץ — אין לכייל לפניו.")

    s = s[(s.usage == "calibrate") & (s.yr <= max_season)].copy()
    s["lat"] = s.player.astype(str).str.split("/").str[0]
    s["key"] = s.lat.map(smk.norm)

    p = ps.dropna(subset=["player_name"]).copy()
    p["key"] = (p.player_name.str.split(",").str[1].fillna("")
                + p.player_name.str.split(",").str[0]).map(smk.norm)
    p["pc"] = p.player_code.astype(str)
    dupe_keys = p.drop_duplicates(["key", "pc"]).key.value_counts()
    ambiguous = set(dupe_keys[dupe_keys > 1].index)
    if ambiguous & set(s.key):
        notes.append(f"⚠️ {len(ambiguous & set(s.key))} שמות מלאים "
                     "מתאימים ליותר מקוד אחד — נלקח הראשון.")
    kmap = p.drop_duplicates("key").set_index("key").pc

    s["player_code"] = s.key.map(kmap)
    s.loc[s.player_code.isna(), "player_code"] = \
        s.loc[s.player_code.isna(), "key"].map(smk.ALIAS)
    n_unres = int(s.player_code.isna().sum())
    if n_unres:
        notes.append(f"{n_unres} שורות חיצוניות ללא קוד — יורדות "
                     "(אושר שלא שיחקו ביורוליג).")
    s = s[s.player_code.notna()].copy()

    s["club_code"] = s.club.map(smk.CLUBMAP)
    if s.club_code.isna().any():
        raise SystemExit("מועדונים ללא מיפוי ב-CLUBMAP: "
                         + ", ".join(sorted(set(s.loc[s.club_code.isna(),
                                                      "club"]))))
    return pd.DataFrame({"player_code": s.player_code.astype(str),
                         "club": s.club_code.astype(str),
                         "season": s.yr.astype(int),
                         "salary": pd.to_numeric(s.salary,
                                                 errors="coerce").astype(float),
                         "src": "external"}), notes


def sample(anch: pd.DataFrame, feat: pd.DataFrame, ps: pd.DataFrame,
           max_season: int) -> tuple[pd.DataFrame, list]:
    """מדגם הכיול המלא, מוצלב לפיצ'רים של אותה עונה."""
    ext, notes = _external_rows(ps, max_season)
    d = pd.concat([_anchor_rows(anch, max_season), ext], ignore_index=True)
    d = d[d.salary.notna() & (d.salary > 0)]

    # שחקן שמופיע בשני המקורות באותה עונה: העוגן גובר (קוד מאומת).
    n_before = len(d)
    d = (d.sort_values("src")                      # anchor < external
         .drop_duplicates(["player_code", "season"], keep="first"))
    if len(d) < n_before:
        notes.append(f"{n_before - len(d)} כפילויות עוגן/חיצוני — "
                     "העוגן גבר.")

    F = feat.copy()
    F["player_code"] = F.player_code.astype(str)
    F = F.drop_duplicates(["player_code", "season"])
    d = d.merge(F[["player_code", "season"] + ro.COST_FEATURES],
                on=["player_code", "season"], how="inner")
    d = d.dropna(subset=ro.COST_FEATURES)
    d["log_sal"] = np.log(d.salary)
    return d.reset_index(drop=True), notes


# ============================ האמידה ============================
def fit(d: pd.DataFrame):
    """אפקטים קבועים למועדון + דמה לעונה. β₁ נאמד בתוך מועדון."""
    X = pd.get_dummies(d.club, prefix="c", drop_first=True).astype(float)
    if SEASON_DUMMY and d.season.nunique() > 1:
        X = pd.concat([X, pd.get_dummies(d.season, prefix="y",
                                         drop_first=True).astype(float)],
                      axis=1)
    X[ro.COST_FEATURES] = d[ro.COST_FEATURES].astype(float).values
    return sm.OLS(d.log_sal.astype(float), sm.add_constant(X)).fit()


class MarketCostModel:
    """עוטף את הרגרסיה ומחזיר log(מחיר במיליוני יורו) במועדון ממוצע.

    החתימה תואמת ל-`cm` הישן: `build()` ב-optimizer_backtest קורא
    `np.exp(cm.predict(X)) * smear * mean_salary`. עם mean_salary=1.0
    (נתיב הסווייפ) התוצאה היא מיליוני יורו.
    """

    def __init__(self, res, alpha_bar, season_shift, meta):
        self._res = res
        self.alpha_bar = float(alpha_bar)
        self.season_shift = float(season_shift)
        self.beta1 = float(res.params[ro.COST_FEATURES[0]])
        self.beta2 = float(res.params[ro.COST_FEATURES[1]])
        self.nobs = float(res.nobs)
        self.rsquared = float(res.rsquared)
        self.resid = res.resid
        self.meta = meta

    def predict(self, X):
        X = pd.DataFrame(X)
        if ro.COST_FEATURES[0] in X.columns:
            x1 = X[ro.COST_FEATURES[0]].astype(float).values
            x2 = X[ro.COST_FEATURES[1]].astype(float).values
        else:                                   # מערך: [const, pir, el]
            v = X.values.astype(float)
            x1, x2 = v[:, -2], v[:, -1]
        lp = (self.alpha_bar + self.season_shift
              + self.beta1 * x1 + self.beta2 * x2)
        return pd.Series(lp - np.log(UNIT_DIVISOR), index=X.index)


def build(anch: pd.DataFrame, feat: pd.DataFrame, ps: pd.DataFrame,
          test: int, train_max: int, verbose: bool = True):
    """המודל המלא לעונת `test`. מחזיר (cm, smear)."""
    max_season = test if SALARY_MAX_SEASON == "test" else train_max
    d, notes = sample(anch, feat, ps, max_season)
    if len(d) < MIN_ROWS:
        raise SystemExit(
            f"מדגם הכיול הוא {len(d)} שורות בלבד (מינימום {MIN_ROWS}). "
            f"בדוק את usage בקבצי השכר לפני שממשיכים.")

    res = fit(d)
    clubs = sorted(d.club.unique())
    # α לכל מועדון: הקבוע הוא מועדון הבסיס, השאר סטייה ממנו.
    alphas = {c: float(res.params.get(f"c_{c}", 0.0)) + float(res.params["const"])
              for c in clubs}
    alpha_bar = float(np.mean(list(alphas.values())))

    # רמת המחירים של עונת המבחן. אם אינה במדגם — האחרונה שיש, ומדווח.
    seasons = sorted(int(s) for s in d.season.unique())
    tgt = test if test in seasons else max(seasons)
    if tgt != test:
        notes.append(f"⚠️ אין שכר מעונת {test} במדגם; מתומחר ברמת {tgt}.")
    season_shift = float(res.params.get(f"y_{tgt}", 0.0))

    smear = float(np.mean(np.exp(res.resid)))

    # β₁ תחת הכלל השני — דיאגנוסטיקה, לא בשימוש לתמחור.
    alt_beta1 = None
    alt_season = train_max if SALARY_MAX_SEASON == "test" else test
    try:
        d_alt, _ = sample(anch, feat, ps, alt_season)
        if len(d_alt) >= MIN_ROWS:
            alt_beta1 = float(fit(d_alt).params[ro.COST_FEATURES[0]])
    except SystemExit:
        alt_beta1 = None

    cm = MarketCostModel(res, alpha_bar, season_shift, meta=dict(
        spec="market_fe", salary_max_season=SALARY_MAX_SEASON,
        max_season=int(max_season), test=int(test), train_max=int(train_max),
        n=int(res.nobs), n_clubs=len(clubs), seasons=seasons,
        beta1=round(float(res.params[ro.COST_FEATURES[0]]), 4),
        beta1_se=round(float(res.bse[ro.COST_FEATURES[0]]), 4),
        beta1_t=round(float(res.tvalues[ro.COST_FEATURES[0]]), 2),
        beta2=round(float(res.params[ro.COST_FEATURES[1]]), 4),
        beta2_t=round(float(res.tvalues[ro.COST_FEATURES[1]]), 2),
        r2=round(float(res.rsquared), 3),
        alpha_bar=round(alpha_bar, 4), season_shift=round(season_shift, 4),
        smear=round(smear, 4), unit="EUR_millions",
        beta1_alt_rule=(None if alt_beta1 is None else round(alt_beta1, 4)),
        alt_rule=("train_max" if SALARY_MAX_SEASON == "test" else "test"),
        clubs={c: int((d.club == c).sum()) for c in clubs},
        notes=notes))
    LAST_FIT.clear()
    LAST_FIT.update(cm.meta)

    if verbose:
        report(cm)
    return cm, smear


def report(cm: MarketCostModel) -> None:
    m = cm.meta
    print(f"  עלות (שוק): β₁={m['beta1']:+.4f} (ר\"ס {m['beta1_se']:.4f}, "
          f"t={m['beta1_t']:+.2f}) · β₂={m['beta2']:+.4f} "
          f"(t={m['beta2_t']:+.2f})")
    print(f"              n={m['n']} · {m['n_clubs']} מועדונים · "
          f"עונות {m['seasons']} · R²={m['r2']:.3f}")
    print(f"              α̅={m['alpha_bar']:.4f} · דמת עונה "
          f"{m['season_shift']:+.4f} · Duan={m['smear']:.4f} · "
          f"יחידות {m['unit']}")
    if m["beta1_alt_rule"] is not None:
        print(f"              β₁ תחת הכלל '{m['alt_rule']}': "
              f"{m['beta1_alt_rule']:+.4f}")
    for n in m["notes"]:
        print(f"              {n}")


# ============================ הרצה עצמאית ============================
def main() -> int:
    import optimizer_backtest as ob
    sep = "=" * 76
    print(sep)
    print("cost_market — מודל המחיר של השוק (ADR 0001)")
    print(sep)
    feat, anch, pos, ps = ob.load_all()
    for train_max, test in [(2023, 2024), (2024, 2025)]:
        print(f"\n--- עונת מבחן {test} (אימון <= {train_max}) ---")
        cm, smear = build(anch, feat, ps, test, train_max)
        d, _ = sample(anch, feat, ps,
                      test if SALARY_MAX_SEASON == "test" else train_max)
        print("  שורות למועדון: " + " · ".join(
            f"{k}:{v}" for k, v in sorted(cm.meta["clubs"].items())))
        X = sm.add_constant(d[ro.COST_FEATURES].astype(float),
                            has_constant="add")
        pred = np.exp(cm.predict(X)) * smear
        print(f"  מחיר חזוי במדגם (M€): חציון {np.median(pred):.2f} · "
              f"טווח {pred.min():.2f}-{pred.max():.2f}")
        print(f"  שכר בפועל     (M€): חציון {d.salary.median()/1e6:.2f} · "
              f"טווח {d.salary.min()/1e6:.2f}-{d.salary.max()/1e6:.2f}")
    print(sep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
