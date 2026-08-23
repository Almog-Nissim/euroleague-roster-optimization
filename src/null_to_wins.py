"""null_to_wins.py — יום 13. הפירוק מול מודל האפס, בניצחונות.

--------------------------------------------------------------------
למה זה נדרש
--------------------------------------------------------------------
`wins_conversion.py` מדווח +2.03 = **מנוע מאולץ מול המועדון**.
`project_state.md` סעיף 8א קבע ביום 8 שההשוואה הנכונה היא **מול
אקראי**, לא מול המועדון — כי מבנה האילוצים לבדו מייצר יתרון.

⛔ אבל 8א מיושן. הוא מצטט מכבי 2024: אקראי 109.1, rand_win 0.72.
   `why_100.py` תחת הקוד הנוכחי מחזיר 96.8 ו-0.21. הריצה שמאחורי
   8א קדמה ליישור המטרה ולתיקון האינדקס.

**התמונה המעודכנת, על 38:** אקראי גרוע מהמועדון ב-5.95 (חציון),
ומנצח אותו ב-9 מ-38 בלבד. ולכן +2.03 הוא **הערכת חסר** של תרומת
המודל, לא הערכת יתר.

--------------------------------------------------------------------
שלושת הפערים, ומה כל אחד מודד
--------------------------------------------------------------------
    אקראי − מועדון    מה שהמועדון יודע מעבר להגרלה עיוורת
    חופשי − אקראי     🔴 מה שהאופטימיזציה שווה. ההשוואה הנקייה.
    מאולץ − מועדון    הכותרת הנוכחית (+2.03)

⚠️ `q_cap` נמדד תחת אילוץ זהות הכדור; `q_rand` אינו. לכן
   `מאולץ − אקראי` מערבב שני אילוצים ומדווח כאן **בסוגריים
   בלבד**. ההשוואה הנקייה היא `חופשי − אקראי`.

--------------------------------------------------------------------
מקדם ההמרה
--------------------------------------------------------------------
כל שלושת הפערים הם השוואות **בתקציב מקובע** — אותו מועדון, אותו
כסף, סגל אחר. ולכן כולם דורשים את המקדם ה**חלקי**
(`wins ~ q + log(B)`), בדיוק כמו `W_gap`. שימוש בגולמי מייחס
להקצאה מה שהתקציב קנה.

--------------------------------------------------------------------
מנגנון אלמוג — נבדק, לא מונח
--------------------------------------------------------------------
טענתו: מועדון חזק מפסיד יותר מהגרלה אקראית, מועדון חלש מרוויח
ממנה. חלק מזה **מכני** — `rand_win` הוא P(אקראי > מועדון), אז
`q_club` גבוה מוריד אותו בהגדרה.

המבחן הלא-מכני: `q_rand` עצמו נע 90.3–110.3 ומשתנה עם התקציב.
לכן נבדק אם **הסטייה של המועדון מהניקוד שתקציבו מנבא** מסבירה
את `rand_win` מעבר ל-`q_club` הגולמי.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""
PRED = {
    "1. חופשי − אקראי, ניצחונות": ("+3.5..+5.0", "+3.0..+4.5"),
    "2. אקראי − מועדון, ניצחונות": ("",          "−0.8..−1.6"),
    "3. corr(שארית q, rand_win)":  ("",          "< −0.60"),
    "4. בקרה: מאולץ − מועדון":     ("+2.03",     "+2.03"),
}
BASE_HEADLINE = 2.03
N_BOOT = 4000
SEED = 13
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

SEP = "=" * 78
NAME2CODE = {
    "ברצלונה": "BAR", "צסקא מוסקבה": "CSK", "ריאל מדריד": "MAD",
    "חימקי": "KHI", "מילאנו": "MIL", "פנרבחצה": "ULK", "זניט": "DYR",
    "אנדולו אפס": "IST", 'מכבי ת"א': "TEL", "באיירן": "MUN",
    "באסקוניה": "BAS", "אולימפיאקוס": "OLY", "ולנסיה": "PAM",
    "פנאתינייקוס": "PAN", "ז'לגיריס": "ZAL", "ASVEL": "ASV",
    "אלבה ברלין": "BER", "הכוכב האדום": "RED", "מונקו": "MCO",
    "פרטיזן": "PAR", "וירטוס": "VIR", "פריז": "PRS",
    'הפועל ת"א': "HTA", "דובאי": "DUB",
}


def h(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def zin(df: pd.DataFrame, col: str) -> pd.Series:
    g = df.groupby("season")[col]
    return (df[col] - g.transform("mean")) / g.transform("std")


def load() -> pd.DataFrame:
    u = pd.read_csv(PROCESSED_DIR / "usage_constrained_results.csv")
    w = pd.read_csv(PROCESSED_DIR / "why_100_results.csv")
    d = u.merge(w[["season", "club", "q_rand", "rand_win", "n_ok",
                   "n_scoring", "cost_wasted"]],
                on=["season", "club"], how="inner")
    ts = pd.read_csv(PROCESSED_DIR / "team_season.csv")
    d = d.merge(ts[["season", "team", "wins", "team_games"]]
                .rename(columns={"team": "club"}),
                on=["season", "club"], how="inner")
    bud = pd.read_csv(PROCESSED_DIR / "club_budgets_gemini.csv")
    bud["club"] = bud.club.map(NAME2CODE)
    d = d.merge(bud[["season", "club", "net_eur"]].dropna(subset=["club"]),
                on=["season", "club"], how="inner").dropna(subset=["net_eur"])
    return d.reset_index(drop=True)


def coefs(d: pd.DataFrame):
    """מחזיר s_partial ומקדם ההמרה k. זהה ל-wins_conversion."""
    qz, wz = zin(d, "q_club"), zin(d, "wins")
    lbz = zin(d.assign(lb=np.log(d.net_eur)), "lb")
    X = sm.add_constant(pd.DataFrame({"qz": qz.values, "lbz": lbz.values}))
    m = sm.OLS(wz.values, X).fit()
    k = float((d.groupby("season").wins.transform("std")
               / d.groupby("season").q_club.transform("std")).mean())
    return float(m.params.iloc[1]), k


def main() -> int:
    rng = np.random.default_rng(SEED)
    print(SEP)
    print("null_to_wins — הפירוק מול מודל האפס, בניצחונות")
    print("תחזיות ננעלו. ראו ראש הקובץ.")
    print(SEP)

    d = load()
    print(f"\n  n = {len(d)}  ·  " + " · ".join(
        f"{s}: {c}" for s, c in d.groupby("season").size().items()))
    print(f"  הגרלות חוקיות n_ok: חציון {d.n_ok.median():.0f} · "
          f"מינימום {d.n_ok.min():.0f}")

    s_par, k = coefs(d)
    print(f"\n  מקדם חלקי s_partial = {s_par:.4f} · "
          f"ס\"ת ניצחונות/ניקוד k = {k:.4f}")

    d["g_rand_club"] = d.q_rand - d.q_club
    d["g_free_rand"] = d.q_free - d.q_rand
    d["g_cap_rand"] = d.q_cap - d.q_rand
    d["g_cap_club"] = d.q_cap - d.q_club
    d["g_free_club"] = d.q_free - d.q_club

    # ---------------------------------------------------- בקרת שחזור
    h("0. בקרת שחזור — הכותרת חייבת לחזור")
    ctrl = s_par * k * float(d.g_cap_club.median())
    hit = abs(ctrl - BASE_HEADLINE) <= 0.05
    print(f"  מאולץ − מועדון = {ctrl:+.2f}  (צפוי {BASE_HEADLINE:+.2f})  "
          f"{'✅' if hit else '❌'}")
    if not hit:
        print("\n  ❌ אם הכותרת לא חוזרת, שום מספר אחר כאן אינו תקף.")
        return 1

    # ---------------------------------------------------- הפערים
    h("1. שלושת הפערים — ניקוד וניצחונות")

    def boot(col):
        out, n = [], len(d)
        for _ in range(N_BOOT):
            i = rng.integers(0, n, n)
            s = d.iloc[i].reset_index(drop=True)
            if s.season.nunique() < 2:
                continue
            try:
                sp, kk = coefs(s)
                out.append(sp * kk * float(s[col].median()))
            except Exception:
                continue
        return np.array(out)

    rows = []
    plan = [("אקראי − מועדון", "g_rand_club", ""),
            ("🔴 חופשי − אקראי", "g_free_rand", "ההשוואה הנקייה"),
            ("(מאולץ − אקראי)", "g_cap_rand", "⚠️ מערבב אילוצים"),
            ("מאולץ − מועדון", "g_cap_club", "הכותרת הנוכחית"),
            ("חופשי − מועדון", "g_free_club", "")]
    print(f"  {'פער':<20}{'ניקוד':>9}{'ניצחונות':>11}"
          f"{'CI95':>22}   הערה")
    for nm, col, note in plan:
        pt = s_par * k * float(d[col].median())
        bs = boot(col)
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print(f"  {nm:<20}{d[col].median():>9.2f}{pt:>+11.2f}"
              f"   [{lo:+.2f}, {hi:+.2f}]  {note}")
        rows.append(dict(gap=nm, pts=float(d[col].median()), wins=pt,
                         lo=lo, hi=hi, width=hi - lo))

    add = rows[0]["wins"] + rows[1]["wins"]
    print(f"\n  בדיקת אדיטיביות: ({rows[0]['wins']:+.2f}) + "
          f"({rows[1]['wins']:+.2f}) = {add:+.2f}  מול "
          f"חופשי−מועדון {rows[4]['wins']:+.2f}")
    print("  ⚠️ חציונים אינם אדיטיביים. פער קטן כאן צפוי ואינו באג.")

    # ---------------------------------------------------- המנגנון
    h("2. מנגנון אלמוג — חזק מפסיד מאקראי, חלש מרוויח")
    d["lb"] = np.log(d.net_eur)
    mb = sm.OLS(d.q_club, sm.add_constant(
        pd.DataFrame({"lb": d.lb.values,
                      "s25": (d.season == 2025).astype(float).values}))).fit()
    d["q_resid"] = d.q_club - mb.fittedvalues
    print(f"  q_club ~ log(B) + עונה:  R² = {mb.rsquared:.3f}")
    print(f"\n  corr(q_club גולמי , rand_win)   = "
          f"{d.q_club.corr(d.rand_win):+.3f}   (חלקית מכני)")
    print(f"  corr(שארית q      , rand_win)   = "
          f"{d.q_resid.corr(d.rand_win):+.3f}   ← המבחן")
    print(f"  corr(q_rand       , rand_win)   = "
          f"{d.q_rand.corr(d.rand_win):+.3f}")
    m2 = sm.OLS(d.rand_win, sm.add_constant(
        d[["q_resid", "lb"]])).fit()
    print(f"\n  rand_win ~ שארית_q + log(B):  R² = {m2.rsquared:.3f}")
    for c in ("q_resid", "lb"):
        print(f"    {c:<10} β={float(m2.params[c]):+.5f}  "
              f"p={float(m2.pvalues[c]):.4f}")
    print(f"\n  יתרון המנוע על אקראי, לפי חצאי המדגם:")
    med = d.q_resid.median()
    for lbl, sub in [("מועדונים מעל הצפוי", d[d.q_resid > med]),
                     ("מועדונים מתחת לצפוי", d[d.q_resid <= med])]:
        print(f"    {lbl:<22} n={len(sub):<3} "
              f"חופשי−אקראי {sub.g_free_rand.median():>6.2f} נק' · "
              f"rand_win {sub.rand_win.median():.2f}")

    # ---------------------------------------------------- הכסף המבוזבז
    h("3. המספר שלא צריך יחידות LP")
    print(f"  שחקנים מנקדים בסגל המועדון: חציון {d.n_scoring.median():.0f}")
    if "cost_wasted" in d:
        print(f"  חלק התקציב על שחקנים שאינם מנקדים: "
              f"חציון {d.cost_wasted.median():.1%}")
        print(f"    ובאירו נטו: חציון "
              f"{(d.cost_wasted * d.net_eur).median():.2f}M€ לעונה")

    # ---------------------------------------------------- תחזיות
    h("4. לוח התחזיות")
    actual = {
        "1. חופשי − אקראי, ניצחונות": f"{rows[1]['wins']:+.2f}",
        "2. אקראי − מועדון, ניצחונות": f"{rows[0]['wins']:+.2f}",
        "3. corr(שארית q, rand_win)": f"{d.q_resid.corr(d.rand_win):+.3f}",
        "4. בקרה: מאולץ − מועדון": f"{ctrl:+.2f}",
    }
    print(f"  {'מבחן':<30}{'אלמוג':>14}{'קלוד':>14}{'בפועל':>12}")
    for kk, (a, c) in PRED.items():
        print(f"  {kk:<30}{a:>14}{c:>14}{actual[kk]:>12}")

    pd.DataFrame(rows).to_csv(PROCESSED_DIR / "null_to_wins.csv", index=False)
    print(f"\n  נשמר: null_to_wins.csv")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())