"""
usage_curve.py — האם יש עקומת שימוש-יעילות, ואם כן האם היא אמיתית.

הרקע
----
בדיקת הכוח נתנה שלוש נקודות, כולן באזור "זיהוי חלש":

    סף דקות   ס"ת פנימי   תצפיות   שחקנים
    300        2.26        1,528     377
    600        2.04          732     200
    900        1.84          132      49

מגמה מונוטונית כלפי מטה, בעוד הס"ת **בין** שחקנים דווקא עולה
(4.69 -> 4.76 -> 5.24). כלומר סינון השוליים מחדד את ההבדל בין
שחקנים ומצמצם את ההבדל בתוך שחקן: **usage הוא תכונה של השחקן
יותר משהוא תכונה של הסביבה.**

900 אינו שמיש — 132 תצפיות, 28 שחקנים עם שתי עונות בלבד.
מדגם העבודה הוא **600**.

שני מבחנים
----------
א. **חישוב כוח מפורש.** עם ס"ת פנימי 2.04 ו-732 תצפיות, מה
   השיפוע המינימלי שנזהה ב-80%? אם התשובה היא "רק שיפוע גדול
   פי שלושה מהספרות", המבחן חסר טעם — ועדיף לדעת לפני.

ב. 🔴 **הפיצול אי-זוגי/זוגי.** זה העיקר.
   `TS% = PTS / (2·(FGA + 0.44·FTA))` ו-usage מכיל
   `FGA + 0.44·FTA`. הם חולקים אברים, ולכן רעש ב-FGA לבדו
   מייצר שיפוע שלילי **גם כשאין שום עקומה**.

   הפתרון: usage ממשחקים אי-זוגיים, TS% ממשחקים זוגיים. הרעש
   המשותף נשבר; אות אמיתי שורד.

   אם השיפוע קורס בפיצול — מדדנו אריתמטיקה.
   אם הוא שורד — יש ממצא, למרות הכוח החלש.

⚠️ מגבלה שנשארת: תוצאת null אינה ראיה לשטוח. יום 9 כבר מצא
אדיטיביות מלאה ברמת הקבוצה (יחס 0.994, HHI p=0.383), ובכוח
הזה לא נוכל להבחין בין "שטוח" ל"לא רואים".

הרצה:  python src/usage_curve.py --min-minutes 600
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import load_boxscores, repo_root, resolve  # noqa: E402
from verify_boxscores import parse_minutes  # noqa: E402

OUT_REL = "data/processed/usage_curve_results.csv"


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


# ---------------------------------------------------------------- בנייה
def filter_regular_season(bx: pd.DataFrame, index_path: Path) -> pd.DataFrame:
    """
    משאיר עונה סדירה בלבד.

    usage בפלייאוף מתרכז בשחקנים מובילים, וזה מנפח את השונות
    הפנימית מסיבה שאינה שינוי תפקיד. ורק ל-2022 ול-2024 יש Phase
    בקובץ עצמו — לשאר הוא מגיע מ-game_index.
    """
    if not index_path.exists():
        print(f"  ⚠️ לא נמצא {index_path} — הסינון לא רץ.")
        return bx

    idx = pd.read_csv(index_path, dtype={"Gamecode": str}, low_memory=False)
    idx["Gamecode"] = idx["Gamecode"].astype(str).str.strip()
    phase = (idx["Phase"].astype(str).str.upper()
             .str.replace(r"[^A-Z]", "", regex=True))
    rs = set(zip(idx.loc[phase.isin({"RS", "REGULARSEASON", "REGULAR"}), "Season"],
                 idx.loc[phase.isin({"RS", "REGULARSEASON", "REGULAR"}), "Gamecode"]))

    before = len(bx)
    key = list(zip(bx["Season"], bx["Gamecode"].astype(str).str.strip()))
    out = bx[[k in rs for k in key]].copy()
    print(f"  סינון לעונה סדירה: {before:,} -> {len(out):,} שורות "
          f"({1 - len(out) / before:.1%} הוסרו)")
    return out


def player_season_split(bx: pd.DataFrame, min_minutes: float) -> pd.DataFrame:
    """
    מצרפת לרמת שחקן-עונה-מועדון, ובמקביל בונה שתי גרסאות נפרדות
    ממשחקים אי-זוגיים ומשחקים זוגיים.
    """
    d = bx.copy()
    pid = d["Player_ID"].astype(str).str.strip().str.upper()
    d = d[~pid.isin(["TOTAL", "TEAM", "NAN", ""])]

    for c in ["Points", "FieldGoalsAttempted2", "FieldGoalsAttempted3",
              "FreeThrowsAttempted", "Turnovers", "Valuation"]:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)

    d["min_num"] = d["Minutes"].apply(parse_minutes)
    d["FGA"] = d["FieldGoalsAttempted2"] + d["FieldGoalsAttempted3"]
    d["poss"] = d["FGA"] + 0.44 * d["FreeThrowsAttempted"] + d["Turnovers"]

    # 🔴 החצאים מוקצים לפי סדר המשחקים **של הקבוצה**, לא של הליגה.
    # בגרסה הקודמת ההקצאה נעשתה על gamecode ברמת הליגה, וקבוצה
    # שמשחקיה נפלו במרווחים קבועים קיבלה את כולם לאותו חצי —
    # `usage_odd` ו-`ts_even` מעולם לא הופיעו יחד באותה שורה.
    order = (d[["Season", "Team", "Gamecode"]].drop_duplicates()
               .sort_values(["Season", "Team", "Gamecode"],
                            key=lambda s: s.astype(str).str.zfill(8)))
    order["half"] = order.groupby(["Season", "Team"]).cumcount() % 2
    d = d.merge(order, on=["Season", "Team", "Gamecode"], how="left")

    tm = (d.groupby(["Season", "Gamecode", "Team"])
            .agg(tm_poss=("poss", "sum"), tm_min=("min_num", "sum")).reset_index())
    d = d.merge(tm, on=["Season", "Gamecode", "Team"], how="left")

    keys = ["Season", "Player_ID", "Team"]

    def agg(frame):
        g = (frame.groupby(keys)
                  .agg(minutes=("min_num", "sum"), poss=("poss", "sum"),
                       pts=("Points", "sum"), fga=("FGA", "sum"),
                       fta=("FreeThrowsAttempted", "sum"), pir=("Valuation", "sum"),
                       tm_poss=("tm_poss", "sum"), tm_min=("tm_min", "sum"),
                       games=("Gamecode", "nunique")).reset_index())
        g["usage"] = 100 * (g["poss"] * (g["tm_min"] / 5)) / (g["minutes"] * g["tm_poss"])
        den = 2 * (g["fga"] + 0.44 * g["fta"])
        g["ts"] = np.where(den > 0, 100 * g["pts"] / den, np.nan)
        # ppm — התפוקה הכוללת, לא רק קליעה. עקומה עשויה להתקיים
        # באיבודים או בהחלטות ולא ב-TS%.
        g["ppm"] = np.where(g["minutes"] > 0, g["pir"] / g["minutes"], np.nan)
        return g

    full = agg(d)
    odd = agg(d[d["half"] == 0]).rename(columns={"usage": "usage_odd", "ts": "ts_odd",
                                                 "ppm": "ppm_odd", "minutes": "min_odd"})
    even = agg(d[d["half"] == 1]).rename(columns={"usage": "usage_even", "ts": "ts_even",
                                                  "ppm": "ppm_even", "minutes": "min_even"})

    out = (full[full["minutes"] >= min_minutes]
           .merge(odd[keys + ["usage_odd", "ts_odd", "ppm_odd", "min_odd"]], on=keys, how="left")
           .merge(even[keys + ["usage_even", "ts_even", "ppm_even", "min_even"]],
                  on=keys, how="left"))
    return out


# ---------------------------------------------------------------- אמידה
def within_fe(df: pd.DataFrame, xcol: str, ycol: str):
    """
    OLS עם אפקטים קבועים לשחקן ולעונה, בניכוי ממוצעים.
    מחזיר beta, se, t, n, וטווח סמך.
    """
    d = df[[xcol, ycol, "Player_ID", "Season"]].dropna().copy()
    if len(d) < 20:
        return None

    # ניכוי כפול: שחקן ואז עונה
    for col in (xcol, ycol):
        d[col] = d[col] - d.groupby("Player_ID")[col].transform("mean")
        d[col] = d[col] - d.groupby("Season")[col].transform("mean")

    x, y = d[xcol].to_numpy(), d[ycol].to_numpy()
    vx = float((x ** 2).sum())
    if vx <= 0:
        return None

    beta = float((x * y).sum() / vx)
    resid = y - beta * x
    n = len(d)
    k = d["Player_ID"].nunique() + d["Season"].nunique()
    dof = max(n - k - 1, 1)
    se = float(np.sqrt((resid ** 2).sum() / dof / vx))
    return {"beta": beta, "se": se, "t": beta / se if se else np.nan,
            "n": n, "players": d["Player_ID"].nunique(),
            "ci_lo": beta - 1.96 * se, "ci_hi": beta + 1.96 * se}


def fmt(r, label: str) -> None:
    if r is None:
        print(f"  {label:<28} — מדגם קטן מדי")
        return
    sig = "***" if abs(r["t"]) > 2.58 else "**" if abs(r["t"]) > 1.96 else "n.s."
    print(f"  {label:<28} β={r['beta']:+.4f}  se={r['se']:.4f}  "
          f"t={r['t']:+.2f} {sig:<4} n={r['n']}  "
          f"CI[{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]")


# ---------------------------------------------------------------- כוח
def power_analysis(sd_within_x: float, sd_y: float, n: int, players: int) -> None:
    hdr("א. חישוב כוח — מה בכלל נוכל לזהות")

    dof = max(n - players - 10, 1)
    se_approx = sd_y / (sd_within_x * np.sqrt(max(n - 1, 1)))
    mde = 2.80 * se_approx          # 1.96 + 0.84, לכוח 80%

    print(f"  ס\"ת פנימי ב-usage : {sd_within_x:.2f} נק' אחוז")
    print(f"  ס\"ת ב-TS%         : {sd_y:.2f} נק' אחוז")
    print(f"  תצפיות            : {n}   שחקנים: {players}   dof≈{dof}")
    print(f"\n  se מקורב          : {se_approx:.4f}")
    print(f"  🔴 השיפוע המינימלי שנזהה ב-80%: |β| >= {mde:.3f}")
    print(f"     כלומר: עלייה של 5 נק' ב-usage חייבת להוריד לפחות "
          f"{abs(mde) * 5:.2f} נק' ב-TS% כדי שנראה אותה.")

    print("\n  להשוואה — הספרות מדווחת בערך β בין -0.2 ל--0.5.")
    if abs(mde) > 0.5:
        print("  🔴 ה-MDE שלנו גדול מהאפקט הצפוי. תוצאת null תהיה חסרת")
        print("     משמעות — לא נוכל להבחין בין 'שטוח' ל'לא רואים'.")
    elif abs(mde) > 0.2:
        print("  ⚠️ ה-MDE בתוך הטווח הצפוי אך בקצה העליון. נזהה אפקט")
        print("     חזק בלבד; אפקט מתון יחמוק.")
    else:
        print("  ✅ ה-MDE מתחת לאפקט הצפוי. יש כוח מספק.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--min-minutes", type=float, default=600)
    ap.add_argument("--regular-season", action="store_true",
                    help="לסנן פלייאוף לפי game_index")
    ap.add_argument("--index", default="data/processed/game_index.csv")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")
    bx = load_boxscores(args.root, verbose=False)
    if args.regular_season:
        bx = filter_regular_season(bx, resolve(args.index))
    ps = player_season_split(bx, args.min_minutes)

    print(f"\nמדגם: {len(ps):,} תצפיות שחקן-עונה-מועדון (>= {args.min_minutes:.0f} דק')")

    sd_within = float(
        (ps["usage"] - ps.groupby("Player_ID")["usage"].transform("mean")).std())
    power_analysis(sd_within, float(ps["ts"].std()), len(ps), ps["Player_ID"].nunique())

    # ------------------------------------------------------------ ב
    hdr("ב. 🔴 השיפוע — גולמי מול מפוצל")
    print("  גולמי  : usage ו-TS% מאותם משחקים — חולקים את FGA+0.44·FTA")
    print("  מפוצל  : usage ממשחקים אי-זוגיים, TS% מזוגיים\n")

    results = {}
    for name, y, yo, ye in [("TS% (קליעה)", "ts", "ts_odd", "ts_even"),
                            ("ppm (תפוקה כוללת)", "ppm", "ppm_odd", "ppm_even")]:
        print(f"  --- {name} ---")
        raw_r = within_fe(ps, "usage", y)
        fmt(raw_r, "גולמי (אותם משחקים)")
        sp = within_fe(ps, "usage_odd", ye)
        fmt(sp, "מפוצל (אי-זוגי -> זוגי)")
        rv = within_fe(ps, "usage_even", yo)
        fmt(rv, "מפוצל הפוך (זוגי -> אי-זוגי)")
        results[name] = (raw_r, sp, rv)
        print()

    raw, split, rev = results["TS% (קליעה)"]

    # ------------------------------------------------------------ פלצבו
    hdr("ג. פלצבו — usage מעורבב בתוך שחקן")
    print("  אם השיפוע שורד ערבוב, משהו שגוי במפרט.\n")
    rng = np.random.default_rng(11)
    sh = ps.copy()
    sh["usage_shuf"] = sh.groupby("Player_ID")["usage"].transform(
        lambda s: rng.permutation(s.to_numpy()))
    fmt(within_fe(sh, "usage_shuf", "ts"), "מעורבב -> TS%")
    fmt(within_fe(sh, "usage_shuf", "ppm"), "מעורבב -> ppm")

    # ------------------------------------------------------------ קריאה
    hdr("קריאת התוצאה")
    if raw and split:
        # 🔴 "היחלשות" מדווחת רק אם היה שיפוע גולמי מלכתחילה.
        # בגרסה קודמת הודפס "היחלשות 57.9%" על מעבר מ-+0.036 ל--0.015 —
        # היחלשות של אפס לעומת אפס, שנקראה כאילו הייתה ממצא.
        if abs(raw["t"]) < 1.96:
            print("  ⚠️ הגולמי עצמו אינו מובהק — אין שיפוע להיחלש ממנו.")
            print("     המכנה המשותף FGA+0.44·FTA לא ייצר הטיה כאן.")
        else:
            print(f"  היחלשות בפיצול: {1 - abs(split['beta']) / abs(raw['beta']):.1%}")

        survives = abs(split["t"]) > 1.96 and np.sign(split["beta"]) == np.sign(raw["beta"])
        if survives:
            print("\n  ✅ השיפוע שורד את הפיצול — הקשר אינו מכני.")
            print("     ממצא אמיתי, גם אם הכוח חלש.")
            print("\n  ⚠️ אבל יום 9 מצא אדיטיביות מלאה ברמת הקבוצה")
            print("     (יחס 0.994, HHI p=0.383). אם העקומה תלולה, שתי")
            print("     המדידות סותרות ואחת מהן שגויה.")
        else:
            print("\n  🔴 אין שיפוע מזוהה.")
            print(f"     רווח סמך: [{split['ci_lo']:+.3f}, {split['ci_hi']:+.3f}]")
            print("\n  מה שאפשר לומר: עקומה חזקה כפי שמתוארת בספרות הייתה")
            print("  נראית. אפקט מתון היה חומק. זו **אינה** ראיה לשטוח.")

    out = resolve(OUT_REL)
    out.parent.mkdir(parents=True, exist_ok=True)
    ps.to_csv(out, index=False)
    print(f"\n  נשמר: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())