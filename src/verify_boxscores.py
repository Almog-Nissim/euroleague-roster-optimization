"""
verify_boxscores.py — שער האימות. רץ לפני שנוגעים בעקומת ה-usage.

תיקונים
-------
🔴 **תיקיית עבודה.** `player_season.csv` ופלט הצבירה נפתרו מול
`src/` במקום מול שורש הריפו. עכשיו דרך `el_paths.resolve`.
🔴 `glob("*.csv")` בלע את `accumulated_rs_2025.csv` — קובץ מצטבר
בסכמה אחרת. עכשיו הזיהוי לפי תוכן, והדילוגים מדווחים.

תחזיות נעולות
-------------
אלמוג: שחזור PIR — התאמה מלאה, חד משמעית.
קלוד : 99.5%+. מתחת ל-95% -> הנוסחה שלנו שגויה, לא הדאטה.
⚠️ שתי תחזיות זהות אינן אימות — הן מתאם. לכן אי-ההתאמות מפורקות
לפי עונה, לפי גודל הפער ולפי שחקנים עם אפס דקות.

**קריאת הסימן:** פער קבוע = חסר איבר בנוסחה. פער מפוזר = בעיה בדאטה.

הרצה:  python src/verify_boxscores.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import load_boxscores, repo_root, resolve  # noqa: E402

PIR_PLUS = ["Points", "TotalRebounds", "Assistances", "Steals", "BlocksFavour", "FoulsReceived"]
PIR_MINUS_DIRECT = ["Turnovers", "BlocksAgainst", "FoulsCommited"]

FAIL: list[str] = []
WARN: list[str] = []


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def parse_minutes(s) -> float:
    """'23:45' -> 23.75 ; 'DNP' / '' / NaN -> 0.0"""
    if pd.isna(s):
        return 0.0
    s = str(s).strip()
    if not s or s.upper() in ("DNP", "DNS", "-"):
        return 0.0
    m = re.match(r"^(\d+):(\d{1,2})$", s)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60.0
    try:
        return float(s)
    except ValueError:
        return np.nan


# ---------------------------------------------------------------- A
def check_schema(df: pd.DataFrame) -> None:
    hdr("A. אחידות סכמה")
    schemas = df.attrs.get("schemas", {})
    base = None
    for season, cols in sorted(schemas.items()):
        cols_set = set(cols) - {"__file"}
        if base is None:
            base = cols_set
        extra, missing = cols_set - base, base - cols_set
        flag = "✅" if not extra and not missing else "⚠️"
        print(f"  {flag} {season}: {len(cols_set)} עמודות"
              + (f"  יתרות: {sorted(extra)}" if extra else "")
              + (f"  חסרות: {sorted(missing)}" if missing else ""))

    have = sorted(s for s, c in schemas.items() if "Phase" in c)
    lack = sorted(s for s, c in schemas.items() if "Phase" not in c)
    print(f"\n  עם Phase : {have}")
    print(f"  בלי Phase: {lack}")
    if lack:
        WARN.append(f"{len(lack)} עונות בלי Phase — game_index.py לפני כל סינון פלייאוף")

    present = sorted(int(s) for s in schemas)
    gaps = [y for y in range(2016, 2026) if y not in present and y != 2021]
    print(f"\n  עונות שנטענו: {present}")
    if gaps:
        FAIL.append(f"עונות חסרות: {gaps}")
        print(f"  🔴 חסרות: {gaps}")
    if 2021 not in present:
        WARN.append("2021 עדיין לא נמשכה")


# ---------------------------------------------------------------- B
def split_players(df: pd.DataFrame):
    hdr("B. שורות שחקן מול שורות סיכום")
    pid = df["Player_ID"].astype(str).str.strip()
    name = df.get("Player", pd.Series([""] * len(df))).astype(str).str.strip().str.upper()
    is_total = (pid.str.upper().isin(["TOTAL", "TEAM", "NAN", ""])
                | name.str.contains(r"TOTAL|TEAM$", regex=True, na=False))
    print(f"  שורות שחקן : {int((~is_total).sum()):,}")
    print(f"  שורות סיכום: {int(is_total.sum()):,}")
    if is_total.sum():
        print(f"  דוגמאות: {df.loc[is_total, 'Player'].dropna().unique()[:5]}")
    return df[~is_total].copy(), df[is_total].copy()


# ---------------------------------------------------------------- C
def check_pir(players: pd.DataFrame) -> None:
    hdr("C. 🔴 שחזור PIR מהרכיבים מול Valuation")

    need = PIR_PLUS + PIR_MINUS_DIRECT + [
        "FieldGoalsAttempted2", "FieldGoalsMade2",
        "FieldGoalsAttempted3", "FieldGoalsMade3",
        "FreeThrowsAttempted", "FreeThrowsMade", "Valuation",
    ]
    missing = [c for c in need if c not in players.columns]
    if missing:
        FAIL.append(f"חסרות עמודות לשחזור PIR: {missing}")
        print(f"  🔴 חסרות: {missing}")
        return

    d = players.copy()
    for c in need:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    missed = ((d["FieldGoalsAttempted2"] - d["FieldGoalsMade2"])
              + (d["FieldGoalsAttempted3"] - d["FieldGoalsMade3"])
              + (d["FreeThrowsAttempted"] - d["FreeThrowsMade"]))
    d["PIR_calc"] = d[PIR_PLUS].sum(axis=1) - missed - d[PIR_MINUS_DIRECT].sum(axis=1)
    d["PIR_diff"] = d["PIR_calc"] - d["Valuation"]

    valid = d["PIR_diff"].notna()
    exact = float((d.loc[valid, "PIR_diff"] == 0).mean())
    n_bad = int((d.loc[valid, "PIR_diff"] != 0).sum())

    print(f"  שורות שנבדקו : {int(valid.sum()):,}")
    print(f"  התאמה מדויקת : {exact:.4%}")
    print(f"  אי-התאמות    : {n_bad:,}")

    if exact == 1.0:
        print("\n  ✅ התאמה מלאה. הרכיבים אמינים — הפירוק מבוסס.")
        return
    if exact >= 0.995:
        print("\n  ✅ מעל הסף שנרשם מראש (99.5%).")
    elif exact >= 0.95:
        WARN.append(f"שחזור PIR {exact:.3%} — מתחת לתחזית, מעל סף הפסילה")
        print("\n  ⚠️ מתחת לתחזית של שנינו. קרא את הפירוק לפני שממשיכים.")
    else:
        FAIL.append(f"שחזור PIR {exact:.3%} — מתחת ל-95%.")
        print("\n  🔴 מתחת ל-95%. **עצור.** הפירוק עומד על חול.")

    bad = d[valid & (d["PIR_diff"] != 0)]
    if len(bad):
        print("\n  לפי עונה:")
        tab = bad.groupby("Season").agg(n=("PIR_diff", "size"), mean_diff=("PIR_diff", "mean"))
        tab["share"] = tab["n"] / d[valid].groupby("Season").size()
        print(tab.to_string())

        print("\n  התפלגות הפער (קבוע -> חסר איבר בנוסחה):")
        print(bad["PIR_diff"].value_counts().head(10).to_string())

        if "Minutes" in bad.columns:
            print(f"\n  שיעור אי-ההתאמות עם 0 דקות: "
                  f"{float(bad['Minutes'].apply(parse_minutes).eq(0).mean()):.1%}")

        print("\n  דוגמאות:")
        cols = [c for c in ["Season", "Gamecode", "Player", "Valuation", "PIR_calc", "PIR_diff"]
                if c in bad.columns]
        print(bad[cols].head(5).to_string(index=False))


# ---------------------------------------------------------------- D
def check_minutes(players: pd.DataFrame) -> None:
    hdr("D. דקות — סכום לקבוצה למשחק")
    if "Minutes" not in players.columns:
        WARN.append("אין עמודת Minutes")
        return
    d = players.copy()
    d["min_num"] = d["Minutes"].apply(parse_minutes)

    unparsed = int(d["min_num"].isna().sum())
    print(f"  ערכים שלא נפרסרו: {unparsed:,}")
    if unparsed:
        print(f"  דוגמאות: {d.loc[d['min_num'].isna(), 'Minutes'].unique()[:10]}")
        WARN.append(f"{unparsed} ערכי דקות לא נפרסרו")

    tm = d.groupby(["Season", "Gamecode", "Team"])["min_num"].sum().reset_index()
    print("\n  התפלגות דקות-קבוצה-משחק:")
    print(tm["min_num"].describe().to_string())

    reg = tm["min_num"].between(199.5, 200.5)
    ot = (tm["min_num"].between(224.5, 225.5) | tm["min_num"].between(249.5, 250.5)
          | tm["min_num"].between(274.5, 275.5))
    odd = tm[~(reg | ot)]
    print(f"\n  בדיוק 200 (רגיל) : {reg.mean():.2%}")
    print(f"  הארכות           : {ot.mean():.2%}")
    print(f"  לא מוסבר         : {len(odd):,}")
    if len(odd):
        print(odd.head(10).to_string(index=False))
        WARN.append(f"{len(odd)} קבוצות-משחק עם סכום דקות לא מוסבר")


# ---------------------------------------------------------------- E
def check_rows_per_game(players: pd.DataFrame) -> None:
    hdr("E. שורות למשחק")
    g = players.groupby(["Season", "Gamecode"]).size()
    print(g.groupby("Season").describe().to_string())

    thin = g[g < 20]
    if len(thin):
        print(f"\n  ⚠️ {len(thin)} משחקים עם פחות מ-20 שורות:")
        print(thin.head(15).to_string())
        WARN.append(f"{len(thin)} משחקים חלקיים")

    print("\n  משחקים ייחודיים לעונה:")
    print(players.groupby("Season")["Gamecode"].nunique().to_string())


# ---------------------------------------------------------------- F
def check_ids(players: pd.DataFrame, player_season: Path) -> None:
    hdr("F. התפר — התאמת Player_ID")
    if not player_season.exists():
        WARN.append(f"לא נמצא {player_season} — בדיקת התפר לא רצה")
        print(f"  ⚠️ לא נמצא {player_season}")
        return

    ps = pd.read_csv(player_season, dtype=str, low_memory=False)
    id_col = next((c for c in ps.columns if c.lower() in
                   ("player_id", "player_code", "playercode", "code")), None)
    if id_col is None:
        WARN.append("לא זוהתה עמודת מזהה ב-player_season")
        print(f"  ⚠️ עמודות: {list(ps.columns)}")
        return
    print(f"  קובץ: {player_season}")
    print(f"  עמודת מזהה: {id_col}")

    bx_raw = players["Player_ID"].astype(str).str.strip()
    ps_raw = ps[id_col].astype(str).str.strip()

    # 🔴 מזהה אינו מספר. ב-2016 כ-19% מהמזהים נושאים אותיות —
    # PLUO, PARN, PCHX, PJPF. נרמול מבוסס-ספרות הופך את PLUO
    # למחרוזת ריקה ומקריס עשרות שחקנים למזהה אחד. אותה משפחה
    # של הבאג `lstrip('P')` מיום 9.
    alnum = ~bx_raw.str.match(r"^P\d+$", na=False)
    alnum_share = float(alnum.mean())
    print(f"\n  מזהים שאינם בפורמט P+ספרות: {int(alnum.sum()):,} ({alnum_share:.1%})")
    if alnum_share > 0.01:
        print(f"    דוגמאות: {sorted(bx_raw[alnum].unique())[:8]}")
        print("    🔴 נרמול מבוסס-ספרות ימחק אותם. השתמש ב-as-is בלבד.")

    variants = {
        "as-is": lambda s: s,
        "upper": lambda s: s.str.upper(),
        "strip leading P": lambda s: s.str.replace(r"^P", "", regex=True),
        "digits only": lambda s: s.str.replace(r"\D", "", regex=True),
        "digits, no leading zeros": lambda s: s.str.replace(r"\D", "", regex=True).str.lstrip("0"),
        "zero-pad 6": lambda s: s.str.replace(r"\D", "", regex=True).str.zfill(6),
    }

    print(f"\n  ייחודיים: בוקסקור {bx_raw.nunique():,} · player_season {ps_raw.nunique():,}")
    print(f"\n  {'נרמול':<28} {'חפיפה':>8} {'% מהבוקסקור':>14}")
    print("  " + "-" * 52)
    best, best_n = None, -1
    for name, fn in variants.items():
        a, b = set(fn(bx_raw).unique()), set(fn(ps_raw).unique())
        inter = len(a & b)
        print(f"  {name:<28} {inter:>8,} {inter / max(len(a), 1):>13.1%}")
        if inter > best_n:
            best, best_n = name, inter

    print(f"\n  הטוב ביותר: {best} ({best_n:,})")
    if best != "as-is" and alnum_share > 0.01:
        WARN.append(f"הנרמול המנצח הוא '{best}' אך {alnum_share:.1%} מהמזהים "
                    f"נושאים אותיות — בדוק שאינו מקריס אותם")
    if best_n < 0.8 * bx_raw.nunique():
        FAIL.append(f"חפיפת מזהים מקסימלית {best_n} — התפר שבור")
        print("  🔴 חפיפה נמוכה. זה התפר שהפיל אותנו בעבר.")
    else:
        print(f"  ✅ '{best}' הוא הנרמול הקנוני. כתוב אותו למקום אחד בקוד.")


# ---------------------------------------------------------------- G
def check_aggregation(players: pd.DataFrame) -> None:
    hdr("G. צבירה לשחקן-עונה")
    print("  קובעת אם ימים 1-9 עומדים על אותו בסיס כמו הבוקסקורים.")
    d = players.copy()
    d["min_num"] = d["Minutes"].apply(parse_minutes)
    agg = (d.groupby(["Season", "Player_ID"])
             .agg(games_bx=("Gamecode", "nunique"),
                  minutes_bx=("min_num", "sum"),
                  pir_bx=("Valuation", lambda s: pd.to_numeric(s, errors="coerce").sum()))
             .reset_index())
    out = resolve("data/processed/boxscore_player_season_agg.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(out, index=False)
    print(f"  נשמר: {out}  ({len(agg):,} שורות)")
    print("\n  ⚠️ ההשוואה עצמה דורשת את הנרמול מ-F ואת סינון ה-Phase")
    print("     (player_season אינו כולל פלייאוף). רק אחרי game_index.py.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--player-season", default="data/processed/player_season.csv")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")

    hdr("טעינה")
    df = load_boxscores(args.root, verbose=True)
    print(f"\n  סה\"כ {len(df):,} שורות")

    check_schema(df)
    players, _ = split_players(df)
    check_pir(players)
    check_minutes(players)
    check_rows_per_game(players)
    check_ids(players, resolve(args.player_season))
    check_aggregation(players)

    hdr("סיכום השער")
    if FAIL:
        print("  🔴 עצור:")
        for f in FAIL:
            print(f"     · {f}")
    if WARN:
        print("  ⚠️ לטיפול:")
        for w in WARN:
            print(f"     · {w}")
    if not FAIL and not WARN:
        print("  ✅ השער נקי. המשך ל-usage_power_check.py")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())