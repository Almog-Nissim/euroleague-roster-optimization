"""wins_conversion.py — יום 12. הכותרת, כהפרש ולא כרמה.

--------------------------------------------------------------------
שלוש ההחלטות שננעלו לפני ההרצה
--------------------------------------------------------------------
1. **שני המנועים, מוצהרים מראש.** החופשי (יתרון 18.3%) והמאולץ
   בזהות הכדור (6.5%). לא בוחרים בדיעבד — ההפרש ביניהם הוא
   הממצא: כמה מהכותרת תלוי באילוץ שהוא זהות מתמטית.

2. **שני מקדמים שונים, ואסור לערבב.**

     W_gap(B)   — ניצחונות מעל מועדון אמיתי **באותו תקציב**.
                  זו השוואה בתקציב מקובע, ולכן המקדם הוא
                  ה**חלקי** — `wins ~ q + log(budget)`.
     W_level(B) — רמת הניצחונות של הסגל. הרגרסיה הדו-משתנית,
                  עם התקציב בפועל, כי הסגל אכן עלה כסף.

   שימוש במקדם הגולמי ל-W_gap מייחס להקצאה מה שהתקציב קנה.

3. **יחידות.** רגרסיית הניצחונות רצה על ניקוד **מנורמל
   תוך-עונתית**; `q_club`/`q_free`/`q_cap` הם גולמיים. זה בדיוק
   הכשל של יום 11 (סעיף 2). לכן הנרמול מפורש, ושני הממוצעים
   מודפסים לפני ההמרה.

⚠️ ציר ה-X ביחידות מנורמלות בלבד. ההמרה ליורו הוקפאה — שלושה
   מפרטי כיול לגיטימיים נותנים 19.1 / 24.5 / 30.5 לאותה נקודה.

--------------------------------------------------------------------
ההסתייגות שחייבת ללוות כל מספר כאן
--------------------------------------------------------------------
השיפוע נאמד **בין מועדונים**. מועדון עם ניקוד גבוה הוא גם עשיר,
עם מאמן טוב יותר. בקרת התקציב מנכה חלק מזה, לא את כולו.

ורצועת ההפרש שמדווחת כאן היא **סטטיסטית בלבד**. היא אינה מכילה
את שגיאת האקסטרפולציה של הקיר (סעיף 0א): הרגרסיה נאמדה על פיזור
ניקוד של 6-10 נקודות ומוחלת על פער של 18.6. אי-הוודאות האמיתית
גדולה מהמספר שיודפס.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""
# היסטורי, יום 12 — לוח התחזיות של הגרסה הקודמת. לא מודפס מ-v1.0.
PRED = {
    "1. s_partial / s_raw":      ("0.40-0.45",  "0.38-0.48"),
    "2א. הפרש, מנוע חופשי":      ("+2.6..+3.8", "+2.6..+3.8"),
    "2ב. הפרש, מנוע מאולץ":      ("+0.5..+1.0", "+0.9..+1.5"),
    "3. רוחב רצועת ההפרש":       ("1.5-2.0",    "1.9-2.6"),
    "4. רוחב רצועת הרמה":        ("5-6",        "6-9"),
}
# ====================================================================


import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from roster_optimizer import PROCESSED_DIR  # noqa: E402

N_BOOT = 4000
SEED = 12
SEP = "=" * 76


def h(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def zdemean(df: pd.DataFrame, col: str) -> pd.Series:
    """נרמול z בתוך עונה. 2016-2023 שיחקו 30-34 מחזורים, 2025 — 38."""
    g = df.groupby("season")[col]
    return (df[col] - g.transform("mean")) / g.transform("std")


# 🔴 v1.0, 2026-09-21 — ננעל לפני ההרצה, משני הצדדים. הכותרת עוברת
#    לקונבנציה של ADR 0006: המנוע על התוכנית שלו, המועדון על מה ששיחק.
#    גם הרגרסיה עוברת ל-q_club_actual — שיפוע מסקאלה אחת על פער מסקאלה
#    אחרת הוא בדיוק מה שסעיף "יחידות" למעלה אוסר.
PRED_V1 = dict(claude=(4.6, 5.6), almog=(4.5, 5.0))   # ניצחונות לעונה, מאולץ
LEGACY_WINS = 4.26            # FROZEN עד v1.0 — חייב להשתחזר, זה ה-guard
LEGACY_TOL = 0.01


def budgets() -> pd.DataFrame:
    # 🔴 בקרת התקציב חייבת להיות התקציב **האמיתי נטו**, לא המנורמל.
    # המנורמל הוא תוצר מודל העלות, שמכווץ הפרשים בין מועדונים פי
    # 3.3 (scale_regression, סעיף 1ב). ו-`net` ולא `gross` — ההחלטה
    # "נטו בלבד" רשומה מיום 3.
    bud = pd.read_csv(PROCESSED_DIR / "club_budgets_gemini.csv")
    NAME2CODE = {
        "ברצלונה": "BAR", "צסקא מוסקבה": "CSK", "ריאל מדריד": "MAD",
        "חימקי": "KHI", "מילאנו": "MIL", "פנרבחצה": "ULK",
        "זניט": "DYR", "אנדולו אפס": "IST", 'מכבי ת"א': "TEL",
        "באיירן": "MUN", "באסקוניה": "BAS", "אולימפיאקוס": "OLY",
        "ולנסיה": "PAM", "פנאתינייקוס": "PAN", "ז'לגיריס": "ZAL",
        "ASVEL": "ASV", "אלבה ברלין": "BER", "הכוכב האדום": "RED",
        "מונקו": "MCO", "פרטיזן": "PAR", "וירטוס": "VIR",
        "פריז": "PRS", 'הפועל ת"א': "HTA", "דובאי": "DUB",
    }
    # ⚠️ PAR = פרטיזן (מ-2022), PRS = פריז (מ-2024). אומת מול team_season.
    bud["club"] = bud.club.map(NAME2CODE)
    return bud[["season", "club", "net_eur"]].dropna(subset=["club"])


def convert(d: pd.DataFrame, rng, label: str):
    """שיפוע ניקוד->ניצחונות על q_club, ופער gap מומר באותה סקאלה.

    d חייב להכיל: season, club, q_club, gap, wins, net_eur.
    מחזיר (row, fit) — fit לסעיף הרמה.
    """
    d = d.copy()
    d["qz"] = zdemean(d, "q_club")
    d["wz"] = zdemean(d, "wins")
    d["lb"] = np.log(d.net_eur)
    d["lbz"] = zdemean(d, "lb")
    sd_w = d.groupby("season").wins.transform("std")
    sd_q = d.groupby("season").q_club.transform("std")
    m_raw = sm.OLS(d.wz, sm.add_constant(d[["qz"]])).fit()
    m_par = sm.OLS(d.wz, sm.add_constant(d[["qz", "lbz"]])).fit()
    s_raw = float(m_raw.params.iloc[1])
    s_par = float(m_par.params.iloc[1])
    k = float((sd_w / sd_q).mean())
    pt = s_par * k * float(d.gap.median())

    out = []
    n = len(d)
    for _ in range(N_BOOT):
        i = rng.integers(0, n, n)
        s = d.iloc[i]
        if s.season.nunique() < 2:
            continue
        try:
            sz = zdemean(s, "q_club")
            wzb = zdemean(s, "wins")
            lbb = zdemean(s.assign(lb=np.log(s.net_eur)), "lb")
            X = sm.add_constant(pd.DataFrame(
                {"qz": sz.values, "lbz": lbb.values}))
            mb = sm.OLS(wzb.values, X).fit()
            kb = float((s.groupby("season").wins.transform("std")
                        / s.groupby("season").q_club.transform("std")).mean())
            out.append(float(mb.params.iloc[1]) * kb * float(s.gap.median()))
        except Exception:
            continue
    lo, hi = np.percentile(np.array(out), [2.5, 97.5])

    print(f"\n  [{label}]  n={n} · q_club ממוצע {d.q_club.mean():.2f}")
    print(f"    גולמי β={s_raw:.4f} R²={m_raw.rsquared:.3f} · "
          f"חלקי β={s_par:.4f} R²={m_par.rsquared:.3f} · "
          f"s_par/s_raw={s_par / s_raw:.3f}")
    print(f"    ניצחון לנקודת ניקוד (חלקי) {s_par * k:.4f} · "
          f"פער ניקוד חציוני {d.gap.median():.2f}")
    print(f"    🔴 הפרש ניצחונות = {pt:+.2f}   CI95 [{lo:+.2f}, {hi:+.2f}]"
          f"   רוחב {hi - lo:.2f}")
    row = dict(engine=label, gap_pts=float(d.gap.median()), wins=pt,
               lo=lo, hi=hi, width=hi - lo, slope_partial=s_par, k=k,
               frac=s_par / s_raw, n=n)
    return row, (m_par, sd_w)


def main() -> int:
    rng = np.random.default_rng(SEED)
    print(SEP)
    print("wins_conversion — הכותרת כהפרש. יחידות מנורמלות בלבד. v1.0 / ADR 0006")
    print(SEP)

    ts = pd.read_csv(PROCESSED_DIR / "team_season.csv")
    ts = ts[["season", "team", "wins", "win_pct", "team_games"]].rename(
        columns={"team": "club"})
    bud = budgets()

    def prep(d):
        d = d.merge(ts, on=["season", "club"], how="inner")
        return d.merge(bud, on=["season", "club"],
                       how="inner").dropna(subset=["net_eur"])

    # ------------------------------------------- הקונבנציה הישנה = guard
    # usage_constrained_results.csv: המנוע מחולק מחדש בדיעבד, המועדון
    # חמדני. זה מה ש-FROZEN הציג עד v1.0 (4.26). הוא חייב להשתחזר כאן,
    # כדי שהמעבר ל-ADR 0006 יהיה הרצה אחת ולא שני מספרים בלי גשר.
    old = pd.read_csv(PROCESSED_DIR / "usage_constrained_results.csv")
    old = prep(old.assign(gap=old.q_cap - old.q_club))
    h("1. הקונבנציה הישנה — שחזור של FROZEN")
    legacy, _ = convert(old[["season", "club", "q_club", "gap", "wins",
                             "net_eur"]], rng,
                        "קונבנציה ישנה (ADR 0005 A)")

    # ------------------------------------------- ADR 0006 = הכותרת
    # headline_exact.csv: המנוע על התוכנית של ה-LP המאולץ עם הצורה,
    # gap=0, הוכח אופטימלי 38/38. המועדון על הדקות ששיחק.
    ex = pd.read_csv(PROCESSED_DIR / "headline_exact.csv")
    ex = prep(ex.assign(q_club=ex.q_club_actual,
                        gap=ex.q_plan - ex.q_club_actual))
    h("2. הכותרת — ADR 0006, מנוע מאולץ על התוכנית שלו")
    spec, (m_par, sd_w) = convert(ex[["season", "club", "q_club", "gap",
                                      "wins", "net_eur"]], rng, "מאולץ")

    # ------------------------------------------- הרמה
    h("3. הרמה — ולמה היא לא הכותרת")
    resid_sd = float(np.std(m_par.resid, ddof=3))
    lvl_w = 2 * 1.96 * resid_sd * float(sd_w.mean())
    print(f"  רוחב רצועת הרמה (95%) = {lvl_w:.2f} ניצחונות · "
          f"רוחב רצועת ההפרש = {spec['width']:.2f} · "
          f"יחס {lvl_w / spec['width']:.1f}x")

    # ------------------------------------------- guards
    h("guards")
    g1 = abs(legacy["wins"] - LEGACY_WINS) <= LEGACY_TOL
    g2 = spec["n"] == 38 or spec["n"] == legacy["n"]
    g3 = spec["lo"] > 0
    print(f"  {'✅' if g1 else '❌'} הקונבנציה הישנה משחזרת את FROZEN "
          f"{LEGACY_WINS}: {legacy['wins']:+.2f}")
    print(f"  {'✅' if g2 else '❌'} אותו מדגם בשתי הקונבנציות: "
          f"{legacy['n']} / {spec['n']}")
    print(f"  {'✅' if g3 else '❌'} הקצה התחתון של הכותרת חיובי: "
          f"{spec['lo']:+.2f}")

    h("מול התחזיות שננעלו")
    for who, (a, b) in PRED_V1.items():
        ok = a <= spec["wins"] <= b
        print(f"  {'✅' if ok else '❌'} {who:<7} [{a}, {b}]  ->  "
              f"{spec['wins']:+.2f}")

    out = pd.DataFrame([spec, legacy])
    out.to_csv(PROCESSED_DIR / "wins_conversion.csv", index=False)
    print(f"\n  נשמר: {PROCESSED_DIR / 'wins_conversion.csv'}")
    print(SEP)
    return 0 if (g1 and g2) else 1


if __name__ == "__main__":
    raise SystemExit(main())