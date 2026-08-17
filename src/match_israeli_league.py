"""
match_israeli_league.py  (Day 6)
--------------------------------
מצליב את ליגת העל הישראלית ליורוליג, ואומד את מקדם ההמרה ביניהן.

--------------------------------------------------------------------
הבעיה
--------------------------------------------------------------------
אין מזהה משותף. השמות בעברית ("רומן סורקין") מול לטינית
("SORKIN, ROMAN"), ותעתיק עברי אינו חד-ערכי: ב = b או v,
כ = k או ch, פ = p או f.

הפתרון אינו לתעתק אלא **להשוות שלדי עיצורים** עם מחלקות ממוזגות.
"סורקין" -> s-r-k-n · "SORKIN" -> s-r-k-n.

ומה שהופך את זה לקל: **הקבוצה והעונה ידועות משני הצדדים.** זו
בעיה של 10 מול 15 בתוך סגל, לא 457 מול 1,045. ההשמה אופטימלית
(Hungarian) ולא חמדנית - אחרת שני שחקנים יכולים להיתפס לאותה שורה.

--------------------------------------------------------------------
מקדם ההמרה - למה זה העיקר
--------------------------------------------------------------------
מכבי והפועל משחקות **שתי מסגרות באותה עונה**. לכן לכל שחקן שלהן
יש שני PIR מדודים - על אותו כושר, אותו גיל, אותה שנה. ההפרש
ביניהם הוא מקדם ההמרה בין הליגות, **נאמד ולא מוצהר**.

בלעדיו גור לביא במדד 19.0 בגלבוע גליל הוא מספר חסר משמעות
ביורוליג. איתו - הוא נכנס למאגר המועמדים.

--------------------------------------------------------------------
מה זה לא עושה
--------------------------------------------------------------------
- לא מאשר התאמות אוטומטית מתחת לסף. הן נכתבות לקובץ לאישור ידני,
  כמו קובץ העמדות
- לא מניח שהמקדם קבוע. אם הוא לא יציב בין שחקנים או בין עונות,
  זה ממצא ומודפס ככזה

הרצה:
    python src/match_israeli_league.py
"""

import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import RAW_DIR, PROCESSED_DIR

SRC = "israeli_league_players_local0.csv"
OUT_MATCH = "israeli_el_matches.csv"
OUT_REVIEW = "israeli_el_matches_REVIEW.csv"

# שם הקבוצה בליגה המקומית -> קוד ביורוליג
TEAM_MAP = {'מכבי ת"א': "TEL", 'הפועל ת"א': "HTA"}

ACCEPT = 0.70          # מעל - מתקבל · מתחת - לאישור ידני
MIN_GAMES = 5          # פחות מזה: המדידה רועשת מכדי לשמש למקדם

# מחלקות עיצורים ממוזגות. ב=b/v, כ=k/ch, פ=p/f, צ=ts/z.
HEB = {'ב': 'b', 'ו': 'b', 'ג': 'g', 'ד': 'd', 'ז': 'z', 'ח': 'h',
       'ה': 'h', 'ט': 't', 'י': '', 'כ': 'k', 'ך': 'k', 'ל': 'l',
       'מ': 'm', 'ם': 'm', 'נ': 'n', 'ן': 'n', 'ס': 's', 'ע': '',
       'פ': 'p', 'ף': 'p', 'צ': 'z', 'ץ': 'z', 'ק': 'k', 'ר': 'r',
       'ש': 's', 'ת': 't', 'א': ''}
LAT = str.maketrans({'v': 'b', 'w': 'b', 'b': 'b', 'j': 'g', 'g': 'g',
                     'd': 'd', 'z': 'z', 'h': 'h', 't': 't', 'k': 'k',
                     'c': 'k', 'q': 'k', 'l': 'l', 'm': 'm', 'n': 'n',
                     's': 's', 'p': 'p', 'f': 'p', 'r': 'r', 'x': 'ks',
                     'y': '', 'a': '', 'e': '', 'i': '', 'o': '',
                     'u': ''})


def heb_skel(s):
    s = re.sub(r"[^֐-׿ ]", " ", str(s))
    return "".join(HEB.get(c, "") for c in s if c != " ")


def lat_skel(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z ]", " ", s)
    s = s.replace("sh", "s").replace("ch", "h").replace("ts", "z")
    return s.translate(LAT).replace(" ", "")


def score(he, lat):
    """שם עברי הוא 'פרטי משפחה', לטיני הוא 'MSHPAHA, PRATI'.
    מנסים גם את הסדר ההפוך ולוקחים את המקסימום."""
    a, b = heb_skel(he), lat_skel(lat)
    if not a or not b:
        return 0.0
    parts = str(lat).split(",")
    alt = lat_skel(" ".join(reversed(parts))) if len(parts) > 1 else b
    return max(SequenceMatcher(None, a, b).ratio(),
               SequenceMatcher(None, a, alt).ratio())


def match_roster(il, el):
    """השמה אופטימלית, לא חמדנית.

    חמדני היה מאפשר לשני שחקנים עבריים להיתפס לאותה שורה לטינית
    ולהשאיר אחרת ריקה. Hungarian ממקסם את סכום הציונים תחת אילוץ
    חד-חד-ערכיות - וזה בדיוק המבנה כאן.
    """
    S = np.array([[score(h, l) for l in el.player_name]
                  for h in il.player_name_he])
    if S.size == 0:
        return []
    r, c = linear_sum_assignment(-S)
    return [(il.iloc[i], el.iloc[j], float(S[i, j])) for i, j in zip(r, c)]


def main():
    src = RAW_DIR / SRC
    if not src.exists():
        raise SystemExit(
            f"לא נמצא {src}\n"
            "  הרץ קודם: python src/fetch_israeli_league.py --full --local 0")

    isr = pd.read_csv(src)
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    isr["el_team"] = isr.team_he.map(TEAM_MAP)
    isr = isr[isr.el_team.notna()]

    print("=" * 74)
    print("הצלבת ליגת העל <-> יורוליג")
    print("=" * 74)

    rows = []
    for (season, team), il in isr.groupby(["season", "el_team"]):
        el = ps[(ps.season == season) &
                ps.team.astype(str).str.contains(team, na=False)]
        if el.empty:
            print(f"  [דילוג] {team} {season}: אין סגל יורוליג")
            continue
        pairs = match_roster(il.reset_index(drop=True),
                             el.reset_index(drop=True))
        print(f"  {team} {season}: {len(il)} מקומית x {len(el)} יורוליג "
              f"-> {len(pairs)} זוגות")
        for a, b, s in pairs:
            rows.append({
                "season": season, "team": team, "score": round(s, 3),
                "name_he": a.player_name_he, "name_el": b.player_name,
                "player_code": b.player_code,
                "il_games": a.games, "il_min": a.min_pg, "il_pir": a.pir,
                "el_games": b.games, "el_min": b.min_per_game,
                "el_pir": b.pir_per_game,
            })

    m = pd.DataFrame(rows).sort_values("score", ascending=False)
    ok = m[m.score >= ACCEPT].copy()
    rev = m[m.score < ACCEPT].copy()

    print(f"\n  התאמות: {len(m)} | מעל סף {ACCEPT}: {len(ok)} | "
          f"לאישור ידני: {len(rev)}")

    print("\n" + "=" * 74)
    print("התאמות שהתקבלו")
    print("=" * 74)
    print(f"{'ציון':>6}  {'עברית':<20}{'לטינית':<26}{'עונה':>6}"
          f"{'PIR מקומי':>11}{'PIR יורוליג':>13}")
    for t in ok.itertuples():
        print(f"{t.score:>6.2f}  {t.name_he:<20}{str(t.name_el)[:25]:<26}"
              f"{t.season:>6}{t.il_pir:>11.1f}{t.el_pir:>13.1f}")

    if len(rev):
        print("\n" + "=" * 74)
        print("לאישור ידני — מתחת לסף")
        print("=" * 74)
        for t in rev.itertuples():
            print(f"{t.score:>6.2f}  {t.name_he:<20}"
                  f"{str(t.name_el)[:25]:<26}{t.season:>6}")

    # ---------- מקדם ההמרה ----------
    print("\n" + "=" * 74)
    print("מקדם ההמרה בין הליגות")
    print("=" * 74)
    d = ok[(ok.il_games >= MIN_GAMES) & (ok.el_games >= MIN_GAMES) &
           (ok.il_min > 0) & (ok.el_min > 0)].copy()
    d["il_ppm"] = d.il_pir / d.il_min
    d["el_ppm"] = d.el_pir / d.el_min
    d["ratio"] = d.el_ppm / d.il_ppm
    print(f"  n={len(d)} (לפחות {MIN_GAMES} משחקים בשתי הליגות)")
    if len(d) < 5:
        print("  [FAIL] מדגם קטן מדי למקדם. לא מדווח מספר.")
        return

    print(f"\n  PIR לדקה: מקומית חציון {d.il_ppm.median():.3f} | "
          f"יורוליג חציון {d.el_ppm.median():.3f}")
    print(f"  יחס (יורוליג/מקומית): חציון {d.ratio.median():.3f} | "
          f"ממוצע {d.ratio.mean():.3f} | "
          f"סטיית תקן {d.ratio.std():.3f}")
    print(f"  טווח: {d.ratio.min():.3f}-{d.ratio.max():.3f}")

    print(f"\n  לפי עונה:")
    print(d.groupby("season").agg(
        n=("ratio", "size"), חציון=("ratio", "median"),
        סטיית_תקן=("ratio", "std")).round(3).to_string())

    cv = d.ratio.std() / d.ratio.mean()
    print(f"\n  מקדם שונות של היחס: {cv:.0%}")
    if cv > 0.35:
        print("  🔴 היחס אינו יציב בין שחקנים. **זה ממצא**: המרה")
        print("  במקדם יחיד תכניס שגיאה גדולה מהאות. הפריט נשאר פתוח.")
    else:
        print("  היחס יציב מספיק להמרה במקדם יחיד.")

    ok.to_csv(PROCESSED_DIR / OUT_MATCH, index=False,
              encoding="utf-8-sig")
    if len(rev):
        rev.to_csv(PROCESSED_DIR / OUT_REVIEW, index=False,
                   encoding="utf-8-sig")
    print(f"\n[נכתב] {PROCESSED_DIR / OUT_MATCH} | {len(ok)} שורות")
    if len(rev):
        print(f"[נכתב] {PROCESSED_DIR / OUT_REVIEW} | {len(rev)} "
              f"שורות לאישור ידני")


if __name__ == "__main__":
    main()