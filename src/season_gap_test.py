"""season_gap_test.py — יום 13. האם פי 2.3 הוא הבדל או רעש.

--------------------------------------------------------------------
מה נבדק
--------------------------------------------------------------------
היחס s_partial / s_raw הוא 0.367 ב-2024 ו-0.837 ב-2025. שתי
היפותזות נשללו: פיזור התקציב (יום 12) ושני המצטרפים (ratio_2025).
אין היפותזה שלישית — ולכן השאלה עוברת מ"למה" ל"האם".

⚠️ ההבחנה שהמבחן הזה בנוי עליה:

    leave-two-out  מודד **רגישות** — כמה היחס זז כשמורידים שתיים.
                   190 השורות נגזרות מ-20 תצפיות וחופפות כמעט
                   לגמרי. זו אינה התפלגות דגימה, ו-p שנאמד עליה
                   אינו p. (זה בדיוק מה שלא רשמתי מראש ב-
                   ratio_2025.py, סעיף 4.)

    bootstrap      מודד **אי-ודאות דגימה** — רצועה סביב היחס.
    permutation    מודד **מובהקות ההפרש** — תחת אפס שאין הבדל
                   עונתי, כמה קל לקבל פער של 0.47 במקרה.

שלושתם מדווחים. רק השלישי עונה על השאלה.

--------------------------------------------------------------------
מבנה מבחן התמורות
--------------------------------------------------------------------
הנרמול נעשה **בתוך העונה האמיתית** ורק אחר כך תווית העונה
מעורבבת. אחרת הערבוב היה מוחק את מרכוז העונה, ומייצר אפס שמודד
גם את זה. 38 מועדונים, חלוקה אקראית ל-18/20, 5000 תמורות.

--------------------------------------------------------------------
שתי תוצאות, שתיהן סוגרות
--------------------------------------------------------------------
  p גבוה   → פי 2.3 הוא רעש דגימה. השאלה נסגרת, המגבלה נרשמת
             ב"מה המנוע לא יודע", ואין חוב פתוח לפני הפרונט.
  p נמוך   → ההבדל אמיתי. אין הסבר, אבל ידוע שיש מה להסביר,
             וזה נרשם כמגבלה מכומתת ולא כתעלומה.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""
PRED = {
    "1. חפיפת רצועות בוטסטרפ":  ("",  "כן"),
    "2. p (תמורות, דו-צדדי)":    ("",  "0.05–0.35"),
    "3. רוחב רצועת יחס 2024":    ("",  "> 0.50"),
    "4. 0.799 בטווח L2O של 2024": ("", "לא"),
}
BASELINE = {2024: 0.367, 2025: 0.837}   # season_heterogeneity, הגדרה נגזרת
N_BOOT = 4000
N_PERM = 5000
SEED = 13
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

SEP = "=" * 76
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


def load() -> pd.DataFrame:
    """⚠️ ההגדרה הנגזרת — qclub_3seasons, לא usage_constrained.
    שתי ההגדרות אינן נותנות אותו יחס (0.254 מול 0.367 ב-2024).
    כאן נבדק הפער שדווח בסעיף 5, ולכן זו ההגדרה הנכונה."""
    d = pd.read_csv(PROCESSED_DIR / "qclub_3seasons.csv")
    ts = pd.read_csv(PROCESSED_DIR / "team_season.csv")
    d = d.merge(ts[["season", "team", "wins"]].rename(
        columns={"team": "club"}), on=["season", "club"], how="inner")
    bud = pd.read_csv(PROCESSED_DIR / "club_budgets_gemini.csv")
    bud["club"] = bud.club.map(NAME2CODE)
    d = d.merge(bud[["season", "club", "net_eur"]].dropna(subset=["club"]),
                on=["season", "club"], how="inner").dropna(subset=["net_eur"])
    return d[d.season.isin([2024, 2025])].reset_index(drop=True)


def ratio_from_z(qz, wz, lbz):
    """מקבל וקטורים מנורמלים. מחזיר s_raw, s_par, יחס."""
    X1 = sm.add_constant(pd.DataFrame({"qz": qz}))
    X2 = sm.add_constant(pd.DataFrame({"qz": qz, "lbz": lbz}))
    s_raw = float(sm.OLS(wz, X1).fit().params.iloc[1])
    s_par = float(sm.OLS(wz, X2).fit().params.iloc[1])
    if abs(s_raw) < 1e-8:
        return None
    return s_raw, s_par, s_par / s_raw


def zcols(df):
    """נרמול בתוך עונה — לפני כל ערבוב."""
    out = df.copy()
    out["lb"] = np.log(out.net_eur)
    for a, b in [("q_club", "qz"), ("wins", "wz"), ("lb", "lbz")]:
        g = out.groupby("season")[a]
        out[b] = (out[a] - g.transform("mean")) / g.transform("std")
    return out


def fit_sub(df):
    r = ratio_from_z(df.qz.values, df.wz.values, df.lbz.values)
    return None if r is None else r[2]


def main() -> int:
    rng = np.random.default_rng(SEED)
    print(SEP)
    print("season_gap_test — 0.367 מול 0.837: הבדל או רעש")
    print("תחזיות ננעלו. ראו ראש הקובץ.")
    print(SEP)

    d = zcols(load())

    # ------------------------------------------------ בקרת שחזור
    h("0. בקרת שחזור")
    ok = True
    obs = {}
    for s in (2024, 2025):
        r = fit_sub(d[d.season == s])
        obs[s] = r
        hit = abs(r - BASELINE[s]) <= 0.005
        ok &= hit
        print(f"  {s}  n={int((d.season == s).sum()):<3} יחס {r:.3f}  "
              f"(צפוי {BASELINE[s]:.3f})  {'✅' if hit else '❌'}")
    if not ok:
        print("\n  ❌ השחזור נכשל — עוצרים.")
        return 1
    gap = obs[2025] - obs[2024]
    print(f"\n  ✅ הפער הנצפה: {gap:+.3f}  (פי {obs[2025]/obs[2024]:.1f})")

    # ------------------------------------------------ leave-two-out
    h("1. רגישות — leave-two-out בשתי העונות")
    l2o = {}
    for s in (2024, 2025):
        g = d[d.season == s]
        cl = sorted(g.club.unique())
        vals = [fit_sub(g[~g.club.isin(p)]) for p in combinations(cl, 2)]
        vals = np.array([v for v in vals if v is not None])
        l2o[s] = vals
        print(f"  {s}  זוגות {len(vals):>3}  טווח "
              f"{vals.min():.3f}..{vals.max():.3f}  חציון {np.median(vals):.3f}")
    lo24, hi24 = l2o[2024].min(), l2o[2024].max()
    inside = lo24 <= obs[2025] <= hi24
    overlap_l2o = (min(hi24, l2o[2025].max())
                   - max(lo24, l2o[2025].min()))
    print(f"\n  0.799/0.837 בתוך טווח L2O של 2024? "
          f"{'כן' if inside else 'לא'}")
    print(f"  חפיפת הטווחים: {overlap_l2o:+.3f} "
          f"({'חופפים' if overlap_l2o > 0 else 'מנותקים'})")
    print("\n  ⚠️ זו רגישות, לא אי-ודאות. אין להסיק מכאן מובהקות.")

    # ------------------------------------------------ bootstrap
    h("2. אי-ודאות דגימה — bootstrap בתוך עונה")
    boots = {}
    for s in (2024, 2025):
        g = d[d.season == s].reset_index(drop=True)
        n = len(g)
        out = []
        for _ in range(N_BOOT):
            i = rng.integers(0, n, n)
            v = fit_sub(g.iloc[i].reset_index(drop=True))
            if v is not None and np.isfinite(v):
                out.append(v)
        a = np.array(out)
        boots[s] = a
        lo, hi = np.percentile(a, [2.5, 97.5])
        print(f"  {s}  חציון {np.median(a):.3f}  "
              f"CI95 [{lo:.3f}, {hi:.3f}]  רוחב {hi-lo:.3f}  "
              f"(נאמדו {len(a)})")
    c24 = np.percentile(boots[2024], [2.5, 97.5])
    c25 = np.percentile(boots[2025], [2.5, 97.5])
    ov = min(c24[1], c25[1]) - max(c24[0], c25[0])
    print(f"\n  חפיפת הרצועות: {ov:+.3f}  "
          f"({'חופפות' if ov > 0 else 'מנותקות'})")
    print("  ⚠️ היחס הוא מנה של מקדמים — הזנב כבד כש-s_raw קטן.")

    # ------------------------------------------------ permutation
    h("3. מבחן תמורות — האם ההפרש מובהק")
    lab = d.season.values.copy()
    n24 = int((lab == 2024).sum())
    null = []
    for _ in range(N_PERM):
        p = rng.permutation(len(d))
        a, b = p[:n24], p[n24:]
        ra = fit_sub(d.iloc[a])
        rb = fit_sub(d.iloc[b])
        if ra is None or rb is None:
            continue
        if np.isfinite(ra) and np.isfinite(rb):
            null.append(rb - ra)
    null = np.array(null)
    pval = float((np.abs(null) >= abs(gap)).mean())
    print(f"  תמורות שנאמדו: {len(null)}")
    print(f"  אפס — Δיחס: חציון {np.median(null):+.3f}  "
          f"ס\"ת {null.std(ddof=1):.3f}")
    print(f"  אחוזוני 2.5/97.5: {np.percentile(null, 2.5):+.3f} · "
          f"{np.percentile(null, 97.5):+.3f}")
    print(f"\n  🔴 הפער הנצפה {gap:+.3f}  →  p = {pval:.4f} (דו-צדדי)")
    if pval >= 0.05:
        print("\n  ⇒ אין עדות להבדל עונתי. פי 2.3 עקבי עם רעש דגימה")
        print("    על 18 ו-20 תצפיות. השאלה נסגרת כמגבלה.")
    else:
        print("\n  ⇒ ההבדל אינו מוסבר ברעש. אין היפותזה מסבירה,")
        print("    אבל הוא מכומת ונרשם ככזה.")

    # ------------------------------------------------ תחזיות
    h("4. לוח התחזיות")
    actual = {
        "1. חפיפת רצועות בוטסטרפ": "כן" if ov > 0 else "לא",
        "2. p (תמורות, דו-צדדי)": f"{pval:.4f}",
        "3. רוחב רצועת יחס 2024": f"{c24[1]-c24[0]:.3f}",
        "4. 0.799 בטווח L2O של 2024": "כן" if inside else "לא",
    }
    print(f"  {'מבחן':<30}{'אלמוג':>12}{'קלוד':>14}{'בפועל':>12}")
    for k, (a, c) in PRED.items():
        print(f"  {k:<30}{a:>12}{c:>14}{actual[k]:>12}")

    pd.DataFrame(dict(
        metric=["ratio_2024", "ratio_2025", "gap", "p_perm",
                "ci_lo_2024", "ci_hi_2024", "ci_lo_2025", "ci_hi_2025"],
        value=[obs[2024], obs[2025], gap, pval,
               c24[0], c24[1], c25[0], c25[1]],
    )).to_csv(PROCESSED_DIR / "season_gap_test.csv", index=False)
    print(f"\n  נשמר: season_gap_test.csv")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())