"""export_dashboard.py — יום 13, מעודכן יום 14. שכבת הייצוא.

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
🔴 יום 14 — שני תיקונים למנגנון ההקפאה עצמו
--------------------------------------------------------------------
**(1) ערך יתום הוסר.** `ratio_partial_raw: 0.636` ישב ב-`FROZEN`
ומעולם לא נבדק: אין לו קריאת `check`, הוא לא נכתב ל-`D`, והערך
אינו מופיע ב-`season_heterogeneity.csv` (שם היחסים הם 0.748 /
0.837 / 0.367 / 0.837). כלומר `FROZEN` הציג שבעה ערכים מוגנים
בעוד ששה מוגנים בפועל. **הגנה מדומה גרועה מהיעדר הגנה**, כי היא
משביתה את החשד.

**(2) בקרת כיסוי.** הבאג לעיל אפשרי בגלל שכל ה-`check` תלויים
בקבצים: אם קובץ חסר, הבלוק מדולג ו-`ok` נשאר True. עכשיו כל
קריאה נרשמת, ובסיום נבדק שכל מפתח ב-`FROZEN` אכן נבדק. מפתח
שלא נבדק עוצר את הבנייה — בין אם נשמט ובין אם הקובץ חסר.

**(3) סנכרון ל-dashboard/public.** הקובץ נכתב לשני יעדים. ביום
14 התגלה שהם היו מנותקים: `public/` נשאר על גרסה ישנה, ו-
`npm run build` ארז אותה וסימן ✓. אותה משפחה כמו שני מיפויי
NAME2CODE. הפלט מדפיס hash של שניהם.

--------------------------------------------------------------------
מה לא נכנס
--------------------------------------------------------------------
⛔ הרוויה ביורו. שלושה מפרטי כיול נותנים 19.3 / 24.5 / 30.5.
   ציר התקציב ביחידות מנורמלות בלבד, טווח תוקף עד ~19.5.
⛔ "58% מהקשר הוא תקציב" · "המנוע בוחר בדיוק 12" · "2024 חריגה".
   שלושתם ירדו מדרגת ממצא.
"""

import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from roster_optimizer import PROCESSED_DIR  # noqa: E402

# ⚠️ שני יעדים. ROOT = PROCESSED_DIR.parent.parent (data/processed → הפרויקט)
ROOT = PROCESSED_DIR.parent.parent
OUT = PROCESSED_DIR.parent / "dashboard" / "dashboard_data.json"
PUB = ROOT / "dashboard" / "public" / "dashboard_data.json"
TOL = 0.02
SEP = "=" * 76

# ============ ערכים מוקפאים — כל שינוי כאן דורש נימוק בקומיט ============
# ⚠️ כל מפתח כאן **חייב** לעבור ב-check(). בקרת הכיסוי בסעיף 6
#    עוצרת אם מפתח לא נבדק. אל תוסיף ערך בלי קריאת check מתאימה.
# 🔴 יום 15 — עודכן אחרי הריפיט של ADR 0001. הישן והחדש זה לצד
#    זה נוצרים ע"י src/refit_diff.py ב-data/processed/refit_day15_diff.csv
#    ומתועדים ב-docs/refit-day15-diff.md. **הערכים הישנים נשארים כאן
#    בהערה בכוונה**: הקפאה שמתעדכנת בלי עקבות אינה הקפאה.
#
#      מפתח                     לפני     אחרי
#      headline_capped_wins      2.03     4.26
#      headline_free_wins        5.17     4.90
#      gap_random_club_wins     -1.65    -1.72
#      gap_free_random_wins      6.84     6.61
#      n_club_seasons            38.0     38.0
#      wasted_budget_share      0.269    0.308
#
# 🔴 v1.0, 2026-09-21 — ADR 0006. הכותרת עברה לקונבנציה שבה אף צד לא
#    מחולק מחדש בדיעבד: המנוע על התוכנית של ה-LP המאולץ עם אילוץ הצורה
#    (gap=0, הוכח 38/38), המועדון על הדקות ששיחק. wins_conversion.py
#    מריץ את שתי הקונבנציות ומוודא שהישנה משחזרת את 4.26.
#
#      מפתח                     יום 15    v1.0
#      headline_capped_wins      4.26     5.01   CI95 [1.39, 8.69]
#      headline_free_wins        4.90     —      הוסר: ל-ADR 0006 אין ניקוד
#                                                לפי תוכנית למנוע החופשי
#
#    ארבעת הראשונים נגזרים מ-usage_constrained_results.csv, שתלוי
#    ב-usage_curve_results_min0.csv. הקובץ המקורי במעקב מ-8661308,
#    ו-refit_diff.py מוודא שמפרט club_relative משחזר עליו את יום 14
#    שורה-שורה. (עד יום 15 כאן היה כתוב 5.10 — ערך מריצת סנדבוקס
#    על קובץ usage משוחזר.)
FROZEN = {
    "headline_capped_wins":  5.01,
    "headline_adv_cap":      0.1892,     # v1.0, headline_exact.csv
    "gap_random_club_wins": -1.72,
    "gap_free_random_wins":  6.61,
    "n_club_seasons":       38.0,
    "wasted_budget_share":   0.308,
}

CHECKED = set()          # נרשם ע"י check(), נאכף בסעיף 6


def h(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def check(name, got, hard=True):
    exp = FROZEN[name]
    CHECKED.add(name)
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
    ok &= check("headline_capped_wins", float(cap.wins))

    g = {r.gap: r for _, r in nw.iterrows()}
    rc = next(v for k, v in g.items() if "אקראי − מועדון" in k)
    fr = next(v for k, v in g.items() if "חופשי − אקראי" in k)
    ok &= check("gap_random_club_wins", float(rc.wins))
    ok &= check("gap_free_random_wins", float(fr.wins))

    # ה-caveat שלמטה טוען שתי טענות. שתיהן נבדקות כאן, לא רק נכתבות.
    if float(cap.lo) <= 0:
        print("  ❌ ה-caveat טוען שהקצה התחתון של הטווח חיובי — והוא לא.")
        ok = False
    if float(rc.wins) >= 0:
        print("  ❌ ה-caveat טוען שמבנה האילוצים מוריד מהתוצאה — והוא לא.")
        ok = False

    D["headline"] = {
        "primary": {
            "value": round(float(cap.wins), 2),
            "ci": [round(float(cap.lo), 2), round(float(cap.hi), 2)],
            "label": "ניצחונות נוספים בעונה מאופטימיזציה של התקציב הקיים",
            "engine": "מאולץ: זהות הכדור + צורת הדקות · ADR 0006",
            "caveat": "גם בקצה הזהיר של הטווח התוצאה חיובית — "
                      "אותו תקציב, הקצאה טובה יותר. הטווח מודד "
                      "את הרעש בלבד: ההמרה לניצחונות נלמדה "
                      "מהפרשים קטנים מאלה שהמנוע מייצר, ומנגד "
                      "מבנה האילוצים דווקא מוריד מהתוצאה — "
                      f"כלומר תרומת המודל עצמו גדולה מ-{float(cap.wins):.2f}. "
                      "המספר מדווח רק עם הפירוק שלו (ADR 0006): המנוע "
                      "נמדד על התוכנית שהתחייב אליה והמועדון על הסבב "
                      "ששיחק — אף צד לא מחולק מחדש בדיעבד.",
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
        share = float(w1.cost_wasted.median())
        ok &= check("wasted_budget_share", share)
        # ⚠️ ההגדרה, מ-why_100.scoring_players:
        #    score_rows מחלק 200 דקות משוקללות לסגל האמיתי לפי
        #    ppm_true, ומי שקיבל ≤0.5 דקות נספר כמחוץ לרוטציה.
        #    זו חלוקה של **המודל**, לא של המאמן. המאמן כן נתן להם
        #    דקות; המודל אומר שלא היה כדאי. הסייג הזה מחזק את
        #    המספר, לא מחליש אותו — מספר בלי הגדרה הוא סיסמה.
        D["wasted"] = {
            "share": round(share, 3),
            "n_scoring_median": int(w1.n_scoring.median()),
            "roster_median": 16,
            "label": "מועדון יורוליג ממוצע משלם על שחקנים שאינם "
                     "חלק מהרוטציה",
            "definition": "כשמחלקים את דקות המשחק בין שחקני הסגל לפי "
                          "התפוקה שלהם לדקה, לחלקם לא נשארות דקות כלל.",
            "caveat": "זו חלוקה של המודל, לא של המאמן. המאמן כן נתן "
                      "להם דקות — המודל אומר שלא היה כדאי.",
        }
        print(f"  שחקנים מנקדים: {int(w1.n_scoring.median())} מתוך 16")

    # ---------------------------------------------------- הבנצ'מרק
    h("3. הבנצ'מרק")
    uc = read("usage_constrained_results.csv")
    hx = read("headline_exact.csv")
    if uc is not None and hx is not None:
        ok &= check("n_club_seasons", float(len(uc)))
        m = uc.merge(w1[["season", "club", "q_rand", "rand_win"]],
                     on=["season", "club"], how="left") if w1 is not None else uc
        D["benchmark"] = {
            "n": int(len(uc)),
            "seasons": sorted(int(s) for s in uc.season.unique()),
            # 🔴 v1.0: היתרון מ-headline_exact.csv, הקונבנציה של ADR 0006 — אותו
            #    מקור כמו הכותרת. קודם: usage_constrained_results (0.1414), כלומר
            #    אריח ישן מתחת לכותרת חדשה. המנוע החופשי הוסר עם הכותרת שלו.
            "adv_cap_pct": round(float(hx.adv_F_exact.median()), 4),
            "n_win": int((hx.adv_F_exact > 0).sum()),
        }
        ok &= check("headline_adv_cap", float(hx.adv_F_exact.median()))
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
    # כל מגבלה: כותרת · הסבר בשפה יומיומית · הפירוט הטכני.
    # ⚠️ הניסוח הקודם היה ז'רגון ("s_partial", "פיזור ניקוד 6-10")
    #    ולכן היה קריא רק למי שכבר יודע. מגבלה שאיש לא מבין
    #    אינה מגבלה מוצהרת.
    D["limitations"] = [
        {"t": "המנוע מניח שכל שחקן פנוי לקנייה",
         "p": "לשחקן אמיתי יש חוזה, משפחה והעדפות. המנוע בוחר מתוך "
              "כל מי ששיחק בליגה, כאילו כולם על המדף. זו לא טעות "
              "בקוד — פשוט אין נתונים על מי היה באמת זמין.",
         "x": "הנחת מודל מוצהרת, נבחרה ביום 3 יחד עם דחיית מסלול C."},

        {"t": "אי-הוודאות גדולה מהמספרים שמודפסים לידה",
         "p": "כשמריצים את אותו ניתוח בשלוש דרכים סבירות, התשובות "
              "רחוקות זו מזו יותר מטווח השגיאה שמופיע לצידן. כלומר "
              "איך בחרנו למדוד משפיע יותר מגודל המדגם.",
         "x": "רצועת הרוויה 6.8M€ מול פער 11M€ בין שלושה מפרטי כיול "
              "(19.3 / 24.5 / 30.5). רגרסיה אינה מודדת את זה."},

        {"t": "ההמרה לניצחונות נמתחת מעבר למה שנמדד",
         "p": "הקשר בין ניקוד לניצחונות נלמד מהפרשים קטנים בין "
              "מועדונים, ומוחל על הפרש גדול בהרבה שהמנוע מייצר. "
              "כמו למדוד גובה של ילדים ולנבא גובה של מבוגר.",
         "x": "נאמד על פיזור ניקוד 6–10 נקודות, מוחל על פער 18.6. "
              "אזור האקסטרפולציה מסומן באפור בגרפים."},

        {"t": "מועדון טוב הוא לא רק סגל טוב",
         "p": "מועדון עם ניקוד גבוה הוא בדרך כלל גם עשיר, עם מאמן "
              "טוב יותר ומתקנים טובים יותר. ניכינו חלק מזה, לא את "
              "הכול. לכן המספר הוא תקרה, לא אומדן.",
         "x": "השיפוע נאמד בין מועדונים. בקרת log(תקציב) מנכה חלק "
              "מההשפעה; מאמן, לכידות ובריאות נשארים בפנים."},

        {"t": "שחקן בעונתו הראשונה — המחיר הוא ניחוש",
         "p": "מודל המחיר לומד מהעונה הקודמת של השחקן. למי שמגיע "
              "ליורוליג לראשונה אין עונה קודמת, והוא מקבל הערכה גסה.",
         "x": "המודל נשען על pir_lag. 107 מתוך 335 שחקני המאגר אינם "
              "ב-player_features כלל."},

        {"t": "המנוע מתמחר את כל הליגה באותו שוק",
         "p": "בפועל מועדון בספרד משלם אחרת ממועדון בישראל — מיסים, "
              "שחקנים מקומיים, שחקני נוער שגדלו במועדון. המנוע מתעלם מזה בכוונה, "
              "כי השאלה היא 'מה אפשר לקנות בכסף' ולא 'כמה זה עולה "
              "לכם'. עקומת המחיר נלמדת עכשיו מ-13 מועדונים במקום "
              "מאחד, אבל **הרמה** עדיין אחת לכל הליגה.",
         "x": "יום 15: המפרט הוחלף ל-log(שכר) = α_מועדון + β·x "
              "(ADR 0001). β₁ ירד מ-0.2317 ל-0.1727. הרמה עדיין "
              "משותפת: קריאת הציר כיורו נכשלה במבחן קבלה מוצהר "
              "(refit_acceptance, MAE 8.57M€), ולכן הציר נשאר "
              "ביחידות מנורמלות."},

        {"t": "אין כאן סכומים ביורו — בכוונה",
         "p": "התקציב מוצג ביחידות מנורמלות: יחידה אחת היא שחקן מאגר "
              "ממוצע. ניסינו להמיר ליורו, ושלוש דרכים סבירות להמיר נתנו "
              "תשובות שרחוקות 11 מיליון זו מזו — ולכן הורדנו את היורו "
              "מהממשק ולא הצגנו אותו עם ±.",
         "x": "ההמרה נבדקה מול תקציבי המועדונים בפועל ונכשלה בשלושת "
              "השערים שהוגדרו מראש (refit_acceptance). v1.0 הסיר את "
              "תצוגת היורו כולה, כולל הסכום לשחקן."},
    ]

    # ---------------------------------------------------------- כתיבה
    h("6. סיכום")

    # ⚠️ בקרת כיסוי — יום 14. ratio_partial_raw ישב ב-FROZEN בלי
    #    שאיש בדק אותו. כאן נאכף שכל מפתח מוקפא אכן עבר check().
    #    זה תופס גם מפתח שנשמט וגם בלוק שדולג בגלל קובץ חסר.
    unchecked = sorted(set(FROZEN) - CHECKED)
    print(f"  כיסוי ההקפאה: {len(CHECKED)}/{len(FROZEN)} נבדקו")
    if unchecked:
        print(f"  ❌ מפתחות מוקפאים שלא נבדקו: {unchecked}")
        print("     או שהקובץ המייצר חסר, או שקריאת check נשמטה.")
        print("     ערך מוקפא שאינו נבדק הוא הגנה מדומה — לא נכתב דבר.")
        return 1

    if not ok:
        print("  ❌ בקרת ההקפאה נכשלה. לא נכתב דבר.")
        print("     מספר השתנה מאז ההקפאה — או באג, או שינוי מכוון.")
        print("     אם מכוון: עדכן FROZEN בקומיט נפרד עם נימוק.")
        return 1

    # ⚠️ json.dumps כותב NaN חשוף, ו-JSON.parse בדפדפן נופל עליו:
    #    "Unexpected token 'N'". ארבעה מופעים ב-budget_curve הפילו את
    #    טעינת הקובץ **בשקט** — ה-fetch נכשל ו-catch בלע. בדיוק
    #    המשפחה של כשל שקט שהפרויקט נלחם בה.
    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        if isinstance(o, float) and not np.isfinite(o):
            return None
        return o

    D = clean(D)
    try:
        txt = json.dumps(D, ensure_ascii=False, indent=2, allow_nan=False)
    except ValueError as e:
        print(f"  ❌ עדיין יש ערך לא-סופי ב-JSON: {e}")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(txt, encoding="utf-8")
    PUB.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT, PUB)

    ha = hashlib.md5(OUT.read_bytes()).hexdigest()[:12]
    hb = hashlib.md5(PUB.read_bytes()).hexdigest()[:12]
    kb = OUT.stat().st_size / 1024
    print(f"  ✅ כל הבקרות עברו · JSON תקני (allow_nan=False)")
    print(f"  נכתב:   {OUT}  ({kb:.1f} KB)")
    print(f"  סונכרן: {PUB}")
    print(f"  hash:   {ha} · {hb}  {'✅' if ha == hb else '❌ לא זהים'}")
    if ha != hb:
        return 1
    print(f"  מפתחות: {' · '.join(D.keys())}")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())