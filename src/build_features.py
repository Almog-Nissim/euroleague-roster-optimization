"""
build_features.py  (Day 4, task 3)
----------------------------------
בונה טבלת פיצ'רים ברמת שחקן-עונת-יעד עבור מודל העלות.

העיקרון שקובע את כל הקובץ:
    עלות היא פונקציה של העבר. ערך הוא תחזית לעתיד.
כל פיצ'ר כאן מחושב מעונות שקדמו לעונת היעד בלבד. אם PIR של עונת
היעד ידלוף לאגף העלות, ספירמן יחזור ~0.95 והמודל ריק.
הדליפה נבדקת מפורשות ב-assert_no_leakage(), לא מונחת.

מפרט הפיצ'רים (אושר יום 4):
    pir_lag_raw     0.6*PIR(t-1) + 0.4*PIR(t-2)
    pir_lag_shrunk  w*pir_lag_raw + (1-w)*league_mean,  w = games/(games+k)
    min_lag         אותו שקלול על דקות למשחק
    el_seasons      ספירת עונות עד t-1 (1/2/3/4+), מ-2016
    age_c, age_c2   (age-27), (age-27)^2

התכווצות: שחקן עם 30 משחקים סביר יותר להיות בקצוות - לא כי הוא
קיצוני אלא כי לא הספיק להתכנס. בלי התכווצות, הרגרסיה לומדת שיפוע
מנקודות רועשות. k=40 הוא פרמטר מוצהר, נבדק גם ב-20 ו-60.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR

# --- פרמטרים מוצהרים (ניתוח רגישות במשימה הבאה) ---
W_LAG1, W_LAG2 = 0.6, 0.4      # משקלי t-1 / t-2
K_SHRINK = 40                   # חצי-משקל בכ-40 משחקים
EL_SEASONS_TOPCODE = 4          # 4 = "4 ומעלה"
AGE_CENTER = 27                 # מרכוז, לא הנחה על מיקום ה-prime

FIRST_SEASON = 2016             # תחילת הדאטה
MIN_TARGET_SEASON = 2018        # צריך לפחות שתי עונות היסטוריה
OUT_NAME = "player_features.csv"


def build_lags(df: pd.DataFrame) -> pd.DataFrame:
    """לכל (שחקן, עונת יעד) - מה היה ידוע בסוף העונה הקודמת."""
    d = df.sort_values(["player_code", "season"]).copy()
    g = d.groupby("player_code", sort=False)

    for col, out in [("pir_per_game", "pir"), ("min_per_game", "min"),
                     ("games", "games")]:
        d[f"{out}_lag1"] = g[col].shift(1)
        d[f"{out}_lag2"] = g[col].shift(2)
        d[f"{out}_lag1_season"] = g["season"].shift(1)
        d[f"{out}_lag2_season"] = g["season"].shift(2)

    # ספירה מצטברת של עונות קודמות - לא כולל את השורה הנוכחית
    d["el_seasons_raw"] = g.cumcount()
    return d


def weighted_lag(v1, v2, g1, g2):
    """שקלול t-1/t-2. אם t-2 חסרה, כל המשקל על t-1 - לא NaN."""
    v1, v2 = np.asarray(v1, float), np.asarray(v2, float)
    g1, g2 = np.asarray(g1, float), np.asarray(g2, float)

    has2 = ~np.isnan(v2)
    val = np.where(has2, W_LAG1 * v1 + W_LAG2 * v2, v1)
    games = np.where(has2, np.nan_to_num(g1) + np.nan_to_num(g2),
                     np.nan_to_num(g1))
    return val, games


def shrink(values, games, league_mean, k=K_SHRINK):
    """w = games/(games+k). 100 משחקים -> w~0.71, 20 -> w~0.33."""
    w = games / (games + k)
    return w * values + (1 - w) * league_mean, w


def assert_no_leakage(feat: pd.DataFrame):
    """כל עונה שנכנסה לפיצ'ר חייבת להיות קטנה מעונת היעד."""
    bad = []
    for c in ("pir_lag1_season", "pir_lag2_season"):
        v = feat[c]
        viol = feat.loc[v.notna() & (v >= feat.season)]
        if len(viol):
            bad.append((c, len(viol)))
    if bad:
        raise RuntimeError(f"דליפה: עונת מקור >= עונת יעד -> {bad}")

    # פיצ'ר שמתואם 1:1 עם היעד הוא דליפה גם אם העונות תקינות
    r = feat[["pir_lag_shrunk", "pir_per_game"]].corr().iloc[0, 1]
    if r > 0.95:
        raise RuntimeError(f"pir_lag_shrunk מתואם {r:.3f} עם היעד - חשד לדליפה")
    print(f"[CHECK] אין דליפה | corr(pir_lag_shrunk, pir_target) = {r:.3f}")


def build():
    src = PROCESSED_DIR / "player_season.csv"
    if not src.exists():
        raise SystemExit(f"missing input: {src.resolve()}")

    df = pd.read_csv(src, dtype={"player_code": str})
    print("=" * 70)
    print(f"BUILD FEATURES | {len(df)} שורות | עונות "
          f"{df.season.min()}-{df.season.max()}")
    print(f"פרמטרים: w={W_LAG1}/{W_LAG2} | k={K_SHRINK} | מרכוז גיל={AGE_CENTER}")
    print("=" * 70)

    d = build_lags(df)

    # ממוצע ליגה פר-עונה. לא ממוצע גלובלי: הליגה משתנה, וזה בדיוק
    # הלקח מהנרמול הפנים-עונתי של יום 2.
    league = (df.groupby("season")
                .apply(lambda x: np.average(x.pir_per_game, weights=x.games),
                       include_groups=False)
                .rename("league_pir_mean"))
    d = d.merge(league, left_on="season", right_index=True, how="left")

    pir_raw, pir_games = weighted_lag(d.pir_lag1, d.pir_lag2,
                                      d.games_lag1, d.games_lag2)
    min_raw, _ = weighted_lag(d.min_lag1, d.min_lag2,
                              d.games_lag1, d.games_lag2)

    d["pir_lag_raw"] = pir_raw
    d["games_lag"] = pir_games
    d["min_lag"] = min_raw
    d["pir_lag_shrunk"], d["shrink_w"] = shrink(pir_raw, pir_games,
                                                d.league_pir_mean.values)

    d["el_seasons"] = d.el_seasons_raw.clip(upper=EL_SEASONS_TOPCODE)
    d["age_c"] = d.age - AGE_CENTER
    d["age_c2"] = d.age_c ** 2

    # שורה שמישה = יש לפחות עונה קודמת אחת, ועונת היעד לא מוקדמת מדי
    feat = d[(d.season >= MIN_TARGET_SEASON) & d.pir_lag1.notna()].copy()

    assert_no_leakage(feat)

    cols = ["season", "player_code", "player_name", "team", "is_traded",
            "age", "age_c", "age_c2",
            "pir_lag_raw", "pir_lag_shrunk", "shrink_w", "games_lag",
            "min_lag", "el_seasons", "league_pir_mean",
            "pir_lag1_season", "pir_lag2_season",
            "pir_per_game", "min_per_game", "games", "sum_pir"]
    feat = feat[cols].sort_values(["season", "pir_lag_shrunk"],
                                  ascending=[True, False])

    out = PROCESSED_DIR / OUT_NAME
    feat.to_csv(out, index=False)
    if not out.exists():
        raise RuntimeError(f"הכתיבה דווחה כהצלחה אך הקובץ אינו קיים: {out}")

    print(f"\n[SUCCESS] {out.resolve()}  ({len(feat)} שורות)")
    report(feat)


def report(feat: pd.DataFrame):
    print("\n--- שורות לעונת יעד ---")
    print(feat.groupby("season").agg(
        n=("player_code", "size"),
        median_games_lag=("games_lag", "median"),
        median_w=("shrink_w", "median"),
    ).round(3).to_string())

    print(f"\n--- el_seasons (יעד 2025) ---")
    t = feat[feat.season == 2025].el_seasons.value_counts().sort_index()
    for k, v in t.items():
        print(f"  {int(k)}{'+' if k == EL_SEASONS_TOPCODE else ' '}: "
              f"{v:>4}  ({v/t.sum()*100:5.1f}%)")

    print(f"\n--- ההתכווצות עובדת? ---")
    b = feat.copy()
    b["games_bucket"] = pd.cut(b.games_lag, [0, 20, 40, 60, 80, 200],
                               labels=["<20", "20-40", "40-60", "60-80", "80+"])
    g = b.groupby("games_bucket", observed=True).agg(
        n=("shrink_w", "size"),
        mean_w=("shrink_w", "mean"),
        sd_raw=("pir_lag_raw", "std"),
        sd_shrunk=("pir_lag_shrunk", "std"),
    ).round(3)
    g["sd_reduction"] = (1 - g.sd_shrunk / g.sd_raw).round(3)
    print(g.to_string())
    print("\nהתכווצות תקינה אם sd_reduction יורד ככל שיש יותר משחקים.")


if __name__ == "__main__":
    build()