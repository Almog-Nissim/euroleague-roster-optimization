"""
game_index.py — טבלת משחקים: season, gamecode, phase, round, date, teams

סטטוס: ✅ אומת מול 2022 — התאמה 100% ב-Phase וב-Round, אפס משחקים
בצד אחד בלבד. העימוד (offset/limit) עובד, totalItems מאשר משיכה מלאה.

תיקון אחרון
-----------
🔴 טווחי השפיות היו **מקודדים מהזיכרון** ונפלו בשתי עונות:
   · 2025 — 380 משחקי RS. הליגה התרחבה ל-20 קבוצות (20×19=380).
   · 2019 — 306 משחקי RS בעונה שבוטלה במרץ 2020.

הוחלפו בבדיקה **נגזרת**: משחקי RS חייבים להיות בדיוק `T·(T−1)`,
כש-`T` הוא מספר הקבוצות שמופיעות ב-index עצמו. מאומת על שלושת
הפורמטים — 16×15=240, 18×17=306, 20×19=380 — ולא יתיישן.

🔴 הממצא שנחשף בדרך: **הפיד מחזיר משחקים מתוכננים, לא משוחקים.**
2019 מציגה עונה מלאה למרות שנעצרה אחרי 28 מחזורים. קובץ הבוקסקור
(7,009 שורות ≈ 253 משחקים ≈ 28 מחזורים) הוא השלם; ה-index מכיל
~54 משחקים שלא שוחקו.

**חובה לסנן על `Played` לפני כל join לבוקסקור.**
ולבדוק בנפרד מאיפה הגיע המכנה של מודל הזמינות ל-2019.

הרצה:
  python src/game_index.py --probe --seasons 2018
  python src/game_index.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_api import SCHEDULE_ENDPOINTS, fetch, make_session  # noqa: E402
from el_paths import find_boxscores, repo_root, resolve  # noqa: E402

OUT_REL = "data/processed/game_index.csv"

PAGING_VARIANTS = [
    ("offset/limit", lambda off, size: {"offset": off, "limit": size}),
    ("skip/take", lambda off, size: {"skip": off, "take": size}),
    ("page/size", lambda off, size: {"page": off // max(size, 1), "size": size}),
    ("from/count", lambda off, size: {"from": off, "count": size}),
]

FIELD_ALIASES = {
    "gamecode": ["gamecode", "gameCode", "game_code", "code", "gameNumber", "id"],
    "phase": ["phase", "phaseType", "phasetype", "phaseTypeCode", "competitionPhase"],
    "round": ["round", "roundNumber", "gameday", "gameDay", "week"],
    "date": ["date", "startDate", "utcDate", "localDate", "startTime", "played_on"],
    "home_team": ["homeTeam", "home", "hometeam", "local", "localTeam",
                  "codeteama", "teamA", "homeClub", "teamHome"],
    "away_team": ["awayTeam", "away", "road", "roadTeam", "awayteam", "visitor",
                  "guest", "codeteamb", "teamB", "awayClub", "teamAway"],
    "played": ["played", "isPlayed", "status", "gameStatus"],
}

RS_LABELS = {"RS", "REGULARSEASON", "REGULAR"}


def _flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}{k}"
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if not isinstance(vv, (dict, list)):
                        out[f"{key}.{kk}"] = vv
                out.setdefault(key, v.get("code") or v.get("name") or v.get("tvCode"))
            elif not isinstance(v, list):
                out[key] = v
    return out


# מילים שמסגירות שדה שאינו שם קבוצה
_NOT_TEAM = ("score", "quarter", "point", "result", "win", "id", "logo", "image")

# טוקן לחיפוש נסיגה, לשדות שבהם שם מדויק לא נמצא
_FALLBACK_TOKENS = {"home_team": ("home", "local"), "away_team": ("away", "road", "visitor")}


def _pick(row: dict, canonical: str):
    """
    שלב 1 — שם מדויק מרשימת ה-aliases.
    שלב 2 — נסיגה לחיפוש טוקן.

    שלב 2 קיים כי רשימת ה-aliases חסרה את `away` והשדה יצא ריק,
    בעוד `home` כן היה ברשימה. כל מועדון נספר רק במשחקי הבית שלו,
    וכל המכנים יצאו חצי. נסיגה גנרית עדיפה על רשימה ארוכה יותר.
    """
    for alias in FIELD_ALIASES[canonical]:
        for key in row:
            if key.lower() == alias.lower() or key.lower().endswith("." + alias.lower()):
                val = row[key]
                if val not in (None, ""):
                    return val

    for token in _FALLBACK_TOKENS.get(canonical, ()):
        for key, val in row.items():
            kl = key.lower()
            if token in kl and not any(bad in kl for bad in _NOT_TEAM):
                if isinstance(val, str) and val.strip():
                    return val
    return None


def _extract_games(payload) -> list[dict]:
    if isinstance(payload, list):
        return [g for g in payload if isinstance(g, dict)]
    if isinstance(payload, dict):
        for key in ("data", "games", "items", "results", "game", "schedule"):
            v = payload.get(key)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
            if isinstance(v, dict):
                inner = _extract_games(v)
                if inner:
                    return inner
    return []


def _metadata(payload) -> dict:
    if isinstance(payload, dict):
        return {k: v for k, v in payload.items()
                if k not in ("data", "games", "items", "results", "schedule")
                and not isinstance(v, list)}
    return {}


def _total_items(payload) -> int | None:
    meta = _metadata(payload)
    inner = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else meta
    for k in ("totalItems", "total", "totalCount", "count"):
        if isinstance(inner, dict) and k in inner:
            try:
                return int(inner[k])
            except (TypeError, ValueError):
                pass
    return None


def _first_code(games: list[dict]):
    return str(_pick(_flatten(games[0]), "gamecode")) if games else None


def probe(seasons: list[int]) -> None:
    session = make_session()
    season = seasons[0]
    print("=" * 74)
    print(f"בדיקת endpoints ועימוד — עונה {season}")
    print("=" * 74)

    for name, url_t, params_t in SCHEDULE_ENDPOINTS:
        url = url_t.format(season=season)
        base = {k: v.format(season=season) for k, v in params_t.items()}
        res = fetch(session, url, params=base, retries=1, sleep=1.0)
        print(f"\n--- {name} ---")
        if not res.ok:
            print(res.describe())
            continue

        games = _extract_games(res.payload)
        print(f"  משחקים בעמוד ראשון: {len(games)}")
        print(f"  METADATA: {_metadata(res.payload)}")
        print(f"  totalItems: {_total_items(res.payload)}")
        if not games:
            continue

        flat = _flatten(games[0])
        print(f"\n  שדות: {sorted(flat.keys())}")
        print("  מיפוי:")
        for canon in FIELD_ALIASES:
            print(f"    {canon:<10} -> {_pick(flat, canon)!r}")

        page1_first = _first_code(games)
        print(f"\n  gamecode ראשון בעמוד 1: {page1_first}")
        print("  האם עמוד 2 שונה מעמוד 1:")
        for pname, pfn in PAGING_VARIANTS:
            p2 = fetch(session, url, params={**base, **pfn(len(games), len(games))},
                       retries=1, sleep=1.0)
            if not p2.ok:
                print(f"    {pname:<14} ❌ בקשה נכשלה")
                continue
            g2 = _extract_games(p2.payload)
            if not g2:
                print(f"    {pname:<14} ⚠️ עמוד ריק")
            elif _first_code(g2) == page1_first:
                print(f"    {pname:<14} ❌ אותו עמוד — הפרמטר לא נתפס")
            else:
                print(f"    {pname:<14} ✅ עמוד שונה ({_first_code(g2)})")


# שדות שחייבים להיות מלאים. ריק ולו בשורה אחת = שגיאה קשה.
CRITICAL_FIELDS = ["Gamecode", "Phase", "HomeTeam", "AwayTeam"]


def completeness_check(df: pd.DataFrame) -> list[str]:
    """
    האם כל שדה קנוני התמלא בפועל.

    הבדיקה הזו נוספה אחרי ש-`AwayTeam` יצא ריק בשקט ב-3,131 שורות,
    וכל המכנים במודל הזמינות יצאו חצי. שדה ריק אינו "חסר מידע" —
    הוא כשל מיפוי, וצריך לצעוק.
    """
    problems = []
    for col in CRITICAL_FIELDS:
        if col not in df.columns:
            problems.append(f"עמודה חסרה לגמרי: {col}")
            continue
        n_null = int(df[col].isna().sum() + (df[col].astype(str).str.strip() == "").sum())
        if n_null:
            problems.append(f"{col}: {n_null}/{len(df)} ריקים — כשל מיפוי, לא חוסר מידע")
    return problems


def structural_check(df: pd.DataFrame, season: int, expected_total: int | None) -> list[str]:
    """
    בדיקה נגזרת, לא מקודדת:
      · RS חייב להיות T·(T−1) כש-T = מספר הקבוצות ב-index
      · סך המשחקים חייב להתאים ל-totalItems של הפיד
      · FF תקני = 4 משחקים
    """
    problems = []

    if expected_total is not None and len(df) != expected_total:
        problems.append(f"נמשכו {len(df)} מתוך {expected_total} שהפיד מדווח")

    phase_norm = (df["Phase"].astype(str).str.upper().str.strip()
                  .str.replace(r"[^A-Z]", "", regex=True))
    rs = df[phase_norm.isin(RS_LABELS)]

    teams = pd.unique(pd.concat([rs["HomeTeam"], rs["AwayTeam"]]).dropna().astype(str))
    n_teams = len(teams)
    if n_teams >= 2:
        expected_rs = n_teams * (n_teams - 1)
        mark = "✅" if len(rs) == expected_rs else "🔴"
        print(f"           {mark} RS: {len(rs)} · {n_teams} קבוצות · צפוי {n_teams}×{n_teams - 1}={expected_rs}")
        if len(rs) != expected_rs:
            problems.append(f"RS={len(rs)} אך {n_teams} קבוצות מחייבות {expected_rs}")
    else:
        problems.append("לא זוהו קבוצות — בדוק את מיפוי HomeTeam/AwayTeam")

    ff = int(phase_norm.eq("FF").sum())
    if ff and ff not in (3, 4):
        problems.append(f"FF={ff} (תקין: 4 עם משחק על המקום השלישי, 3 בלעדיו)")

    return problems


def report_played(index: pd.DataFrame) -> None:
    """
    תיאור בלבד — בלי פסק דין.

    הגרסה הקודמת השוותה את השדה לרשימת ערכי-אמת שניחשתי
    (TRUE / PLAYED / FINAL) והדפיסה "0 משוחקים" בכל עונה. זה שגוי:
    2022 עברה אימות מול הבוקסקור ב-100%. הסמנטיקה של השדה אינה
    ידועה לנו, ולכן היא לא מפורשת כאן.

    ההכרעה מי שוחק נמצאת ב-`index_audit.py`, מול אמת הקרקע —
    נוכחות המשחק בקובץ הבוקסקור.
    """
    print("\n" + "=" * 74)
    print("השדה Played — ערכים גולמיים (הפרשנות ב-index_audit.py)")
    print("=" * 74)

    if "Played" not in index.columns:
        print("  אין עמודה Played.")
        return

    print(f"  ריקים: {int(index['Played'].isna().sum()):,} מתוך {len(index):,}")
    print("\n  ערכים ייחודיים:")
    print(index["Played"].astype(str).value_counts(dropna=False).head(15).to_string())
    print("\n  ⚠️ אין כאן קביעה מי שוחק. הרץ index_audit.py.")


def build_season(session, season: int, endpoint_name, paging: str,
                 page_size: int, max_games: int = 2000) -> pd.DataFrame:
    candidates = SCHEDULE_ENDPOINTS
    if endpoint_name:
        candidates = [e for e in SCHEDULE_ENDPOINTS if e[0] == endpoint_name]
    pfn = dict(PAGING_VARIANTS)[paging]

    for name, url_t, params_t in candidates:
        url = url_t.format(season=season)
        base = {k: v.format(season=season) for k, v in params_t.items()}

        all_games: list[dict] = []
        seen_first = set()
        offset = 0
        expected_total = None

        while True:
            res = fetch(session, url, params={**base, **pfn(offset, page_size)},
                        retries=3, sleep=1.0)
            if not res.ok:
                break

            if offset == 0:
                expected_total = _total_items(res.payload)
                if expected_total is not None:
                    print(f"  [{season}] הפיד מדווח {expected_total} משחקים")

            page = _extract_games(res.payload)
            if not page:
                break

            fc = _first_code(page)
            if fc in seen_first:
                print(f"  [{season}] ⚠️ העמוד חזר על עצמו — העימוד לא נתפס. עוצר.")
                break
            seen_first.add(fc)

            all_games.extend(page)
            if len(page) < page_size:
                break
            offset += len(page)
            if offset >= max_games:
                print(f"  [{season}] ⚠️ עצירת בטיחות ב-{offset}")
                break

        if not all_games:
            continue

        rows = []
        for g in all_games:
            flat = _flatten(g)
            rows.append({
                "Season": season,
                "Gamecode": _pick(flat, "gamecode"),
                "Phase": _pick(flat, "phase"),
                "Round": _pick(flat, "round"),
                "Date": _pick(flat, "date"),
                "HomeTeam": _pick(flat, "home_team"),
                "AwayTeam": _pick(flat, "away_team"),
                "Played": _pick(flat, "played"),
                "SourceEndpoint": name,
            })
        df = pd.DataFrame(rows)
        df["Gamecode"] = df["Gamecode"].astype(str).str.strip()
        before = len(df)
        df = df.drop_duplicates("Gamecode")
        dup = before - len(df)

        print(f"  [{season}] {len(df)} משחקים מ-{name}"
              + (f"  (הוסרו {dup} כפילויות)" if dup else ""))

        for p in completeness_check(df):
            print(f"           🔴 {p}")
        for p in structural_check(df, season, expected_total):
            print(f"           🔴 {p}")
        return df

    print(f"  [{season}] 🔴 אף endpoint לא החזיר משחקים")
    return pd.DataFrame()


def validate_against_2022(index: pd.DataFrame, path_2022) -> bool:
    print("\n" + "=" * 74)
    print("אימות מול 2022 — העונה היחידה שיש בה Phase ו-Round אמיתיים")
    print("=" * 74)

    if path_2022 is None or not Path(path_2022).exists():
        print("  🔴 לא נמצא קובץ בוקסקור ל-2022. האימות לא רץ.")
        return False

    print(f"  קובץ: {path_2022}")
    bx = pd.read_csv(path_2022, dtype={"Gamecode": str}, low_memory=False)
    if "Phase" not in bx.columns:
        print("  🔴 אין Phase בקובץ 2022.")
        return False

    truth = (bx[["Gamecode", "Phase", "Round"]]
             .assign(Gamecode=lambda d: d["Gamecode"].astype(str).str.strip())
             .drop_duplicates("Gamecode"))
    ours = index[index["Season"] == 2022][["Gamecode", "Phase", "Round"]].copy()
    ours["Gamecode"] = ours["Gamecode"].astype(str).str.strip()

    merged = truth.merge(ours, on="Gamecode", how="outer",
                         suffixes=("_true", "_ours"), indicator=True)
    only_bx = int((merged["_merge"] == "left_only").sum())
    only_idx = int((merged["_merge"] == "right_only").sum())
    both = merged[merged["_merge"] == "both"].copy()

    def norm(s):
        return (s.astype(str).str.upper().str.strip()
                .str.replace(r"[^A-Z0-9]", "", regex=True))

    phase_match = float((norm(both["Phase_true"]) == norm(both["Phase_ours"])).mean()) if len(both) else 0.0
    round_match = float((pd.to_numeric(both["Round_true"], errors="coerce")
                         == pd.to_numeric(both["Round_ours"], errors="coerce")).mean()) if len(both) else 0.0

    print(f"  בבוקסקור בלבד : {only_bx}")
    print(f"  ב-index בלבד  : {only_idx}")
    print(f"  הצטלבו        : {len(both)}")
    print(f"  התאמת Phase   : {phase_match:.4%}")
    print(f"  התאמת Round   : {round_match:.4%}")

    if only_bx == 0 and phase_match == 1.0 and round_match == 1.0:
        print("\n  ✅ התאמה מלאה. מותר להחיל את ה-index על שאר העונות.")
        return True

    print("\n  🔴 אין התאמה מלאה. אל תחיל את המיפוי.")
    if len(both):
        bad = both[norm(both["Phase_true"]) != norm(both["Phase_ours"])]
        if len(bad):
            print("\n  דוגמאות:")
            print(bad[["Gamecode", "Phase_true", "Phase_ours"]].head(10).to_string(index=False))
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int,
                    default=[2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025])
    ap.add_argument("--endpoint", default="v2_games")
    ap.add_argument("--paging", default="offset/limit",
                    choices=[n for n, _ in PAGING_VARIANTS])
    ap.add_argument("--page-size", type=int, default=200)
    ap.add_argument("--root", default=None)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--force-save", action="store_true", help="אל תשתמש בזה.")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")

    if args.probe:
        probe(args.seasons)
        return 0

    session = make_session()
    frames = []
    for season in args.seasons:
        df = build_season(session, season, args.endpoint, args.paging, args.page_size)
        if not df.empty:
            frames.append(df)

    if not frames:
        print("🔴 שום דבר לא נמשך.")
        return 1

    index = pd.concat(frames, ignore_index=True)

    fatal = completeness_check(index)
    if fatal:
        print("\n🔴 שדות קריטיים ריקים:")
        for p in fatal:
            print(f"   · {p}")

    boxscores = find_boxscores(args.root, verbose=False)
    ok = validate_against_2022(index, boxscores.get(2022)) and not fatal

    print("\nמשחקים לפי עונה ו-Phase:")
    print(index.groupby(["Season", "Phase"]).size().to_string())

    report_played(index)

    out_path = resolve(OUT_REL)
    if not ok and not args.force_save:
        print(f"\n🔴 האימות לא עבר — **הקובץ לא נשמר** ({out_path}).")
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    index.to_csv(out_path, index=False)
    print(f"\n✅ נשמר: {out_path}  ({len(index)} שורות)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())