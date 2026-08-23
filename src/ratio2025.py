"""ratio_2025.py — יום 13. למה 2024 ו-2025 שונות פי 4.2.

--------------------------------------------------------------------
מה נבדק
--------------------------------------------------------------------
היחס s_partial / s_raw נע 0.254 (2024) ↔ 0.799 (2025) על שני
מדגמים מלאים. זה החסם היחיד שנשאר על הכותרת.

שתי היפותזות, שני מנגנונים, שני מקורות — ולכן זה מבחן ולא הרצה:

  A (אלמוג)  שני מצטרפי 2025 — דובאי והפועל — עם תקציב גבוה
             וניקוד סגל שלא תואם, מנתקים את הקשר תקציב↔ניצחונות.
             חיזוי: הוצאתם תוריד את יחס 2025 **מתחת ל-0.55**.

  B (קלוד)   פיזור. ס"ת q_club הוא 9.83 ב-2025 מול 6.44 ב-2024.
             יותר שונות בניקוד משאירה פחות לתקציב להסביר, בלי
             קשר לזהות המועדונים. חיזוי: היחס יירד אך יעצור
             ב-**0.60–0.75**.

--------------------------------------------------------------------
🔴 המכשיר — למה זה לא רק "להוריד שניים ולראות"
--------------------------------------------------------------------
הורדת שני מועדונים תמיד תזיז את היחס. השאלה היא אם דובאי והפועל
מזיזים אותו **יותר מזוג אקראי**.

לכן נאמדות כל 190 החלופות C(20,2), ומדווח האחוזון של הזוג הנחזה
בתוך ההתפלגות. אם הוא באחוזון 40, התחזית ריקה גם אם היחס ירד.

זו אותה משפחה של "המנוע בוחר בדיוק 12 (12 הוא המינימום המותר)":
מבחן שלא יכול היה להראות אחרת אינו מבחן.

--------------------------------------------------------------------
ומרוץ סוסים ישיר בין A ל-B
--------------------------------------------------------------------
על 190 הזוגות נאמדת רגרסיה:

    ratio ~ drop_DUB + drop_HTA + sd_q(שנותר)

A חוזה שהאינדיקטורים נושאים את המידע. B חוזה ש-sd_q נושא אותו,
והאינדיקטורים מתאפסים בנוכחותו. שתיהן יכולות ליפול.

⚠️ האינדיקטורים ו-sd_q מתואמים מבנית — הוצאת חריג משנה את הפיזור.
   לכן מדווחים גם מקדמים בודדים וגם משותפים.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""
PRED = {
    "1. יחס 2025 בלי DUB+HTA":   ("< 0.55",      "0.60–0.75"),
    "2. אחוזון הזוג ב-190":       ("> 90",        "60–85"),
    "3. מקדם sd_q (מרוץ)":        ("לא מובהק",   "מובהק שלילי"),
    "4. n זוגות שיורדים מ-0.55":  ("< 20",        "20–60"),
}
BASELINE = {"ratio_2025": 0.799, "ratio_2024": 0.254, "ratio_all": 0.636}
# ====================================================================

import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from roster_optimizer import PROCESSED_DIR  # noqa: E402

PAIR = ("DUB", "HTA")
MIN_N = 12
TOL = 0.005
SEP = "=" * 76


def h(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def zdemean(df: pd.DataFrame, col: str) -> pd.Series:
    g = df.groupby("season")[col]
    return (df[col] - g.transform("mean")) / g.transform("std")


def load() -> pd.DataFrame:
    """זהה ל-wins_conversion.py. אם זה מתפצל — שני מיפויים בשקט."""
    d = pd.read_csv(PROCESSED_DIR / "usage_constrained_results.csv")
    ts = pd.read_csv(PROCESSED_DIR / "team_season.csv")
    d = d.merge(ts[["season", "team", "wins", "win_pct", "team_games"]]
                .rename(columns={"team": "club"}),
                on=["season", "club"], how="inner")

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
    bud["club"] = bud.club.map(NAME2CODE)
    d = d.merge(bud[["season", "club", "net_eur"]].dropna(subset=["club"]),
                on=["season", "club"], how="inner").dropna(subset=["net_eur"])
    return d


def fit(df: pd.DataFrame):
    """מחזיר s_raw, s_partial, יחס, β_תקציב, R². None אם מנוון."""
    if len(df) < MIN_N:
        return None
    x = df.copy()
    x["qz"] = zdemean(x, "q_club")
    x["wz"] = zdemean(x, "wins")
    x["lbz"] = zdemean(x.assign(lb=np.log(x.net_eur)), "lb")
    if x[["qz", "wz", "lbz"]].isna().any().any():
        return None
    m_raw = sm.OLS(x.wz, sm.add_constant(x[["qz"]])).fit()
    m_par = sm.OLS(x.wz, sm.add_constant(x[["qz", "lbz"]])).fit()
    s_raw = float(m_raw.params.iloc[1])
    s_par = float(m_par.params.iloc[1])
    if abs(s_raw) < 1e-6:
        return None
    return dict(n=len(x), s_raw=s_raw, s_partial=s_par,
                ratio=s_par / s_raw,
                b_budget=float(m_par.params.iloc[2]),
                p_budget=float(m_par.pvalues.iloc[2]),
                r2=float(m_par.rsquared),
                sd_q=float(x.q_club.std(ddof=1)),
                sd_lb=float(np.log(x.net_eur).std(ddof=1)))


def main() -> int:
    print(SEP)
    print("ratio_2025 — התחזית מול התפלגות ההשוואה")
    print("תחזיות ננעלו. ראו ראש הקובץ.")
    print(SEP)

    d = load()

    # ------------------------------------------------ בקרת שחזור
    h("0. בקרת שחזור — לפני כל מסקנה")
    ok = True
    for lbl, sub in [("מאוחד", d), ("2024", d[d.season == 2024]),
                     ("2025", d[d.season == 2025])]:
        r = fit(sub)
        key = {"מאוחד": "ratio_all", "2024": "ratio_2024",
               "2025": "ratio_2025"}[lbl]
        exp = BASELINE[key]
        hit = abs(r["ratio"] - exp) <= TOL
        ok &= hit
        print(f"  {lbl:<8} n={r['n']:<3} יחס {r['ratio']:.3f}  "
              f"(צפוי {exp:.3f})  {'✅' if hit else '❌'}")
    if not ok:
        print("\n  ❌ השחזור נכשל. עוצרים — אין טעם לבדוק תחזית")
        print("     על מספר שאינו המספר שנרשם ביום 12.")
        return 1
    print("\n  ✅ שלושת המספרים משוחזרים. ממשיכים.")

    s25 = d[d.season == 2025].copy()
    base = fit(s25)
    clubs = sorted(s25.club.unique())
    print(f"\n  מועדוני 2025 ({len(clubs)}): {' '.join(clubs)}")
    for c in PAIR:
        if c not in clubs:
            print(f"  ❌ {c} אינו במדגם 2025. התחזית אינה ניתנת לבדיקה.")
            return 1

    # ------------------------------------------------ הזוג הנחזה
    h("1. הזוג הנחזה — דובאי + הפועל")
    tgt = fit(s25[~s25.club.isin(PAIR)])
    print(f"  לפני:  n={base['n']}  יחס {base['ratio']:.3f}  "
          f"β_תקציב {base['b_budget']:+.3f} (p={base['p_budget']:.3f})  "
          f"sd_q {base['sd_q']:.2f}")
    print(f"  אחרי:  n={tgt['n']}  יחס {tgt['ratio']:.3f}  "
          f"β_תקציב {tgt['b_budget']:+.3f} (p={tgt['p_budget']:.3f})  "
          f"sd_q {tgt['sd_q']:.2f}")
    print(f"  Δיחס = {tgt['ratio'] - base['ratio']:+.3f}")

    # ------------------------------------------------ leave-one-out
    h("2. השפעה בודדת — מי באמת מזיז את היחס")
    loo = []
    for c in clubs:
        r = fit(s25[s25.club != c])
        if r:
            loo.append(dict(club=c, ratio=r["ratio"],
                            d_ratio=r["ratio"] - base["ratio"],
                            sd_q=r["sd_q"]))
    loo = pd.DataFrame(loo).sort_values("d_ratio")
    for _, r in loo.iterrows():
        mark = " ←" if r.club in PAIR else ""
        print(f"  בלי {r.club:<4} יחס {r.ratio:.3f}  "
              f"Δ {r.d_ratio:+.3f}{mark}")
    rank = {c: int((loo.club == c).idxmax()) for c in PAIR}
    pos = [int(loo.reset_index(drop=True).index[
        loo.reset_index(drop=True).club == c][0]) + 1 for c in PAIR]
    print(f"\n  דירוג הזוג בהשפעה מטה (1 = הכי מוריד): "
          f"{PAIR[0]}={pos[0]}/{len(loo)} · {PAIR[1]}={pos[1]}/{len(loo)}")

    # ------------------------------------------------ כל 190 הזוגות
    h("3. התפלגות ההשוואה — כל C(20,2) הזוגות")
    rows = []
    for a, b in combinations(clubs, 2):
        r = fit(s25[~s25.club.isin([a, b])])
        if r:
            rows.append(dict(a=a, b=b, ratio=r["ratio"], sd_q=r["sd_q"],
                             sd_lb=r["sd_lb"], b_budget=r["b_budget"],
                             drop_DUB=int(PAIR[0] in (a, b)),
                             drop_HTA=int(PAIR[1] in (a, b))))
    P = pd.DataFrame(rows)
    tv = tgt["ratio"]
    pct = float((P.ratio > tv).mean() * 100)
    print(f"  זוגות שנאמדו: {len(P)} מתוך 190")
    print(f"  יחס — חציון {P.ratio.median():.3f} · "
          f"טווח {P.ratio.min():.3f}..{P.ratio.max():.3f}")
    print(f"  אחוזוני 5/25/75/95: "
          + " · ".join(f"{np.percentile(P.ratio, q):.3f}"
                       for q in (5, 25, 75, 95)))
    print(f"\n  🔴 הזוג הנחזה ({tv:.3f}) נמצא באחוזון {100 - pct:.0f}")
    print(f"     כלומר {pct:.0f}% מהזוגות מורידים את היחס פחות ממנו.")
    n55 = int((P.ratio < 0.55).sum())
    print(f"  🔴 זוגות שמורידים מתחת ל-0.55: {n55} מתוך {len(P)} "
          f"({n55 / len(P):.0%})")
    print("\n  ⚠️ אם האחוזון קרוב ל-50, הזוג אינו מיוחד — הירידה היא")
    print("     תכונה של הורדת שתי תצפיות, לא של דובאי והפועל.")

    # ------------------------------------------------ מרוץ הסוסים
    h("4. מרוץ סוסים — זהות מול פיזור")
    P["sd_qz"] = (P.sd_q - P.sd_q.mean()) / P.sd_q.std(ddof=1)
    for nm, cols in [("A — זהות בלבד", ["drop_DUB", "drop_HTA"]),
                     ("B — פיזור בלבד", ["sd_qz"]),
                     ("משותף", ["drop_DUB", "drop_HTA", "sd_qz"])]:
        m = sm.OLS(P.ratio, sm.add_constant(P[cols])).fit()
        print(f"\n  {nm}   R²={m.rsquared:.3f}")
        for c in cols:
            print(f"    {c:<10} β={float(m.params[c]):+.4f}  "
                  f"p={float(m.pvalues[c]):.4f}")
    print("\n  ⚠️ המשתנים מתואמים מבנית. R² של 'משותף' מול השניים")
    print("     האחרים הוא מה שאומר אם נוסף מידע.")
    print(f"\n  מתאם (sd_q , יחס) = {P.ratio.corr(P.sd_q):+.3f}")
    print(f"  מתאם (sd_lb , יחס) = {P.ratio.corr(P.sd_lb):+.3f}")

    # ------------------------------------------------ תחזיות
    h("5. לוח התחזיות")
    actual = {
        "1. יחס 2025 בלי DUB+HTA": f"{tv:.3f}",
        "2. אחוזון הזוג ב-190": f"{100 - pct:.0f}",
        "3. מקדם sd_q (מרוץ)": f"{P.ratio.corr(P.sd_q):+.3f}",
        "4. n זוגות שיורדים מ-0.55": f"{n55}",
    }
    print(f"  {'מבחן':<28}{'אלמוג':>16}{'קלוד':>16}{'בפועל':>12}")
    for k, (a, c) in PRED.items():
        print(f"  {k:<28}{a:>16}{c:>16}{actual[k]:>12}")

    P.to_csv(PROCESSED_DIR / "ratio_2025_pairs.csv", index=False)
    loo.to_csv(PROCESSED_DIR / "ratio_2025_loo.csv", index=False)
    print(f"\n  נשמר: ratio_2025_pairs.csv ({len(P)}) · "
          f"ratio_2025_loo.csv ({len(loo)})")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())