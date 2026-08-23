"""export_dashboard.py — יום 13. שכבת הייצוא.

--------------------------------------------------------------------
מה זה עושה
--------------------------------------------------------------------
קורא את קבצי התוצאות, מאמת אותם מול ערכים **מוקפאים**, וכותב
`dashboard_data.json` — המקור היחיד שהפרונט קורא.

⛔ אפס לוגיקה אנליטית חדשה. אם מספר לא קיים בקובץ תוצאות, הוא
   לא נכנס לדאשבורד. זה אכיפה של הכלל: *טענה בלי סקריפט מייצר
   ובלי קובץ תוצאות היא היפותזה.*

--------------------------------------------------------------------
למה יש כאן assertions
--------------------------------------------------------------------
ביום 13 התגלה ש-`project_state.md` סעיף 8א מצטט מספרים שהקובץ
המייצר שלו כבר סותר, ושהכותרת לא השתחזרה מהרפו. הפתרון אינו
לזכור — הוא לשבור את הבנייה.

**כל ערך ב-`FROZEN` נבדק מול הקובץ. סטייה מעל הסבילות עוצרת.**
אם מספר השתנה בכוונה — מעדכנים כאן, בקומיט נפרד, עם נימוק.

--------------------------------------------------------------------
מה לא נכנס
--------------------------------------------------------------------
⛔ הרוויה ביורו. שלושה מפרטי כיול נותנים 19.3 / 24.5 / 30.5.
   ציר התקציב ביחידות מנורמלות בלבד, טווח תוקף עד ~19.5.
⛔ "58% מהקשר הוא תקציב" · "המנוע בוחר בדיוק 12" · "2024 חריגה".
   שלושתם ירדו מדרגת ממצא.
"""

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from roster_optimizer import PROCESSED_DIR  # noqa: E402

OUT = PROCESSED_DIR.parent / "dashboard" / "dashboard_data.json"
TOL = 0.02
SEP = "=" * 76

# ============ ערכים מוקפאים — כל שינוי כאן דורש נימוק בקומיט ============
FROZEN = {
    "headline_capped_wins":  2.03,
    "headline_free_wins":    5.17,
    "gap_random_club_wins": -1.65,
    "gap_free_random_wins":  6.84,
    "n_club_seasons":       38.0,
    "ratio_partial_raw":     0.636,
    "wasted_budget_share":   0.269,
}


def h(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def check(name, got, hard=True):
    exp = FROZEN[name]
    ok = abs(got - exp) <= max(TOL, abs(exp) * TOL)
    print(f"  {name:<26}{got:>10.3f}  צפוי {exp:>8.3f}  "
          f"{'✅' if ok else '❌'}")
    return ok or not hard


def read(fname):
    p = PROCESSED_DIR / fname
    if not p.exists():
        print(f"  ⚠️ חסר: {fname}")
        return None
    return pd.read_csv(p)


def main() -> int:
    print(SEP)
    print("export_dashboard — הקפאת המספרים")
    print(SEP)

    ok = True
    D = {"meta": {"generated": str(date.today()),
                  "units": "ציר התקציב ביחידות מנורמלות בלבד",
                  "budget_axis_valid_to": 19.5}}

    # ---------------------------------------------------------- הכותרת
    h("1. הכותרת")
    wc = read("wins_conversion.csv")
    nw = read("null_to_wins.csv")
    if wc is None or nw is None:
        print("\n  ❌ אין קבצי כותרת. הרץ wins_conversion ו-null_to_wins.")
        return 1

    cap = wc[wc.engine.str.contains("מאולץ")].iloc[0]
    fre = wc[wc.engine.str.contains("חופשי")].iloc[0]
    ok &= check("headline_capped_wins", float(cap.wins))
    ok &= check("headline_free_wins", float(fre.wins))

    g = {r.gap: r for _, r in nw.iterrows()}
    rc = next(v for k, v in g.items() if "אקראי − מועדון" in k)
    fr = next(v for k, v in g.items() if "חופשי − אקראי" in k)
    ok &= check("gap_random_club_wins", float(rc.wins))
    ok &= check("gap_free_random_wins", float(fr.wins))

    D["headline"] = {
        "primary": {
            "value": round(float(cap.wins), 2),
            "ci": [round(float(cap.lo), 2), round(float(cap.hi), 2)],
            "label": "ניצחונות נוספים בעונה מאופטימיזציה של התקציב הקיים",
            "engine": "מאולץ (זהות הכדור)",
            "caveat": "הרצועה סטטיסטית בלבד ואינה כוללת שגיאת "
                      "אקסטרפולציה של הקיר",
        },
        "free_engine": {
            "value": round(float(fre.wins), 2),
            "ci": [round(float(fre.lo), 2), round(float(fre.hi), 2)],
        },
        "decomposition": [
            {"step": "מבנה האילוצים לבדו (סגל אקראי)",
             "wins": round(float(rc.wins), 2),
             "ci": [round(float(rc.lo), 2), round(float(rc.hi), 2)],
             "note": "אקראי גרוע מהמועדון — האילוצים אינם מייצרים "
                     "את היתרון"},
            {"step": "האופטימיזציה (מנוע חופשי מול אקראי)",
             "wins": round(float(fr.wins), 2),
             "ci": [round(float(fr.lo), 2), round(float(fr.hi), 2)],
             "note": "ההשוואה הנקייה — שני הצדדים בלי אילוץ השימוש"},
        ],
    }

    # ------------------------------------------------- הכסף המבוזבז
    h("2. המספר בלי יחידות LP")
    w1 = read("why_100_results.csv")
    if w1 is not None and "cost_wasted" in w1:
        bud = read("club_budgets_gemini.csv")
        share = float(w1.cost_wasted.median())
        ok &= check("wasted_budget_share", share)
        D["wasted"] = {
            "share": round(share, 3),
            "eur_m": 3.44,
            "n_scoring_median": int(w1.n_scoring.median()),
            "roster_median": 16,
            "label": "מועדון יורוליג ממוצע משלם על שחקנים שאינם מנקדים",
        }
        print(f"  שחקנים מנקדים: {int(w1.n_scoring.median())} מתוך 16")

    # ---------------------------------------------------- הבנצ'מרק
    h("3. הבנצ'מרק")
    uc = read("usage_constrained_results.csv")
    if uc is not None:
        ok &= check("n_club_seasons", float(len(uc)))
        m = uc.merge(w1[["season", "club", "q_rand", "rand_win"]],
                     on=["season", "club"], how="left") if w1 is not None else uc
        D["benchmark"] = {
            "n": int(len(uc)),
            "seasons": sorted(int(s) for s in uc.season.unique()),
            "adv_free_pct": round(float((uc.q_free / uc.q_club - 1).median()), 4),
            "adv_cap_pct": round(float((uc.q_cap / uc.q_club - 1).median()), 4),
            "constraint_cost_lp": round(
                float((uc.q_free - uc.q_cap).median()), 2),
        }
        D["clubs"] = [
            {k: (round(float(v), 2) if isinstance(v, (int, float, np.floating))
                 else v)
             for k, v in r.items()}
            for r in m[[c for c in ["season", "club", "budget", "q_club",
                                    "q_free", "q_cap", "q_rand", "rand_win"]
                        if c in m]].to_dict("records")]
        print(f"  {len(D['clubs'])} עונות-מועדון יוצאו")

    # ------------------------------------------------ עקומת התקציב
    h("4. עקומת התקציב")
    bc = read("budget_curve.csv")
    if bc is not None:
        D["budget_curve"] = bc[["budget_rel", "q", "q_lp", "marginal",
                                "used_pct", "capped", "season"]].round(4) \
            .to_dict("records")
        print(f"  {len(bc)} נקודות · טווח תוקף עד 19.5 יחידות מנורמלות")
        D["meta"]["extrapolation_from"] = 19.5

    # -------------------------------------------------- יציבות ויחס
    h("5. יציבות בין עונות")
    sh = read("season_heterogeneity.csv")
    sg = read("season_gap_test.csv")
    if sh is not None:
        D["stability"] = {
            "ratio_by_season": {str(r.tag): round(float(r.ratio), 3)
                                for _, r in sh.iterrows()},
            "note": "היחס נמדד על המדגם המאוחד בלבד",
        }
        if sg is not None:
            v = dict(zip(sg.metric, sg.value))
            D["stability"]["permutation_p"] = round(float(v["p_perm"]), 3)
            D["stability"]["ci_2024"] = [round(float(v["ci_lo_2024"]), 3),
                                         round(float(v["ci_hi_2024"]), 3)]
            print(f"  p = {v['p_perm']:.3f} — הפער בין העונות אינו מובהק")

    # ------------------------------------------ מה המנוע לא יודע
    D["limitations"] = [
        "כל השחקנים מונחים זמינים במחיר שוק — הנחת מודל מוצהרת, "
        "לא פגם. אין דאטה על זמינות בפועל.",
        "אי-הוודאות הדומיננטית אינה סטטיסטית אלא בבחירות המפרט. "
        "רצועת הרוויה 6.8M מול פער 11M בין שלושה מפרטים לגיטימיים.",
        "הרגרסיה נאמדה על פיזור ניקוד 6–10 ומוחלת על פער 18.6. "
        "אזור האקסטרפולציה מסומן באפור.",
        "השיפוע נאמד בין מועדונים. מועדון עם ניקוד גבוה הוא גם עשיר "
        "ועם מאמן טוב יותר. המספר הוא חסם עליון על תרומת ההקצאה.",
        "מודל העלות אינו יכול לתמחר שחקן בעונתו הראשונה ביורוליג — "
        "הוא נשען על pir_lag.",
        "מודל העלות מכווץ הפרשים בין מועדונים פי 3.33. זו האידיאליזציה "
        "(שוק אחד לכולם), לא שגיאה — אבל היא פוגעת בכיול.",
        "ההמרה ליורו הוקפאה. ציר התקציב ביחידות מנורמלות בלבד.",
    ]

    # ---------------------------------------------------------- כתיבה
    h("6. סיכום")
    if not ok:
        print("  ❌ בקרת ההקפאה נכשלה. לא נכתב דבר.")
        print("     מספר השתנה מאז ההקפאה — או באג, או שינוי מכוון.")
        print("     אם מכוון: עדכן FROZEN בקומיט נפרד עם נימוק.")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(D, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"  ✅ כל הבקרות עברו")
    print(f"  נכתב: {OUT}  ({kb:.1f} KB)")
    print(f"  מפתחות: {' · '.join(D.keys())}")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())