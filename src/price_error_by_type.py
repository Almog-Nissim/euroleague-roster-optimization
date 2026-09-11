"""price_error_by_type.py — שלב 1ג'. האם המודל מתמחר כוכבים בחסר,
ואם כן — האם המנוע מנצל את זה.

--------------------------------------------------------------------
למה זה ההסבר האחרון ששרד
--------------------------------------------------------------------
הכותרת קפצה מ-2.03 ל-4.26 ניצחונות אחרי הריפיט. `curse_selection`
הראה שאין הטיית בחירה בתפוקה (‎-2.8% ישן, ‎-0.5% חדש), ולכן קללת
המנצח אינה ההסבר. נשאר ערוץ אחד:

    תקציב המועדון מחושב לפי מחירי המודל של הסגל שהוא העמיד.
    אם המודל מתמחר כוכבים נמוך מדי ביחס לשוק, קבוצה עתירת
    כוכבים מקבלת תקציב מודל קטן, והמנוע קונה כוכבים בהנחה
    שאף מועדון אמיתי לא מקבל. ארביטראז' משגיאה, לא הקצאה טובה.

--------------------------------------------------------------------
שני מדדים, ובכוונה
--------------------------------------------------------------------
    שגיאה_M€  = מחיר_מודל(M€) − שכר_אמיתי(M€)
    שגיאה_log = log(מחיר_מודל) − log(שכר_אמיתי)

⚠️ שיפוע ב-M€ **תלוי בבחירת הסקלה**: המפרט הישן מתמחר ביחידות
   יחס לממוצע סגל מכבי, והחדש ביחידות מאגר, וכל המרה ליורו היא
   כפל בסקלר. בלוגים סקלר משנה **רק את החותך**, ולכן השיפוע
   בלוגים בר-השוואה בין המפרטים והוא המדד הקובע. ה-M€ מדווח כי
   עליו ננעלו החיזויים.

--------------------------------------------------------------------
שני מדגמים
--------------------------------------------------------------------
נקי    HTA · OLY · BAS — אף שורת שכר שלהם לא נכנסה לכיול.
מלא    כל מי שיש לו שכר 2025 ידוע. ⚠️ מכיל את מועדוני הכיול,
       ששם השגיאה מוקטנת בבנייה. משמש **רק** למבחן הבחירה,
       שדורש חפיפה עם הסגלים שהמנוע קנה.

--------------------------------------------------------------------
חיזויים שננעלו
--------------------------------------------------------------------
    שיפוע M€, ישן           קלוד +0.05..+0.20
    שיפוע M€, חדש           קלוד -0.15..+0.05   אלמוג -0.05..+0.05
    הנבחרים מול המאגר       קלוד בחסר >= 0.2M€  אלמוג בחסר 0.1..0.4M€
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
from paths import PROCESSED_DIR  # noqa: E402
from league_backtest import build_pool  # noqa: E402
from optimise_consistent import optimise_v2  # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER  # noqa: E402
from display_money_check import real_salaries  # noqa: E402
import salary_market as smk  # noqa: E402

SEASON, TRAIN_MAX = 2025, 2024
OOS_CLUBS = ["HTA", "OLY", "BAS"]
B_GRID = np.arange(8.0, 40.5, 0.5)
SEP = "=" * 78


def eur_scale(info) -> float:
    """מכפיל שממיר יחידת ציר ל-M€, לפי המפרט שרץ."""
    if ob.COST_SPEC == "market":
        return float(info.get("cost_scale", 1.0))
    # מפרט ישן: cost הוא יחס לשכר הממוצע במועדון הכיול.
    a = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv")
    cal = a[(a.usage == "calibrate") & (a.season <= TRAIN_MAX)]
    g = cal.groupby(["club", "season"]).salary_mid.mean()
    return float(g.mean() / 1e6)


def club_of(ps: pd.DataFrame) -> pd.Series:
    s = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                    dtype={"player_code": str})
    s = s[s.season == SEASON]
    m = dict(zip(s.player_code.astype(str), s.club))
    e = pd.read_csv(PROCESSED_DIR / "salary_external_2025.csv")
    e = e[e.yr == SEASON].copy()
    e["key"] = e.player.astype(str).str.split("/").str[0].map(smk.norm)
    p = ps.dropna(subset=["player_name"]).copy()
    p["key"] = (p.player_name.str.split(",").str[1].fillna("")
                + p.player_name.str.split(",").str[0]).map(smk.norm)
    kmap = p.drop_duplicates("key").set_index("key").player_code.astype(str)
    e["code"] = e.key.map(kmap)
    e.loc[e.code.isna(), "code"] = e.loc[e.code.isna(), "key"].map(smk.ALIAS)
    for c, cl in zip(e.code, e.club.map(smk.CLUBMAP)):
        if pd.notna(c):
            m.setdefault(str(c), cl)
    return pd.Series(m)


def slope(d, ycol):
    X = sm.add_constant(d[ro.COST_FEATURES[0]].astype(float))
    r = sm.OLS(d[ycol].astype(float), X).fit()
    return (float(r.params[ro.COST_FEATURES[0]]),
            float(r.bse[ro.COST_FEATURES[0]]),
            float(r.tvalues[ro.COST_FEATURES[0]]),
            float(r.pvalues[ro.COST_FEATURES[0]]))


def main() -> int:
    print(SEP)
    print(f"price_error_by_type — שלב 1ג' · מפרט {ob.COST_SPEC}")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    cand, info = build_pool(SEASON, TRAIN_MAX, feat, anch, pos, ps)
    cand = cand.reset_index(drop=True)
    scale = eur_scale(info)
    print(f"  מכפיל ליחידת M€: {scale:.4f} · מאגר {len(cand)}")

    real = real_salaries()
    cand["code"] = cand.player_code.astype(str)
    d = cand[cand.code.isin(real.index)].copy()
    d["real"] = d.code.map(real.real)
    d["model"] = d.cost * scale
    d["err_m"] = d.model - d.real
    d["err_log"] = np.log(d.model) - np.log(d.real)
    d["club"] = d.code.map(club_of(ps))

    # מי נבחר אי-פעם לאורך הסליידר
    chosen = set()
    for B in B_GRID:
        sel, _ = optimise_v2(cand, float(B), MIN_LEGAL_ROSTER)
        if sel is not None:
            chosen |= set(cand[sel].code)
    d["chosen"] = d.code.isin(chosen)

    print(f"\n  שכר 2025 ידוע ל-{len(d)} משחקני המאגר · "
          f"מהם נבחרים {int(d.chosen.sum())}")

    oos = d[d.club.isin(OOS_CLUBS)]
    print(f"\n{SEP}\n1. שיפוע השגיאה מול איכות — מדגם נקי "
          f"(HTA/OLY/BAS, n={len(oos)})\n{SEP}")
    res = {}
    for lbl, col in [("M€ ליחידת pir", "err_m"), ("log ליחידת pir", "err_log")]:
        b, se, t, p = slope(oos, col)
        res[col] = b
        print(f"  {lbl:<18} {b:+.4f}  (ר\"ס {se:.4f} · t={t:+.2f} · "
              f"p={p:.3f})")
    print(f"  הטיה חציונית: {oos.err_m.median():+.2f}M€ · "
          f"{oos.err_log.median():+.3f} log")

    print(f"\n{SEP}\n2. אותו שיפוע, מדגם מלא (n={len(d)})\n{SEP}")
    print("  ⚠️ מכיל מועדוני כיול — השגיאה שם מוקטנת בבנייה.")
    for lbl, col in [("M€", "err_m"), ("log", "err_log")]:
        b, se, t, p = slope(d, col)
        print(f"  {lbl:<5} {b:+.4f}  (t={t:+.2f} · p={p:.3f})")

    print(f"\n{SEP}\n3. מבחן הבחירה — הנבחרים מול השאר\n{SEP}")
    print(f"  {'קבוצה':<10}{'n':>4}{'שגיאה M€ חציון':>18}"
          f"{'שגיאה log':>13}{'pir חציון':>12}")
    for lbl, g in [("נבחרו", d[d.chosen]), ("לא נבחרו", d[~d.chosen])]:
        print(f"  {lbl:<10}{len(g):>4}{g.err_m.median():>+18.3f}"
              f"{g.err_log.median():>+13.3f}"
              f"{g[ro.COST_FEATURES[0]].median():>12.2f}")
    gap_m = float(d[d.chosen].err_m.median() - d[~d.chosen].err_m.median())
    gap_l = float(d[d.chosen].err_log.median() - d[~d.chosen].err_log.median())
    print(f"\n  פער: {gap_m:+.3f}M€ · {gap_l:+.3f} log")
    print("  שלילי = הנבחרים מתומחרים בחסר יותר = ארביטראז'.")

    out = PROCESSED_DIR / f"price_error_{ob.COST_SPEC}.csv"
    d.to_csv(out, index=False)
    print(f"\n  נשמר: {out.name}\n{SEP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
