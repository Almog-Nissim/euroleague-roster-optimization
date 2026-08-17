"""
absence_position_test.py  (Day 7 -> 8)
--------------------------------------
לאן הולכות הדקות של שחקן שנעדר — לפי **עמדתו**.

--------------------------------------------------------------------
ההשערה, של אלמוג
--------------------------------------------------------------------
> "השחקן השביעי צריך להיות תלוי בשחקן שלא זמין. אם העמדה של
>  השחקן שנעדר היא G, אז G אחר בהסתברות גבוהה ישחק יותר, ו-F
>  בהסתברות קטנה ישחק יותר (הם דומים יותר בתפקוד על המגרש),
>  וסנטר בסיכוי ממש קטן יקבל יותר דקות."

זו טענה על **מטריצת תחלופה**, לא על סקלר. מבחן המאמן של יום 7
מדד רק "לאן הדקות הלכו לפי דירוג" ו**לא התנה על עמדת הנעדר** —
כלומר לא יכול היה לבדוק את זה בכלל.

--------------------------------------------------------------------
מה שהקוד עושה היום
--------------------------------------------------------------------
`score` ו-`simulate` מחלקים דקות **חמדנית לפי ppm**, עם שתי
תקרות בלבד: 32 דקות לשחקן, ותקרת עמדה על סך הדקות
(`POS_MAX_SHARE = {G: .698, F: .794, C: .282}`).

**אין בקוד שום כלל של "מי מחליף את מי".** לכן:
  - אם ההשערה של אלמוג מתאשרת בסימולציה, היא **נובעת מהתקרות**
  - אם היא נדחית, הקוד מפזר דקות בין עמדות בצורה שהמאמן לא היה
    מרשה, וזה **פגם במודל** ולא ממצא

בשני המקרים התשובה שימושית.

--------------------------------------------------------------------
המבחן
--------------------------------------------------------------------
בכל משחק מסומן מי נעדר. משווים את דקות השחקנים הנוכחים במשחקים
שבהם **בדיוק אחד** נעדר, לפי עמדת הנעדר, מול משחקים שבהם **אף
אחד** לא נעדר. הפלט הוא מטריצה 3x3:

    שורה  = עמדת הנעדר
    עמודה = עמדת מי שקיבל דקות
    תא    = דקות נוספות בממוצע למשחק

תחזית אלמוג = אלכסון דומיננטי, G->F חלש, ו-C->G / G->C כמעט אפס.
"""

# ====================================================================
# תחזיות — ננעלו לפני ההרצה
# ====================================================================
PRED_ALMOG = "diagonal_dominant"
PRED_ALMOG_WHY = (
    "אותה עמדה מקבלת את רוב הדקות; G<->F חלש כי התפקוד דומה; "
    "C מנותק כמעט לגמרי."
)
PRED_CLAUDE = "diagonal_only_for_C"
PRED_CLAUDE_WHY = (
    "בקוד אין כלל תחלופה, רק תקרות. תקרת C היא 28.2% — הדוקה "
    "מאוד — ולכן היעדרות סנטר **חייבת** להתמלא בסנטר, והאלכסון "
    "ב-C יהיה חזק. אבל תקרות G (69.8%) ו-F (79.4%) רופפות ואינן "
    "כובלות, ולכן היעדרות של G תתמלא פשוט **על ידי ה-ppm הגבוה "
    "הבא**, בלי קשר לעמדתו. כלומר: אלכסון ב-C, ערבוב ב-G/F. "
    "אם אלמוג צודק לאורך כל האלכסון — זה אומר שהתקרות מייצרות "
    "התנהגות נכונה במקרה, ולא שהמודל יודע להחליף."
)
DIAG_STRONG = 0.55   # שיעור הדקות שהולך לאותה עמדה, מעליו = אלכסון
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
from optimise_consistent import optimise_v2
from final_day7 import prep, MIN_LEGAL_ROSTER

SEP = "=" * 78
DRAWS = 200
GAMES = ro.GAMES_PER_SEASON
SEED = 20260817
POSN = ["G", "F", "C"]


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def allocate(pp, pos, present):
    """חלוקת דקות למשחק אחד — זהה למנגנון שבקוד."""
    n = len(pp)
    caps = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
            for g in ro.POS_MAX_SHARE}
    left = ro.MINUTES_PER_GAME
    m = np.zeros(n)
    for j in range(n):                      # pp כבר ממוין יורד
        if not present[j]:
            continue
        g = pos[j]
        take = min(ro.MAX_MIN_PLAYER, left, caps[g])
        m[j] = take
        left -= take
        caps[g] -= take
    return m


def run(club, train_max, test, feat, anch, pos, ps):
    cand = prep(club, train_max, test, feat, anch, pos, ps)
    r = cr.roster_df(club, test)
    B = float(r.salary.dropna().sum()) + cr.budget_only_total(club, test)
    sel, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
    rr = cand[sel]

    order = np.argsort(-rr.ppm_true.values)
    pp = rr.ppm_true.values[order]
    pz = rr.position.values[order]
    av = np.clip(rr.avail_true.values[order], 0, 1)
    n = len(pp)

    rng = np.random.default_rng(SEED)
    base = allocate(pp, pz, np.ones(n, bool))       # כולם נוכחים

    # דקות נוספות, לפי (עמדת הנעדר, עמדת המקבל)
    # 🔴 תיקון: חייבים להתנות על כך שהנעדר **בכלל שיחק**.
    # בסגל של 12 רק ~7 מקבלים דקות (7x32 > 200), ולכן היעדרות של
    # מדורג 8-12 אינה משנה דבר — והיא בלעה את רוב התצפיות
    # והחזירה טבלה של אפסים. זהו הרוטציה, לא הסגל.
    rot = np.where(base > 0)[0]
    print(f"  [{club}] {len(rot)} מתוך {n} מקבלים דקות כשכולם נוכחים")

    gain = {a: {b: 0.0 for b in POSN} for a in POSN}
    cnt = {a: 0 for a in POSN}
    for _ in range(DRAWS * GAMES):
        present = rng.random(n) < av
        out_rot = rot[~present[rot]]
        if len(out_rot) != 1:          # בדיוק אחד **מהרוטציה** נעדר
            continue
        j = int(out_rot[0])
        a = pz[j]
        cnt[a] += 1
        m = allocate(pp, pz, present)
        d = m - base
        d[j] = 0.0
        for b in POSN:
            mask = (pz == b)
            if mask.any():
                gain[a][b] += float(np.sum(np.maximum(d[mask], 0.0)))

    h(f"{club} {test}  ·  סגל {n}  ·  "
      f"{sum(cnt.values())} משחקים עם נעדר יחיד")
    print(f"  הרכב הסגל: " +
          " ".join(f"{g}={int((pz == g).sum())}" for g in POSN))
    total_lbl = "סה" + chr(34) + "כ"
    print("\n  " + f"{'עמדת הנעדר':<14}" +
          "".join(f"{'-> ' + b:>10}" for b in POSN) +
          f"{total_lbl:>10}{'אלכסון':>9}")
    ok = {}
    for a in POSN:
        if cnt[a] == 0:
            print(f"  {a:<14}   אין תצפיות")
            continue
        row = np.array([gain[a][b] for b in POSN]) / cnt[a]
        tot = row.sum()
        share = row[POSN.index(a)] / tot if tot > 1e-9 else np.nan
        ok[a] = share
        print(f"  {a:<14}" + "".join(f"{v:>10.2f}" for v in row) +
              f"{tot:>10.2f}{share:>8.0%}")
    return ok


def main():
    print(SEP)
    print("לאן הולכות הדקות של הנעדר — לפי עמדתו")
    print("תחזיות ננעלו לפני ההרצה. ראו ראש הקובץ.")
    print(SEP)
    print(f"\n  תקרות העמדה בקוד: " +
          " ".join(f"{g}={ro.POS_MAX_SHARE[g]:.1%}" for g in POSN))
    print("  (זה המנגנון היחיד בקוד שיכול לייצר תלות בעמדה —")
    print("   אין שום כלל של 'מי מחליף את מי')")

    feat, anch, pos, ps = ob.load_all()
    res = {}
    for club, tr, te in [("TEL", 2023, 2024), ("HTA", 2024, 2025)]:
        res[club] = run(club, tr, te, feat, anch, pos, ps)

    h("הכרעה")
    print(f"  {'':<8}" + "".join(f"{g:>10}" for g in POSN))
    for club, d in res.items():
        print(f"  {club:<8}" +
              "".join(f"{d.get(g, float('nan')):>9.0%}" for g in POSN))
    print(f"\n  סף 'אלכסון דומיננטי': {DIAG_STRONG:.0%}")
    print(f"\n  אלמוג ניבא : {PRED_ALMOG} — אלכסון בכל שלוש העמדות")
    print(f"  קלוד ניבא  : {PRED_CLAUDE} — אלכסון ב-C בלבד, "
          "ערבוב ב-G/F")

    allv = [(c, g, v) for c, d in res.items() for g, v in d.items()]
    diag_all = all(v >= DIAG_STRONG for _, _, v in allv)
    diag_c = all(v >= DIAG_STRONG for _, g, v in allv if g == "C")
    mix_gf = all(v < DIAG_STRONG for _, g, v in allv if g in ("G", "F"))
    if diag_all:
        print("\n  -> אלכסון בכל העמדות. **אלמוג צדק.**")
    elif diag_c and mix_gf:
        print("\n  -> אלכסון ב-C בלבד. **קלוד צדק** — והמשמעות היא")
        print("     שהתקרה של C היא שמייצרת את ההתנהגות, לא ידע")
        print("     על תחלופה. ב-G/F הקוד מחלק דקות בין עמדות")
        print("     בצורה שמאמן לא היה מרשה. **פגם במודל.**")
    else:
        print("\n  -> אף תחזית לא מתאשרת נקי.")
    print(SEP)


if __name__ == "__main__":
    main()
