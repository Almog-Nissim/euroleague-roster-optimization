"""
player_id.py — נרמול מזהה שחקן. מקום אחד, לא שישה.

הכלל
----
`player_season` שומר את אותו קוד כמו הבוקסקור, בלי ה-`P` המוביל,
ובלי אפסים מובילים כשהקוד מספרי.

    P012099  ->  012099  ->  12099
    PTGB     ->  TGB
    PBMT     ->  BMT

כלומר: להסיר `P` מוביל, ואז אפסים מובילים אם מה שנשאר מספרי.

למה זה קריטי
------------
בשער האימות הנרמול ש"ניצח" היה `digits only` עם 89.6% חפיפה,
והוא הופך את `PTGB` ואת `PBMT` למחרוזת **ריקה**. 83 שחקנים
מתמוטטים למפתח אחד — ואלה לא שחקני שוליים:

    LLULL, SERGIO        5,228 דקות · 10 עונות
    RODRIGUEZ, SERGIO    4,921 דקות
    FERNANDEZ, RUDY      4,260 דקות
    DATOME, LUIGI        4,025 דקות
    SHVED, ALEXEY        3,667 דקות

אלה בעלי הדקות הגבוהות ביורוליג בעשור. צירוף לפי ספרות היה
מוחק מהמאגר בדיוק את השחקנים שהאופטימייזר הכי רוצה.

זו המשפחה של הבאג מיום 9 — `lstrip('P')` שהשאיר `'012099'`,
"חפיפה 6 במקום 263, פעם חמישית". ההבדל: שם חסרו האפסים, כאן
חסרו האותיות.

הרצה כבדיקה:  python src/player_id.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

_LEADING_P = re.compile(r"^P", re.IGNORECASE)


def canonical(value) -> str:
    """מזהה בודד -> צורה קנונית."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    if not s:
        return ""
    s = _LEADING_P.sub("", s, count=1)
    if s.isdigit():
        s = s.lstrip("0") or "0"
    return s


def canonical_series(s: pd.Series) -> pd.Series:
    return s.map(canonical)


def collisions(s: pd.Series) -> pd.DataFrame:
    """
    מזהים גולמיים שונים שנופלים לאותה צורה קנונית.

    ⚠️ הבדיקה הזו היא כל העניין. נרמול שמקריס שני שחקנים לאחד גרוע
    יותר מנרמול שלא מתאים כלום, כי הוא נכשל בשקט.
    """
    df = pd.DataFrame({"raw": s.astype(str).str.strip()}).drop_duplicates()
    df["canon"] = canonical_series(df["raw"])
    df = df[df["canon"] != ""]
    dup = df.groupby("canon")["raw"].agg(list)
    return dup[dup.map(len) > 1].reset_index()


def _self_test() -> int:
    from el_paths import load_boxscores, repo_root, resolve  # noqa: E402

    print(f"שורש הריפו: {repo_root()}")

    cases = [
        ("P012099", "12099"), ("PTGB", "TGB"), ("PBMT", "BMT"),
        ("P004863", "4863"), ("  P012099  ", "12099"), ("P000000", "0"),
        ("", ""), (None, ""), ("TGB", "TGB"),
    ]
    print("\nמקרי יחידה:")
    bad = 0
    for raw, want in cases:
        got = canonical(raw)
        ok = got == want
        bad += not ok
        print(f"  {'✅' if ok else '🔴'} {raw!r:<14} -> {got!r:<10} (צפוי {want!r})")
    if bad:
        print(f"\n🔴 {bad} מקרים נכשלו.")
        return 1

    bx = load_boxscores(verbose=False)
    pid = bx["Player_ID"].astype(str).str.strip()
    pid = pid[~pid.str.upper().isin(["TEAM", "TOTAL", "NAN", ""])]

    print("\n" + "=" * 74)
    print("התנגשויות בתוך הבוקסקור")
    print("=" * 74)
    col = collisions(pid)
    if len(col):
        print(f"  🔴 {len(col)} התנגשויות:")
        print(col.head(20).to_string(index=False))
        return 1
    print(f"  ✅ אין. {pid.nunique():,} מזהים ייחודיים נשארו ייחודיים.")

    ps_path = resolve("data/processed/player_season.csv")
    if not ps_path.exists():
        print(f"\n⚠️ לא נמצא {ps_path}")
        return 0

    ps = pd.read_csv(ps_path, dtype=str, low_memory=False)
    code_col = next((c for c in ps.columns
                     if c.lower() in ("player_code", "player_id", "code")), None)
    if code_col is None:
        print(f"\n⚠️ לא זוהתה עמודת קוד: {list(ps.columns)}")
        return 0

    a = set(canonical_series(pid).unique()) - {""}
    b = set(canonical_series(ps[code_col]).unique()) - {""}

    print("\n" + "=" * 74)
    print("חפיפה מול player_season")
    print("=" * 74)
    print(f"  בוקסקור       : {len(a):,}")
    print(f"  player_season : {len(b):,}")
    print(f"  חפיפה         : {len(a & b):,}  ({len(a & b) / len(a):.1%} מהבוקסקור)")
    print(f"  רק בבוקסקור   : {len(a - b):,}")
    print(f"  רק ב-player_season: {len(b - a):,}")

    if len(a & b) / len(a) > 0.95:
        print("\n  ✅ התפר סגור. השתמש ב-canonical() בכל צירוף.")
    else:
        print(f"\n  ⚠️ {len(a - b)} מזהים עדיין לא נמצאים — צפוי אם 2021 טרם")
        print("     נכנסה ל-player_season (47 שחקנים ששיחקו רק שם).")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())