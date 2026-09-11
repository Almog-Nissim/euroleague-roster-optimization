"""refit_acceptance.py — מבחן הקבלה לציר היורו. יום 15.

--------------------------------------------------------------------
מה נשאל כאן
--------------------------------------------------------------------
ADR 0001 מתמחר את המאגר ב-α הממוצע. `cost_market` מפרש את זה
כפשוטו: α הוא רמת מחירים ביורו, ולכן exp(α̅+βx) הוא מחיר ביורו
והציר 8–40 נקרא כמיליוני יורו נטו.

זו טענה **חיצונית** — היא נבדקת מול נתון שאינו במודל. אם היא
נכשלת, אין לרשום יורו על הציר. הסף הוגדר לפני ההרצה:

    1. fit_eur על מועדוני 2025:  a ∈ [0.85, 1.15] ו-|b| ≤ 2.0M€
       (a≈1, b≈0 פירושו שהציר כבר ביורו ואינו זקוק למיפוי)

    2. MAE של fit_eur ≤ 2.15M€
       (הבסיס של המיפוי הישן. ציר גרוע ממנו אינו שיפור)

    3. מבחן ברמת **שחקן**, על HTA · OLY · BAS בלבד:
       Spearman ≥ 0.60 ו-MAE ≤ 1.35M€

שלושת המועדונים בתנאי 3 הם המדגם החוץ-מדגמי היחיד שקיים: אף
שורת שכר שלהם לא נכנסה לכיול (usage='test', ו-OLY בעוגנים
'structure_only'). זה חזק יותר מבדיקת התצוגה שבשלב 5 של הספק,
שרצה על 11 שחקנים ש**ה-LP בחר** — כלומר מוטים לכיוון מי שהמודל
מתמחר בחסר.

⚠️ הטיה מוצהרת בתנאי 3: המודל מתמחר ב-α ממוצע ובכוונה מתעלם
   מהמועדון. HTA ו-OLY אינם מועדון ממוצע. שגיאת הרמה שלהם היא
   בדיוק מה שאפקט קבוע היה סופג, ולכן MAE כאן הוא חסם עליון על
   שגיאת התמחור — לא אומדן שלה. מדווח גם Spearman, שאינו רגיש
   לרמה, וגם ההטיה החציונית לכל מועדון בנפרד.

הרצה:
    COST_SPEC=market python src/refit_acceptance.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import optimizer_backtest as ob  # noqa: E402
import roster_optimizer as ro  # noqa: E402
import cost_market  # noqa: E402
from paths import PROCESSED_DIR  # noqa: E402
from league_backtest import build_pool, club_side  # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER  # noqa: E402
from club_codes import NAME2CODE  # noqa: E402
import salary_market as smk  # noqa: E402

SEASON, TRAIN_MAX = 2025, 2024
OOS_CLUBS = ["HTA", "OLY", "BAS"]          # לא נגעו בכיול. שלב 1.

# ---------------- סף שהוצהר לפני ההרצה ----------------
T1_A = (0.85, 1.15)
T1_B_ABS = 2.0
T2_MAE = 2.15
T3_SPEARMAN = 0.60
T3_MAE = 1.35
# ------------------------------------------------------

SEP = "=" * 78


def h(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def oos_salaries(ps: pd.DataFrame) -> pd.DataFrame:
    """כל תצפית שכר אמיתית של מועדוני המבחן בעונת SEASON."""
    a = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                    dtype={"player_code": str})
    a["salary"] = pd.to_numeric(a.salary_mid, errors="coerce")
    a = a[(a.season == SEASON) & a.player_code.notna() & a.salary.notna()
          & a.club.isin(OOS_CLUBS)]
    rows = [pd.DataFrame({"player_code": a.player_code.astype(str),
                          "club": a.club, "salary": a.salary.astype(float),
                          "src": "anchor"})]

    s = pd.read_csv(PROCESSED_DIR / "salary_external_2025.csv")
    s = s[(s.yr == SEASON)].copy()
    s["club_code"] = s.club.map(smk.CLUBMAP)
    s = s[s.club_code.isin(OOS_CLUBS)]
    s["key"] = s.player.astype(str).str.split("/").str[0].map(smk.norm)
    p = ps.dropna(subset=["player_name"]).copy()
    p["key"] = (p.player_name.str.split(",").str[1].fillna("")
                + p.player_name.str.split(",").str[0]).map(smk.norm)
    p["pc"] = p.player_code.astype(str)
    kmap = p.drop_duplicates("key").set_index("key").pc
    s["player_code"] = s.key.map(kmap)
    s.loc[s.player_code.isna(), "player_code"] = \
        s.loc[s.player_code.isna(), "key"].map(smk.ALIAS)
    s = s[s.player_code.notna()]
    rows.append(pd.DataFrame({"player_code": s.player_code.astype(str),
                              "club": s.club_code,
                              "salary": pd.to_numeric(s.salary,
                                                      errors="coerce"),
                              "src": "external"}))

    d = pd.concat(rows, ignore_index=True)
    d = d[d.salary.notna() & (d.salary > 0)]
    return (d.sort_values("src")                 # anchor גובר
            .drop_duplicates("player_code", keep="first")
            .reset_index(drop=True))


def main() -> int:
    print(SEP)
    print(f"refit_acceptance — מבחן הקבלה לציר היורו · מפרט "
          f"{ob.COST_SPEC}")
    print(f"סף שהוצהר: a∈[{T1_A[0]},{T1_A[1]}] · |b|≤{T1_B_ABS} · "
          f"MAE≤{T2_MAE} · ρ≥{T3_SPEARMAN} · MAE_שחקן≤{T3_MAE}")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    cand, info = build_pool(SEASON, TRAIN_MAX, feat, anch, pos, ps)
    cand = cand.reset_index(drop=True)
    fit_meta = dict(cost_market.LAST_FIT) if cost_market.LAST_FIT else {}
    if fit_meta:
        h("מודל העלות שנאמד")
        cost_market.report(_Shim(fit_meta))

    h("0. המאגר ורמת המחירים")
    print(f"  {len(cand)} שחקנים · מחיר {cand.cost.min():.2f}–"
          f"{cand.cost.max():.2f} · חציון {cand.cost.median():.2f} · "
          f"ממוצע {cand.cost.mean():.2f}")

    # ------------------------------------------------ תקציבי המועדונים
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})
    posmap = pos.set_index(pos.player_code.astype(str)).position
    gmax = float(ps[ps.season == SEASON].games.max())
    clubs = []
    for club in sorted(split[split.season == SEASON].club.unique()):
        keep, _ = club_side(cand, split, club, SEASON, gmax, posmap)
        if len(keep) < MIN_LEGAL_ROSTER:
            continue
        clubs.append(dict(club=club, budget=float(keep.cost.sum()),
                          n=len(keep)))
    cb = pd.DataFrame(clubs)
    print(f"\n  תקציבי {len(cb)} מועדונים: {cb.budget.min():.2f}–"
          f"{cb.budget.max():.2f} · חציון {cb.budget.median():.2f}")
    outside = cb[(cb.budget < 8.0) | (cb.budget > 40.0)]
    print(f"  מחוץ לרשת 8–40: {len(outside)}"
          + (f"  ({', '.join(outside.club)})" if len(outside) else ""))

    # ------------------------------------------------ תנאי 1 + 2
    h("1+2. fit_eur — הציר מול תקציבי היורו בפועל")
    bud = pd.read_csv(PROCESSED_DIR / "club_budgets_gemini.csv")
    bud["club"] = bud.club.map(NAME2CODE)
    m = (cb[["club", "budget"]]
         .merge(bud[bud.season == SEASON][["club", "net_eur"]], on="club")
         .dropna())
    x, y = m.budget.values.astype(float), m.net_eur.values.astype(float)
    a, b = np.polyfit(x, y, 1)
    pred = a * x + b
    r = float(np.corrcoef(x, y)[0, 1])
    mae = float(np.abs(y - pred).mean())
    ident_mae = float(np.abs(y - x).mean())      # אם הציר כבר יורו
    print(f"  net_eur = {a:.4f}·ציר {b:+.4f}   n={len(m)} · "
          f"R²={r*r:.3f} · MAE={mae:.2f}M€")
    print(f"  MAE אם קוראים את הציר כיורו ישירות (a=1,b=0): "
          f"{ident_mae:.2f}M€")
    m2 = m.assign(err=y - x).sort_values("err")
    print(f"  הסטיות הגדולות: " + " · ".join(
        f"{r_.club} {r_.budget:.1f}→{r_.net_eur:.1f} ({r_.err:+.1f})"
        for _, r_ in pd.concat([m2.head(2), m2.tail(2)]).iterrows()))

    t1 = (T1_A[0] <= a <= T1_A[1]) and abs(b) <= T1_B_ABS
    t2 = mae <= T2_MAE
    print(f"\n  תנאי 1  a={a:.3f} b={b:+.3f}   "
          f"{'✅' if t1 else '❌'}")
    print(f"  תנאי 2  MAE={mae:.2f}          {'✅' if t2 else '❌'}")

    # ------------------------------------------------ תנאי 3
    h("3. מבחן חוץ-מדגמי ברמת שחקן — HTA · OLY · BAS")
    real = oos_salaries(ps)
    F = feat[feat.season == SEASON].drop_duplicates("player_code").copy()
    F["player_code"] = F.player_code.astype(str)
    d = real.merge(F[["player_code"] + ro.COST_FEATURES], on="player_code",
                   how="inner").dropna(subset=ro.COST_FEATURES)
    # ⚠️ המבחן הזה שואל על **רמת המחירים ביורו**, ולכן הוא מכפיל
    #    חזרה במחלק הנרמול. אחרת הוא ישווה יחידות מאגר למיליוני
    #    יורו ו-MAE יהיה חסר משמעות (ρ אינו רגיש לכך).
    scale = float(info.get("cost_scale", 1.0))
    cmap = cand.set_index(cand.player_code.astype(str)).cost * scale
    d["model_m"] = d.player_code.map(cmap)
    n_nopool = int(d.model_m.isna().sum())
    d = d[d.model_m.notna()].copy()
    d["real_m"] = d.salary / 1e6
    d["err"] = d.model_m - d.real_m

    from scipy import stats as st
    rho, p_rho = st.spearmanr(d.model_m, d.real_m)
    mae_p = float(d.err.abs().mean())
    print(f"  n={len(d)} שחקנים ({n_nopool} נפלו — לא במאגר) · "
          f"מקורות: " + " · ".join(f"{k}:{v}" for k, v in
                                   d.src.value_counts().items()))
    print(f"  {'מועדון':<7}{'n':>4}{'מודל חציון':>13}{'אמת חציון':>12}"
          f"{'הטיה חציונית':>15}{'MAE':>8}")
    for club, g in d.groupby("club"):
        print(f"  {club:<7}{len(g):>4}{g.model_m.median():>13.2f}"
              f"{g.real_m.median():>12.2f}{g.err.median():>+15.2f}"
              f"{g.err.abs().mean():>8.2f}")
    print(f"\n  Spearman ρ = {rho:+.3f} (p={p_rho:.4f}) · MAE = {mae_p:.2f}M€ · "
          f"הטיה חציונית {d.err.median():+.2f}M€")

    t3 = (rho >= T3_SPEARMAN) and (mae_p <= T3_MAE)
    print(f"  תנאי 3  ρ={rho:.3f} MAE={mae_p:.2f}   {'✅' if t3 else '❌'}")

    # ------------------------------------------------ פסק
    h("פסק")
    for i, (nm, okk) in enumerate([("1 fit_eur a,b", t1),
                                   ("2 fit_eur MAE", t2),
                                   ("3 שחקן חוץ-מדגמי", t3)], 1):
        print(f"  {nm:<22}{'✅ עבר' if okk else '❌ נכשל'}")
    verdict = t1 and t2 and t3
    print()
    if verdict:
        print("  ✅ שלושת הסף עברו. הציר נרשם ביורו.")
    else:
        print("  ❌ לפחות תנאי אחד נכשל. לפי מה שהוסכם מראש: המחירים")
        print("     הפנימיים נשארים, הציר חוזר לחסר-יחידות (חלוקה")
        print("     בממוצע המאגר), ו-fit_eur נשאר ממיר. הכישלון עצמו")
        print("     ממצא: השוק מתומחר נכון בצורה ולא ברמה.")

    out = PROCESSED_DIR / "refit_acceptance.csv"
    pd.DataFrame([dict(
        spec=ob.COST_SPEC, season=SEASON,
        beta1=fit_meta.get("beta1"), n_fit=fit_meta.get("n"),
        n_clubs_fit=fit_meta.get("n_clubs"),
        pool_cost_mean=round(float(cand.cost.mean()), 4),
        club_budget_median=round(float(cb.budget.median()), 3),
        fit_eur_a=round(float(a), 4), fit_eur_b=round(float(b), 4),
        fit_eur_r2=round(r * r, 3), fit_eur_mae=round(mae, 3),
        identity_mae=round(ident_mae, 3),
        player_n=len(d), player_rho=round(float(rho), 4),
        player_mae=round(mae_p, 3),
        player_bias_med=round(float(d.err.median()), 3),
        t1=t1, t2=t2, t3=t3, verdict=verdict)]).to_csv(out, index=False)
    d.to_csv(PROCESSED_DIR / "refit_player_check.csv", index=False)
    print(f"\n  נשמר: {out.name} · refit_player_check.csv")
    print(SEP)
    return 0 if verdict else 2


class _Shim:
    """מאפשר ל-cost_market.report להדפיס meta שנשמר ב-LAST_FIT."""

    def __init__(self, meta):
        self.meta = meta


if __name__ == "__main__":
    raise SystemExit(main())
