"""scale_regression.py — כיול הסקלה על 18 מועדונים במקום חציון אחד.

יום 11 המיר יחידות מנורמלות למיליוני יורו דרך נקודה אחת:

    scale = חציון(תקציב אמיתי) / חציון(תקציב מנורמל) = 13.35 / 15.04 = 0.888

והבוטסטרפ נתן רצועה של 12.4M על מספר של 20M, כי התפלגות
התקציבים דו-מודלית עם פער ריק בין 10 ל-13.2 והחציון נופל בתוכו.

כאן מוחלפת נקודת החציון ברגרסיה על כל 18 המועדונים. ארבעה דברים
נמדדים, ואף אחד מהם לא היה לנו:

  1. הסקלה כשיפוע, עם CI שנשען על 18 תצפיות ולא על נקודה אחת
  2. **החותך** — האם ההמרה כפלית או אפינית
  3. R² — כמה טוב מודל העלות משחזר תקציבים אמיתיים. אין לנו
     בדיקה כזו בכלל
  4. `b` ב-log-log — בדיקה צולבת ל-0.76 של יום 11 ברמת השחקן

--------------------------------------------------------------------
החלטות שננעלו לפני ההרצה
--------------------------------------------------------------------
כיוון:      real ~ norm ולא ההפך. התקציב האמיתי הוא 18 הערכות
            עיתונאיות, כלומר המשתנה הרועש; משתנה רועש על ציר X
            מטה את השיפוע לאפס (attenuation).

מירכוז:     הרגרסיה על (norm − mean). החותך הופך לפרשני — התקציב
            האמיתי במועדון ממוצע — והקורלציה שלו עם השיפוע קורסת,
            כך שה-SE של השיפוע אינו מנופח סתם.

חותך:       **לא** דרך הראשית. רצפות ה-CBS אינן הסיבה — הן לא היו
            נאכפות ב-2024 (עונת חסד), ואף מועדון אינו קרוב אליהן,
            ורצפה שלא מחייבת אינה מייצרת חותך. הסיבה האמיתית היא
            שהמודל פורש מחירים רחב מדי (0.76): מועדון עתיר כוכבים
            מקבל תקציב מנורמל מנופח והזול מכווץ, ולכן norm נפרש
            יותר מ-real ⇒ שיפוע<1 וחותך>0. חותך ושיפוע<1 הם
            **אותו ממצא**, לא שניים.

מכבי:       מודל העלות כויל על מכבי. ההשארה שלה בכיול טאוטולוגית
            חלקית — אותו נימוק שהוציא 39 עוגנים ב-price_structure.
            רץ עם ובלי, והשארית שלה מדווחת בנפרד.

רישיון:     לא שלושה חותכים. ב-2024 החלוקה בפועל היא שתיים — 12
            רישיונות ארוכי-טווח מול 6 שנתיים. dof אחד.
            ⚠️ ננעל מראש: אפקט מובהק כאן **אינו** ראיה לרצפה
            רגולטורית, כי סוג הרישיון מבולבל עם גודל המועדון.

הרצה:  python src/scale_regression.py
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

from roster_optimizer import PROCESSED_DIR  # noqa: E402

SEASON = 2024
N_BOOT = 4000
SEED = 12

# תוויות עבריות -> קודי מועדון. ידני בכוונה: 18 שורות שאפשר
# לקרוא ולוודא, במקום התאמה מטושטשת שאף אחד לא בודק.
NAME2CODE = {
    "ריאל מדריד": "MAD", "פנאתינייקוס": "PAN", "אולימפיאקוס": "OLY",
    "אנדולו אפס": "IST", "פנרבחצה": "ULK", "ברצלונה": "BAR",
    "מילאנו": "MIL", "הכוכב האדום": "RED", "מונקו": "MCO",
    "פרטיזן": "PAR", "וירטוס": "VIR", "באיירן": "MUN",
    "באסקוניה": "BAS", "ז'לגיריס": "ZAL", 'מכבי ת"א': "TEL",
    "ASVEL": "ASV", "פריז": "PRS", "אלבה ברלין": "BER",
}

# רישיון ארוך-טווח (A) מול שנתי, 2024-25.
ANNUAL_LICENCE = {"PRS", "PAR", "RED", "MCO", "IST", "ULK"}

SEP = "=" * 78


def h(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def load() -> pd.DataFrame:
    rel = pd.read_csv(PROCESSED_DIR / "budget_relative.csv")
    rel = rel[rel.season == SEASON][["club", "budget_rel"]]

    gem = pd.read_csv(PROCESSED_DIR / "club_budgets_gemini.csv")
    gem = gem[gem.season == SEASON].copy()
    gem["club"] = gem.club.map(NAME2CODE)
    miss = gem[gem.club.isna()]
    if len(miss):
        raise SystemExit(f"תוויות לא ממופות: {list(miss.club)}")

    d = rel.merge(gem[["club", "net_eur", "gross_eur"]], on="club",
                  how="inner")
    npool = pd.read_csv(PROCESSED_DIR / "n_pool_2024.csv") \
        if (PROCESSED_DIR / "n_pool_2024.csv").exists() else None
    if npool is not None:
        d = d.merge(npool, on="club", how="left")
    print(f"  התאמה: {len(d)}/{len(rel)} מנורמלים · {len(gem)} אמיתיים")
    unmatched = set(rel.club) ^ set(gem.club)
    if unmatched:
        print(f"  ⚠️ לא הותאמו: {sorted(unmatched)}")
    d["annual"] = d.club.isin(ANNUAL_LICENCE).astype(int)
    return d.sort_values("net_eur", ascending=False).reset_index(drop=True)


def fit(y, x, label, centred=True):
    xc = x - x.mean() if centred else x
    m = sm.OLS(y, sm.add_constant(xc)).fit()
    a, s = float(m.params[0]), float(m.params[1])
    ci = np.asarray(m.conf_int())
    print(f"\n  {label}")
    print(f"    שיפוע {s:.4f}  CI95 [{ci[1, 0]:.4f}, {ci[1, 1]:.4f}]  "
          f"רוחב {ci[1, 1] - ci[1, 0]:.4f}  p={m.pvalues[1]:.4f}")
    print(f"    חותך  {a:.4f}  CI95 [{ci[0, 0]:.4f}, {ci[0, 1]:.4f}]  "
          f"p={m.pvalues[0]:.4f}"
          + ("   (במועדון ממוצע)" if centred else ""))
    print(f"    R² {m.rsquared:.4f}   n={int(m.nobs)}")
    return m, s, a


def main() -> int:
    rng = np.random.default_rng(SEED)
    h("כיול הסקלה — רגרסיה על 18 מועדונים")
    d = load()

    y = d.net_eur.values
    x = d.budget_rel.values
    xbar = float(x.mean())

    print(f"\n  אמיתי (נטו M€):  חציון {np.median(y):.2f}  "
          f"טווח {y.min():.1f}–{y.max():.1f}  ס\"ת {y.std(ddof=1):.2f}")
    print(f"  מנורמל:          חציון {np.median(x):.2f}  "
          f"טווח {x.min():.1f}–{x.max():.1f}  ס\"ת {x.std(ddof=1):.2f}")
    sd_ratio = y.std(ddof=1) / x.std(ddof=1)
    print(f"  יחס ס\"ת (real/norm) = {sd_ratio:.3f}")
    print("     >1 ⇒ התקציבים האמיתיים נפרשים **יותר** מהמודל,")
    print("          כלומר המודל **מכווץ** הפרשים ברמת המועדון.")
    print("     <1 ⇒ ההפך: המודל פורש רחב מדי.")

    # -------------------------------------------------- 1. רמות
    h("1. רגרסיית רמות")
    print(f"  ⚠️ החותך מדווח במירכוז: התקציב האמיתי במועדון שהתקציב")
    print(f"     המנורמל שלו הוא הממוצע ({xbar:.2f}).")
    m_c, s_c, a_c = fit(y, x, "עם חותך (ממורכז)")
    m_r, s_r, _ = fit(y, x, "עם חותך (לא ממורכז)", centred=False)
    a_raw = float(m_r.params[0])
    print(f"    → החותך הגולמי (norm=0): {a_raw:.3f} M€"
          "   ⚠️ אקסטרפולציה — אין מועדון בקרבת אפס")

    m_o = sm.OLS(y, x).fit()
    s_o = float(m_o.params[0])
    ci_o = np.asarray(m_o.conf_int())[0]
    print(f"\n  דרך הראשית (ללא חותך)")
    print(f"    שיפוע {s_o:.4f}  CI95 [{ci_o[0]:.4f}, {ci_o[1]:.4f}]  "
          f"רוחב {ci_o[1] - ci_o[0]:.4f}")
    print(f"    R² (לא בר-השוואה) {m_o.rsquared:.4f}")
    print(f"\n  ההשוואה: 0.888 של יום 11 היה חציון/חציון. "
          f"דרך הראשית נותנת {s_o:.3f}, עם חותך {s_c:.3f}.")

    # מבחן פורמלי: האם החותך נדרש
    print(f"\n  האם החותך נדרש? F-test מול דרך הראשית: "
          f"p = {m_r.pvalues[0]:.4f}")

    # -------------------------------------------------- 1ב. המנגנון
    h("1ב. המנגנון — עלות לשחקן")
    d["rel_pp"] = d.budget_rel / d.n_pool
    d["eur_pp"] = d.net_eur / d.n_pool
    r_rel = d.rel_pp.max() / d.rel_pp.min()
    r_eur = d.eur_pp.max() / d.eur_pp.min()
    print(f"\n  עלות לשחקן, מנורמל: {d.rel_pp.min():.3f}–{d.rel_pp.max():.3f}"
          f"   יחס {r_rel:.2f}")
    print(f"  עלות לשחקן, אמיתי : {d.eur_pp.min():.3f}–{d.eur_pp.max():.3f}"
          f"   יחס {r_eur:.2f}")
    print(f"  המודל מכווץ פי {r_eur / r_rel:.2f}")
    print("\n  ⚠️ הכיווץ הוא ב**רצפה**, לא בתקרה: המחיר הזול ביותר")
    print("     שהמודל יודע לתת חוסם מלמטה כל סגל זול. זו בדיוק")
    print("     הקריאה של יום 9 — β₁ מודד את הרצפה, לא את התקרה.")

    # -------------------------------------------------- 2. log-log
    h("2. log-log — בדיקה צולבת ל-0.76")
    ly, lx = np.log(y), np.log(x)
    m_l, b, _ = fit(ly, lx, "log(real) ~ log(norm)")
    print(f"\n    b = {b:.3f}. ברמת השחקן יום 11 מדד שיפוע שוק~מודל "
          f"0.76.")
    if b < 0.6:
        print("    b נמוך משמעותית מ-0.76 ⇒ יש רכיב חיבורי מעל "
              "פרישת-היתר.")
    elif b > 0.95:
        print("    b ≈ 1 ⇒ פרישת-היתר ברמת השחקן מתקזזת ברמת "
              "המועדון. חדשות טובות לעקומה.")
    else:
        print("    b בטווח שעקבי עם פרישת-יתר כפלית טהורה.")

    # -------------------------------------------------- 3. אבחון
    h("3. אבחון — מינוף, מכבי, רישיון")
    infl = m_c.get_influence()
    cook = infl.cooks_distance[0]
    resid = m_c.resid
    dd = d.assign(fitted=m_c.fittedvalues, resid=resid, cook=cook)
    dd["resid_rank"] = dd.resid.abs().rank()
    print("\n" + dd[["club", "budget_rel", "net_eur", "fitted", "resid",
                     "cook", "annual"]].round(3).to_string(index=False))

    thr = 4 / len(d)
    big = dd[dd.cook > thr]
    print(f"\n  סף Cook 4/n = {thr:.3f} · חורגים: "
          f"{list(big.club) if len(big) else 'אין'}")

    tel = dd[dd.club == "TEL"]
    if len(tel):
        r = float(tel.resid.iloc[0])
        rank = int(tel.resid_rank.iloc[0])
        print(f"\n  מכבי (TEL): שארית {r:+.3f} M€ · דירוג |שארית| "
              f"{rank}/{len(d)} "
              f"({'שליש תחתון' if rank <= len(d)/3 else 'לא בשליש התחתון'})")

    # LOO על הסקלה
    loo = []
    for i in range(len(d)):
        k = np.ones(len(d), bool); k[i] = False
        mi = sm.OLS(y[k], sm.add_constant(x[k] - x[k].mean())).fit()
        loo.append(float(mi.params[1]))
    loo = np.array(loo)
    worst = int(np.argmax(np.abs(loo - s_c)))
    print(f"\n  LOO על השיפוע: {loo.min():.4f}–{loo.max():.4f} "
          f"(מלא {s_c:.4f})")
    print(f"    הזזה מרבית: {d.club.iloc[worst]} → {loo[worst]:.4f} "
          f"({abs(loo[worst] / s_c - 1):+.1%})")

    # מכבי בחוץ
    k = (d.club != "TEL").values
    m_nt = sm.OLS(y[k], sm.add_constant(x[k] - x[k].mean())).fit()
    print(f"\n  בלי מכבי: שיפוע {float(m_nt.params[1]):.4f} · "
          f"R² {m_nt.rsquared:.4f} (n=17)")

    # רישיון — dof אחד, אחרי בקרת תקציב
    m_lic = sm.OLS(y, sm.add_constant(
        np.column_stack([x - xbar, d.annual.values]))).fit()
    p_lic = float(m_lic.pvalues[2])
    print(f"\n  רישיון שנתי (dof=1, אחרי בקרת תקציב מנורמל): "
          f"β={float(m_lic.params[2]):+.3f} M€  p={p_lic:.4f}")
    print("  ⚠️ מובהקות כאן אינה ראיה לרצפת CBS — סוג הרישיון "
          "מבולבל עם גודל המועדון.")

    # -------------------------------------------------- 4. בוטסטרפ
    h("4. הרצועה — רגרסיה מול חציון")
    bs_s, bs_a, bs_med = [], [], []
    n = len(d)
    for _ in range(N_BOOT):
        i = rng.integers(0, n, n)
        xb, yb = x[i], y[i]
        if xb.std() < 1e-9:
            continue
        mb = sm.OLS(yb, sm.add_constant(xb - xb.mean())).fit()
        bs_s.append(float(mb.params[1]))
        bs_a.append(float(mb.params[0]))
        bs_med.append(np.median(yb) / np.median(xb))
    bs_s = np.array(bs_s); bs_a = np.array(bs_a); bs_med = np.array(bs_med)

    q = lambda v: np.percentile(v, [2.5, 97.5])  # noqa: E731
    ls, hs = q(bs_s); lm, hm = q(bs_med); la, ha = q(bs_a)
    print(f"\n  {'שיטה':<26}{'אומדן':>10}{'CI95':>26}{'רוחב':>10}")
    print(f"  {'חציון/חציון (יום 11)':<26}{np.median(y)/np.median(x):>10.4f}"
          f"{f'[{lm:.4f}, {hm:.4f}]':>26}{hm-lm:>10.4f}")
    print(f"  {'שיפוע רגרסיה':<26}{s_c:>10.4f}"
          f"{f'[{ls:.4f}, {hs:.4f}]':>26}{hs-ls:>10.4f}")
    print(f"  {'חותך (ממורכז) M€':<26}{a_c:>10.4f}"
          f"{f'[{la:.4f}, {ha:.4f}]':>26}{ha-la:>10.4f}")
    print(f"\n  צמצום רוחב: {1 - (hs-ls)/(hm-lm):+.1%}")

    # -------------------------------------------------- 5. רוויה
    h("5. הרוויה — המרה אפינית")
    sat = pd.read_csv(PROCESSED_DIR / "scale_sensitivity.csv")
    print("\n  ⚠️ ההמרה היא EUR = a + s·norm, לא סקלה יחידה.")
    print("     השולי ('מה מיליון קונה') תלוי ב-s בלבד.")
    print("     הרמה ('הרוויה ב-X M€') תלויה גם ב-a — והוא "
          "המאוקסטרפל.\n")
    print(f"  {'עונה':<8}{'sat_norm':>10}{'יום 11':>10}{'רגרסיה':>10}"
          f"{'CI95':>24}")
    rows = []
    for _, r in sat.iterrows():
        sn = float(r.sat_norm)
        old = float(r.sat_point)
        new = a_raw + s_c * sn
        bs_new = bs_a + bs_s * (sn - xbar)
        lo, hi = q(bs_new)
        print(f"  {int(r.season):<8}{sn:>10.1f}{old:>10.1f}{new:>10.1f}"
              f"{f'[{lo:.1f}, {hi:.1f}]':>24}")
        rows.append(dict(season=int(r.season), sat_norm=sn,
                         sat_day11=old, sat_reg=new, lo=lo, hi=hi))
    out = pd.DataFrame(rows)
    print(f"\n  ממוצע: {out.sat_reg.mean():.1f} M€  "
          f"רצועה [{out.lo.mean():.1f}, {out.hi.mean():.1f}]  "
          f"רוחב {out.hi.mean()-out.lo.mean():.1f}M "
          f"(יום 11: 12.4M)")

    p = PROCESSED_DIR / "scale_regression.csv"
    dd.to_csv(p, index=False)
    pd.DataFrame(rows).to_csv(
        PROCESSED_DIR / "scale_regression_saturation.csv", index=False)
    print(f"\n  נשמר: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())