"""
build_positions.py  (Day 6)
---------------------------
קולט את גיליון העמדות הידני ומייצר data/processed/player_positions.csv.

העיקרון שקובע את הקובץ: **הקוד הוא המפתח, השם הוא תצוגה.**
העמודה שמולאה ידנית היא העמדה בלבד. הקודים הופקו מהדאטה ולא הוקלדו -
וזה בדיוק ההפך מבאג 4 של יום 4, שבו 12 מתוך 28 קודים ידניים היו
שגויים ושניים הצביעו על שחקנים אחרים לגמרי.

לכן הסקריפט מצליב לפי קוד, **ומאמת את השם כבקרה**. אי-התאמת שם
אינה שגיאה - היא אזהרה שמודפסת. אי-התאמת קוד היא שגיאה שזורקת.

הסקריפט זורק ולא מדפיס OK על:
  - קוד שאינו קיים ב-player_features
  - עמדה שאינה G/F/C
  - כפילות קוד
  - כיסוי מתחת לסף על מאגר המועמדים של עונת הדמו

הרצה:
    python src/build_positions.py <path_to_xlsx>
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR, RAW_DIR, DATA_DIR, ROOT_DIR

# PyCharm מריץ בלי ארגומנטים. במקום להיכשל, מחפשים במקומות הסבירים.
# הסדר מכוון: תיקיית הפרויקט לפני Downloads, כדי שקובץ שכבר נכנס
# לריפו ינצח עותק ישן בהורדות.
SEARCH_DIRS = [
    DATA_DIR / "manual",
    ROOT_DIR,
    RAW_DIR,
    PROCESSED_DIR,
    Path.home() / "Downloads",
    Path.home() / "Desktop",
]
SEARCH_GLOB = "*ositions*.xlsx"

VALID = {"G", "F", "C"}
DEMO_SEASON = 2025
MIN_COVERAGE = 1.00        # מאגר המועמדים חייב כיסוי מלא
SHEET = "positions"
OUT = "player_positions.csv"

COLS = ["priority", "player_code", "player_name", "team_last", "teams_all",
        "seasons", "age", "games", "min_pg", "pir_pg", "position"]


def load_sheet(path):
    df = pd.read_excel(path, sheet_name=SHEET, dtype={"קוד שחקן": str})
    if df.shape[1] < 11:
        raise ValueError(f"צפויות לפחות 11 עמודות, יש {df.shape[1]}. "
                         "נמחקה עמודה?")
    df = df.iloc[:, :11]
    df.columns = COLS
    df["player_code"] = df.player_code.astype(str).str.strip()
    df["position"] = (df.position.astype(str).str.strip().str.upper()
                      .replace({"NAN": None, "": None}))
    return df


def validate(df, feat):
    errs, warns = [], []

    dup = df[df.player_code.duplicated(keep=False)]
    if len(dup):
        errs.append(f"כפילות קוד: {sorted(dup.player_code.unique())}")

    filled = df[df.position.notna()]
    bad = filled[~filled.position.isin(VALID)]
    if len(bad):
        errs.append("עמדה לא חוקית: " +
                    ", ".join(f"{r.player_code}={r.position!r}"
                              for r in bad.itertuples()))

    known = set(feat.player_code)
    unknown = sorted(set(df.player_code) - known)
    if unknown:
        errs.append(f"{len(unknown)} קודים שאינם ב-player_features: "
                    f"{unknown[:10]}")

    # בקרת שם - אזהרה, לא שגיאה. הקוד הוא המפתח.
    nm = feat.drop_duplicates("player_code").set_index("player_code")
    for r in df.itertuples():
        if r.player_code not in nm.index:
            continue
        want = str(nm.loc[r.player_code, "player_name"]).strip()
        got = str(r.player_name).strip()
        if want != got:
            warns.append(f"{r.player_code}: גיליון={got!r} דאטה={want!r}")

    return errs, warns


def coverage(df, feat):
    print("\n" + "=" * 70)
    print("כיסוי")
    print("=" * 70)
    filled = set(df[df.position.notna()].player_code)
    rows = []
    for s in sorted(feat.season.unique()):
        pool = set(feat[feat.season == s].player_code)
        cov = len(pool & filled) / len(pool)
        rows.append({"עונה": s, "מאגר": len(pool),
                     "עם עמדה": len(pool & filled), "כיסוי": f"{cov:.1%}"})
    print(pd.DataFrame(rows).to_string(index=False))

    pool = set(feat[feat.season == DEMO_SEASON].player_code)
    cov = len(pool & filled) / len(pool)
    if cov < MIN_COVERAGE:
        missing = sorted(pool - filled)[:15]
        raise ValueError(
            f"כיסוי {cov:.1%} על מאגר {DEMO_SEASON}, נדרש "
            f"{MIN_COVERAGE:.0%}. חסרים: {missing}")
    return cov


def roster_shape(df, feat):
    """מה הסגלים האמיתיים עושים בפועל.

    אילוץ העמדות ב-PuLP צריך להיגזר מכאן ולא מהאינטואיציה. זה
    'כלל לפני מקרה': הגבולות נקבעים ממה שקבוצות אמיתיות עשו,
    לפני שרואים מה האופטימייזר רוצה לעשות.
    """
    print("\n" + "=" * 70)
    print(f"מבנה הסגלים בפועל - עונת {DEMO_SEASON}")
    print("=" * 70)

    pos = df.set_index("player_code").position
    d = feat[feat.season == DEMO_SEASON].copy()
    d["position"] = d.player_code.map(pos)

    # שחקן שהוחלף נושא 'ASV;ULK' בעמודת הקבוצה. בלי הפיצול הזה כל
    # צירוף כזה נספר כ"קבוצה" בת שחקן אחד, וכל מינימום נגרר ל-0.
    n_traded = int(d.team.astype(str).str.contains(";").sum())
    d = (d.assign(team=d.team.astype(str).str.split(";"))
         .explode("team"))
    d["team"] = d.team.str.strip()
    print(f"  {n_traded} שחקנים שהוחלפו - נספרים בכל אחת מקבוצותיהם")
    print(f"  קבוצות אחרי הפיצול: {d.team.nunique()}\n")

    t = (d.pivot_table(index="team", columns="position",
                       values="player_code", aggfunc="count")
         .fillna(0).astype(int))
    for c in ("G", "F", "C"):
        if c not in t.columns:
            t[c] = 0
    t = t[["G", "F", "C"]]
    t["סה\"כ"] = t.sum(axis=1)
    print(t.sort_index().to_string())

    print("\n  מינימום שנצפה בפועל על פני כל הקבוצות:")
    for c in ("G", "F", "C"):
        print(f"    {c}: min={t[c].min()} | חציון={t[c].median():.0f} | "
              f"max={t[c].max()}")

    print("\n  אילוץ מוצע ל-PuLP (הרצפה שנצפתה בפועל):")
    for c in ("G", "F", "C"):
        print(f"    Σ x(i | pos={c}) >= {int(t[c].min())}")
    print("\n  זה אילוץ *רופף* בכוונה: הוא לא מכריח את האופטימייזר")
    print("  להיראות כמו קבוצה ממוצעת, רק אוסר סגל בלתי אפשרי.")
    return t


def find_input():
    """אם לא ניתן ארגומנט - מחפשים. אם נמצא יותר מאחד, לא מנחשים.

    קובץ זמני של Excel נפתח ב-'~$' ונראה בדיוק כמו הקובץ האמיתי
    ל-glob. הוא מסונן, אחרת openpyxl נופל על קובץ נעול.
    """
    hits = []
    for d in SEARCH_DIRS:
        try:
            if not d.is_dir():
                continue
            hits += [p for p in sorted(d.glob(SEARCH_GLOB))
                     if not p.name.startswith("~$")]
        except OSError:
            continue

    # אותו קובץ יכול להופיע בשתי תיקיות מהרשימה
    uniq, seen = [], set()
    for p in hits:
        r = p.resolve()
        if r not in seen:
            seen.add(r)
            uniq.append(p)

    if not uniq:
        print("לא נמצא קובץ עמדות. שלוש דרכים:")
        print(f"  1. לשים את ה-xlsx ב: {DATA_DIR / 'manual'}")
        print("  2. להריץ עם נתיב: python src/build_positions.py <xlsx>")
        print("  3. ב-PyCharm: Run > Edit Configurations > Parameters")
        print("\nנסרקו:")
        for d in SEARCH_DIRS:
            print(f"    {d}  {'(קיימת)' if d.is_dir() else '(לא קיימת)'}")
        raise SystemExit(1)

    if len(uniq) > 1:
        print("נמצאו כמה קבצים מתאימים. ציין נתיב מפורש:")
        for p in uniq:
            print(f"    {p}")
        raise SystemExit(1)

    print(f"[נמצא] {uniq[0]}")
    return uniq[0]


def main():
    if len(sys.argv) >= 2:
        path = Path(sys.argv[1])
        if not path.exists():
            raise FileNotFoundError(path)
    else:
        path = find_input()

    feat = pd.read_csv(PROCESSED_DIR / "player_features.csv",
                       dtype={"player_code": str})
    df = load_sheet(path)
    print(f"[קלט] {len(df)} שורות | מולאו {df.position.notna().sum()}")

    errs, warns = validate(df, feat)
    if warns:
        print(f"\n[אזהרה] {len(warns)} אי-התאמות שם (הקוד הוא המפתח):")
        for w in warns[:10]:
            print("   ", w)
    if errs:
        for e in errs:
            print(f"\n[שגיאה] {e}")
        raise ValueError(f"{len(errs)} שגיאות. לא נכתב קובץ.")

    coverage(df, feat)
    roster_shape(df, feat)

    # השם נלקח מהדאטה, לא מהגיליון - כדי שטעות הקלדה לא תזלוג פנימה
    nm = feat.drop_duplicates("player_code").set_index("player_code")
    out = df[df.position.notna()][["player_code", "position"]].copy()
    out["player_name"] = out.player_code.map(nm.player_name)
    out = out[["player_code", "player_name", "position"]].sort_values(
        "player_code")

    dest = PROCESSED_DIR / OUT
    out.to_csv(dest, index=False)
    print(f"\n[נכתב] {dest} | {len(out)} שורות")
    print(out.position.value_counts().to_string())


if __name__ == "__main__":
    main()