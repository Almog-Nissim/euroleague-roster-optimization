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


def main() -> int:
    rng = np.random.default_rng(SEED)
    print(SEP)
    print("wins_conversion — הכותרת כהפרש. יחידות מנורמלות בלבד.")
    print(SEP)

    d = pd.read_csv(PROCESSED_DIR / "usage_constrained_results.csv")
    ts = pd.read_csv(PROCESSED_DIR / "team_season.csv")
    d = d.merge(ts[["season", "team", "wins", "win_pct", "team_games"]]
                .rename(columns={"team": "club"}),
                on=["season", "club"], how="inner")

    # 🔴 בקרת התקציב חייבת להיות התקציב **האמיתי נטו**, לא המנורמל.
    # המנורמל הוא תוצר מודל העלות, שמכווץ הפרשים בין מועדונים פי
    # 3.3 (scale_regression, סעיף 1ב). בקרה מכווצת מנכה פחות, ולכן
    # מנפחת את המקדם החלקי: 0.69 מול 0.39 עם gross ו-0.13 עם net.
    # ו-`net` ולא `gross`, כי gross כולל אולם, טיסות, צוות ומיסים —
    # ההחלטה "נטו בלבד" רשומה מיום 3.
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
    # ⚠️ PAR = פרטיזן (מ-2022), PRS = פריז (מ-2024). אומת מול
    #    team_season לפי עונת ההצטרפות. היפוך כאן הפך את הנקודה
    #    החריגה ב-scale_regression.
    bud["club"] = bud.club.map(NAME2CODE)
    n0 = len(d)
    d = d.merge(bud[["season", "club", "net_eur"]].dropna(subset=["club"]),
                on=["season", "club"], how="inner").dropna(subset=["net_eur"])
    print(f"\n  n = {len(d)} עונות-מועדון (מתוך {n0}; המסנן הוא כיסוי "
          f"תקציב נטו) · משחקים בעונה {sorted(d.team_games.unique())}")
    print("  " + " · ".join(f"{s}: {c}" for s, c in
                            d.groupby("season").size().items()))

    # ---------------------------------------------------- מבחן היחידות
    h("0. מבחן היחידות — הלקח של יום 11, מיושם")
    print(f"  ניקוד גולמי  q_club : ממוצע {d.q_club.mean():.2f} · "
          f"ס\"ת {d.q_club.std(ddof=1):.2f}")
    print(f"  ניקוד גולמי  q_free : ממוצע {d.q_free.mean():.2f}")
    print(f"  ניקוד גולמי  q_cap  : ממוצע {d.q_cap.mean():.2f}")
    for s, g in d.groupby("season"):
        print(f"    עונה {s}: q_club ממוצע {g.q_club.mean():.2f} · "
              f"ס\"ת {g.q_club.std(ddof=1):.2f} · "
              f"ניצחונות ממוצע {g.wins.mean():.1f}")
    print("\n  ⚠️ הרגרסיה תרוץ על z תוך-עונתי משני הצדדים. "
          "הפערים יומרו באותה סקאלה.")

    # ---------------------------------------------------- הרגרסיות
    h("1. שני המקדמים")
    d["qz"] = zdemean(d, "q_club")
    d["wz"] = zdemean(d, "wins")
    d["lb"] = np.log(d.net_eur)   # אמיתי נטו
    d["lbz"] = zdemean(d, "lb")
    sd_w = d.groupby("season").wins.transform("std")
    sd_q = d.groupby("season").q_club.transform("std")

    m_raw = sm.OLS(d.wz, sm.add_constant(d[["qz"]])).fit()
    m_par = sm.OLS(d.wz, sm.add_constant(d[["qz", "lbz"]])).fit()
    s_raw = float(m_raw.params.iloc[1])
    s_par = float(m_par.params.iloc[1])
    frac = s_par / s_raw

    print(f"\n  גולמי   wins_z ~ q_z            β={s_raw:.4f}  "
          f"R²={m_raw.rsquared:.3f}  p={m_raw.pvalues.iloc[1]:.4f}")
    print(f"  חלקי    wins_z ~ q_z + log(B)_z  β={s_par:.4f}  "
          f"R²={m_par.rsquared:.3f}  p={m_par.pvalues.iloc[1]:.4f}")
    print(f"          מקדם התקציב             β="
          f"{float(m_par.params.iloc[2]):.4f}  "
          f"p={m_par.pvalues.iloc[2]:.4f}")
    print(f"\n  🔴 s_partial / s_raw = {frac:.3f}   "
          f"(יום 9 מדד 0.42 — בקרת שחזור)")

    # ניצחונות לנקודת ניקוד גולמית
    k = float((sd_w / sd_q).mean())
    print(f"\n  המרה: ס\"ת ניצחונות / ס\"ת ניקוד = {k:.4f}")
    print(f"    → ניצחון לנקודת ניקוד, גולמי {s_raw * k:.4f} · "
          f"חלקי {s_par * k:.4f}")

    # ---------------------------------------------------- ההפרשים
    h("2. ההפרש — שני המנועים")
    d["gap_free"] = d.q_free - d.q_club
    d["gap_cap"] = d.q_cap - d.q_club
    for nm, col in [("חופשי", "gap_free"), ("מאולץ", "gap_cap")]:
        g = d[col]
        print(f"  {nm:<8} פער ניקוד: חציון {g.median():>6.2f} · "
              f"ממוצע {g.mean():>6.2f} · טווח {g.min():>6.2f}..{g.max():>6.2f}")

    def boot(col):
        """רצועה שמפיצה גם את השיפוע וגם את הפער, על אותן דגימות."""
        out = []
        n = len(d)
        for _ in range(N_BOOT):
            i = rng.integers(0, n, n)
            s = d.iloc[i]
            if s.season.nunique() < 2:
                continue
            try:
                sz = zdemean(s.assign(_i=range(len(s))), "q_club")
                wzb = zdemean(s, "wins")
                lbb = zdemean(s.assign(lb=np.log(s.net_eur)), "lb")
                X = sm.add_constant(pd.DataFrame(
                    {"qz": sz.values, "lbz": lbb.values}))
                mb = sm.OLS(wzb.values, X).fit()
                kb = float((s.groupby("season").wins.transform("std")
                            / s.groupby("season").q_club.transform("std")
                            ).mean())
                out.append(float(mb.params.iloc[1]) * kb
                           * float(s[col].median()))
            except Exception:
                continue
        return np.array(out)

    print()
    rows = []
    for nm, col in [("חופשי", "gap_free"), ("מאולץ", "gap_cap")]:
        pt = s_par * k * float(d[col].median())
        bs = boot(col)
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print(f"  🔴 מנוע {nm:<8} הפרש ניצחונות = {pt:+.2f}   "
              f"CI95 [{lo:+.2f}, {hi:+.2f}]   רוחב {hi - lo:.2f}")
        rows.append(dict(engine=nm, gap_pts=float(d[col].median()),
                         wins=pt, lo=lo, hi=hi, width=hi - lo))

    # ---------------------------------------------------- הרמה
    h("3. הרמה — ולמה היא לא הכותרת")
    resid_sd = float(np.std(m_par.resid, ddof=3))
    lvl_w = 2 * 1.96 * resid_sd * float((sd_w).mean())
    print(f"  ס\"ת שארית ברגרסיה (יחידות z): {resid_sd:.4f}")
    print(f"  ס\"ת ניצחונות ממוצעת בעונה:    {float(sd_w.mean()):.2f}")
    print(f"\n  🔴 רוחב רצועת הרמה (95%) = {lvl_w:.2f} ניצחונות")
    print(f"     מול רוחב רצועת ההפרש     = "
          f"{rows[0]['width']:.2f} (חופשי) · {rows[1]['width']:.2f} (מאולץ)")
    print(f"     יחס: {lvl_w / rows[1]['width']:.1f}x")
    print("\n  לכן הכותרת היא הפרש. הרמה סופגת את כל מה שלא מודלנו —")
    print("  מאמן, לכידות, בריאות, מזל. ההפרש מנכה אותם בין שני")
    print("  סגלים שנמדדים באותו מודל ובאותה עונה.")

    # ---------------------------------------------------- תחזיות
    h("4. לוח התחזיות")
    print(f"  {'מבחן':<26}{'אלמוג':>14}{'קלוד':>14}{'בפועל':>14}")
    actual = {
        "1. s_partial / s_raw": f"{frac:.3f}",
        "2א. הפרש, מנוע חופשי": f"{rows[0]['wins']:+.2f}",
        "2ב. הפרש, מנוע מאולץ": f"{rows[1]['wins']:+.2f}",
        "3. רוחב רצועת ההפרש": f"{rows[1]['width']:.2f}",
        "4. רוחב רצועת הרמה": f"{lvl_w:.2f}",
    }
    for kk, (a, c) in PRED.items():
        print(f"  {kk:<26}{a:>14}{c:>14}{actual[kk]:>14}")

    out = pd.DataFrame(rows)
    out.to_csv(PROCESSED_DIR / "wins_conversion.csv", index=False)
    print(f"\n  נשמר: {PROCESSED_DIR / 'wins_conversion.csv'}")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())