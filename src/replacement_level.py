"""
replacement_level.py  (Day 7)
-----------------------------
מודד את רמת המחליף במקום להמציא אותה.

--------------------------------------------------------------------
מה זה "מחליף" ולמה זה מכריע
--------------------------------------------------------------------
בניקוד, סגל צריך לכסות 200 דקות למשחק. שחקן משחק לכל היותר 32
דקות ונספר לפי שיעור המשחקים שבהם היה זמין. סגל של 7 מכסה בפועל
כ-167 דקות — **33 חסרות בכל משחק**, ומישהו משחק אותן.

עד היום המספר היה `REPLACEMENT_PCTL = 10`: אחוזון 10 של **מאגר
המועמדים**. יום 6 סימן אותו כ"הצהרה שאי אפשר למדוד" וכציר רגישות
שיכול להפוך את מסקנת גודל הסגל.

הוא גם **מוטה כלפי מעלה מבנית**: מאגר המועמדים כולל רק מי ששיחק
ביורוליג בעונה הקודמת, כלומר החלשים כבר סוננו ממנו. "המחליף"
שיצא הוא שחקן יורוליג בינוני-חלש, לא מי שחותמים בדחיפות בינואר.

--------------------------------------------------------------------
המדידה
--------------------------------------------------------------------
במקום אחוזון שרירותי — **האוכלוסייה שבאמת ממלאת דקות**: שחקנים
ששיחקו מעט משחקים ואינם עוגני שכר בשום מועדון.

אלמוג מסר את שני המקרים של מכבי 24/25 מתוך היכרות:
    עומר מאייר  — עלה מהנוער, מתחת לגיל 18, **חינם**   ppm 0.243
    אלפא קאבה   — חוזה כחודש, שוחרר                    ppm 0.000
    ממוצע                                              **0.122**

--------------------------------------------------------------------
איזה סטטיסטי
--------------------------------------------------------------------
**הממוצע, לא החציון.** ב-`score` הדקות שנשארו מוכפלות במספר הזה
פעם אחת, דטרמיניסטית — כלומר הוא נכנס כתוחלת. רבע מאוכלוסיית
הממלאים תורמת 0.000 בדיוק, והחציון מתעלם מהזנב הזה ומנפח את
המחליף בכ-45%.

הרצה:
    python src/replacement_level.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR

MAX_GAMES = 10          # "מילא דקות" ולא היה חלק מהרוטציה
SEP = "=" * 74


def load():
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    anch = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                       dtype={"player_code": str})
    d = ps[ps.min_per_game > 0].copy()
    d["ppm"] = d.pir_per_game / d.min_per_game
    d["anchor"] = d.player_code.astype(str).isin(
        set(anch.player_code.dropna().astype(str)))
    return d


def measure(d, season=None, max_games=MAX_GAMES):
    """רמת המחליף: תוחלת ה-ppm של מי שממלא דקות.

    season=None -> כל העונות (יציב, מומלץ).
    """
    sub = d[(d.games <= max_games) & (~d.anchor)]
    if season is not None:
        sub = sub[sub.season == season]
    if len(sub) < 30:
        return np.nan, len(sub)
    return float(sub.ppm.mean()), len(sub)


def main():
    d = load()
    print(SEP)
    print("רמת מחליף — נמדדת, לא מונחת")
    print(SEP)

    print("\n1. שני המקרים של מכבי 24/25 (זוהו על ידי אלמוג)")
    for code, lab in [("11433", "מאייר (נוער, חינם)"),
                      ("7855", "קאבה (חוזה זמני)")]:
        r = d[(d.season == 2024) & (d.player_code.astype(str) == code)]
        if len(r):
            print(f"   {lab:<26} ppm = {float(r.ppm.iloc[0]):.3f}")
    two = d[(d.season == 2024) &
            (d.player_code.astype(str).isin(["11433", "7855"]))].ppm.mean()
    print(f"   {'ממוצע השניים':<26} ppm = {two:.3f}")

    print(f"\n2. אוכלוסיית הממלאים בכל הליגה "
          f"(<= {MAX_GAMES} משחקים, לא עוגן שכר)")
    sub = d[(d.games <= MAX_GAMES) & (~d.anchor)]
    print(f"   n = {len(sub)}")
    print(f"   {'ממוצע  (הסטטיסטי הנכון)':<30}{sub.ppm.mean():>8.3f}")
    print(f"   {'חציון':<30}{sub.ppm.median():>8.3f}")
    print(f"   {'אחוזון 25':<30}{sub.ppm.quantile(.25):>8.3f}")
    print(f"   {'שיעור שתורמים בדיוק 0.000':<30}"
          f"{(sub.ppm == 0).mean():>8.1%}")

    lvl, n = measure(d)
    print(f"\n3. ההשוואה")
    print(f"   {'מכבי — שני מקרים':<34}{two:>8.3f}")
    print(f"   {'הליגה — ' + str(n) + ' תצפיות':<34}{lvl:>8.3f}")
    print(f"   הפרש: {abs(two - lvl):.3f}  — שני מקורות בלתי תלויים")

    print(f"\n4. מול ההנחה הישנה")
    feat_pool = d[d.season.isin([2024, 2025])]
    for s in (2024, 2025):
        p10 = float(np.percentile(d[d.season == s].ppm, 10))
        print(f"   אחוזון 10 של עונת {s}: {p10:.3f}")
    print(f"   בקוד (על מאגר המועמדים, שממנו סוננו החלשים): "
          f"~0.175-0.192")
    print(f"   🔴 ההנחה גבוהה ב-{0.19 / lvl - 1:.0%} מהמדידה.")

    print(f"\n5. יציבות — האם המספר תלוי בעונה או בסף")
    print(f"   {'סף משחקים':<14}{'n':>6}{'ממוצע':>10}")
    for mg in (5, 8, 10, 12, 15):
        v, nn = measure(d, max_games=mg)
        print(f"   <= {mg:<11}{nn:>6}{v:>10.3f}")
    print(f"\n   {'עונה':<14}{'n':>6}{'ממוצע':>10}")
    for s in sorted(d.season.unique()):
        v, nn = measure(d, season=int(s))
        print(f"   {int(s):<14}{nn:>6}{v:>10.3f}" if not np.isnan(v)
              else f"   {int(s):<14}{nn:>6}{'—':>10}")

    print(f"\n{SEP}")
    print(f"REPLACEMENT_PPM = {lvl:.3f}   (במקום אחוזון 10)")
    print("הכיוון: המחליף גרוע מההנחה -> עומק שווה יותר ->")
    print("מסקנת 'סגל של 8 עדיף על 16' מיום 6 עלולה להתהפך.")
    print(SEP)
    return lvl


if __name__ == "__main__":
    main()
