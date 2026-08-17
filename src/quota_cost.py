"""
quota_cost.py  (Day 8)
----------------------
כמה מהיתרון של המנוע הוא **חופש שלא היה למועדון**.

--------------------------------------------------------------------
הפגם שההשגה של אלמוג הצביעה עליו
--------------------------------------------------------------------
המנוע ממטב **מסגרת אחת** — 200 דקות יורוליג — ומקבל את **מלוא**
תקציב המועדון. המועדון בנה את אותו סגל לשתי מסגרות, ומחזיק
שחקנים בגלל מכסת ליגת העל ולא בגלל תרומתם ליורוליג.

נמדד ביום 8:

    מכבי  : 6 ישראלים = 2,955,000 = **39% מהתקציב**, 15.8 דק' ממוצע
    הפועל : 5 ישראלים = 3,000,000 = **13% מהתקציב**,  6.5 דק' ממוצע

בהפועל: מדר 1.2M ל-10.3 דק' · שגב 300K לשלוש דקות במשחק אחד.

**כלומר ה-+9.4% מנופח**, והשאלה היא בכמה.

--------------------------------------------------------------------
שני מבחנים, שניהם בלי דאטה חדש
--------------------------------------------------------------------
**א. גזירת תקציב** — למנוע ניתן רק החלק ה"חופשי" (61% / 87%),
   והוא מנוקד מול הסגל **המלא** של המועדון. זה **חסם תחתון קשה**:
   המנוע משלם על המכסה ולא מקבל ממנה כלום.

**ב. נעילת המכסה** — המנוע חייב לקחת את אותם שחקנים ישראלים
   שהמועדון החזיק, בעלותם, וממטב את היתרה. זו הגרסה הריאלית:
   אותה מחויבות, אותו כסף, ואת השאר הוא בוחר.

ב' עדיף. א' מדווח לצדו כדי לתחום את הטווח.

⚠️ **מגבלה:** `is_israeli` קיים רק לעוגנים, ולכן המנוע נאלץ
לקחת את **הישראלים של המועדון עצמו** ולא ישראלים כלשהם. זו
הטבה למועדון — במציאות אפשר היה להחליף אותם באחרים. לאום לכל
המאגר הוא איסוף ידני, כמו העמדות.

--------------------------------------------------------------------
תחזיות — ננעלות לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
PRED_CLAUDE = "survives_at_maccabi_shrinks_a_lot"
PRED_CLAUDE_WHY = (
    "אצל מכבי הישראלים אינם זבל — סורקין 23.4 דק', בלאט 24.2, "
    "דיברתלומאו 17.4. הנעילה תעלה כסף אבל תקבל תמורה, ולכן "
    "היתרון ישרוד ויתכווץ ל-3%-7%. אצל הפועל הישראלים מייצרים "
    "6.5 דקות בממוצע על 3M — שם הנעילה היא כמעט הפסד מוחלט, "
    "ואני צופה שהיתרון **יתאפס או יתהפך לשלילי**. כלומר: המבחן "
    "יפריד בין שני המועדונים, ולא יוריד את שניהם באותה מידה."
)
PRED_ALMOG = "maccabi_survives_hapoel_zeroes"   # אלמוג, לפני ההרצה
# ====================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster_optimizer as ro
import optimizer_backtest as ob
import club_rosters as cr
from roster_membership_audit import score_rows
from optimise_consistent import optimise_v2
from final_day7 import prep, bench, MIN_LEGAL_ROSTER

SEP = "=" * 78
REPL = 0.127


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def main():
    print(SEP)
    print("כמה מהיתרון הוא חופש שלא היה למועדון")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    rows = []

    for club, train_max, test in [("TEL", 2023, 2024), ("HTA", 2024, 2025)]:
        cand = prep(club, train_max, test, feat, anch, pos, ps)
        r = cr.roster_df(club, test)
        a = anch[(anch.club == club) & (anch.season == test)]
        isr = set(a[a.is_israeli == 1].player_code.dropna().astype(str))

        B = float(r.salary.dropna().sum()) + cr.budget_only_total(club, test)
        quota_cost = float(r[r.player_code.isin(isr)].salary.sum())
        free = B - quota_cost
        bq, _, _, _, _ = bench(club, test, ps, posmap, REPL)

        h(f"{club} {test}   תקציב {B:,.0f}   מכסה {quota_cost:,.0f} "
          f"({quota_cost / B:.0%})   חופשי {free:,.0f}")
        print(f"  המועדון בפועל: {bq:.1f}")

        # --- בסיס: חופש מלא ---
        sel, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
        q0, _, _ = score_rows(cand[sel], "ppm_true", "avail_true", REPL)

        # --- א. גזירת תקציב ---
        selA, _ = optimise_v2(cand, free, MIN_LEGAL_ROSTER)
        qA = (score_rows(cand[selA], "ppm_true", "avail_true", REPL)[0]
              if selA is not None else np.nan)

        # --- ב. נעילת המכסה ---
        idx = list(cand.index[cand.player_code.astype(str).isin(isr)])
        n_lock = len(idx)
        selB, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER, locked=idx)
        qB = (score_rows(cand[selB], "ppm_true", "avail_true", REPL)[0]
              if selB is not None else np.nan)

        print(f"\n  {'תרחיש':<26}{'n':>4}{'ניקוד':>9}{'מול המועדון':>13}")
        print(f"  {'חופש מלא (הישן)':<26}{int(sel.sum()):>4}{q0:>9.1f}"
              f"{q0 / bq - 1:>+12.1%}")
        if selA is not None:
            print(f"  {'א. תקציב חופשי בלבד':<26}{int(selA.sum()):>4}"
                  f"{qA:>9.1f}{qA / bq - 1:>+12.1%}")
        else:
            print(f"  {'א. תקציב חופשי בלבד':<26}   אין פתרון")
        if selB is not None:
            print(f"  {'ב. מכסה נעולה':<26}{int(selB.sum()):>4}{qB:>9.1f}"
                  f"{qB / bq - 1:>+12.1%}   ({n_lock} נעולים מתוך "
                  f"{len(isr)} ישראלים)")
        else:
            print(f"  {'ב. מכסה נעולה':<26}   אין פתרון")

        rows.append(dict(club=club, base=q0 / bq - 1,
                         cut=qA / bq - 1 if selA is not None else np.nan,
                         lock=qB / bq - 1 if selB is not None else np.nan))

    h("הכרעה")
    df = pd.DataFrame(rows)
    print(df.to_string(index=False, float_format=lambda v: f"{v:+.1%}"))
    print("\n  'ב' היא המספר להשתמש בו. 'א' הוא חסם תחתון קשה.")
    print(f"\n  קלוד ניבא: {PRED_CLAUDE}")
    print("    מכבי ישרוד ויתכווץ ל-3%-7% · הפועל יתאפס או יתהפך")
    print(SEP)


if __name__ == "__main__":
    main()
