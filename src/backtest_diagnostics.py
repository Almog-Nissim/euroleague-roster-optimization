"""
backtest_diagnostics.py  (Day 6)
--------------------------------
שלוש בדיקות על **הבקטסט עצמו**, לא על המודל.

הרצנו את הבקטסט וקיבלנו שני מספרים שנראים כמו מסקנות:

    TEL 2024   +21.2%   המנוע מנצח את מכבי
    HTA 2025    -0.5%   המנוע שווה להפועל
    lambda     שטוח     הפסימיות לא עוזרת

לפני שרושמים אותם, צריך לדעת אם המבחן בכלל **יכול היה**
להראות משהו אחר. שלושתם חשודים מסיבה מבנית שונה.

--------------------------------------------------------------------
א. האם התקציב בכלל מגביל?
--------------------------------------------------------------------
בהפועל התקציב המושווה הוא 18,000,000, והאופטימייזר בחר 7
שחקנים. 7 הוא בדיוק המינימום המתמטי: 200/32 = 6.25 -> 7.

זה חשוד. אם התקציב לא נגמר, האופטימייזר אינו פותר בעיית הקצאה
אלא פשוט מדרג לפי ppm ולוקח את הראש. במצב כזה:
  - "המנוע שווה להפועל" אינו ממצא על אופטימיזציה
  - וגם lambda לא יכול לשנות כלום, כי אין אילוץ שנלחצים עליו

המבחן: כמה מהתקציב **נוצל בפועל**, ומה קורה כשנותנים פי 10.
אם התוצאה זהה - האילוץ דקורטיבי.

--------------------------------------------------------------------
ב. האם ל-ppm_sd יש בכלל פיזור בקרב הנבחרים?
--------------------------------------------------------------------
ב-pessimism_sweep, ppm_sd מחושב מ-**משתנה יחיד**: min_pg_lag.
זה נבע מההטרוסקדסטיות שנמדדה, וזה נכון בממוצע.

אבל המועמדים הטובים כולם שיחקו הרבה דקות. כלומר בקרב מי שנבחר,
min_pg_lag רווי - וממילא גם ppm_sd. חיסור lambda*sd מקבוצה
שכל ה-sd שלה זהה הוא **חיסור קבוע**, והוא לא משנה דירוג.

אם זה המצב, "הפסימיות נדחתה" אינו ממצא אלא **מבחן חסר עוצמה**.
זו הבחנה שאני חייב לעשות לפני שאני רושם את המסקנה, כי כתבתי
אותה כבר פעם אחת בניסוח חזק מדי.

--------------------------------------------------------------------
ג. האם שני הצדדים נספרים על אותו כסף?
--------------------------------------------------------------------
בבקטסט:
    real    = כל מועמדי TEL בעונת המבחן        -> 9 שחקנים
    B_fair  = סכום שכר העוגנים שהם גם מועמדים  -> 7 שחקנים

כלומר מכבי מנוקדת על 9 שחקנים, והמנוע מקבל תקציב שמכסה 7 מהם.
שני שחקנים בסגל של מכבי הם, לצורך ההשוואה, **חינם**.

הכיוון לא ברור מראש, ולכן צריך למדוד:
  - לצמצם את מכבי ל-7 המתומחרים מוריד לה ניקוד, אבל אולי גם
    משאיר אותה בלי מספיק שחקנים ל-200 דקות - וזה ארטיפקט של
    גודל סגל, בדיוק הבעיה שכבר זיהינו במקום אחר
  - להשאיר 9 נותן לה שני שחקנים במתנה

מודדים את שתי הגרסאות ואת מספר הדקות שכל צד באמת מילא.

--------------------------------------------------------------------
תחזיות - נכתבו לפני ההרצה
--------------------------------------------------------------------
א. TEL: ניצול >= 95% מהתקציב (מגביל).
   HTA: ניצול <= 70%, והכפלת התקציב פי 10 לא תשנה את הבחירה.
ב. מקדם השונות של ppm_sd בקרב 15 המובילים: מתחת ל-15%.
   כלומר הציר מנוון.
ג. מכבי על 9 שחקנים ממלאת 200 דקות; על 7 - לא. ההפרש בניקוד
   יהיה גדול מ-10%, כלומר ההשוואה רגישה להחלטה הזו.

הרצה:
    python src/audits/backtest_diagnostics.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import roster_optimizer as ro
import optimizer_backtest as bt
import pessimism_sweep as ps_mod

SCENARIOS = [("TEL", 2023, 2024), ("HTA", 2024, 2025)]
LAMBDAS = [0.0, 0.5, 1.0, 2.0]
TOP_N = 15
SEP = "=" * 74


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def score_verbose(r, ppm_col, avail_col):
    """כמו bt.score, אבל מחזיר גם כמה דקות באמת מולאו.

    bt.score מפסיק כשנגמרים השחקנים ולא כשנגמרות הדקות. סגל קטן
    מדי מקבל ניקוד נמוך לא בגלל איכות אלא בגלל שאין את מי לשלוח
    לפרקט. בלי המספר הזה אי אפשר להבחין בין השניים.
    """
    ppm = r[ppm_col].values
    av = r[avail_col].values
    pos = r.position.values
    caps = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
            for g in ro.POS_MAX_SHARE}
    left = ro.MINUTES_PER_GAME
    q, used, n_play = 0.0, 0.0, 0
    for j in np.argsort(-ppm):
        g = pos[j]
        take = min(ro.MAX_MIN_PLAYER, left, caps[g]) * av[j]
        if take <= 0:
            continue
        q += take * ppm[j]
        left -= take
        caps[g] -= take
        used += take
        n_play += 1
    return q, used, n_play


def best_roster(cand, budget):
    """הסגל הטוב ביותר לפי המודל תחת התקציב, בסריקת גודל סגל."""
    best = None
    for mr in range(6, 17):
        sel, mins = ro.optimise(cand, budget, mr)
        if sel is None:
            continue
        qp = bt.score(cand[sel], "ppm", "avail")
        if best is None or qp > best[0]:
            best = (qp, sel)
    return best


# ====================================================================
def check_budget(cand, budget, club, test):
    h(f"א. האם התקציב מגביל?  —  {club} {test}")
    best = best_roster(cand, budget)
    if best is None:
        print("  אין פתרון אפשרי. אין מה לבדוק.")
        return None
    sel = best[1]
    spent = float(cand.loc[sel, "cost"].sum())
    print(f"  תקציב            : {budget:>14,.0f}")
    print(f"  עלות הסגל שנבחר  : {spent:>14,.0f}")
    print(f"  ניצול            : {spent / budget:>13.1%}")
    print(f"  גודל הסגל        : {int(sel.sum()):>14d}   "
          f"(מינימום מתמטי {int(np.ceil(ro.MINUTES_PER_GAME / ro.MAX_MIN_PLAYER))})")

    big = best_roster(cand, budget * 10)
    same = big is not None and bool((big[1] == sel).all())
    print(f"\n  עם תקציב פי 10   : "
          f"{'אותה בחירה בדיוק' if same else 'בחירה אחרת'}")

    binding = (spent / budget) > 0.95 and not same
    if binding:
        print("\n  ✅ התקציב מגביל. האופטימייזר פותר בעיית הקצאה.")
    else:
        print("\n  🔴 **התקציב אינו מגביל.** האופטימייזר אינו מקצה כסף -")
        print("  הוא מדרג לפי ppm ולוקח את הראש עד שהדקות נגמרות.")
        print("  כל מסקנה מהתרחיש הזה היא על **זיהוי כישרון**, לא על")
        print("  ניהול תקציב. וגם lambda לא יכול להשפיע: אין אילוץ")
        print("  שנלחצים עליו, ולכן אין מה להחליף במה.")
    return {"club": club, "season": test, "budget": budget,
            "spent": spent, "util": spent / budget,
            "n": int(sel.sum()), "same_x10": same, "binding": binding}


# ====================================================================
def check_sd(cand, club, test):
    h(f"ב. האם ל-ppm_sd יש פיזור בקרב המובילים?  —  {club} {test}")
    top = cand.nlargest(TOP_N, "ppm")
    cv_all = cand.ppm_sd.std() / cand.ppm_sd.mean()
    cv_top = top.ppm_sd.std() / top.ppm_sd.mean()
    print(f"  כל המאגר (n={len(cand)}): ppm_sd ממוצע "
          f"{cand.ppm_sd.mean():.4f} | מקדם שונות {cv_all:.1%}")
    print(f"  {TOP_N} המובילים    : ppm_sd ממוצע "
          f"{top.ppm_sd.mean():.4f} | מקדם שונות {cv_top:.1%}")
    print(f"  טווח בקרב המובילים : {top.ppm_sd.min():.4f}-"
          f"{top.ppm_sd.max():.4f}")

    print(f"\n  min_pg_lag בקרב המובילים: "
          f"{top.min_pg_lag.min():.1f}-{top.min_pg_lag.max():.1f} "
          f"(חציון {top.min_pg_lag.median():.1f})")
    print("  זהו המשתנה **היחיד** שממנו ppm_sd נגזר.")

    print(f"\n  כמה מהדירוג משתנה תחת ענישה:")
    print(f"{'lambda':>8}{'חפיפה עם top-8':>18}{'הפרש ppm מרבי':>18}")
    base = set(cand.nlargest(8, "ppm").player_code)
    for lam in LAMBDAS:
        p = cand.ppm - lam * cand.ppm_sd
        new = set(cand.assign(p=p).nlargest(8, "p").player_code)
        pen_spread = float((lam * top.ppm_sd).max() -
                           (lam * top.ppm_sd).min())
        print(f"{lam:>8.2f}{len(base & new)}/8{'':>13}{pen_spread:>18.4f}")

    print(f"\n  לייחוס: הפרש ה-ppm בין המוביל למקום {TOP_N} הוא "
          f"{top.ppm.max() - top.ppm.min():.4f}.")
    print("  אם פיזור הענישה קטן ממנו בהרבה, lambda אינו יכול")
    print("  להחליף שחקנים - וה'שטיחות' היא תכונה של המבחן.")

    degenerate = cv_top < 0.15
    if degenerate:
        print("\n  🔴 **הציר מנוון.** ppm_sd כמעט קבוע בקרב מי שנבחר,")
        print("  ולכן lambda*sd הוא חיסור קבוע שאינו משנה דירוג.")
        print("  'הפסימיות נדחתה' אינו ממצא - המבחן חסר עוצמה.")
        print("\n  התיקון אינו lambda גדול יותר אלא sd אחר: שגיאת")
        print("  התחזית של ה-WLS (get_prediction().se_mean), שגדלה")
        print("  עם מינוף - גיל חריג, פער עונות, מעט עונות יורוליג -")
        print("  ולא רק עם מיעוט דקות.")
    else:
        print("\n  ✅ יש פיזור. השטיחות אינה ארטיפקט של הציר.")
    return {"club": club, "cv_top": cv_top, "degenerate": degenerate}


# ====================================================================
def check_symmetry(cand, anch, club, test):
    h(f"ג. האם שני הצדדים נספרים על אותו כסף?  —  {club} {test}")
    tel = anch[(anch.club == club) & (anch.season == test)]
    real = cand[cand.team.astype(str).str.contains(club, na=False)]
    priced = set(tel.player_code)
    real_p = real[real.player_code.isin(priced)]

    q9, u9, n9 = score_verbose(real, "ppm_true", "avail_true")
    q7, u7, n7 = score_verbose(real_p, "ppm_true", "avail_true")

    print(f"  סגל המועדון במאגר      : {len(real)} שחקנים")
    print(f"  מתוכם עם שכר ידוע      : {len(real_p)}")
    print(f"  ללא שכר (חינם בהשוואה) : {len(real) - len(real_p)}")
    if len(real) > len(real_p):
        miss = real[~real.player_code.isin(priced)]
        print("\n  מי שאין לו שכר:")
        for t in miss.itertuples():
            print(f"    {str(t.player_name)[:28]:<30} "
                  f"ppm בפועל {t.ppm_true:>6.3f}  "
                  f"דקות למשחק {t.min_per_game:>5.1f}")

    print(f"\n{'גרסה':<24}{'n':>4}{'ניקוד':>10}{'דקות שמולאו':>14}"
          f"{'שיחקו':>8}")
    print(f"{'כל הסגל':<24}{len(real):>4}{q9:>10.1f}{u9:>14.1f}{n9:>8}")
    print(f"{'רק המתומחרים':<24}{len(real_p):>4}{q7:>10.1f}"
          f"{u7:>14.1f}{n7:>8}")

    short = u7 < ro.MINUTES_PER_GAME - 1
    print(f"\n  הפרש בניקוד: {q9 / q7 - 1:+.1%}")
    if short:
        print(f"  🔴 גרסת המתומחרים **לא מילאה 200 דקות** "
              f"({u7:.0f} בלבד).")
        print("  הניקוד הנמוך שלה אינו איכות אלא גודל סגל. לצמצם את")
        print("  המועדון לשחקנים המתומחרים אינו תיקון - הוא מחליף")
        print("  הטיה אחת באחרת.")
        print("\n  התיקון הנכון: מילוי ברמת החלפה בשני הצדדים, בדיוק")
        print("  כמו ב-roster_optimizer. קבוצה לא משחקת 4 על 5, וגם")
        print("  לא 200 דקות עם 7 שחקנים.")
    else:
        print("  שתי הגרסאות מילאו 200 דקות. ההפרש הוא איכות בלבד.")
    return {"club": club, "n_free": len(real) - len(real_p),
            "q_all": q9, "q_priced": q7, "short": short}


# ====================================================================
def main():
    print(SEP)
    print("דיאגנוסטיקה של הבקטסט — האם המבחן יכול היה להראות אחרת?")
    print(SEP)
    feat, anch, pos, ps = bt.load_all()

    rows_b, rows_s, rows_y = [], [], []
    for club, train_max, test in SCENARIOS:
        bt.TRAIN_MAX, bt.TEST, bt.TARGET_CLUB = train_max, test, club
        cm, smear, agg, am, pm, PF, lagged = bt.fit_models(ps, feat, anch)
        cand = bt.build(lagged, feat, pos, cm, smear, agg, am, pm, PF,
                        bt.scale_for(anch, club, test))
        cand["ppm_true"] = cand.pir_per_game / cand.min_per_game
        cand["avail_true"] = cand.frac
        cand = ps_mod.add_sd(cand, lagged)

        tel = anch[(anch.club == club) & (anch.season == test)]
        visible = tel[tel.player_code.isin(set(cand.player_code))]
        B_fair = float(visible.salary_mid.sum())

        r = check_budget(cand, B_fair, club, test)
        if r:
            rows_b.append(r)
        rows_s.append(check_sd(cand, club, test))
        rows_y.append(check_symmetry(cand, anch, club, test))

    h("מה זה עושה לשלוש התוצאות")
    for r in rows_b:
        tag = "הקצאה תחת מחסור" if r["binding"] else "דירוג ללא אילוץ"
        print(f"  {r['club']} {r['season']}: ניצול {r['util']:.0%} -> {tag}")
    if any(not r["binding"] for r in rows_b):
        print("\n  תרחיש שבו התקציב אינו מגביל אינו מאמת את המנוע")
        print("  כמכשיר אופטימיזציה. הוא מאמת את מודל התפוקה בלבד.")
    if all(r["degenerate"] for r in rows_s):
        print("\n  ציר ה-lambda מנוון בשני התרחישים. אין להסיק ממנו")
        print("  שהפסימיות לא עוזרת - רק שהמבחן הזה לא בדק אותה.")
    if any(r["short"] for r in rows_y):
        print("\n  ההשוואה מול המועדון רגישה לשאלה מי נספר. המספר")
        print("  שדווח (+21.2%) תלוי בהחלטה שלא הוצדקה.")
    print(SEP)


if __name__ == "__main__":
    main()