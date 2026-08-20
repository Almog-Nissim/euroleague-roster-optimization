"""
fetch_boxscores.py  (Day 7, v2)
-------------------------------
מושך בוקסקור ברמת משחק — עם ויסות קצב, נסיגה מדורגת, שמירת
ביניים, ו**כישלון רועש**.

--------------------------------------------------------------------
למה נכתב מחדש
--------------------------------------------------------------------
`get_players_boxscore_stats_single_season` יורה כ-3 בקשות בשנייה
ומקבל **429 Too Many Requests**. וגרוע מזה — הוא מדפיס

    Skip and continue.

ו**ממשיך**. אילו ההרצה הייתה מסתיימת, היה נוצר קובץ שנראה תקין
וחסרים בו עשרות משחקים **בלי שאיש יידע**.

זו בדיוק המשפחה שסומנה ביום 6:
    "בדיקת עשן שבודקת רק exit=0 היא אותו באג."

הקובץ הזה עושה את ההפך: אם משחק חסר, הוא **נכשל ואומר אילו**.
עונה חלקית לעולם אינה נשמרת בשם הסופי.

--------------------------------------------------------------------
המבנה
--------------------------------------------------------------------
1. שולפים את רשימת ה-gamecodes של העונה
2. מושכים אחד-אחד עם `SLEEP` בין בקשות
3. על 429 — נסיגה מדורגת (2, 4, 8, 16, 32 שניות), עד `MAX_RETRY`
4. כל `CHKPT` משחקים נשמרת טיוטה `..._partial.csv`
5. הרצה חוזרת **ממשיכה** מהטיוטה ולא מושכת מחדש
6. בסוף — אימות שכל ה-gamecodes קיימים. חסר -> חריגה

⚠️ `gamecode` הוא **מזהה ולא מספר** (באג 1 של יום 4, חזר ביום 6).
הוא מוחזק כמחרוזת לכל אורך הדרך.

הרצה:
    python src/fetch_boxscores.py 2025
    python src/fetch_boxscores.py 2024 2025
"""

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import RAW_DIR

from euroleague_api.boxscore_data import BoxScoreData

SLEEP = 1.8          # שניות בין בקשות. 2.2/שנ' הפיל אותנו ב-429
MAX_RETRY = 6
CHKPT = 25
SEP = "=" * 74


def with_retry(fn, what, tries=MAX_RETRY, wait=15.0):
    """נסיגה מדורגת סביב **כל** קריאת רשת.

    ⚠️ בגרסה הראשונה עטפתי רק את משיכת המשחקים ולא את שליפת
    רשימת ה-gamecodes — ואז 429 על הקריאה הראשונה הפיל את
    כל הריצה מיד. אותה משפחה: הגנתי על הלולאה ולא על הכניסה
    אליה.
    """
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as exc:                      # noqa: BLE001
            last = exc
            if "429" not in str(exc) and "Too Many" not in str(exc):
                raise
            print(f"    429 על {what} — ממתין {wait:.0f} שנ' "
                  f"(ניסיון {i + 1}/{tries})")
            time.sleep(wait)
            wait = min(wait * 2, 240)
    raise RuntimeError(
        f"🔴 {what}: 429 גם אחרי {tries} ניסיונות.\n"
        f"   זו חסימה ברמת ה-IP ולא קצב — ההרצה הקודמת שרפה את\n"
        f"   המכסה. **המתן 20-30 דקות** והרץ שוב. הטיוטה נשמרת,\n"
        f"   ולכן שום דבר שכבר נמשך לא יימשך שוב.\n"
        f"   המקור: {last}")


def gamecodes(b, season):
    """רשימת ה-gamecodes של העונה, כמחרוזות."""
    gc = with_retry(lambda: b.get_gamecodes_season(season),
                    f"רשימת המשחקים של {season}")
    col = next((c for c in gc.columns
                if c.lower() in ("gamecode", "game_code", "gamenumber")), None)
    if col is None:
        raise ValueError(f"לא נמצאה עמודת gamecode ב-{gc.columns.tolist()}")
    return [str(v) for v in gc[col].tolist()]


def fetch_one(b, season, gc):
    """משחק אחד, עם נסיגה מדורגת. מחזיר DataFrame או None (לא נמצא).

    None מוחזר **רק** כשהשרת אומר במפורש שאין משחק כזה. 429 או
    שגיאת רשת אינם None — הם ניסיון נוסף, ואם נגמרו הניסיונות
    הפונקציה **זורקת**.
    """
    wait = 2.0
    last = None
    for attempt in range(MAX_RETRY):
        try:
            df = b.get_players_boxscore_stats(season, gc)
            if df is None or not len(df):
                return None
            return df
        except Exception as exc:          # noqa: BLE001
            last = exc
            msg = str(exc)
            if "429" in msg or "Too Many" in msg or "Connection" in msg:
                print(f"    429/רשת על {gc} — ממתין {wait:.0f} שנ' "
                      f"(ניסיון {attempt + 1}/{MAX_RETRY})")
                time.sleep(wait)
                wait *= 2
                continue
            if "404" in msg or "not find" in msg.lower():
                return None
            time.sleep(wait)
            wait *= 2
    raise RuntimeError(f"נכשל על gamecode {gc} אחרי {MAX_RETRY} ניסיונות: "
                       f"{last}")


def fetch_season(season):
    final = RAW_DIR / f"boxscore_player_{season}.csv"
    part = RAW_DIR / f"boxscore_player_{season}_partial.csv"
    if final.exists():
        print(f"  [{season}] קיים ומאומת — מדלג")
        return pd.read_csv(final, dtype=str)

    b = BoxScoreData(competition="E")
    codes = gamecodes(b, season)
    print(f"  [{season}] {len(codes)} משחקים ברשימה")

    done, frames = set(), []
    if part.exists():
        prev = pd.read_csv(part, dtype=str)
        frames.append(prev)
        done = set(prev.Gamecode.astype(str))
        print(f"  [{season}] ממשיך מטיוטה — {len(done)} משחקים כבר בידינו")

    todo = [c for c in codes if c not in done]
    missing, t0 = [], time.time()
    for i, gc in enumerate(todo, 1):
        df = fetch_one(b, season, gc)
        if df is None:
            missing.append(gc)
        else:
            df = df.copy()
            df["Gamecode"] = str(gc)
            df["Season"] = str(season)
            frames.append(df)
        if i % CHKPT == 0 or i == len(todo):
            pd.concat(frames, ignore_index=True).to_csv(part, index=False)
            el = time.time() - t0
            print(f"    {i}/{len(todo)}  ({el:.0f} שנ', "
                  f"נותרו ~{el / i * (len(todo) - i):.0f} שנ')")
        time.sleep(SLEEP)

    out = pd.concat(frames, ignore_index=True)
    got = set(out.Gamecode.astype(str))
    absent = [c for c in codes if c not in got]

    print(f"\n  [{season}] {len(out)} שורות · {len(got)} משחקים "
          f"מתוך {len(codes)}")
    if absent:
        # לא שומרים עונה חלקית בשם הסופי. הטיוטה נשארת כדי
        # שהרצה חוזרת תמשיך ולא תתחיל מאפס.
        raise RuntimeError(
            f"🔴 חסרים {len(absent)} משחקים ב-{season}: "
            f"{absent[:15]}{'...' if len(absent) > 15 else ''}\n"
            f"   הטיוטה נשמרה ב-{part.name} — הרץ שוב כדי להשלים.\n"
            f"   **הקובץ הסופי לא נכתב.** עונה חלקית אינה נשמרת.")

    out.to_csv(final, index=False)
    part.unlink(missing_ok=True)
    print(f"  ✅ [{season}] נשמר {final.name}")
    return out


def main(seasons):
    """🔴 יום 10: ריצת אצווה על 7 עונות.

    הגרסה הקודמת זרקה חריגה על עונה חסרה, וכך **הרגה את כל
    האצווה** — עונה אחת שנפלה על 429 מנעה משש האחרות לרוץ.
    עכשיו כל עונה נתפסת בנפרד, הטיוטה שלה נשמרת, והריצה
    ממשיכה. בסוף מודפס סיכום.

    הרצה חוזרת משלימה רק את מה שחסר — הטיוטות נשארות.
    """
    seasons = [int(x) for x in seasons]
    print(f"{SEP}\nאצווה: {len(seasons)} עונות — "
          + ", ".join(map(str, seasons)) + f"\n{SEP}")
    ok, failed, t0 = [], [], time.time()
    for s in seasons:
        print(f"\n{SEP}\nעונה {s}\n{SEP}")
        try:
            df = fetch_season(s)
            ok.append((s, len(df)))
            print(f"  עמודות: {df.columns.tolist()}")
        except Exception as exc:
            failed.append((s, str(exc).splitlines()[0]))
            print(f"  🔴 {s} לא הושלמה — ממשיך לעונה הבאה.")
            print(f"     {str(exc).splitlines()[0]}")

    el = time.time() - t0
    print(f"\n{SEP}\nסיכום אצווה   ({el/60:.0f} דקות)\n{SEP}")
    for s, n in ok:
        print(f"  ✅ {s}   {n:,} שורות")
    for s, why in failed:
        print(f"  🔴 {s}   {why}")
    if failed:
        print(f"\n  {len(failed)} עונות לא הושלמו. הטיוטות נשמרו —")
        print("  הרץ את אותה פקודה שוב והיא תמשיך מהנקודה שנעצרה.")
        print("  אם 429 חוזר, העלה את SLEEP מ-0.8 ל-1.5.")
    else:
        print("\n  הבא: python src/split_multiclub.py "
              + " ".join(str(s) for s, _ in ok))
    print(SEP)
    return len(failed)


DEFAULT_SEASONS = "2016 2017 2018 2019 2020 2021 2022 2023"


def parse_seasons(argv):
    """מקבל כל צורה: ארגומנטים, מחרוזת עם פסיקים, או ברירת מחדל.

    🔴 PyCharm מריץ בלי ארגומנטים, ולכן הרשימה נכתבה כמחרוזת
       אחת עם פסיקים ו-int() נפל עליה. פרסור סובלני פותר את זה
       פעם אחת לכל צורות ההרצה.
    """
    raw = " ".join(argv) if argv else DEFAULT_SEASONS
    out = []
    for tok in raw.replace(",", " ").split():
        tok = tok.strip()
        if not tok:
            continue
        if not tok.isdigit():
            raise SystemExit(f"עונה לא חוקית: {tok!r}. צפוי מספר, למשל 2016.")
        out.append(int(tok))
    if not out:
        raise SystemExit("לא נמסרו עונות.")
    return out


if __name__ == "__main__":
    sys.exit(main(parse_seasons(sys.argv[1:])))