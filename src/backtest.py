"""
backtest.py
-----------
שאלת השער: האם ערך סגל בעונה t-1 מנבא ניצחונות בעונה t?

זו לא השאלה האנליטית של הפרויקט — זו התנאי שמכשיר אותה.
אם המדד לא מנבא, כל אופטימיזציה שתיבנה מעליו ממקסמת רעש.

שלוש החלטות מתודולוגיות מקודדות כאן:

  1. זיווג במיזוג על season+1, לא shift().
     2021 הושמטה (אי-סנכרון endpoints: טבלה על 28 משחקים, סטטיסטיקות
     על 30-32, לא אחיד בין קבוצות). shift() היה מזווג את 2020 עם 2022
     בשקט — פער של שנתיים. מיזוג על התאמה מדויקת חוסם את זה מבנית:
     זוג לא רצוף פשוט לא מוצא בן זוג ונופל מעצמו.

  2. שגיאות תקן מקובצות לפי קבוצה.
     אותה קבוצה מופיעה עד 8 פעמים. ריאל מדריד בכל שורה היא לא תצפית
     עצמאית — אותו מועדון, אותו תקציב, אותו מנגנון גיוס. OLS רגיל
     מניח עצמאות ולכן ייתן p-value אופטימי מדי.

  3. שלוש הרצות על ספי כיסוי שונים.
     סף הכיסוי הוא בחירה, וכיסוי נמוך אינו אקראי ביחס לתוצאה:
     אולימפיאקוס 2025 קנתה בדדליין ולקחה תואר; פרטיזן מכרה ונאבקה.
     אם המסקנה יציבה בשלושת הספים, בחירת הסף לא מניעה אותה.
     אם היא מתהפכת — זה הממצא החשוב ביותר.

דרישה: pip install statsmodels
מיקום: src/backtest.py
"""

import os
import pandas as pd

from paths import PROCESSED_DIR, ROOT_DIR

try:
    import statsmodels.api as sm
except ImportError:
    raise SystemExit("חסר statsmodels. הרץ:  pip install statsmodels")

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", None)

# ----------------------------------------------------------------------
# הגדרות
# ----------------------------------------------------------------------
IN_FILE = os.path.join(PROCESSED_DIR, "team_season.csv")

# ספי כיסוי לבדיקת רובוסטיות. 0.0 = בלי סינון כלל.
# כדי שההרצה הראשונה תהיה משמעותית, build_team_season.py צריך לרוץ
# עם COVERAGE_MIN = 0.0 כך שהקובץ יכיל את כל 158 השורות.
COVERAGE_THRESHOLDS = [0.00, 0.90, 0.95]

# העמודות שנלקחות מהעונה הקודמת
PREV_COLS = ["pir_z", "pir_per_round", "sum_pir",
             "win_pct", "win_pct_z", "team_games", "minutes_coverage"]

# המפרט הראשי: z מול z.
# pir_per_round אינו בר-השוואה בין עונות (16 קבוצות ב-2016 מול 20 ב-2025),
# ולכן התקנון התוך-עונתי הוא המפרט הנכון. הגולמי רץ כמשני לשקיפות.
SPECS = [
    ("pir_z_prev",         "win_pct_z", "z-score (ראשי)"),
    ("pir_per_round_prev", "win_pct",   "גולמי (משני)"),
]


# ----------------------------------------------------------------------
def build_pairs(df):
    """
    מזווג כל קבוצה-עונה עם העונה הקודמת שלה.

    המנגנון: מזיזים את season של עותק הטבלה ב-1+ וממזגים על התאמה
    מדויקת של (season, team). שורה של 2022 מחפשת בן זוג שמקורו ב-2021;
    2021 לא בטבלה, ולכן היא לא מוצאת. אין בדיקה שאפשר לשכוח.
    """
    prev = df[["season", "team"] + PREV_COLS].copy()
    prev["season_prev"] = prev["season"]
    prev["season"] = prev["season"] + 1
    prev = prev.rename(columns={c: f"{c}_prev" for c in PREV_COLS})

    pairs = df.merge(prev, on=["season", "team"], how="inner")

    # שכבת ביטחון: המיזוג כבר מבטיח את זה, אבל כשל שקט כאן
    # היה מזהם את כל התוצאה.
    gap = pairs["season"] - pairs["season_prev"]
    assert (gap == 1).all(), f"זוגות לא רצופים: {sorted(gap.unique())}"

    return pairs


def run_spec(pairs, xcol, ycol, label):
    """OLS עם שגיאות תקן רגילות ומקובצות. מחזיר dict לסיכום."""
    d = pairs[[xcol, ycol, "team", "season"]].dropna()
    if len(d) < 10:
        print(f"   [SKIP] {label}: רק {len(d)} תצפיות")
        return None

    X = sm.add_constant(d[[xcol]])
    plain = sm.OLS(d[ycol], X).fit()
    clust = sm.OLS(d[ycol], X).fit(
        cov_type="cluster", cov_kwds={"groups": d["team"]}
    )

    lo, hi = clust.conf_int().loc[xcol]
    n_clusters = d["team"].nunique()

    print(f"\n   --- {label} ---")
    print(f"   n={len(d)}  clusters={n_clusters}  R²={plain.rsquared:.3f}")
    print(f"   coef  = {clust.params[xcol]:+.4f}")
    print(f"   SE    = {plain.bse[xcol]:.4f} (רגיל) -> "
          f"{clust.bse[xcol]:.4f} (מקובץ)   "
          f"[יחס {clust.bse[xcol]/plain.bse[xcol]:.2f}x]")
    print(f"   p     = {clust.pvalues[xcol]:.4f} (מקובץ)   "
          f"[{plain.pvalues[xcol]:.4f} רגיל]")
    print(f"   95%CI = [{lo:+.4f}, {hi:+.4f}]"
          f"{'   <-- חוצה אפס' if lo < 0 < hi else ''}")

    if n_clusters < 20:
        print(f"   [WARN] רק {n_clusters} קלאסטרים — "
              f"שגיאות התקן המקובצות עלולות להיות לא אמינות")

    return {"spec": label, "n": len(d), "clusters": n_clusters,
            "r2": round(plain.rsquared, 4),
            "coef": round(clust.params[xcol], 4),
            "se_plain": round(plain.bse[xcol], 4),
            "se_clustered": round(clust.bse[xcol], 4),
            "p_clustered": round(clust.pvalues[xcol], 4),
            "ci_low": round(lo, 4), "ci_high": round(hi, 4),
            "crosses_zero": bool(lo < 0 < hi)}


def contemporaneous_check(pairs):
    """
    ניגוד אבחוני: רגרסיה בו-זמנית של אותה עונה על עצמה.
    היא טאוטולוגית-חלקית ולכן לא הכותרת — אבל היא מפרידה שני מצבים:
      בו-זמנית חזקה + מושהית חלשה = PIR מודד ניצחון, הסגל לא מתמיד
      שתיהן חלשות                  = הבעיה במדד עצמו
    """
    print("\n" + "-" * 74)
    print("ניגוד אבחוני: רגרסיה בו-זמנית (t -> t), על אותן שורות")
    print("-" * 74)
    return run_spec(pairs, "pir_z", "win_pct_z", "בו-זמנית t->t")


# ----------------------------------------------------------------------
def main():
    if not os.path.exists(IN_FILE):
        raise SystemExit(f"קובץ חסר: {IN_FILE}\nהרץ קודם build_team_season.py")

    df = pd.read_csv(IN_FILE)
    print("=" * 74)
    print("BACKTEST — האם ערך סגל ב-t-1 מנבא ניצחונות ב-t")
    print("=" * 74)
    print(f"קלט: {len(df)} שורות | עונות: {sorted(df['season'].unique())}")
    print(f"כיסוי מינימלי בקובץ: {df['minutes_coverage'].min():.1%}")

    if df["minutes_coverage"].min() >= 0.90:
        print("[NOTE] הקובץ כבר מסונן ב-90%. "
              "להרצת רובוסטיות מלאה: COVERAGE_MIN = 0.0 ב-build והרצה מחדש.")

    # --- ספירת זוגות לפי מעבר, לאימות מול הציפייה ---
    pairs_all = build_pairs(df)
    counts = (pairs_all.groupby(["season_prev", "season"])
                       .size().rename("pairs").reset_index())
    print(f"\nזוגות לפי מעבר (סה\"כ {len(pairs_all)}):")
    print(counts.to_string(index=False))

    spanning = counts[counts["season"] - counts["season_prev"] != 1]
    if not spanning.empty:
        raise SystemExit(f"[FAIL] מעברים לא רצופים: \n{spanning}")

    # --- שלוש הרצות רובוסטיות ---
    summary = []
    for thr in COVERAGE_THRESHOLDS:
        sub = df[df["minutes_coverage"] >= thr].copy()
        pairs = build_pairs(sub)

        print("\n" + "=" * 74)
        print(f"COVERAGE >= {thr:.0%}   |   {len(sub)} שורות -> {len(pairs)} זוגות")
        print("=" * 74)

        for xcol, ycol, label in SPECS:
            res = run_spec(pairs, xcol, ycol, label)
            if res:
                res["coverage_min"] = thr
                summary.append(res)

    # --- ניגוד אבחוני, על המפרט המרכזי בלבד ---
    main_pairs = build_pairs(df[df["minutes_coverage"] >= 0.90])
    contemporaneous_check(main_pairs)

    # --- סיכום ---
    if not summary:
        raise SystemExit("[FAIL] אף מפרט לא רץ. בדוק את קלט הזוגות למעלה.")

    out = pd.DataFrame(summary)[
        ["coverage_min", "spec", "n", "clusters", "r2", "coef",
         "se_plain", "se_clustered", "p_clustered",
         "ci_low", "ci_high", "crosses_zero"]
    ]
    print("\n" + "=" * 74)
    print("סיכום רובוסטיות")
    print("=" * 74)
    print(out.to_string(index=False))

    path = os.path.join(PROCESSED_DIR, "backtest_results.csv")
    out.to_csv(path, index=False)
    print(f"\n[SUCCESS] {path}")

    # --- תרשים פיזור למפרט הראשי ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        d = main_pairs.dropna(subset=["pir_z_prev", "win_pct_z"])
        fig, ax = plt.subplots(figsize=(7, 5))
        for s, g in d.groupby("season"):
            ax.scatter(g["pir_z_prev"], g["win_pct_z"], label=str(s), s=28, alpha=.75)
        b = sm.OLS(d["win_pct_z"],
                   sm.add_constant(d[["pir_z_prev"]])).fit().params
        xs = [d["pir_z_prev"].min(), d["pir_z_prev"].max()]
        ax.plot(xs, [b["const"] + b["pir_z_prev"] * x for x in xs], "k--", lw=1.4)
        ax.axhline(0, color="grey", lw=.6); ax.axvline(0, color="grey", lw=.6)
        ax.set_xlabel("PIR z-score, season t-1")
        ax.set_ylabel("Win% z-score, season t")
        ax.set_title(f"Lagged backtest  (n={len(d)})")
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()

        fig_dir = os.path.join(ROOT_DIR, "figures")
        os.makedirs(fig_dir, exist_ok=True)
        fig_path = os.path.join(fig_dir, "backtest_scatter.png")
        fig.savefig(fig_path, dpi=150)
        print(f"[SUCCESS] {fig_path}")
    except ImportError:
        print("[NOTE] matplotlib לא מותקן — התרשים לא נוצר")


if __name__ == "__main__":
    main()