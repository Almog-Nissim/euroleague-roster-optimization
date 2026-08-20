"""
diagnose_2018.py — לענות על שאלה אחת: למה gamecode 21 בעונת 2018 נופל.

תחזית נעולה לפני ההרצה
----------------------
אני צופה שזה **לא** 429. הנימוק: שישה כישלונות רצופים על אותו מזהה
בדיוק, אחרי 20 משחקים שעברו חלק. Rate limiting מתפוגג עם השהיה,
הוא לא נועל את עצמו על מזהה יחיד.

התחזית: אחת משתיים —
  (א) HTTP 404 / תגובה ריקה — המשחק לא קיים בפיד בעונה הזו
  (ב) HTTP 200 עם גוף שאינו JSON (HTML של שגיאה) -> JSONDecodeError

אם דווקא כן יחזור 429 עקבי על 21 ולא על 20 ו-22, התחזית שלי שגויה
וצריך להסתכל על משהו אחר לגמרי.

הרצה:  python src/diagnose_2018.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_api import fetch, make_session  # noqa: E402

SEASON = 2018
PROBES = [19, 20, 21, 22, 23]


def main() -> int:
    session = make_session()
    print("=" * 74)
    print(f"אבחון עונה {SEASON} — gamecodes {PROBES}")
    print("=" * 74)

    results = {}
    for gc in PROBES:
        url = "https://live.euroleague.net/api/Boxscore"
        params = {"gamecode": gc, "seasoncode": f"E{SEASON}"}
        # retries=2 בכוונה: אנחנו מאבחנים, לא מושכים
        res = fetch(session, url, params=params, retries=2, sleep=1.5)
        results[gc] = res
        print(f"\n--- gamecode {gc} ---")
        print(res.describe())
        if res.ok and isinstance(res.payload, dict):
            stats = res.payload.get("Stats") or res.payload.get("stats")
            n = len(stats) if isinstance(stats, list) else "?"
            print(f"  קבוצות בתגובה: {n}")

    print("\n" + "=" * 74)
    print("קריאת התוצאה")
    print("=" * 74)

    ok = [gc for gc, r in results.items() if r.ok]
    bad = [gc for gc, r in results.items() if not r.ok]

    print(f"  עברו : {ok}")
    print(f"  נפלו : {bad}")

    if bad == [21]:
        r = results[21]
        print("\n  ✅ מבודד ל-21 בלבד -> זה הדאטה, לא הקצב.")
        print(f"     הסיבה בפועל: {r.error_type} / {r.error_repr}")
        print("     הפעולה: לרשום ל-failed_games.csv ולהמשיך. אל תעלה SLEEP.")
    elif len(bad) >= 3:
        print("\n  🔴 נפלו כמה ברצף -> זה כן נראה כמו קצב או חסימה.")
        print("     הפעולה: להעלות SLEEP, ולבדוק אם ה-IP נחסם.")
    elif not bad:
        print("\n  ⚠️ הכול עבר עכשיו. כלומר הכשל היה חולף.")
        print("     המשמעות: הריטריי הקודם לא היה אגרסיבי מספיק, או שהפיד היה למטה.")
        print("     זה עדיין מחייב את התיקון המבני — משחק בודד לא יפיל עונה.")
    else:
        print(f"\n  ⚠️ תמונה מעורבת: {bad}. קרא את ה-error_type של כל אחד למעלה.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())