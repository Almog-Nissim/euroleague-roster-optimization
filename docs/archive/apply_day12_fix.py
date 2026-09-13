"""apply_day12_fix.py — מבצע את שבע העריכות של יום 12 ישירות.

בלי git, בלי patch, בלי בעיות סוף-שורה של Windows.

הרצה מתיקיית הפרויקט הראשית:

    python apply_day12_fix.py

בטוח להרצה חוזרת: אם עריכה כבר בוצעה, היא מדולגת.

--------------------------------------------------------------------
מה זה מתקן
--------------------------------------------------------------------
חמש פונקציות LP בונות משתני PuLP לפי **מיקום** (`range(n)`) ושולפות
קבוצות לפי **תווית** (`pool.index[...]`). כל עוד המאגר מגיע עם
אינדקס רציף 0..n-1 השניים זהים והקוד עובד. הרציפות נשמרה בשורה
אחת ב-`league_backtest.build_pool`, 130 שורות משם, ואף בדיקה לא
ידעה שהיא קיימת.

`sort_values` בלי `reset_index` שובר את זה **בשקט**: אותו מספר
שחקנים, בלי שגיאה, סגל אחר.

ושתי עריכות נפרדות לרשימות `locked`: איפוס בתוך הפונקציה אינו
מתקן אותן, כי הן נבנו במרחב התוויות של הקורא לפני הקריאה.
"""

import io
import os
import sys
from pathlib import Path

GUARD = ("    pool = pool.reset_index(drop=True)   "
         "# אינדקס מיקומי — locked ו-POS_FLOOR נשענים עליו\n")

# (קובץ, העוגן שלפניו מוסיפים את השורה)
LP_SITES = [
    ("src/optimise_consistent.py",
     '    p = pulp.LpProblem("roster_v2", pulp.LpMaximize)'),
    ("src/usage_constrained.py",
     '    p = pulp.LpProblem("roster_capped", pulp.LpMaximize)'),
    ("src/minute_profile.py",
     '    p = pulp.LpProblem("roster_v3", pulp.LpMaximize)'),
    ("src/v0_pipeline.py",
     '    p = pulp.LpProblem("roster", pulp.LpMaximize)'),
    ("src/roster_optimizer.py",
     '    p = pulp.LpProblem("roster", pulp.LpMaximize)'),
]

# (קובץ, לפני, אחרי)
LOCKED_SITES = [
    ("src/quota_cost.py",
     "        idx = list(cand.index[cand.player_code.astype(str).isin(isr)])",
     "        idx = list(np.flatnonzero(\n"
     "            cand.player_code.astype(str).isin(isr).to_numpy()))"
     "   # מיקומי"),
    ("src/roster_optimizer.py",
     "    isr = list(pool.index[pool.is_israeli == 1])",
     "    isr = list(np.flatnonzero((pool.is_israeli == 1).to_numpy()))"
     "   # מיקומי"),
]

ok, skipped, failed = 0, 0, 0


def report(status, path, note=""):
    global ok, skipped, failed
    mark = {"ok": "✅", "skip": "⏭", "fail": "❌"}[status]
    if status == "ok":
        ok += 1
    elif status == "skip":
        skipped += 1
    else:
        failed += 1
    print(f"  {mark} {path:<32} {note}")


def read(p):
    return Path(p).read_text(encoding="utf-8")


def write(p, s):
    # newline="" משמר את סוף-השורה המקורי של הקובץ
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def find_root():
    """מוצא את תיקיית הפרויקט בלי תלות במאיפה הריצו.

    PyCharm מגדיר לעיתים את תיקיית העבודה ל-src/, ולכן חיפוש
    ב-cwd בלבד אינו מספיק.
    """
    cands = [Path.cwd()] + list(Path.cwd().parents)
    cands += [Path(__file__).resolve().parent]
    cands += list(Path(__file__).resolve().parents)
    seen = set()
    for c in cands:
        if c in seen:
            continue
        seen.add(c)
        if (c / "src" / "optimise_consistent.py").exists():
            return c
    return None


def main():
    root = find_root()
    if root is None:
        print("⛔ לא נמצאה תיקיית הפרויקט (src/optimise_consistent.py).")
        print(f"   הרצה מ: {Path.cwd()}")
        print("   שים את הסקריפט בתיקיית הפרויקט הראשית ונסה שוב.")
        return 1
    os.chdir(root)
    print(f"תיקיית הפרויקט: {root}\n")

    print("=" * 66)
    print("apply_day12_fix — שבע עריכות")
    print("=" * 66)

    print("\nא. חמש פונקציות LP")
    for path, anchor in LP_SITES:
        p = Path(path)
        if not p.exists():
            report("fail", path, "הקובץ לא נמצא")
            continue
        s = read(p)
        if "pool = pool.reset_index(drop=True)" in s:
            report("skip", path, "כבר מתוקן")
            continue
        n = s.count(anchor)
        if n != 1:
            report("fail", path, f"העוגן נמצא {n} פעמים, צריך 1")
            continue
        write(p, s.replace(anchor, GUARD + anchor, 1))
        report("ok", path, "שורת ההגנה נוספה")

    print("\nב. שתי רשימות locked")
    for path, old, new in LOCKED_SITES:
        p = Path(path)
        if not p.exists():
            report("fail", path, "הקובץ לא נמצא")
            continue
        s = read(p)
        if "np.flatnonzero" in s and old not in s:
            report("skip", path, "כבר מתוקן")
            continue
        n = s.count(old)
        if n != 1:
            report("fail", path, f"השורה נמצאה {n} פעמים, צריך 1")
            continue
        write(p, s.replace(old, new, 1))
        report("ok", path, "עבר למיקומים")

    print("\n" + "-" * 66)
    print(f"  בוצעו {ok} · דולגו {skipped} · נכשלו {failed}")
    if failed:
        print("\n⛔ יש כשלים. פתח את FIX_manual.md וערוך ידנית "
              "את מה שנכשל.")
        return 1
    print("\n✅ הכל הוחל. עכשיו:")
    print("     python src/index_invariance_test.py")
    print("   צריך לתת 9/9.")
    return 0


if __name__ == "__main__":
    sys.exit(main())