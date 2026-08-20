"""
el_paths.py — שורש הריפו ואיתור קבצי בוקסקור. מקום אחד, לא ארבעה.

שני באגים שהצטברו, ושניהם נסגרים כאן
------------------------------------
1. 🔴 **תיקיית עבודה.** PyCharm מריץ עם CWD = תיקיית הסקריפט. כל
   נתיב יחסי נפתר מול `src/`, ולכן `game_index.csv` נכתב ל-
   `src/data/processed/` ו-`data/raw/boxscores` חיפש בתיקייה שלא
   קיימת. עכשיו השורש מחושב מ-`__file__` ולא מ-CWD — עובד מכל
   מקום שממנו מריצים.
2. 🔴 **שם הקובץ.** ברירת המחדל הייתה `boxscore_2022.csv`, בפועל
   `boxscore_player_2022.csv`.

תיקון (2) לבדו לא היה פותר כלום. שניהם היו צריכים להיסגר יחד.

ובנוסף: `glob("*.csv")` בלע את `accumulated_rs_2025.csv` — קובץ
מצטבר בסכמה אחרת — ושרשר אותו לבוקסקורים. זה לא קורס, זה מדפיס
מספרים סבירים ושגויים. לכן הזיהוי כאן הוא לפי **תוכן**: קובץ
נחשב בוקסקור רק אם יש בו את העמודות שמגדירות שורת שחקן במשחק.
שינוי שם עתידי לא ישבור, וקובץ מצטבר עתידי לא ייבלע.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

REQUIRED_COLS = {"Gamecode", "Player_ID", "Valuation", "Minutes"}
ROOT_MARKERS = [".git", "requirements.txt", "pyproject.toml", "setup.py", ".gitignore"]
SEARCH_DIRS = ["data/raw/boxscores", "data/raw", "data/processed", "data"]
SEASON_RE = re.compile(r"(19|20)(\d{2})")

# קבצי ביניים. `fetch_boxscores_v2` שומר טיוטה כל 25 משחקים, והיא
# עומדת בשני תנאי הזיהוי — שנה בשם ועמודות חובה. בלי הסינון הזה
# טיוטה באמצע ריצה נקלטת כקובץ סופי, וכל בדיקה שמצליבה מולה
# מדווחת "אי-התאמות" שהן פשוט משחקים שטרם נמשכו.
DRAFT_PREFIXES = ("_", "~", ".")
DRAFT_TOKENS = ("draft", "partial", "tmp", "temp", "backup", "old")

_ROOT_CACHE: Path | None = None


def repo_root(verbose: bool = False) -> Path:
    """
    שורש הריפו, מחושב מ-`__file__` ולא מ-CWD.

    סדר החיפוש: סמן ריפו (.git וכו') -> תיקייה שיש בה גם src וגם
    data -> ההורה של `src`. אם כלום לא נמצא, ההורה של תיקיית הקוד.
    """
    global _ROOT_CACHE
    if _ROOT_CACHE is not None:
        return _ROOT_CACHE

    here = Path(__file__).resolve().parent
    root = None

    for p in [here, *here.parents]:
        if any((p / m).exists() for m in ROOT_MARKERS):
            root = p
            break

    if root is None:
        for p in [here, *here.parents]:
            if (p / "src").is_dir() and (p / "data").is_dir():
                root = p
                break

    if root is None:
        root = here.parent if here.name == "src" else here

    _ROOT_CACHE = root
    if verbose:
        print(f"שורש הריפו: {root}")

    stray = root / "src" / "data"
    if stray.is_dir():
        print(f"  ⚠️ קיימת {stray} — שארית מהרצה עם CWD שגוי. מחק אותה.")

    return root


def resolve(rel: str | Path) -> Path:
    """נתיב יחסי -> מוחלט מול שורש הריפו."""
    rel = Path(rel)
    return rel if rel.is_absolute() else repo_root() / rel


def _season_from_name(path: Path) -> int | None:
    matches = SEASON_RE.findall(path.stem)
    years = [int(a + b) for a, b in matches]
    valid = [y for y in years if 2000 <= y <= 2035]
    return valid[-1] if valid else None


def _looks_like_boxscore(path: Path) -> bool:
    try:
        head = pd.read_csv(path, nrows=1)
    except Exception:
        return False
    return REQUIRED_COLS.issubset(set(head.columns))


def _is_draft(path: Path) -> bool:
    stem = path.stem
    if stem.startswith(DRAFT_PREFIXES):
        return True
    return any(tok in stem.lower() for tok in DRAFT_TOKENS)


def find_boxscores(root: str | Path | None = None, verbose: bool = True) -> dict[int, Path]:
    """מחזיר {עונה: נתיב}. מדלג על כל מה שאינו בוקסקור ומדווח למה."""
    base = Path(root).resolve() if root else repo_root()

    candidates: list[Path] = []
    seen = set()
    for d in SEARCH_DIRS:
        p = base / d
        if not p.is_dir():
            continue
        for f in sorted(p.glob("*.csv")):
            if f.resolve() not in seen:
                seen.add(f.resolve())
                candidates.append(f)

    if not candidates:
        for f in sorted(base.rglob("*.csv")):
            if f.resolve() not in seen:
                seen.add(f.resolve())
                candidates.append(f)

    found: dict[int, Path] = {}
    skipped: list[tuple[Path, str]] = []

    for f in candidates:
        season = _season_from_name(f)
        if _is_draft(f):
            skipped.append((f, "טיוטה או קובץ ביניים — משיכה כנראה בעיצומה"))
        elif season is None:
            skipped.append((f, "אין שנה בשם"))
        elif not _looks_like_boxscore(f):
            skipped.append((f, "לא בוקסקור — חסרות עמודות חובה"))
        elif season in found:
            skipped.append((f, f"כפילות לעונה {season} — נבחר {found[season].name}"))
        else:
            found[season] = f

    if verbose:
        print(f"איתור קבצי בוקסקור (שורש: {base})")
        print("-" * 74)
        for season in sorted(found):
            print(f"  ✅ {season}  {found[season].relative_to(base)}")
        for f, why in skipped:
            print(f"  ⏭️  דילוג: {f.name:<32} ({why})")
        if not found:
            print("  🔴 לא נמצא אף קובץ בוקסקור.")
        print()

    return dict(sorted(found.items()))


def load_boxscores(root: str | Path | None = None, seasons: list[int] | None = None,
                   verbose: bool = True) -> pd.DataFrame:
    files = find_boxscores(root, verbose=verbose)
    if seasons:
        files = {s: p for s, p in files.items() if s in seasons}
    if not files:
        raise SystemExit("🔴 אין קבצי בוקסקור לטעינה.")

    frames, schemas = [], {}
    for season, path in files.items():
        df = pd.read_csv(path, dtype={"Gamecode": str, "Player_ID": str}, low_memory=False)
        if "Season" not in df.columns:
            df["Season"] = season
        schemas[str(season)] = list(df.columns)
        df["__file"] = path.name
        frames.append(df)
        if verbose:
            print(f"  נטען {path.name:<34} {len(df):>8,} שורות")

    out = pd.concat(frames, ignore_index=True)
    out.attrs["schemas"] = schemas
    out.attrs["files"] = {s: str(p) for s, p in files.items()}
    return out