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

import argparse
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
import cost_market                                 # noqa: E402

SEASON, TRAIN_MAX = 2025, 2024        # 25/26
B_LO, B_HI, B_STEP = 8.0, 40.0, 0.5

# 🔴 יום 15 — הרוויה נגזרת מהעקומה, לא מוצהרת מראש.
#
# 25.0 היה מספר שנמדד על עקומת המחירים הישנה. אחרי הריפיט של
# ADR 0001 הוא אינו תקף, ו**קבוע מוקפא שנשאר אחרי שהמודל שמתחתיו
# הוחלף הוא בדיוק "סעיף 8א"** — מספר ששרד כי איש לא בדק אותו מול
# הקובץ המייצר. לכן הוא מחושב כאן מהעקומה עצמה, וההצהרה היחידה
# שנשארת היא **הסף** שמגדיר "שטוח".
SATURATION_PREV = 25.0        # לתיעוד ההשוואה בלבד
# 🔴 v1.0 (שלב 2, Q4). B_HI הוא **פלט** של העקומה החדשה: נקודת הרוויה
#    של המנוע של הכותרת, מעוגלת כלפי מעלה. ננעל לפני ההרצה, משני הצדדים.
PRED_SAT = dict(claude=(22.0, 27.0), almog=(24.0, 27.0))
FLAT_EPS = 0.01               # q_LP נשמר בעיגול לשתי ספרות
SPEND_EPS = 0.02              # הוצאה זהה = תקרת הוצאה, לא רעש

# ⚠️ שני יעדים. ROOT = PROCESSED_DIR.parent.parent (data/processed → הפרויקט)
ROOT = PROCESSED_DIR.parent.parent
OUT = PROCESSED_DIR.parent / "dashboard" / "roster_sweep.json"
PUB = ROOT / "dashboard" / "public" / "roster_sweep.json"
# 🔴 ADR 0005. וריאנט הצורה כותב לקובץ נפרד ו**אינו** מסונכרן ל-public
#    בלי --publish: PUB מקומט, וההחלטה לפרסם באה אחרי שנקבע B_HI מהעקומה
#    החדשה (שלב 6 בתוכנית הסגירה), לא כתופעת לוואי של הרצה.
OUT_SHAPE = PROCESSED_DIR.parent / "dashboard" / "roster_sweep_shape.json"
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


def derive_saturation(pts):
    """מאיפה הכסף מפסיק לקנות, ו**מאיזה סוג** העצירה.

    שני משטרים שונים לגמרי, שהמספר לבדו אינו מבחין ביניהם:

      diminishing  המנוע ממשיך להוציא כמעט את כל התקציב, אבל מה
                   שהוא קונה כבר לא משפר. תשואה פוחתת.
      exhausted    ההוצאה עצמה נעצרת. המנוע מחזיק את הסגל הטוב
                   ביותר שהמאגר מאפשר תחת אילוץ הדקות, וכסף נוסף
                   **אינו ניתן להוצאה**. מיצוי.

    ההבחנה אינה סמנטית: הניסוח בממשק ("המאגר אינו נגמר") נכון
    באחד ושקרי בשני. ביום 14 תוקן הניסוח לכיוון הראשון על סמך
    ניצול 99.1% — מדידה שהייתה נכונה לעקומת המחירים **ההיא**.

    ⚠️ שתי נקודות שונות, ואיחודן היה הבאג בגרסה הראשונה כאן:
    q מפסיק לעלות (רוויה) לפני שההוצאה מפסיקה לזוז (תקרה).
    """
    q_max = max(p["q"] for p in pts)
    sat = next(p["budget"] for p in pts
               if all(x["q"] >= q_max - FLAT_EPS
                      for x in pts if x["budget"] >= p["budget"]))
    above = [p for p in pts if p["budget"] >= sat]

    ceil_b = None
    for p in pts:
        tail = [x["spent"] for x in pts if x["budget"] >= p["budget"]]
        if len(tail) > 1 and (max(tail) - min(tail)) <= SPEND_EPS:
            ceil_b = p["budget"]
            break
    frozen = [p for p in pts if ceil_b is not None and p["budget"] >= ceil_b]
    return dict(
        saturation=float(sat), q_max=round(q_max, 2),
        n_flat=len(above), n_points=len(pts),
        spend_ceiling=(None if ceil_b is None
                       else round(float(frozen[0]["spent"]), 2)),
        ceiling_budget=(None if ceil_b is None else float(ceil_b)),
        n_frozen=len(frozen),
        used_median=round(float(np.median([p["used_pct"] for p in above])), 4),
        used_median_frozen=(None if not frozen else round(float(
            np.median([p["used_pct"] for p in frozen])), 4)),
        regime="exhausted" if ceil_b is not None else "diminishing",
        prev_saturation=SATURATION_PREV)


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
    global B_STEP
    ap = argparse.ArgumentParser()
    ap.add_argument("--caps", action="store_true",
                    help="אילוץ צורת הדקות, ADR 0005")
    ap.add_argument("--step", type=float, default=None,
                    help="צעד הגריד. ADR 0005 מריץ 1.0 לשתי העקומות")
    ap.add_argument("--publish", action="store_true",
                    help="לסנכרן ל-dashboard/public. אחרת רק לקובץ המקומי")
    a = ap.parse_args()

    caps = None
    if a.caps:
        import scoring
        caps = scoring.load_caps()
    if a.step is not None:
        B_STEP = a.step
    out_path = OUT_SHAPE if a.caps else OUT
    # 🔴 שתי העקומות על גריד אחד כשיש caps. היום החופשי בצעד 0.5
    #    והמאולץ בצעד 1.0 — שתי רשתות שונות על אותו גרף.
    one_grid = bool(a.caps)

    print(SEP)
    print(f"roster_sweep — פרה-חישוב לעונת {SEASON}/{(SEASON + 1) % 100:02d}")
    print(f"טווח {B_LO}–{B_HI} בצעדי {B_STEP} · בלי אזור אפור")
    if caps:
        print("  🔴 ADR 0005 — אילוץ צורת הדקות פעיל:")
        print("     " + " ".join(f"{k}:{v:.1f}" for k, v in sorted(caps.items())))
        print("     שתי העקומות על גריד אחד · B_HI ייקבע מהעקומה, לא מראש")
        print(f"     יעד: {out_path.name}"
              + ("  + סינכרון ל-public" if a.publish else "  · ללא פרסום"))
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
    cand, pool_info = build_pool(SEASON, TRAIN_MAX, feat, anch, pos, ps)
    cand = cand.reset_index(drop=True)          # ⚠️ באג היישור, יום 12
    # build_pool בולע את הפלט של fit_models, ולכן מודל העלות
    # שמייצר את כל הציר לא היה מודפס בשום מקום. יום 15.
    cost_meta = dict(cost_market.LAST_FIT) if cost_market.LAST_FIT else \
        dict(spec=ob.COST_SPEC)
    cost_meta["cost_scale"] = round(float(pool_info.get("cost_scale", 1.0)), 4)
    cost_meta["normalised"] = bool(pool_info.get("normalised", False))
    if cost_market.LAST_FIT:
        cost_market.report(type("M", (), {"meta": cost_meta})())
    print(f"  מחלק הנרמול: {cost_meta['cost_scale']} "
          f"(יחידת הציר = שחקן מאגר ממוצע)")
    print(f"\n  מאגר: {len(cand)} שחקנים · "
          f"עלות {cand.cost.min():.2f}–{cand.cost.max():.2f} · "
          f"שמות ידועים {sum(str(c) in names for c in cand.player_code)}/{len(cand)}")

    # 🔴 v1.0 (שלב 2, Q3). עם --caps העקומה היא **המנוע של הכותרת**:
    #    optimise_capped — זהות הכדור + צורת הדקות — ב-gap=0, וניקוד לפי
    #    ADR 0006: התוכנית חתוכה לזמינות שהתממשה (score_planned), והמועדון
    #    על מה ששיחק (score_actual). בלי --caps: המצב הישן, זהה לקודם.
    #    gap=0 גם כי בקרת המונוטוניות למטה עוצרת את הכתיבה, ובפער 0.5% ערך
    #    המטרה יכול לרדת בין נקודות סמוכות.
    v1 = bool(caps)
    if v1:
        cand = attach_usage(cand, PROCESSED_DIR / "usage_curve_results_min0.csv",
                            SEASON)
    failed = []
    grid = np.round(np.arange(B_LO, B_HI + 1e-9, B_STEP), 2)
    pts, prev = [], None
    print(f"\n  {'תקציב':>7}{'n':>4}{'הוצא':>8}{'ניצול':>8}"
          f"{'q_LP':>9}{'scoreRows':>9}{'נכנס':>6}{'יצא':>5}")
    for b in grid:
        try:
            if v1:
                sel, mins = optimise_capped(cand, float(b), MIN_LEGAL_ROSTER,
                                            caps=caps, gap=0.0,
                                            time_limit=1800)
            else:
                sel, mins = optimise_v2(cand, float(b), MIN_LEGAL_ROSTER)
        except RuntimeError as exc:          # sol_status == 2, תקרת זמן
            print(f"  {b:>7.1f}  ❌ {exc}")
            failed.append(float(b))
            continue
        if sel is None:
            continue
        rp = roster_payload(cand, sel, mins, names)
        spent = float(cand[sel].cost.sum())
        q = q_lp(cand, sel, mins)                     # ← ערך המטרה
        if v1:          # ADR 0006: התוכנית, חתוכה לזמינות שהתממשה
            q_sr = float(scoring.score_planned(
                cand[sel], "ppm_true", "avail_true",
                np.asarray(mins)[np.asarray(sel)], REPL)[0])
        else:
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
    # v1: מנוע אחד, כמו בכותרת. העקומה הראשית כבר היא המנוע המאולץ.
    cap_grid = [] if v1 else (grid if one_grid else grid[::2])
    for b in cap_grid:
        sel, mins = optimise_capped(cand_u, float(b), MIN_LEGAL_ROSTER,
                                    caps=caps)
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
        if v1:          # ADR 0006: המועדון על הדקות ששיחק
            kk = keep.assign(min_actual=keep.min_per_game * keep.avail_true)
            q_club = float(scoring.score_actual(kk, "ppm_true",
                                                "min_actual", REPL)[0])
        else:
            q_club = float(score_rows(keep, "ppm_true", "avail_true", REPL)[0])
        clubs.append(dict(
            club=club, budget=round(B, 2), n=len(keep),
            q=round(q_club, 2),
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
    S = derive_saturation(pts)
    b_hi_out = B_HI
    if v1:
        if failed:
            print(f"\n  ❌ {len(failed)} נקודות לא הוכחו ({failed}) — לא נכתב דבר.")
            return 1
        b_hi_out = float(np.ceil(S["saturation"]))
        h("B_HI — פלט של העקומה (Q4)")
        print(f"  רוויה {S['saturation']:.1f}  ->  B_HI = {b_hi_out:.0f} "
              f"(מעוגל כלפי מעלה). נקודות מעל: נחתכות.")
        for who, (lo, hi) in PRED_SAT.items():
            ok = lo <= S["saturation"] <= hi
            print(f"  {'✅' if ok else '❌'} תחזית {who} [{lo}, {hi}] -> "
                  f"{S['saturation']:.1f}")
    sat = [p for p in pts if p["budget"] >= S["saturation"]]
    n_sat = sorted({p["n"] for p in sat})
    print(f"  רוויה נגזרת: {S['saturation']:.1f}  "
          f"(לפני הריפיט: {S['prev_saturation']:.1f})")
    print(f"  מעל הרוויה: {S['n_flat']}/{S['n_points']} נקודות · "
          f"q_LP קפוא על {S['q_max']:.2f} · ניצול חציוני "
          f"{S['used_median']:.1%} · תקרת הוצאה {S['spend_ceiling']:.2f}")
    print(f"  גודל סגל מעל הרוויה: {n_sat}")

    # ⚠️ הבקרה. הניסוח בממשק **חייב** להתאים למשטר שנמדד; זה מה
    #    שנשבר כאן: הטקסט המוקפא נכתב למשטר diminishing ורץ על
    #    נתונים שהם exhausted. כל משטר נבדק מול מה שמאפיין אותו.
    if S["regime"] == "diminishing":
        if S["used_median"] < 0.95:
            print(f"  ❌ ניצול {S['used_median']:.1%} אינו תואם משטר "
                  f"'תשואה פוחתת' — עוצרים.")
            return 1
        sat_note = ("מעל נקודה זו התשואה השולית אינה תורמת עוד. "
                    f"הניצול נשאר {S['used_median']:.1%} והמנוע בוחר "
                    f"{n_sat[0]} שחקנים, המאגר אינו נגמר, הכסף מפסיק "
                    "לקנות שיפור. תשואה פוחתת, לא מיצוי.")
        print("  ✅ משטר 'תשואה פוחתת' — הניצול תומך בניסוח.")
    else:
        frozen = [p for p in pts if p["budget"] >= S["ceiling_budget"]]
        churn = sum(len(p["entered"]) + len(p["left"]) for p in frozen[1:])
        if churn:
            print(f"  ❌ 'מיצוי' מחייב סגל קפוא מעל תקרת ההוצאה, "
                  f"ונמדדו {churn} חילופים — עוצרים.")
            return 1
        sat_note = (f"מעל {S['ceiling_budget']:.1f} הכסף אינו ניתן "
                    f"להוצאה. המנוע מחזיק {n_sat[0]} שחקנים — הטובים "
                    f"במאגר תחת אילוץ הדקות — ומוציא "
                    f"{S['spend_ceiling']:.1f} ולא יותר, בכל תקציב עד "
                    f"{pts[-1]['budget']:.0f}. הניצול יורד ל-"
                    f"{S['used_median_frozen']:.1%}. **מיצוי, לא תשואה "
                    "פוחתת** — הפוך מהניסוח שקדם לריפיט של יום 15. "
                    f"התשואה השולית מתאפסת כבר ב-{S['saturation']:.1f}.")
        print(f"  ✅ משטר 'מיצוי' — תקרת הוצאה {S['spend_ceiling']:.2f} "
              f"מ-{S['ceiling_budget']:.1f}, {S['n_frozen']} נקודות קפואות, "
              f"אפס חילופים.")
        print(f"  ⚠️ {S['n_flat']} מתוך {S['n_points']} נקודות הסליידר "
              f"שטוחות. B_HI={B_HI} אינו מתאים עוד לציר הזה — "
              f"החלטת מוצר, לא באג.")

    D = dict(
        meta=dict(season=SEASON, label=f"{SEASON}/{(SEASON + 1) % 100:02d}",
                  units="יחידות מנורמלות",
                  b_lo=B_LO, b_hi=b_hi_out, step=B_STEP,
                  engine=("מאולץ: זהות הכדור + צורת הדקות · ADR 0006"
                          if v1 else "חופשי"),
                  shape_caps=(dict(sorted(caps.items())) if caps else None),
                  saturation=S["saturation"],
                  saturation_regime=S["regime"],
                  saturation_detail=S,
                  saturation_note=sat_note,
                  # 🔴 פרובננס מודל העלות. הציר תלוי בו לחלוטין,
                  #    ובלי זה אי אפשר לדעת מאיזו הרצה ה-JSON הזה.
                  cost_model=cost_meta,
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
        **({"curve": [q for q in pts if q["budget"] <= b_hi_out + 1e-9]}
           if v1 else {"free": pts, "capped": capped}),
        clubs=clubs)

    # ------------------------------------------------ כתיבה + סנכרון
    D = clean(D)
    try:
        txt = json.dumps(D, ensure_ascii=False, allow_nan=False)
    except ValueError as e:
        print(f"\n  ❌ ערך לא-סופי ב-JSON: {e}")
        print("     NaN חשוף מפיל את JSON.parse בדפדפן — לא נכתב דבר.")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(txt, encoding="utf-8")
    ha = hashlib.md5(out_path.read_bytes()).hexdigest()[:12]
    print(f"\n  נכתב:   {out_path}  ({out_path.stat().st_size/1024:.0f} KB)")
    if a.publish:
        PUB.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out_path, PUB)
        hb = hashlib.md5(PUB.read_bytes()).hexdigest()[:12]
        print(f"  סונכרן: {PUB}")
        print(f"  hash:   {ha} · {hb}  {'✅' if ha == hb else '❌ לא זהים'}")
        if ha != hb:
            return 1
    else:
        print(f"  hash:   {ha}")
        print(f"  ⚠️ לא סונכרן ל-{PUB.name} — הקובץ המקומט לא נגע.")
        print("     פרסום עם --publish, אחרי שנקבע B_HI מהעקומה החדשה.")
    print(f"  {len(pts)} נקודות חופשי · {len(capped)} מאולץ · "
          f"{len(clubs)} מועדונים")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())