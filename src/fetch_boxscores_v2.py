"""
fetch_boxscores_v2.py — משיכת בוקסקורים. עצמאי, לא דורש עריכה ידנית.

למה גרסה חדשה ולא טלאי
----------------------
`FETCH_PATCH.md` היה מסמך הוראות לעריכה ידנית — החלטה גרועה. הוא
דרש שינוי קוד בזמן שדברים אחרים רצים, ואין דרך לדעת אם נקלט.
הקובץ הזה רץ כמו שהוא.

מה שונה מהמשיכה של הבוקר
------------------------
1. 🔴 **משחק בודד לא מפיל עונה.** הכישלון נרשם ל-`failed_games_*.csv`
   והלולאה ממשיכה. לאבד משחק אחד מ-260 זה שגיאת עיגול; לאבד עונה
   זה יום עבודה.
2. 🔴 **שגיאות נתפסות עם פרטים.** ההודעה הקודמת הייתה ריקה, ולכן
   הנחנו 429 במקום למדוד. עכשיו: type, repr, status, גוף התגובה.
3. 🔴 **לא חוזרים על 404.** זה מה שיצר את "שש ניסיונות" חסרי הטעם.
4. **רשימת המשחקים מ-`game_index.csv`**, לא מגישוש. וכולל סינון
   `Played == 'result'` — ב-2021 מדלגים מראש על 28 משחקים מבוטלים.
5. **לא דורס קבצים קיימים** בלי `--overwrite`.
6. **טיוטה נשמרת כל 25 משחקים** — קריסה לא מוחקת את מה שנמשך.

⚠️ לא נבדק מול ה-API האמיתי (אין גישת רשת בסביבה שבה נכתב).
הפירסור נבדק מול payload מדומה בלבד. לכן בסוף כל עונה רצה בדיקת
שפיות שמשווה שורות-למשחק לעונות מאותו פורמט:
  2016 = 27.74 · 2017 = 27.85 שורות למשחק.
אם 2018 תצא באזור הזה — הפירסור זהה לקיים. אם תצא ~24 — אנחנו
מפילים שורות שנשמרו בקבצים הקודמים, ואסור לכתוב את הקובץ.

הרצה:
  python src/fetch_boxscores_v2.py                    # 2018 ו-2021
  python src/fetch_boxscores_v2.py --seasons 2018
  python src/fetch_boxscores_v2.py --dry-run          # 3 משחקים בלבד
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_api import fetch, make_session  # noqa: E402
from el_paths import find_boxscores, repo_root, resolve  # noqa: E402

BOXSCORE_URL = "https://live.euroleague.net/api/Boxscore"

COLUMNS = [
    "Season", "Gamecode", "Home", "Player_ID", "IsStarter", "IsPlaying", "Team",
    "Dorsal", "Player", "Minutes", "Points",
    "FieldGoalsMade2", "FieldGoalsAttempted2", "FieldGoalsMade3", "FieldGoalsAttempted3",
    "FreeThrowsMade", "FreeThrowsAttempted",
    "OffensiveRebounds", "DefensiveRebounds", "TotalRebounds",
    "Assistances", "Steals", "Turnovers", "BlocksFavour", "BlocksAgainst",
    "FoulsCommited", "FoulsReceived", "Valuation", "Plusminus",
]

# שדות שמסגירים בלוק סטטיסטיקה (שחקן או סיכום)
STAT_MARKERS = ("Valuation", "Points", "TotalRebounds")

# קצב מסתגל מול חסימות. נמדד: אשכולות של ~13 כישלונות רצופים.
MAX_PACE = 4.0        # שניות בין בקשות, תקרה
COOLDOWN = 60.0       # המתנה אחרי 429, בסדר גודל של החלון


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def gamecodes_for(season: int, index_path: Path, played_only: bool) -> list[str]:
    if not index_path.exists():
        raise SystemExit(f"🔴 לא נמצא {index_path}. הרץ game_index.py קודם.")
    idx = pd.read_csv(index_path, dtype={"Gamecode": str}, low_memory=False)
    sub = idx[idx["Season"] == season].copy()
    if sub.empty:
        raise SystemExit(f"🔴 אין משחקים לעונה {season} ב-index.")

    total = len(sub)
    if played_only and "Played" in sub.columns:
        status = sub["Played"].astype(str).str.lower().str.strip()
        skipped = sub[status != "result"]
        sub = sub[status == "result"]
        if len(skipped):
            print(f"  [{season}] מדלג על {len(skipped)} משחקים שלא שוחקו: "
                  f"{dict(skipped['Played'].astype(str).value_counts())}")

    codes = sub["Gamecode"].astype(str).str.strip().tolist()
    print(f"  [{season}] {len(codes)} משחקים למשיכה (מתוך {total} בלוח)")
    return codes


def _is_stat_block(obj) -> bool:
    return isinstance(obj, dict) and any(m in obj for m in STAT_MARKERS)


def _summary_label(key: str, blk: dict) -> str:
    """
    'Team' או 'Total', כמו בקבצים הקיימים.

    שני סימנים בלתי תלויים: שם המפתח (`totr` מול `tmr`) ושורת
    ה-Total שנושאת ~200 דקות. אם שם המפתח לא מוכר, הדקות מכריעות.
    """
    existing = str(blk.get("Player_ID") or "").strip()
    if existing.upper() in ("TEAM", "TOTAL"):
        return existing.title()

    k = str(key).lower()
    if "tot" in k:
        return "Total"
    if "tm" in k or "team" in k:
        return "Team"

    mins = str(blk.get("Minutes") or "")
    return "Total" if mins.startswith(("200", "225", "250", "275")) else "Team"


def _to_row(entry: dict, season: int, gamecode: str, home: int, team_code) -> dict:
    row = {"Season": season, "Gamecode": str(gamecode), "Home": home}
    for col in COLUMNS:
        if col in row:
            continue
        row[col] = entry.get(col, entry.get(col[0].lower() + col[1:]))
    if row.get("Team") in (None, ""):
        row["Team"] = team_code
    return row


def parse_boxscore(payload, season: int, gamecode: str) -> list[dict]:
    """
    התגובה: {'Stats': [{'Team':..., 'PlayersStats':[...], <סיכומים>}, {...}]}
    Stats[0] = בית, Stats[1] = חוץ.

    שורות הסיכום
    ------------
    הקבצים הקיימים כוללים שתי שורות נוספות לכל קבוצה — `Team` ו-
    `Total` — כלומר 4 למשחק. 27.74 שורות למשחק ב-2016 פחות 4.00 הן
    23.74 שורות שחקנים, וזה בדיוק מה שהמשיכה החדשה החזירה.

    שורת `Total` נושאת `Minutes = 200:00`, כלומר אימות ישיר של אורך
    המשחק והארכות. לכן היא נשמרת ולא מסוננת.

    האיתור הוא **מבני** — כל בלוק שנושא שדות סטטיסטיקה — ולא לפי
    שם מפתח שננחש. שמות המפתחות בפיד לא ידועים לנו.
    """
    if not isinstance(payload, dict):
        return []
    stats = payload.get("Stats") or payload.get("stats") or []
    if not isinstance(stats, list):
        return []

    rows = []
    for team_idx, block in enumerate(stats):
        if not isinstance(block, dict):
            continue
        home = 1 if team_idx == 0 else 0
        team_code = block.get("Team") or block.get("team")

        players = block.get("PlayersStats") or block.get("playersStats") or []
        for p in players:
            if isinstance(p, dict):
                rows.append(_to_row(p, season, gamecode, home, team_code))

        # בלוקי סיכום: כל dict אחר בתוך הבלוק שנושא שדות סטטיסטיקה
        summaries = [(k, v) for k, v in block.items()
                     if k not in ("PlayersStats", "playersStats") and _is_stat_block(v)]
        # 🔴 לבלוקים האלה אין Player_ID בפיד. הפוצ'ר הישן הדביק להם
        # 'Team' ו-'Total' בעצמו. בלי התיוג הם נמשכים אבל אינם ניתנים
        # לזיהוי, וכל צבירה תספור סיכום קבוצה כשחקן.
        summaries.sort(key=lambda kv: _summary_label(*kv) == "Total")
        for key, blk in summaries:
            row = _to_row(blk, season, gamecode, home, team_code)
            label = _summary_label(key, blk)
            row["Player_ID"] = label
            row["Player"] = label
            rows.append(row)

    return rows


def reference_ratio(season: int):
    """
    הסף נמדד מקובץ קיים, לא מקודד.

    בגרסה הקודמת כתבתי `REFERENCE_RATIO = {16: 27.8, ...}` מתוך חישוב
    שלי. מספר מקודד מזדקן ואי אפשר לבדוק אותו. כאן נקראת העונה
    הקרובה ביותר שכבר על הדיסק.
    """
    existing = find_boxscores(verbose=False)
    if not existing:
        return None, None
    nearest = min(existing, key=lambda s: abs(s - season))
    df = pd.read_csv(existing[nearest], dtype={"Gamecode": str}, low_memory=False)
    n = df["Gamecode"].nunique()
    if not n:
        return None, None
    return len(df) / n, nearest


def sanity_check(df: pd.DataFrame, season: int, n_games: int,
                 index_path: Path) -> list[str]:
    problems = []

    ratio = len(df) / max(n_games, 1)
    expected, ref_season = reference_ratio(season)
    if expected:
        print(f"  שורות למשחק: {ratio:.2f}  (בעונת {ref_season}: {expected:.2f})")
        if abs(ratio - expected) > 1.0:
            problems.append(f"שורות למשחק {ratio:.2f} מול {expected:.2f} בעונת "
                            f"{ref_season} — הפירסור שונה מזה שיצר את הקבצים הקיימים")
    else:
        print(f"  שורות למשחק: {ratio:.2f}  (אין קובץ ייחוס)")

    pid = df["Player_ID"].astype(str).str.strip().str.upper()
    n_summary = int(pid.isin(["TEAM", "TOTAL"]).sum())
    print(f"  שורות סיכום: {n_summary / max(n_games, 1):.2f} למשחק  (צפוי 4.00)")
    if abs(n_summary / max(n_games, 1) - 4.0) > 0.5:
        problems.append(f"שורות סיכום {n_summary / max(n_games, 1):.2f} למשחק "
                        f"במקום 4.00 (Team + Total לכל קבוצה)")

    missing_cols = [c for c in COLUMNS if c not in df.columns]
    if missing_cols:
        problems.append(f"עמודות חסרות: {missing_cols}")

    empty = [c for c in COLUMNS if c in df.columns and df[c].isna().all()]
    if empty:
        problems.append(f"עמודות ריקות לגמרי: {empty}")

    if df["Gamecode"].nunique() != n_games:
        problems.append(f"{df['Gamecode'].nunique()} משחקים בדאטה מול {n_games} שנמשכו")

    return problems


def fetch_season(session, season: int, out_dir: Path, index_path: Path,
                 sleep: float, played_only: bool, limit: int | None,
                 resume: bool = False) -> bool:
    hdr(f"עונה {season}")

    out_path = out_dir / f"boxscore_player_{season}.csv"
    draft_path = out_dir / f"_draft_boxscore_player_{season}.csv"

    codes = gamecodes_for(season, index_path, played_only)

    rows: list[dict] = []
    if resume and draft_path.exists():
        prev = pd.read_csv(draft_path, dtype={"Gamecode": str, "Player_ID": str},
                           low_memory=False)
        have = set(prev["Gamecode"].astype(str).str.strip())
        # טיוטה בלי שורות מתויגות נוצרה בגרסה קודמת ואינה שמישה
        labelled = prev["Player_ID"].astype(str).str.upper().isin(["TEAM", "TOTAL"]).any()
        if labelled:
            rows = prev.to_dict("records")
            codes = [c for c in codes if c not in have]
            print(f"  ↻ המשך: {len(have)} משחקים כבר בטיוטה, נותרו {len(codes)}")
        else:
            print("  ⚠️ הטיוטה נוצרה לפני תיקון התיוג — מתחיל מחדש.")

    if limit:
        codes = codes[:limit]
        print(f"  ⚠️ dry-run: {limit} משחקים בלבד")

    failed: list[dict] = []
    done = len({r["Gamecode"] for r in rows}) if rows else 0
    pace = sleep          # קצב מסתגל
    consecutive_ok = 0

    for i, gc in enumerate(codes, 1):
        res = fetch(session, BOXSCORE_URL,
                    params={"gamecode": gc, "seasoncode": f"E{season}"},
                    retries=5, sleep=pace)

        if res.error_type == "RateLimited":
            # 🔴 האטה גלובלית. משחק אחד שנחסם מנבא את ה-13 הבאים —
            # החלון נעול, לא העומס רגעי. ריטריי ארוך יותר לא עוזר;
            # צריך להאט את כל הקצב.
            old = pace
            pace = min(pace * 1.5, MAX_PACE)
            consecutive_ok = 0
            print(f"      ⏳ מאט: {old:.1f} -> {pace:.1f} שניות בין בקשות")
            time.sleep(COOLDOWN)
        elif res.ok:
            consecutive_ok += 1
            if consecutive_ok >= 50 and pace > sleep:
                pace = max(pace / 1.2, sleep)
                consecutive_ok = 0
                print(f"      ⏩ מאיץ בחזרה: {pace:.1f} שניות")

        if not res.ok:
            failed.append({"season": season, "gamecode": gc,
                           "status_code": res.status_code,
                           "error_type": res.error_type,
                           "error_repr": res.error_repr,
                           "content_type": res.content_type,
                           "body_head": res.text_head})
            print(f"  ⚠️ gamecode {gc}: {res.error_type} — ממשיך")
            continue

        parsed = parse_boxscore(res.payload, season, gc)
        if not parsed:
            failed.append({"season": season, "gamecode": gc, "status_code": res.status_code,
                           "error_type": "EmptyParse",
                           "error_repr": "התגובה התקבלה אך לא הופקו שורות",
                           "content_type": res.content_type, "body_head": res.text_head})
            print(f"  ⚠️ gamecode {gc}: התגובה תקינה אך ריקה מבחינת פירסור — ממשיך")
            continue

        rows.extend(parsed)
        done += 1

        if i % 25 == 0:
            pd.DataFrame(rows).to_csv(draft_path, index=False)
            print(f"  ... {i}/{len(codes)}  ({len(rows):,} שורות)")

    if failed:
        fpath = out_dir / f"failed_games_{season}.csv"
        pd.DataFrame(failed).to_csv(fpath, index=False)
        print(f"\n  🟡 {len(failed)} משחקים נכשלו — הרשימה: {fpath}")

    if not rows:
        print("  🔴 לא נמשכה אף שורה.")
        return False

    df = pd.DataFrame(rows)
    df = df[[c for c in COLUMNS if c in df.columns]]

    print(f"\n  נמשכו {done}/{len(codes)} משחקים · {len(df):,} שורות")
    problems = sanity_check(df, season, done, index_path)

    fail_rate = len(failed) / max(len(codes), 1)
    if fail_rate >= 0.02:
        problems.append(f"{fail_rate:.1%} מהמשחקים נכשלו (סף: 2%)")

    if problems:
        print("\n  🔴 בדיקת השפיות נכשלה — **הקובץ לא נכתב**:")
        for p in problems:
            print(f"     · {p}")
        print(f"\n  הטיוטה נשמרה: {draft_path}")
        pd.DataFrame(rows).to_csv(draft_path, index=False)
        return False

    df.to_csv(out_path, index=False)
    if draft_path.exists():
        draft_path.unlink()
    print(f"\n  ✅ נשמר: {out_path}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int, default=[2018, 2021])
    ap.add_argument("--out-dir", default="data/raw")
    ap.add_argument("--index", default="data/processed/game_index.csv")
    ap.add_argument("--sleep", type=float, default=1.2)
    ap.add_argument("--all-games", action="store_true",
                    help="למשוך גם משחקים שלא שוחקו (ברירת מחדל: לא)")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="3 משחקים לעונה")
    ap.add_argument("--resume", action="store_true",
                    help="להמשיך מטיוטה קיימת במקום להתחיל מחדש")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")
    out_dir = resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = resolve(args.index)

    existing = find_boxscores(verbose=False)
    session = make_session()
    results = {}

    for season in args.seasons:
        if season in existing and not args.overwrite:
            print(f"\n  ⏭️  {season} כבר קיים ({existing[season].name}) — מדלג. "
                  f"(--overwrite כדי לדרוס)")
            continue
        results[season] = fetch_season(
            session, season, out_dir, index_path,
            args.sleep, played_only=not args.all_games,
            limit=3 if args.dry_run else None,
            resume=args.resume,
        )

    hdr("סיכום")
    if not results:
        print("  לא נמשכה אף עונה.")
        return 0
    for season, ok in results.items():
        print(f"  {'✅' if ok else '🔴'} {season}")
    print("\n  הבא: python src/verify_boxscores.py")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())