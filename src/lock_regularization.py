"""
lock_regularization.py  (Day 8)
-------------------------------
האם **כפייה** מרסנת את קללת המנצח — או שזה היה במקרה.

--------------------------------------------------------------------
מה גילה quota_cost
--------------------------------------------------------------------
נעילת חמשת הישראלים של מכבי הפכה את הקללה מ-**−7.3% ל-+0.4%**,
בעוד ניקוד המודל ירד (122.1 -> 120.1) כמו שאילוץ חייב לעשות.

ההסבר שהוצע: **שחקן שנכפה לא נבחר על ידי המודל, ולכן אינו נושא
שגיאת אמידה חיובית.** האופטימייזר בוחר בדיוק את מי ש-`ppm` שלו
הוערך ביתר; כל מקום שמוצא מהבחירה הוא מקום בלי קללה.

**אבל אצל מכבי ננעלו שחקני המועדון עצמו** — אותם אנשים שנמצאים
בבנצ'מרק. ככל שנועלים יותר, שני הצדדים מתלכדים וההשוואה
מתנוונת. בקיצון, נעילת כל 12 נותנת 0% בהגדרה. לכן אי אפשר לדעת
אם ראינו ריסון או חפיפה.

--------------------------------------------------------------------
המבחן שמפריד
--------------------------------------------------------------------
לנעול `k` שחקנים **אקראיים מהמאגר** — לא של המועדון — ולמדוד
את הקללה כפונקציה של `k`.

  אם הקללה מתכווצת עם k גם בנעילה אקראית
     -> הריסון נובע מ**הוצאת מקומות מהבחירה**, וזה ממצא כללי
        על האופטימייזר. הישראלים לא מיוחדים.

  אם היא לא מתכווצת
     -> מה שראינו אצל מכבי היה **חפיפה** עם הבנצ'מרק, לא ריסון,
        וה-+16.5% חסר משמעות.

לכל k מוגרלים כמה סטים, והתוצאה היא חציון — אחרת מודדים מזל.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
PRED_CLAUDE = "curse_shrinks_with_k_even_random"
PRED_CLAUDE_WHY = (
    "קללת המנצח היא תכונה של **הבחירה**, לא של השחקנים. שחקן "
    "אקראי נושא שגיאת אמידה בתוחלת אפס; שחקן נבחר נושא אותה "
    "חיובית. לכן כל מקום שמוצא מהבחירה מקטין את הקללה, בערך "
    "ליניארית ב-k. אני צופה שהקללה תעלה מ--7.3% לכיוון אפס "
    "כש-k מגיע ל-8-10, **וגם שניקוד המציאות יירד** — כי שחקנים "
    "אקראיים גרועים מנבחרים. כלומר: פחות קללה, וגם פחות איכות. "
    "אלה שני דברים שונים ואסור לבלבל ביניהם."
)
PRED_ALMOG = "___"
# ====================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import optimizer_backtest as ob
import club_rosters as cr
from roster_membership_audit import score_rows
from optimise_consistent import optimise_v2
from final_day7 import prep, bench, MIN_LEGAL_ROSTER

SEP = "=" * 78
REPL = 0.127
KS = [0, 2, 4, 6, 8, 10]
REPS = 6
SEED = 20260817


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def main():
    print(SEP)
    print("האם כפייה מרסנת את קללת המנצח — נעילה אקראית")
    print("תחזיות ננעלו לפני ההרצה. ראו ראש הקובץ.")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position

    for club, train_max, test in [("TEL", 2023, 2024), ("HTA", 2024, 2025)]:
        cand = prep(club, train_max, test, feat, anch, pos, ps)
        r = cr.roster_df(club, test)
        B = float(r.salary.dropna().sum()) + cr.budget_only_total(club, test)
        bq, _, _, _, _ = bench(club, test, ps, posmap, REPL)
        club_codes = set(r.player_code)
        # רק מועמדים שאינם שחקני המועדון — כדי שלא תהיה חפיפה
        pool = [i for i in cand.index
                if str(cand.at[i, "player_code"]) not in club_codes]

        h(f"{club} {test}   מאגר לנעילה {len(pool)} "
          f"(בלי {len(cand) - len(pool)} שחקני המועדון)")
        print(f"  {'k':>3}{'n':>4}{'מודל':>9}{'מציאות':>10}{'קללה':>9}"
              f"{'מול המועדון':>13}   הערה")
        rng = np.random.default_rng(SEED)
        for k in KS:
            res = []
            reps = 1 if k == 0 else REPS
            for _ in range(reps):
                lk = (list(rng.choice(pool, size=k, replace=False))
                      if k else None)
                sel, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER, locked=lk)
                if sel is None:
                    continue
                rr = cand[sel]
                qp, _, _ = score_rows(rr, "ppm", "avail", REPL)
                qt, _, _ = score_rows(rr, "ppm_true", "avail_true", REPL)
                res.append((len(rr), qp, qt))
            if not res:
                print(f"  {k:>3}   אין פתרון ב-{reps} ההגרלות")
                continue
            a = np.array(res, float)
            n_, qp, qt = np.median(a, axis=0)
            note = "בסיס" if k == 0 else f"{len(res)}/{reps} פתירים"
            print(f"  {k:>3}{n_:>4.0f}{qp:>9.1f}{qt:>10.1f}"
                  f"{qt / qp - 1:>+8.1%}{qt / bq - 1:>+12.1%}   {note}")

    h("קריאה")
    print("  אם הקללה מתכווצת עם k **גם בנעילה אקראית** — הריסון")
    print("  הוא תכונה של הוצאת מקומות מהבחירה, לא של הישראלים,")
    print("  וה-+16.5% של quota_cost היה חפיפה ולא ממצא.")
    print("\n  ושימו לב לשתי עמודות נפרדות: 'קללה' ו'מול המועדון'.")
    print("  קללה קטנה יותר עם ניקוד נמוך יותר אינה שיפור.")
    print(SEP)


if __name__ == "__main__":
    main()
