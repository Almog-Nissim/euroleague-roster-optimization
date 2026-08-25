"""roster_sweep.py — יום 13. פרה-חישוב לבנאי האינטראקטיבי.

--------------------------------------------------------------------
למה פרה-חישוב ולא פותר בדפדפן
--------------------------------------------------------------------
פותר JS (glpk.js) היה דורש לשכתב את פונקציית המטרה, רצפות
העמדה ומודל העלות בשפה שנייה. **שני מימושים מתפצלים בשקט** —
בדיוק כמו שני מיפויי NAME2CODE שהפילו את הכיול ב-13.8% ביום 12.

כאן כל סגל שיוצג הוא **פלט CBC אמיתי**, לא שחזור. וזה גם מהיר
יותר: הזזת סליידר היא lookup, בלי המתנה לרשת.

--------------------------------------------------------------------
טווח הסליידר — 8 עד 40, בלי אזור אפור
--------------------------------------------------------------------
⛔ ה-19.5 שנרשם ביום 12 שייך לכיול **מנורמל→יורו**, שנאמד על 18
   מועדוני 2024 (11.21–22.16). הסליידר ביחידות מנורמלות, ולכן
   המגבלה הזו אינה חלה עליו. 15 מתוך 38 המועדונים נמצאים מעל
   19.5, כולל חציון 2025 (20.25) — אזור אפור שם היה שגוי.

✅ מה שכן קיים בדאטה: **התשואה השולית מתאפסת מעל ~25**, בשתי
   העונות, על 52 נקודות עקומה. וניצול התקציב ב-2024 מעל 19.5
   יורד ל-88.9% — המנוע לא מצליח לבזבז את הכסף. **המאגר נגמר.**

   זה ממצא, לא היעדר תמיכה. הסמן הוא "מכאן הכסף מפסיק לקנות",
   ולא "מכאן איננו יודעים".

⚠️ הסתייגות שנרשמת בפלט: צורת העקומה **לפני** הרוויה רועשת בין
   העונות (2024 שיאה ב-15–19.5 עם +3.95; 2025 שלילית ב-10–15
   עם −2.42). הרוויה יציבה; המסלול אליה פחות.

--------------------------------------------------------------------
מה נשמר
--------------------------------------------------------------------
לכל נקודת תקציב: הסגל המלא (שם, עמדה, עלות, דקות, תרומה),
סכומים, ניצול, והדיף מהנקודה הקודמת — מי נכנס ומי יצא.

--------------------------------------------------------------------
🔴 חזוי מול נצפה — למה שתי הסדרות נשמרות
--------------------------------------------------------------------
`fair_compare.py` בדק השוואה "הוגנת": לנקד גם את המועדון בערך
המטרה החזוי (`optimise_v2` עם סגלו נעול). התוצאה:

    פער חציוני חזוי↔חזוי:   27.74 יחידות (30.0%)
    פער נצפה   (q_free/q_club על ppm_true):      +18.3%

**הפער גדל ב-155%, לא קטן.** ההפרש הוא **קללת המנצח, נמדדת
ישירות**: השחקנים שהמנוע בוחר הם בדיוק אלה ש-`ppm` שלהם הוערך
ביתר, ולכן `ppm_true` שלהם נמוך מהתחזית.

⇒ **אסור להציג חזוי מול חזוי בממשק.** זה מנפח את המנוע ב-12
  נקודות אחוז. למסך "אתה מול המנוע" יש להשתמש ב-
  `usage_constrained_results.csv`, ששני צדדיו נצפים.

⇒ כאן נשמרות **שתיהן**: `q` (חזוי, מונוטוני, מה שהמנוע ידע
  בזמן ההחלטה) ו-`q_realised` (נצפה, מה שקרה). הפער ביניהן
  הוא הסיפור, לא בעיה להסתיר.

⚠️ `fair_compare` נשר על 11 מ-20 המועדונים: `optimise_v2` מגביל
   `Σx ≤ MAX_ROSTER = 16`, ואי אפשר לנעול 17–20 שחקנים. כל
   הנשארים הם סגלים ≤16 — והם נוטים להיות עניים יותר. גם
   ה-27.74 עצמו נאמד על תת-מדגם מוטה.

--------------------------------------------------------------------
✅ רגישות למילוי זהות הכדור — נסגרה
--------------------------------------------------------------------
143 מתוך 335 שחקנים (43%) מקבלים `usage_prior = 20` מומצא.
נבדקו שלושה מילויים:

    20 → פער 22.82   |   24 → 22.16 (−0.66)   |   28 → 22.16

**הכותרת אינה רגישה להנחה.** ‎−2.9% בלבד. ושהמעבר 24→28 אינו
משנה דבר אומר שהאילוץ מפסיק להיות מחייב מעל 24.

--------------------------------------------------------------------
⛔ מה שלא כאן
--------------------------------------------------------------------
עונת 26/27. אין `boxscore_player_2026.csv`, אין תקציבים, ואין
רשימת מועדונים. כשיהיו — זה **מצב תחזית**, לא שחזור: בלי
`q_club` להשוואה ובלי המרה לניצחונות, כי אין תוצאה לאמת מולה.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import optimizer_backtest as ob                     # noqa: E402
from league_backtest import build_pool, club_side, REPL   # noqa: E402
from optimise_consistent import optimise_v2         # noqa: E402
from usage_constrained import optimise_capped, attach_usage  # noqa: E402
from roster_membership_audit import score_rows      # noqa: E402
from roster_optimizer import PROCESSED_DIR          # noqa: E402
from final_day7 import MIN_LEGAL_ROSTER             # noqa: E402

SEASON, TRAIN_MAX = 2025, 2024        # 25/26
B_LO, B_HI, B_STEP = 8.0, 40.0, 0.5
SATURATION = 25.0
OUT = PROCESSED_DIR.parent / "dashboard" / "roster_sweep.json"
SEP = "=" * 76


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def q_lp(cand, sel, mins):
    """🔴 ערך המטרה עצמו: Σ ppm(i)·e(i) — על ppm ה**חזוי**.

    **לא** score_rows. יום 11 הוכיח שהמטרה מונוטונית ב-124 נקודות
    × 38 מועדונים, 0 הפרות — וש-score_rows מקצה דקות מחדש
    בחמדנות ולכן קופצת. סליידר שמוצג עם score_rows יראה נפילות
    של 30% בין שתי נקודות סמוכות, וזו שטות למשתמש.

    ⚠️ `ppm` ולא `ppm_true`. ה-LP ממקסם את התחזית; `ppm_true` הוא
    הנצפה, הוא יכול להיות **שלילי**, והוא אינו המטרה.

    אומת מול budget_curve.csv: `q_lp` נותן **0 הפרות מונוטוניות
    ב-30 מעברים × 4 קבוצות**. `q` (score_rows על ppm_true) נותן
    8–10 הפרות, עד −13.5 — הארטיפקט של יום 11.

    ולבנאי זה גם הכמות הנכונה מהותית: לעונה שטרם שוחקה אין
    `ppm_true` בכלל.
    """
    m = np.asarray(mins)[np.asarray(sel)]
    return float((cand[sel].ppm.values * m).sum())


def roster_payload(cand, sel, mins, names):
    r = cand[sel].copy()
    m = np.asarray(mins)[np.asarray(sel)]
    r["minutes"] = m
    r["contrib"] = r.ppm * m          # חזוי — כמו המטרה
    r["name"] = r.player_code.astype(str).map(names)
    r = r.sort_values("contrib", ascending=False)
    return [dict(
        code=str(x.player_code),
        name=(x["name"] if isinstance(x["name"], str) else f"#{x.player_code}"),
        pos=str(x.position),
        cost=round(float(x.cost), 3),
        minutes=round(float(x.minutes), 1),
        ppm=round(float(x.ppm), 3),
        ppm_true=(round(float(x.ppm_true), 3)
                  if np.isfinite(x.ppm_true) else None),
        avail=round(float(x.avail_true), 3),
        contrib=round(float(x.contrib), 2),
    ) for _, x in r.iterrows()]


def main() -> int:
    print(SEP)
    print(f"roster_sweep — פרה-חישוב לעונת {SEASON}/{SEASON+1-2000}")
    print(f"טווח {B_LO}–{B_HI} בצעדי {B_STEP} · בלי אזור אפור")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    names = (feat.drop_duplicates("player_code")
             .set_index(feat.drop_duplicates("player_code")
                        .player_code.astype(str)).player_name.to_dict())
    cand, _ = build_pool(SEASON, TRAIN_MAX, feat, anch, pos, ps)
    cand = cand.reset_index(drop=True)          # ⚠️ באג היישור, יום 12
    print(f"\n  מאגר: {len(cand)} שחקנים · "
          f"עלות {cand.cost.min():.2f}–{cand.cost.max():.2f} · "
          f"שמות ידועים {sum(str(c) in names for c in cand.player_code)}/{len(cand)}")

    grid = np.round(np.arange(B_LO, B_HI + 1e-9, B_STEP), 2)
    pts, prev = [], None
    print(f"\n  {'תקציב':>7}{'n':>4}{'הוצא':>8}{'ניצול':>8}"
          f"{'q_LP':>9}{'scoreRows':>9}{'נכנס':>6}{'יצא':>5}")
    for b in grid:
        sel, mins = optimise_v2(cand, float(b), MIN_LEGAL_ROSTER)
        if sel is None:
            continue
        rp = roster_payload(cand, sel, mins, names)
        spent = float(cand[sel].cost.sum())
        q = q_lp(cand, sel, mins)                     # ← ערך המטרה
        q_sr = float(score_rows(cand[sel], "ppm_true",
                                "avail_true", REPL)[0])   # להשוואה בלבד
        cur = {p["code"] for p in rp}
        inn = sorted(cur - prev) if prev else []
        out = sorted(prev - cur) if prev else []
        code2name = {p["code"]: p["name"] for p in rp}
        pts.append(dict(
            budget=float(b), n=len(rp), spent=round(spent, 2),
            unspent=round(float(b) - spent, 2),
            used_pct=round(spent / float(b), 4),
            q=round(q, 2), q_realised=round(q_sr, 2),
            optimism=round(q - q_sr, 2),      # קללת המנצח, נקודתית
            roster=rp,
            entered=[code2name.get(c, c) for c in inn],
            left=[c for c in out],
        ))
        mono = "" if (not pts[:-1] or q >= pts[-2]["q"] - 1e-6) else "  ⚠ ירידה"
        print(f"  {b:>7.1f}{len(rp):>4}{spent:>8.2f}{spent/b:>8.1%}"
              f"{q:>9.2f}{q_sr:>9.1f}{len(inn):>6}{len(out):>5}{mono}")
        prev = cur

    # ------------------------------------------------ המנוע המאולץ
    h("המנוע המאולץ — זהות הכדור")
    cand_u = attach_usage(cand, PROCESSED_DIR / "usage_curve_results_min0.csv",
                          SEASON)
    capped = []
    for b in grid[::2]:                        # רזולוציה חצי, יקר יותר
        sel, mins = optimise_capped(cand_u, float(b), MIN_LEGAL_ROSTER)
        if sel is None:
            continue
        capped.append(dict(
            budget=float(b),
            q=round(q_lp(cand_u, sel, mins), 2),
            roster=roster_payload(cand_u, sel, mins, names)))
    print(f"  {len(capped)} נקודות")

    # ------------------------------------------------ המועדונים
    h("המועדונים האמיתיים — 'אתה מול המנוע'")
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})
    posmap = pos.set_index(pos.player_code.astype(str)).position
    gmax = float(ps[ps.season == SEASON].games.max())
    clubs = []
    for club in sorted(split[split.season == SEASON].club.unique()):
        keep, _ = club_side(cand, split, club, SEASON, gmax, posmap)
        if len(keep) < MIN_LEGAL_ROSTER:
            continue
        B = float(keep.cost.sum())
        clubs.append(dict(
            club=club, budget=round(B, 2), n=len(keep),
            q=round(float(score_rows(keep, "ppm_true",
                                     "avail_true", REPL)[0]), 2),
            roster=[dict(code=str(r.player_code),
                         name=names.get(str(r.player_code),
                                        f"#{r.player_code}"),
                         pos=str(r.position), cost=round(float(r.cost), 3),
                         ppm=round(float(r.ppm), 3))
                    for _, r in keep.iterrows()]))
        print(f"  {club:<5} תקציב {B:>6.2f} · סגל {len(keep):>2} · "
              f"ניקוד {clubs[-1]['q']:>6.1f}")

    # ------------------------------------------------ כתיבה
    h("בקרת מונוטוניות — יום 11, מיושם")
    v_lp = [(pts[i]["budget"], pts[i]["q"] - pts[i-1]["q"])
            for i in range(1, len(pts)) if pts[i]["q"] < pts[i-1]["q"] - 1e-6]
    v_sr = sum(1 for i in range(1, len(pts))
               if pts[i]["q_realised"] < pts[i-1]["q_realised"] - 1e-6)
    print(f"  ערך המטרה (q_LP):  {len(v_lp)} הפרות מתוך {len(pts)-1}")
    print(f"  score_rows (נצפה): {v_sr} הפרות — הארטיפקט של יום 11")
    print("  ⚠️ הסליידר מציג q_LP. הנצפה נשמר ב-q_realised להשוואה בלבד.")
    if v_lp:
        for b, d in v_lp[:5]:
            print(f"    ⚠ {b:.1f}: {d:+.3f}")
        print("\n  ❌ המטרה אינה מונוטונית. זה סותר את יום 11 — עוצרים.")
        return 1
    print("  ✅ המטרה מונוטונית. הסליידר בטוח להצגה.")

    h("קללת המנצח — חזוי מול נצפה")
    op = [p["optimism"] for p in pts]
    print(f"  אופטימיות (q − q_realised): חציון {np.median(op):+.2f} · "
          f"טווח {min(op):+.1f}..{max(op):+.1f}")
    print(f"  נקודות שבהן הנצפה **עלה** על החזוי: "
          f"{sum(1 for v in op if v < 0)}/{len(op)}")
    print("  ⚠️ זו אינה שגיאה — זו ההטיה שיום 8 מדד. היא מוצגת בממשק.")

    h("סיכום")
    sat = [p for p in pts if p["budget"] >= SATURATION]
    if sat:
        print(f"  מעל {SATURATION}: ניצול חציוני "
              f"{np.median([p['used_pct'] for p in sat]):.1%} · "
              f"לא מנוצל חציוני "
              f"{np.median([p['unspent'] for p in sat]):.2f}")
    D = dict(
        meta=dict(season=SEASON, label=f"{SEASON-1}/{SEASON-2000}",
                  units="יחידות מנורמלות",
                  b_lo=B_LO, b_hi=B_HI, step=B_STEP,
                  saturation=SATURATION,
                  saturation_note="מעל נקודה זו התשואה השולית מתאפסת "
                                  "והמנוע אינו מצליח לנצל את התקציב — "
                                  "המאגר נגמר. ממצא, לא היעדר תמיכה.",
                  shape_caveat="צורת העקומה לפני הרוויה רועשת בין העונות: "
                               "2024 שיאה ב-15–19.5, 2025 שלילית ב-10–15.",
                  pool_size=int(len(cand)),
                  display_series="q",
                  display_note="q = ערך המטרה החזוי, מונוטוני. "
                               "q_realised = מה שקרה בפועל. הפער "
                               "(optimism) הוא קללת המנצח.",
                  fair_compare_warning="אין להשוות q של המנוע ל-q של "
                                       "מועדון בערך חזוי — זה מנפח "
                                       "ב-12 נק' אחוז. למסך ההשוואה "
                                       "יש להשתמש ב-"
                                       "usage_constrained_results.csv.",
                  usage_fill_sensitivity="−0.66 יחידות בלבד (−2.9%) "
                                         "במעבר ממילוי 20 ל-28"),
        free=pts, capped=capped, clubs=clubs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(D, ensure_ascii=False), encoding="utf-8")
    print(f"\n  נכתב: {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
    print(f"  {len(pts)} נקודות חופשי · {len(capped)} מאולץ · "
          f"{len(clubs)} מועדונים")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())