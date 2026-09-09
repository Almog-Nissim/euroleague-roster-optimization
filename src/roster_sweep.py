"""roster_sweep.py — יום 13, מעודכן יום 14. פרה-חישוב לבנאי האינטראקטיבי.

--------------------------------------------------------------------
למה פרה-חישוב ולא פותר בדפדפן
--------------------------------------------------------------------
פותר JS (glpk.js) היה דורש לשכתב את פונקציית המטרה, רצפות
העמדה ומודל העלות בשפה שנייה. **שני מימושים מתפצלים בשקט** —
בדיוק כמו שני מיפויי NAME2CODE שהפילו את הכיול ב-13.8% ביום 12.

כאן כל סגל שיוצג הוא **פלט CBC אמיתי**, לא שחזור. וזה גם מהיר
יותר: הזזת סליידר היא lookup, בלי המתנה לרשת.

--------------------------------------------------------------------
🔴 יום 14 — סנכרון ל-dashboard/public
--------------------------------------------------------------------
הקובץ נכתב לשני יעדים: `data/dashboard/` (מקור אמת) ו-
`dashboard/public/` (מה ש-Vite אורז ל-dist).

ביום 14 התגלה שהם היו **מנותקים**: התיקונים נכתבו ל-data/ בעוד
`public/` נשאר על גרסת 25.8 2:29. `npm run build` ארז את הישנה
וסימן ✓. בדיוק המשפחה של שני מיפויי NAME2CODE — אותו דאטה בשני
מקומות, אחד מתעדכן והשני לא.

⇒ אין להעתיק ידנית. הכתיבה מסנכרנת, והפלט מדפיס hash של שניהם.

--------------------------------------------------------------------
טווח הסליידר — 8 עד 40, בלי אזור אפור
--------------------------------------------------------------------
⛔ ה-19.5 שנרשם ביום 12 שייך לכיול **מנורמל→יורו**, שנאמד על 18
   מועדוני 2024 (11.21–22.16). הסליידר ביחידות מנורמלות, ולכן
   המגבלה הזו אינה חלה עליו. 15 מתוך 38 המועדונים נמצאים מעל
   19.5, כולל חציון 2025 (20.25) — אזור אפור שם היה שגוי.

✅ מה שכן קיים בדאטה: **התשואה השולית מתאפסת מעל ~25**, בשתי
   העונות, על 52 נקודות עקומה.

⚠️ תוקן ביום 14: הניסוח "**המאגר נגמר**" שהיה כאן ובפלט הופרך.
   הסריקה מראה ניצול חציוני 99.1% מעל 25 והמנוע בוחר 12 שחקנים
   בכל 65 הנקודות. המאגר אינו נגמר — הכסף מפסיק לקנות שיפור.
   **תשואה פוחתת, לא מיצוי.** הסמן הוא "מכאן הכסף מפסיק לקנות",
   ולא "מכאן איננו יודעים" וגם לא "מכאן אין את מי לקנות".

⚠️ הסתייגות שנרשמת בפלט: צורת העקומה **לפני** הרוויה אינה
   יציבה. הניסוח הקודם ("2024 שיאה ב-15–19.5, 2025 שלילית
   ב-10–15") נבדק ביום 14 מול budget_curve.csv ולא תאם: 2024 אכן
   שיאה ב-17.0, אבל שתי העונות שליליות בנקודות מפוזרות לאורך כל
   הטווח. הניגוד המסודר לא קיים. הרוויה יציבה; המסלול אליה לא.

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
  נקודות אחוז (30.0% − 18.3%). למסך "אתה מול המנוע" יש להשתמש
  ב-`usage_constrained_results.csv`, ששני צדדיו נצפים.

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

import hashlib
import json
import shutil
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
from club_codes import NAME2CODE                    # noqa: E402

SEASON, TRAIN_MAX = 2025, 2024        # 25/26
B_LO, B_HI, B_STEP = 8.0, 40.0, 0.5
SATURATION = 25.0

# ⚠️ שני יעדים. ROOT = PROCESSED_DIR.parent.parent (data/processed → הפרויקט)
ROOT = PROCESSED_DIR.parent.parent
OUT = PROCESSED_DIR.parent / "dashboard" / "roster_sweep.json"
PUB = ROOT / "dashboard" / "public" / "roster_sweep.json"
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


def fnum(v, nd=3):
    """float בטוח ל-JSON. NaN/inf → None.

    ⚠️ יום 14: `avail=round(float(x.avail_true), 3)` היה חשוף. NaN
       חשוף ב-JSON מפיל את JSON.parse בדפדפן ("Unexpected token
       'N'") — בדיוק הבאג שהפיל מסך שלם ביום 13.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, nd) if np.isfinite(f) else None


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
        cost=fnum(x.cost),
        minutes=fnum(x.minutes, 1),
        ppm=fnum(x.ppm),
        ppm_true=fnum(x.ppm_true),
        avail=fnum(x.avail_true),
        contrib=fnum(x.contrib, 2),
    ) for _, x in r.iterrows()]


def fit_eur(clubs, season):
    """כיול מנורמל → מיליוני יורו נטו, על מועדוני העונה עצמה.

    ⚠️ מוצג בממשק עם ± ולא כמספר נקי. מודל העלות מכווץ הפרשים
       בין מועדונים פי 3.33 (scale_regression, יום 12): מיסוי,
       שחקנים מקומיים וחניכי נוער אינם בו. דובאי ובאסקוניה
       יושבות על תקציב מנורמל כמעט זהה ומשלמות 18.25M€ ו-8.50M€.

    ⛔ אינו מחליף את הכיול המוקפא של scale_regression. זה מיפוי
       תצוגה בלבד, נאמד על 20 נקודות, לצורך קריאוּת הסליידר.
    """
    bud = pd.read_csv(PROCESSED_DIR / "club_budgets_gemini.csv")
    bud["club"] = bud.club.map(NAME2CODE)
    m = (pd.DataFrame(clubs)[["club", "budget"]]
         .merge(bud[bud.season == season][["club", "net_eur"]], on="club")
         .dropna())
    if len(m) < 8:
        print(f"  ⚠️ רק {len(m)} מועדונים עם תקציב — הכיול לא נאמד")
        return None
    x, y = m.budget.values, m.net_eur.values
    a, b = np.polyfit(x, y, 1)
    pred = a * x + b
    r = float(np.corrcoef(x, y)[0, 1])
    mae = float(np.abs(y - pred).mean())
    worst = m.assign(err=y - pred).reindex(
        np.abs(y - pred).argsort()[::-1]).head(2)
    print(f"  net_eur = {a:.4f}·norm {b:+.3f}   n={len(m)} · "
          f"r={r:.3f} · R²={r*r:.3f} · MAE={mae:.2f}M€")
    for _, w in worst.iterrows():
        print(f"    חריג: {w.club} · מנורמל {w.budget:.1f} → "
              f"ניבוי {a*w.budget+b:.1f} · בפועל {w.net_eur:.1f} "
              f"({w.err:+.1f})")
    print("  ⚠️ מוצג בממשק עם ± ולא כמספר נקי.")
    return dict(a=round(float(a), 4), b=round(float(b), 4),
                r2=round(r * r, 3), mae=round(mae, 2),
                lo=round(float(x.min()), 1), hi=round(float(x.max()), 1),
                n=int(len(m)),
                note="מיפוי תצוגה בלבד. מודל העלות מכווץ הפרשים בין "
                     "מועדונים פי 3.33, ולכן שני מועדונים באותו תקציב "
                     "מנורמל יכולים לשלם סכומים שונים מאוד.")


def clean(o):
    """מנקה NaN/inf רקורסיבית לפני הכתיבה. שכבת הגנה שנייה על fnum."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


def main() -> int:
    print(SEP)
    print(f"roster_sweep — פרה-חישוב לעונת {SEASON}/{(SEASON + 1) % 100:02d}")
    print(f"טווח {B_LO}–{B_HI} בצעדי {B_STEP} · בלי אזור אפור")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    # שמות משלושה מקורות. feat אחרון — הוא המוסמך במקרה של סתירה.
    # ⚠️ feat לבדו נתן 228/335 בלבד: 107 שחקנים קיימים רק ב-
    #    player_season / player_positions.
    names = {}
    for src in (ps, pos, feat):
        if "player_name" in src.columns:
            s = src.dropna(subset=["player_name"]).copy()
            s["k"] = s.player_code.astype(str)
            names.update(s.drop_duplicates("k").set_index("k")
                         .player_name.to_dict())
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
        # ⚠️ יום 14: ההשוואה חייבת להיות מעוגל מול מעוגל. `q` הגולמי
        #    מול `pts[-2]["q"]` המעוגל ייצר 7 דגלי "ירידה" שווא על
        #    נקודות עם 0 נכנס/0 יצא — כלומר בדיוק אותו סגל.
        mono = ("" if (not pts[:-1] or round(q, 2) >= pts[-2]["q"] - 1e-9)
                else "  ⚠ ירידה")
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
                         pos=str(r.position), cost=fnum(r.cost),
                         ppm=fnum(r.ppm))
                    for _, r in keep.iterrows()]))
        print(f"  {club:<5} תקציב {B:>6.2f} · סגל {len(keep):>2} · "
              f"ניקוד {clubs[-1]['q']:>6.1f}")

    # ------------------------------------------------ כיול יורו
    h("כיול תצוגה — יחידות מנורמלות → מיליוני יורו")
    eur = fit_eur(clubs, SEASON)

    # ------------------------------------------------ בקרות
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
    used_sat = 0.0
    if sat:
        used_sat = float(np.median([p['used_pct'] for p in sat]))
        print(f"  מעל {SATURATION}: ניצול חציוני {used_sat:.1%} · "
              f"לא מנוצל חציוני "
              f"{np.median([p['unspent'] for p in sat]):.2f}")
        # ⚠️ הבקרה שהייתה חסרה: הטענה "המאגר אינו נגמר" נשענת על
        #    ניצול גבוה מעל הרוויה. אם הוא יצנח, המחרוזת בממשק
        #    הופכת שקרית — וזה בדיוק איך ש"סעיף 8א" שרד חמישה ימים.
        if used_sat < 0.95:
            print(f"  ❌ הניצול מעל הרוויה צנח ל-{used_sat:.1%}. "
                  f"saturation_note טוען 'המאגר אינו נגמר' — עוצרים.")
            return 1
        n_sat = {p["n"] for p in sat}
        print(f"  ✅ ניצול {used_sat:.1%} · גודל סגל מעל הרוויה: "
              f"{sorted(n_sat)}")

    D = dict(
        meta=dict(season=SEASON, label=f"{SEASON}/{(SEASON + 1) % 100:02d}",
                  units="יחידות מנורמלות",
                  b_lo=B_LO, b_hi=B_HI, step=B_STEP,
                  saturation=SATURATION,
                  saturation_note="מעל נקודה זו התשואה השולית אינה תורמת עוד. "
                                  "הניצול נשאר 99.1% והמנוע בוחר 12 "
                                  "שחקנים, המאגר אינו נגמר, הכסף "
                                  "מפסיק לקנות שיפור. תשואה פוחתת, "
                                  "לא מיצוי.",
                  shape_caveat="צורת העקומה לפני הרוויה אינה יציבה: "
                               "ב-budget_curve (20.8) התשואה השולית "
                               "שלילית בנקודות מפוזרות לאורך הטווח "
                               "בשתי העונות שנבדקו. הריצה ההיא קדמה "
                               "לתיקון האינדקס של יום 12 ולא שוחזרה "
                               "תחת הקוד הנוכחי. הסייג נוגע לאמינות "
                               "הצורה, לא לעקומה המוצגת.",
                  pool_size=int(len(cand)),
                  display_series="q",
                  display_note="q = ערך המטרה החזוי, מונוטוני. "
                               "q_realised = מה שקרה בפועל. הפער "
                               "(optimism) הוא קללת המנצח.",
                  fair_compare_warning="אין להשוות q של המנוע ל-q של "
                                       "מועדון בערך חזוי — זה מנפח "
                                       "ב-12 נק' אחוז. למסך ההשוואה "
                                       "יש להשתמש ב-"
                                       "usage_constrained_results.csv. "
                                       "נמדד על 11 מ-20 מועדונים "
                                       "(סגלים ≤16 בלבד), הנוטים "
                                       "להיות עניים יותר.",
                  usage_fill_sensitivity="−0.66 יחידות בלבד (−2.9%) "
                                         "במעבר ממילוי 20 ל-28",
                  eur=eur),
        free=pts, capped=capped, clubs=clubs)

    # ------------------------------------------------ כתיבה + סנכרון
    D = clean(D)
    try:
        txt = json.dumps(D, ensure_ascii=False, allow_nan=False)
    except ValueError as e:
        print(f"\n  ❌ ערך לא-סופי ב-JSON: {e}")
        print("     NaN חשוף מפיל את JSON.parse בדפדפן — לא נכתב דבר.")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(txt, encoding="utf-8")
    PUB.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT, PUB)

    ha = hashlib.md5(OUT.read_bytes()).hexdigest()[:12]
    hb = hashlib.md5(PUB.read_bytes()).hexdigest()[:12]
    print(f"\n  נכתב:   {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
    print(f"  סונכרן: {PUB}")
    print(f"  hash:   {ha} · {hb}  {'✅' if ha == hb else '❌ לא זהים'}")
    if ha != hb:
        return 1
    print(f"  {len(pts)} נקודות חופשי · {len(capped)} מאולץ · "
          f"{len(clubs)} מועדונים")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())