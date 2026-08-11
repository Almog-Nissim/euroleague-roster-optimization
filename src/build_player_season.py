"""
build_player_season.py  (v2 - Day 4)
------------------------------------
בונה טבלת שחקן-עונה מקבצי accumulated_rs_{season}.csv.

שינויים מגרסת יום 3:
  1. SEASONS מורחב ל-2016-2025 (2021-22 מושמטת - אי-התאמה API/טבלאות).
     נדרש עבור el_seasons: בחלון של 3 עונות בלבד, ותיק עם 12 עונות
     ושחקן עם 3 יושבים באותו תא.
  2. player_code מנורמל למחרוזת ללא אפסים מובילים. שני באגים ידועים
     בשדה הזה: קודים אלפאנומריים (LCZ, JDR) ואפסים מובילים לא יציבים
     בין builds. הקודים האלפאנומריים שייכים דווקא לוותיקים.
  3. כותב ל-player_season_extended.csv ולא דורס את הקובץ המאומת.
     אימות ידני, ואז החלפה. לקח יום 3.
  4. היעדר team_season.csv הוא כשל קשיח, לא אזהרה.

שחקנים שעברו קבוצה (קוד משורשר 'OLY;PAR') *אינם* מושמטים כאן.
ברמת הקבוצה הם הושמטו כי אי אפשר לפצל את דקותיהם בין שני מועדונים.
ברמת השחקן אין בעיה כזו — הוא שיחק, יש לו PIR, ורק שיוך המועדון
מעורפל. מסומנים בדגל is_traded וההחלטה נדחית לשלב הבחירה.
"""

import pandas as pd
from paths import RAW_DIR, PROCESSED_DIR

SEASONS = [2016, 2017, 2018, 2019, 2020, 2022, 2023, 2024, 2025]
EXCLUDED = {2021: "אי-התאמה בין ה-API לטבלאות הדירוג (יום 2)"}

OUT_NAME = "player_season.csv"   # לא דורס את המאומת

TEAM_COL, PIR_COL, MIN_COL = "player.team.code", "pir", "minutesPlayed"
PLAYER_COL, NAME_COL, AGE_COL = "player.code", "player.name", "player.age"
GAMES_COL, STARTS_COL = "gamesPlayed", "gamesStarted"

NUMERIC = [PIR_COL, MIN_COL, GAMES_COL, STARTS_COL, AGE_COL]
REQUIRED = [TEAM_COL, PIR_COL, MIN_COL, PLAYER_COL, NAME_COL, AGE_COL,
            GAMES_COL, STARTS_COL]


def normalise_code(s: pd.Series) -> pd.Series:
    """player_code הוא מחרוזת: קודי ותיקים אלפאנומריים (LCZ, JDR),
    ואפסים מובילים שמופיעים ונעלמים בין builds. מנרמל פעם אחת, בכתיבה."""
    return (s.astype(str).str.strip().str.upper()
             .str.lstrip("0").replace("", pd.NA))


def load(season):
    path = RAW_DIR / f"accumulated_rs_{season}.csv"
    if not path.exists():
        print(f"[SKIP] {season}: קובץ חסר -> {path}")
        return None

    df = pd.read_csv(path, dtype={PLAYER_COL: str})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        print(f"[FAIL] {season}: עמודות חסרות {missing}")
        return None

    for c in NUMERIC:
        before = df[c].notna().sum()
        df[c] = pd.to_numeric(df[c], errors="coerce")
        lost = before - df[c].notna().sum()
        if lost:
            print(f"   [WARN] {season}: {lost} ערכים ב-{c} לא המירו למספר")

    out = df[REQUIRED].rename(columns={
        PLAYER_COL: "player_code", NAME_COL: "player_name", AGE_COL: "age",
        TEAM_COL: "team", GAMES_COL: "games", STARTS_COL: "games_started",
        MIN_COL: "minutes", PIR_COL: "sum_pir",
    })
    out["player_code"] = normalise_code(out["player_code"])
    out["season"] = season
    out["is_traded"] = out["team"].astype(str).str.contains(";", na=False)

    n_bad = int(out["player_code"].isna().sum())
    if n_bad:
        raise RuntimeError(f"{season}: {n_bad} שורות ללא player_code תקין")

    # שחקן ללא משחקים אינו תצפית — המכנה יתפוצץ
    n0 = int((out["games"] <= 0).sum())
    if n0:
        print(f"   [DROP] {n0} שחקנים עם 0 משחקים")
        out = out.loc[out["games"] > 0].copy()

    out["pir_per_game"] = out["sum_pir"] / out["games"]
    out["min_per_game"] = out["minutes"] / out["games"]
    out["start_rate"]   = out["games_started"] / out["games"]

    print(f"   [OK] {season}: {len(out)} שחקנים | "
          f"{int(out['is_traded'].sum())} traded")
    return out


def check_code_stability(master: pd.DataFrame):
    """קוד שמופיע תחת שני שמות שונים = מיחזור קודים.
    בחלון של 4 עונות זה לא צף. ב-9 עונות זה בהחלט יכול."""
    names = master.groupby("player_code")["player_name"].nunique()
    dupes = names[names > 1]
    if len(dupes):
        print(f"\n[FAIL] {len(dupes)} קודים תחת יותר משם אחד:")
        bad = master[master.player_code.isin(dupes.index)]
        print(bad[["player_code", "player_name", "season"]]
              .drop_duplicates().sort_values("player_code")
              .head(20).to_string(index=False))
        raise RuntimeError("player_code אינו מזהה יציב לאורך העונות.")
    print(f"[CHECK] יציבות קודים: {master.player_code.nunique()} קודים, "
          f"שם אחד לכל קוד")


def build():
    print("=" * 70)
    print(f"BUILD PLAYER-SEASON v2 | seasons={SEASONS}")
    for s, why in EXCLUDED.items():
        print(f"  מושמטת: {s} — {why}")
    print("=" * 70)

    frames = [f for f in (load(s) for s in SEASONS) if f is not None]
    if not frames:
        raise RuntimeError("לא נבנתה אף עונה.")

    master = pd.concat(frames, ignore_index=True)

    built, expected = set(master["season"]), set(SEASONS)
    if built != expected:
        raise RuntimeError(f"חסרות עונות: {sorted(expected - built)}")

    master = master[["season", "player_code", "player_name", "age", "team",
                     "is_traded", "games", "games_started", "start_rate",
                     "minutes", "min_per_game", "sum_pir", "pir_per_game"]]
    master = master.sort_values(["season", "sum_pir"], ascending=[True, False])

    check_code_stability(master)

    # --- אימות מול team_season.csv ---
    # team_season נבנה *ללא* שחקנים משורשרים, ולכן ההשוואה מריצה את
    # אותו סינון. פער כלשהו = שתי הטבלאות אינן מתארות אותו דבר.
    ts_path = PROCESSED_DIR / "team_season.csv"
    if not ts_path.exists():
        raise RuntimeError(f"team_season.csv לא נמצא -> {ts_path}. "
                           "האימות הצולב הוא תנאי לכתיבה.")

    ts = pd.read_csv(ts_path)
    mine = (master.loc[~master["is_traded"]]
                  .groupby(["season", "team"])["sum_pir"].sum()
                  .reset_index(name="pir_player_table"))
    cmp = ts[["season", "team", "sum_pir"]].merge(mine, on=["season", "team"])
    cmp["diff"] = (cmp["sum_pir"] - cmp["pir_player_table"]).abs()
    worst = cmp["diff"].max()
    print(f"\n[CHECK] התאמה מול team_season: {len(cmp)} קבוצות-עונה, "
          f"פער מרבי {worst:.6f}")
    if worst > 1e-6:
        print(cmp.nlargest(5, "diff").to_string(index=False))
        raise RuntimeError("סכומי PIR אינם תואמים בין הטבלאות.")

    # כל עונה חייבת להצליב, לא רק הסכום הכולל
    per_season = cmp.groupby("season")["diff"].max()
    unmatched = set(SEASONS) - set(cmp["season"])
    if unmatched:
        raise RuntimeError(f"עונות ללא אימות צולב: {sorted(unmatched)}")
    print(f"[CHECK] כל {len(per_season)} העונות הצליבו")

    out = PROCESSED_DIR / OUT_NAME
    master.to_csv(out, index=False)
    if not out.exists():
        raise RuntimeError(f"הכתיבה דווחה כהצלחה אך הקובץ אינו קיים: {out}")
    print(f"\n[SUCCESS] {out.resolve()}  ({len(master)} שורות)")

    print("\n--- שחקנים לעונה ---")
    print(master.groupby("season").agg(
        players=("player_code", "nunique"),
        traded=("is_traded", "sum"),
        min_median=("minutes", "median"),
        min_max=("minutes", "max"),
    ).to_string())

    # --- התוצר של יום 4: el_seasons ---
    # חלון הקלט לעונת הדמו 2025-26 הוא כל מה שקדם לה.
    win = master[master.season <= 2024]
    n = win.groupby("player_code").season.nunique()
    cat = n.clip(upper=4)
    print(f"\n--- el_seasons (חלון 2016-2024, {len(n)} שחקנים) ---")
    print("ותק גולמי:")
    print(n.value_counts().sort_index().to_string())
    print("\nקטגוריות (4 = 4 ומעלה):")
    for k, v in cat.value_counts(normalize=True).sort_index().items():
        print(f"  {int(k)}{'+' if k == 4 else ' '}: {v*100:5.1f}%  "
              f"(n={int((cat == k).sum())})")

    print("\n--- התפלגות דקות מצטברות ---")
    print(master["minutes"].describe(
        percentiles=[.1, .25, .5, .75, .9]).round(1).to_string())


if __name__ == "__main__":
    build()