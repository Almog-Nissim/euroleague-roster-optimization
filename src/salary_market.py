"""
salary_market.py  (Day 9)
-------------------------
עקומת המחיר של **שוק היורוליג**, ולא של מועדון בודד.

--------------------------------------------------------------------
למה זה נדרש
--------------------------------------------------------------------
`cost_reality` אמד את העקומה על ארבעה מועדונים בלבד, ומצא פיזור
עצום בין מועדונים:

    HTA  β₁=+0.263    TEL  β₁=+0.259
    PAN  β₁=+0.161    OLY  β₁=+0.084

הישראליות תלולות, היווניות שטוחות. עם ארבע תצפיות-מועדון אין
דרך לדעת אם זו שונות אמיתית או רעש — והמספר המצרפי (0.144)
נשלט על ידי מי שיש לו הכי הרבה שורות.

`salary_external_2025` מוסיף שכר מ-**15 מועדונים**, אבל ההצלבה
שלו הייתה לפי שם משפחה ולכן פסולה.

--------------------------------------------------------------------
ההצלבה — אחרי אימות אלמוג
--------------------------------------------------------------------
הצלבה לפי **שם מלא** (פרטי + משפחה, מנורמל): 55 מתוך 66.

ארבעה נסגרו ידנית, אושרו על ידי אלמוג — הבדלי כתיב בלבד:

    Ish Wainwright  ->  13284  WAINRIGHT, ISH      (W אחת אצלנו)
    Edy Tavares     ->   5791  TAVARES, WALTER     (Walter "Edy")
    Wade Baldwin    ->   9863  BALDWIN IV, WADE
    Oshae Brissett  ->  14127  BRISSETT, O'SHAE J

שבעה נותרו ללא התאמה, **ואישרת שלא שיחקו ביורוליג ב-2025/26**:
ABRINES · IBAKA · BELINELLI · NAPIER · GIEDRAITIS(ROKAS) ·
LEE(PARIS) · ALEXANDER(CLIFF). כלומר אין חור בדאטה — הם פשוט
אינם בעונה. יורדים.

וחמישה שמות המשפחה הכפולים (BROWN, FALL, HERNANGOMEZ, JONES)
נפתרו מאליהם בהצלבת שם מלא — אלמוג אישר שהם שחקנים נפרדים.

⚠️ **ים מדר** מופיע פעמיים ולא הוכרע אם זו כפילות או שכר מפוצל.
   עד להכרעה נלקחת שורה אחת והדבר מדווח.

--------------------------------------------------------------------
המפרט — אפקטים קבועים למועדון
--------------------------------------------------------------------
    log(שכר_i) = α_מועדון + β₁·pir_lag_shrunk_i + β₂·el_seasons_i

הגרסה הקודמת השתמשה ב-log(שכר/ממוצע_המועדון). זה דורש שהמדגם
יכסה את **כל** הסגל, אחרת הממוצע מוטה. כאן יש מועדונים עם
2-3 שחקנים בלבד, ולכן α_מועדון (אפקט קבוע) הוא הכלי הנכון:
הוא סופג את הרמה, ו-β₁ נאמד **בתוך מועדון**.
"""

import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR
import roster_optimizer as ro

SEP = "=" * 88
TEST = 2025

# אושר ידנית על ידי אלמוג. הבדלי כתיב בלבד, לא הכרעה שלי.
ALIAS = {
    "ISHWAINWRIGHT": "13284",
    "EDYTAVARES": "5791",
    "WADEBALDWIN": "9863",
    "OSHAEBRISSETT": "14127",
}
# אושר: לא שיחקו ביורוליג 2025/26. לא חור בדאטה.
NOT_IN_SEASON = ["ABRINES", "IBAKA", "BELINELLI", "NAPIER",
                 "GIEDRAITIS", "LEE", "ALEXANDER"]

CLUBMAP = {
    "Hapoel Tel Aviv": "HTA", "Maccabi Tel Aviv": "TEL",
    "Panathinaikos": "PAN", "Olympiacos": "OLY", "Anadolu Efes": "IST",
    "Dubai BC": "DUB", "Real Madrid": "MAD", "Barcelona": "BAR",
    "Fenerbahce": "ULK", "Fenerbahçe": "ULK", "Bayern Munich": "MUN",
    "Virtus Bologna": "VIR", "Crvena Zvezda": "RED", "ASVEL": "ASV",
    "Zalgiris": "ZAL", "Žalgiris": "ZAL", "Valencia": "PAM",
    "Monaco": "MCO", "AS Monaco": "MCO", "Partizan": "PAR", "Paris Basketball": "PRS",
    "Baskonia": "BAS", "Milan": "MIL", "Olimpia Milano": "MIL",
}


def norm(x):
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z]", "", x.upper())


def load_market(ps, feat):
    """כל תצפיות השכר האמיתיות ל-2025, עם קוד שחקן מאומת."""
    out, notes = [], []

    a = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                    dtype={"player_code": str})
    a["salary_mid"] = pd.to_numeric(a.salary_mid, errors="coerce")
    a = a[(a.season == TEST) & a.player_code.notna() & a.salary_mid.notna()]
    out.append(a[["player_code", "club", "salary_mid"]]
               .rename(columns={"salary_mid": "salary"}).assign(src="anchor"))

    s = pd.read_csv(PROCESSED_DIR / "salary_external_2025.csv")
    s["lat"] = s.player.astype(str).str.split("/").str[0]
    s["key"] = s.lat.map(norm)
    p = ps[ps.season == TEST].copy()
    p["key"] = (p.player_name.str.split(",").str[1].fillna("")
                + p.player_name.str.split(",").str[0]).map(norm)
    p["pc"] = p.player_code.astype(str)
    kmap = p.drop_duplicates("key").set_index("key").pc
    s["player_code"] = s.key.map(kmap)
    s.loc[s.player_code.isna(), "player_code"] = \
        s.loc[s.player_code.isna(), "key"].map(ALIAS)
    unres = s[s.player_code.isna()]
    notes.append(f"שכר חיצוני: {int(s.player_code.notna().sum())}/{len(s)} "
                 f"הוצלבו. {len(unres)} נותרו — אושר שלא שיחקו ב-2025/26.")
    s = s[s.player_code.notna()].copy()
    s["club"] = s.club.map(CLUBMAP)
    if s.club.isna().any():
        notes.append("⚠️ שמות מועדון שלא מופו: "
                     + ", ".join(sorted(set(
                         pd.read_csv(PROCESSED_DIR /
                                     "salary_external_2025.csv").club)
                         - set(CLUBMAP))))
    s = s[s.club.notna()]
    out.append(s[["player_code", "club", "salary"]].assign(src="external"))

    d = pd.concat(out, ignore_index=True)
    d["salary"] = pd.to_numeric(d.salary, errors="coerce")
    dup = d[d.duplicated("player_code", keep=False)]
    if len(dup):
        nm = ps[ps.season == TEST].set_index(
            ps[ps.season == TEST].player_code.astype(str)).player_name
        notes.append(f"{dup.player_code.nunique()} שחקנים מופיעים גם "
                     "בעוגנים וגם בחיצוני. העוגן גובר (קוד מאומת).")
    d = (d.sort_values("src")             # anchor < external אלפביתית
         .drop_duplicates("player_code", keep="first"))

    F = feat[feat.season == TEST].drop_duplicates("player_code").copy()
    F["player_code"] = F.player_code.astype(str)
    d = d.merge(F[["player_code"] + ro.COST_FEATURES], on="player_code",
                how="inner").dropna(subset=ro.COST_FEATURES)
    d["log_sal"] = np.log(d.salary)
    return d, notes


def fit(d):
    """אפקטים קבועים למועדון. β₁ נאמד בתוך מועדון."""
    X = pd.get_dummies(d.club, prefix="c", drop_first=True).astype(float)
    X[ro.COST_FEATURES] = d[ro.COST_FEATURES].astype(float).values
    return sm.OLS(d.log_sal, sm.add_constant(X)).fit()


def main():
    print(SEP)
    print("salary_market — עקומת המחיר של השוק, לא של מועדון")
    print(SEP)
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    d, notes = load_market(ps, feat)
    for n in notes:
        print("  " + n)
    print(f"\n  סה\"כ {len(d)} תצפיות שכר מ-{d.club.nunique()} מועדונים "
          f"({int((d.src=='anchor').sum())} עוגנים, "
          f"{int((d.src=='external').sum())} חיצוניים)")
    print(f"  שכר: חציון {d.salary.median():,.0f}  "
          f"טווח {d.salary.min():,.0f}-{d.salary.max():,.0f}")
    print("\n  שחקנים לפי מועדון:")
    vc = d.club.value_counts()
    print("    " + "  ".join(f"{k}:{v}" for k, v in vc.items()))

    m = fit(d)
    print("\n" + SEP)
    print(f"  β₁ (תלילות המחיר באיכות) = {m.params.pir_lag_shrunk:+.3f}   "
          f"ר\"ס {m.bse.pir_lag_shrunk:.3f}   t={m.tvalues.pir_lag_shrunk:+.2f}")
    print(f"  β₂ (ותק)                 = {m.params.el_seasons:+.3f}   "
          f"t={m.tvalues.el_seasons:+.2f}")
    print(f"  R² = {m.rsquared:.3f}   n = {int(m.nobs)}")
    print(f"\n  לשם השוואה: המודל שלנו (כויל על מכבי) = 0.220")
    print(f"               ההרצה הקודמת (4 מועדונים)  = 0.144")
    r = float(m.params.pir_lag_shrunk) / 0.220
    print(f"  יחס מול המודל: {r:.2f}   "
          f"({'השוק תלול יותר' if r > 1 else 'השוק שטוח יותר'})")

    print("\n  β₁ לכל מועדון בנפרד (n>=6):")
    for club, g in d.groupby("club"):
        if len(g) < 6:
            continue
        mm = sm.OLS(g.log_sal, sm.add_constant(
            g[["pir_lag_shrunk"]].astype(float))).fit()
        print(f"    {club:<5} n={len(g):>3}  β₁={mm.params.pir_lag_shrunk:+.3f}"
              f"  (t={mm.tvalues.pir_lag_shrunk:+.2f})  "
              f"מרבי {g.salary.max():>10,.0f}")
    # --- הממצא: β₁ אינו פרמטר אחד. הוא נע עם תקציב המועדון. ---
    bud = {"TEL": 15.91, "HTA": 23.42, "MAD": 23.64, "PAN": 32.12,
           "OLY": 36.93}      # תקציב 2025 מ-league_backtest / club_budgets
    rows = []
    for club, g in d.groupby("club"):
        if len(g) < 6 or club not in bud:
            continue
        mm = sm.OLS(g.log_sal, sm.add_constant(
            g[["pir_lag_shrunk"]].astype(float))).fit()
        rows.append((club, bud[club], float(mm.params.pir_lag_shrunk)))
    if len(rows) >= 4:
        from scipy import stats as st
        b = np.array([r[1] for r in rows], float)
        y = np.array([r[2] for r in rows], float)
        r_, p_ = st.pearsonr(b, y)
        print(f"\n  תקציב מול תלילות (n={len(rows)}): r={r_:+.3f} (p={p_:.3f})")
        print("    " + "  ".join(f"{c}({bb:.0f}M):{yy:+.3f}"
                                 for c, bb, yy in sorted(rows, key=lambda t: t[1])))
        print("  שלילי = ככל שהמועדון עשיר יותר, עקומת השכר שלו שטוחה")
        print("  יותר. עני קונה כוכב אחד; עשיר קונה עומק.")

    d.to_csv(PROCESSED_DIR / "salary_market_2025.csv", index=False)
    print(f"\n  נשמר: salary_market_2025.csv")
    print(SEP)


if __name__ == "__main__":
    main()