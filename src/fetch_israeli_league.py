"""
fetch_israeli_league.py  (Day 6)
--------------------------------
מושך סטטיסטיקה אישית מליגת העל הישראלית מ-basket.co.il.

--------------------------------------------------------------------
למה זה נדרש
--------------------------------------------------------------------
המנוע מתעלם מ-36% מתקציב מכבי - שישה שחקנים שאין להם עונת יורוליג
קודמת, ולכן אין להם pir_lag, ולכן הם נופלים מהמאגר. גור לביא הוא
הדוגמה: 500K בעוגנים שלנו, בלתי נראה למודל, ובליגה המקומית
30.5 דקות למשחק ומדד 19.0.

וזו לא בעיה שולית: מכבי משחקת **שתי מסגרות**. מכסת המקומיים
והליגה המקומית הן חלק ממבנה הסגל, והמודל הנוכחי רואה רק יורוליג.

**"מדד" באתר הוא PIR** - אותה מטריקה בדיוק. אין המרה.
--------------------------------------------------------------------

    stats-individual.asp?cYear=2025&sType=TO&local=1&StatsBoard=0&c=1
                          ^עונה      ^שלב    ^ישראלים        ^סדירה  ^עמוד

    cYear       שנת סיום העונה. 2025 = עונת 2024-25
    local       1 = ישראלים בלבד · 0 = כולם
    StatsBoard  0 = עונה סדירה · 1 = פלייאוף
    c           מספר עמוד, 20 שורות בעמוד

--------------------------------------------------------------------
משמעת
--------------------------------------------------------------------
1. **מצב probe קודם.** עמוד אחד, הדפסת המבנה, ואישור ידני - לפני
   שמושכים עשרות עמודים. אותו לקח מ-positions_probe שניסה 330
   קריאות למועמד.
2. השהיית נימוס בין בקשות.
3. זורק ולא מדפיס OK: אם עמוד חוזר ריק, אם העמודות משתנות בין
   עונות, או אם מספר השורות אינו כמצופה.

הרצה:
    python src/fetch_israeli_league.py            # probe - עמוד אחד
    python src/fetch_israeli_league.py --full     # משיכה מלאה

**ברירת המחדל היא probe בכוונה.** PyCharm מריץ בלי ארגומנטים,
והרצה בשוגג לא אמורה להעמיס על אתר של צד שלישי. משיכה מלאה
דורשת --full מפורש.

תלויות: requests, lxml
"""

import argparse
import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import RAW_DIR, PROCESSED_DIR

BASE = "https://basket.co.il/stats-individual.asp"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
SLEEP = 2.0
MAX_PAGES = 30           # חוסם ריצה בורחת
ENCODINGS = ("windows-1255", "utf-8", "iso-8859-8")
OUT = "israeli_league_players_local{local}.csv"

# 🔴 אי-התאמת מספור שנים - נתפס לפני המשיכה המלאה
#
#   אצלנו        season=2025  ->  עונת 2025-26  (שנת התחלה)
#   basket.co.il cYear=2026   ->  עונת 2025-26  (שנת סיום)
#
#   ולכן:  season = cYear - 1
#
# בלי התיקון כל שורה נכנסת בהיסט של עונה שלמה, וההצלבה מצליחה
# בשקט על הדאטה הלא נכון. שתי העמודות נשמרות כדי שניתן יהיה
# לאמת מול האתר.
SEASON_OFFSET = -1

# העמודות כפי שהאתר מציג אותן. הבדיקה היא על נוכחות, לא על סדר.
NEED = ["שם", "קבוצה", "מדד"]

# מבנה הטבלה באתר (אומת ב-probe):
#   שורה 0  כותרת ממוזגת על כל הרוחב
#   שורה 1  כותרות-על:  2 נק' · 3 נק' · ריבאונדים · עבירות · חסימות
#   שורה 2  הכותרות האמיתיות
#   שורה 3+ דאטה, 20 שורות לעמוד
#
# 'של' ו'על' מופיעים פעמיים - גם בעבירות וגם בחסימות. לכן שם
# העמודה נבנה כ"קבוצת-על + כותרת", אחרת שתי עמודות שונות מקבלות
# את אותו שם ואחת מהן נעלמת בשקט.
HEADER_KEYS = ("שם שחקן", "מדד")

# מיפוי לשמות עבודה. כל מה שלא כאן נשאר בעברית ולא נזרק.
RENAME = {
    "#": "rank", "שם שחקן": "player_name_he", "קבוצה": "team_he",
    "מש'": "games", "דק": "min_pg", "נק": "pts",
    "2 נק'_% / A": "fg2", "3 נק'_% / A": "fg3", "עונשין_% / A": "ft",
    # האתר כותב "%  /  A" ברווחים כפולים; _columns מנרמל אותם
    "ריבאונדים_הגנה": "reb_def", "ריבאונדים_התק": "reb_off",
    "ריבאונדים_סהכ": "reb_tot",
    "עבירות_של": "foul_made", "עבירות_על": "foul_drawn",
    "חט": "steals", "אב": "turnovers", "אס": "assists",
    "חסימות_של": "blk_made", "חסימות_על": "blk_against",
    "מדד": "pir",
}


def get(cYear, page, local=1, board=0, stype="TO"):
    url = (f"{BASE}?cYear={cYear}&sType={stype}&local={local}"
           f"&StatsBoard={board}&c={page}")
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
    except requests.exceptions.ProxyError as e:
        raise SystemExit(
            f"הבקשה נחסמה ע\"י פרוקסי.\n  {url}\n"
            "  זו בעיית רשת, **לא** בעיית דאטה. הפריט נשאר פתוח.\n"
            f"  ({type(e).__name__})")
    except requests.exceptions.RequestException as e:
        raise SystemExit(
            f"הבקשה נכשלה.\n  {url}\n"
            "  זו בעיית רשת, **לא** בעיית דאטה.\n"
            f"  ({type(e).__name__}: {str(e)[:120]})")

    # אתר עברי ישן. הקידוד שהשרת מצהיר עליו לא תמיד נכון, וקידוד
    # שגוי נראה בדיוק כמו דאטה תקין - רק עם ג'יבריש. אותה משפחת
    # באגים של requirements.txt ב-UTF-16.
    for enc in ENCODINGS:
        try:
            txt = r.content.decode(enc)
        except UnicodeDecodeError:
            continue
        if "קבוצה" in txt or "שחקן" in txt:
            return txt, url, enc
    raise ValueError(f"לא זוהה קידוד עברי תקין עבור {url}")


def _find_header(t):
    """שורת הכותרות אינה הראשונה. מוצאים אותה לפי תוכן, לא לפי מיקום.

    להניח ש-header=0 היה מייצר טבלה עם עמודות 0..19 ושורות כותרת
    בתוך הדאטה - כלומר דאטה שנראה תקין ואינו.
    """
    for i in range(min(8, len(t))):
        row = " ".join(str(v) for v in t.iloc[i].tolist())
        if all(k in row for k in HEADER_KEYS):
            return i
    raise ValueError("לא נמצאה שורת כותרות עם 'שם שחקן' ו'מדד'")


def _columns(t, hdr):
    """שם עמודה = קבוצת-על + כותרת, כדי ש'של'/'על' לא יתנגשו."""
    head = [str(v).strip() for v in t.iloc[hdr].tolist()]
    grp = ([str(v).strip() for v in t.iloc[hdr - 1].tolist()]
           if hdr >= 1 else [""] * len(head))
    def norm(x):
        # האתר משתמש ברווחים כפולים ("%  /  A"). בלי נרמול, מפתחות
        # RENAME לא מתאימים והעמודה נשארת מחרוזת עם '%' - כלומר
        # נראית תקינה ואינה מספר.
        return " ".join(str(x).split())

    out = []
    for g, h in zip(grp, head):
        g, h = norm(g), norm(h)
        g = "" if g in ("nan", "NaN", "") else g
        out.append(f"{g}_{h}" if g and g != h else h)
    return out


def parse(html, url):
    try:
        tables = pd.read_html(io.StringIO(html))
    except ImportError as e:
        raise SystemExit(
            "חסרה תלות לניתוח HTML.\n"
            "  python -m pip install lxml\n"
            f"  (המקור: {e})")
    if not tables:
        raise ValueError(f"אין טבלאות ב-{url}")

    best = None
    for t in tables:
        blob = " ".join(str(v) for v in t.head(8).values.ravel())
        if all(k in blob for k in NEED):
            if best is None or len(t) > len(best):
                best = t
    if best is None:
        raise ValueError(f"לא נמצאה טבלת שחקנים ב-{url}")

    hdr = _find_header(best)
    cols = _columns(best, hdr)
    df = best.iloc[hdr + 1:].copy()
    df.columns = cols
    df = df.rename(columns=RENAME)
    df = df[df.get("player_name_he", pd.Series(dtype=object)).notna()]
    return df.reset_index(drop=True)


def to_numeric(df):
    """אחוזים -> שברים, מספרים -> מספרים. מה שלא מומר נשאר ונספר."""
    num = ["games", "min_pg", "pts", "reb_def", "reb_off", "reb_tot",
           "foul_made", "foul_drawn", "steals", "turnovers", "assists",
           "blk_made", "blk_against", "pir"]
    pct = ["fg2", "fg3", "ft"]
    bad = {}
    for c in num:
        if c in df:
            conv = pd.to_numeric(df[c], errors="coerce")
            n = int(conv.isna().sum() - df[c].isna().sum())
            if n:
                bad[c] = n
            df[c] = conv
    for c in pct:
        if c in df:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace("%", "", regex=False)
                .str.split("/").str[0].str.strip(),
                errors="coerce") / 100.0
    if bad:
        print(f"    [WARN] ערכים שלא הומרו למספר: {bad}")
    left = [c for c in df.columns
            if df[c].dtype == object and c not in
            ("player_name_he", "team_he", "rank")]
    if left:
        raise ValueError(
            f"עמודות שנשארו טקסט ולא מופו: {left}\n"
            "  עמודה שנראית כמו מספר ונשמרת כמחרוזת היא באג שקט. "
            "בדוק את RENAME.")
    return df


def probe(cYear):
    print("=" * 74)
    print(f"PROBE — עמוד אחד בלבד, עונת {cYear - 1}-{cYear}")
    print("=" * 74)
    html, url, enc = get(cYear, 1)
    print(f"  URL   : {url}")
    print(f"  עונה  : cYear={cYear} באתר  ->  season="
          f"{cYear + SEASON_OFFSET} אצלנו")
    print(f"  קידוד : {enc}")
    t = to_numeric(parse(html, url))
    print(f"  צורה  : {t.shape}  (צפוי 20 שורות)")
    print(f"  עמודות: {list(t.columns)}")
    print(f"\n  חמש שורות ראשונות:")
    print(t.head(5).to_string(index=False))
    print(f"\n  בדיקת שפיות — pir: חציון {t.pir.median():.1f} | "
          f"טווח {t.pir.min():.1f}-{t.pir.max():.1f}")
    print("\n" + "=" * 74)
    print("  אם המבנה נכון — הרץ עם --full.")
    print("  אם יש ג'יבריש — הקידוד שגוי, אל תמשיך.")
    print("=" * 74)


def scrape_season(cYear, local=1, board=0):
    rows, seen_cols = [], None
    for page in range(1, MAX_PAGES + 1):
        html, url, _ = get(cYear, page, local, board)
        t = to_numeric(parse(html, url))
        if t.empty:
            break
        cols = tuple(str(c) for c in t.columns)
        if seen_cols is None:
            seen_cols = cols
        elif cols != seen_cols:
            raise ValueError(
                f"העמודות השתנו בעמוד {page} של {cYear}. "
                f"לא ממזגים טבלאות עם סכימות שונות.")
        # דף מעבר לאחרון מחזיר את אותו תוכן - עוצרים על כפילות
        if rows and t.equals(rows[-1]):
            break
        rows.append(t)
        print(f"    עמוד {page}: {len(t)} שורות")
        time.sleep(SLEEP)
    else:
        raise RuntimeError(f"נעצר על MAX_PAGES={MAX_PAGES} ב-{cYear}")

    if not rows:
        raise ValueError(f"אפס שורות לעונת {cYear}")
    df = pd.concat(rows, ignore_index=True)
    df.insert(0, "cYear", cYear)                       # כפי שבאתר
    df.insert(1, "season", cYear + SEASON_OFFSET)      # המוסכמה שלנו
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true",
                    help="משיכה מלאה. בלעדיו רץ probe בלבד.")
    ap.add_argument("--seasons", type=int, nargs="+",
                    default=[2023, 2024, 2025, 2026])
    ap.add_argument("--local", type=int, default=1,
                    help="1 = ישראלים בלבד, 0 = כולם")
    args = ap.parse_args()

    if not args.full:
        probe(args.seasons[-1])
        print("\n  להרצה מלאה:  python src/fetch_israeli_league.py --full")
        return

    frames = []
    for y in args.seasons:
        print(f"\n[{y - 1}-{y}]")
        frames.append(scrape_season(y, local=args.local))
    df = pd.concat(frames, ignore_index=True)

    dest = RAW_DIR / OUT.format(local=args.local)
    df.to_csv(dest, index=False, encoding="utf-8-sig")
    if dest.exists():
        print(f"\n[מחליף] {dest.name} קיים ונדרס.")
    print(f"\n[נכתב] {dest} | {len(df)} שורות | "
          f"{df.season.nunique()} עונות | local={args.local}")
    print(df.groupby(["cYear", "season"]).size().to_string())
    print("\n  cYear = כפי שבאתר (שנת סיום) · season = המוסכמה שלנו")
    print("  (שנת התחלה). ההצלבה ל-player_season היא על season.")
    print("\n  utf-8-sig כדי שאקסל בעברית לא יראה ג'יבריש.")
    print("  השלב הבא הוא ההצלבה: שמות בעברית מול "
          "player_name בלטינית. אין מזהה משותף.")


if __name__ == "__main__":
    main()