"""
survival_model.py
-----------------
רגרסיה לוגיסטית לשרידות: P(שורד לעונה t+1 | דקות למשחק, גיל).

למה לוגיסטית ולא הטבלה: התוצאה בינארית, ולכן מודל לינארי רגיל
היה יכול להחזיר הסתברויות מעל 1 או מתחת ל-0. לוגיסטית חסומה במבנה.
בנוסף היא מחליקה את חמשת התאים הדלילים ומחזירה ערך רציף — שחקן
בן 30.9 ובן 31.1 מקבלים תשובות דומות, לא קפיצה על גבול שרירותי.

גיל נכנס ריבועי: הטבלה המוצלבת הראתה שהוא לא מונוטוני — צעירים
שמקבלים דקות שורדים היטב, ורק מ-33 מתחילה ירידה. מודל לינארי בגיל
היה מכריח קו יורד ומעניש את הצעירים על לא כלום.

שגיאות תקן מקובצות לפי שחקן: אותו שחקן מופיע עד 3 פעמים
ואינו 3 תצפיות עצמאיות. אותו נימוק כמו הקיבוץ לפי קבוצה בבקטסט.

הרצה: python src/audits/survival_model.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
import numpy as np
import pandas as pd
import statsmodels.api as sm
from paths import PROCESSED_DIR

AGE_CENTER = 27.0   # מרכוז — בלעדיו המקדם הריבועי בלתי קריא


def prepare():
    df = pd.read_csv(os.path.join(PROCESSED_DIR, "player_season.csv"))
    last = df["season"].max()
    src = df[df["season"] < last].copy()

    alive = set(zip(df["player_code"], df["season"]))
    src["survived"] = [(c, s + 1) in alive
                       for c, s in zip(src["player_code"], src["season"])]
    src["survived"] = src["survived"].astype(int)

    src["age_c"]  = src["age"] - AGE_CENTER
    src["age_c2"] = src["age_c"] ** 2
    return src


def fit(df, cols, label):
    X = sm.add_constant(df[cols])
    m = sm.Logit(df["survived"], X).fit(
        disp=0, cov_type="cluster",
        cov_kwds={"groups": df["player_code"]})
    print(f"\n--- {label} ---")
    print(m.summary2().tables[1].round(4).to_string())
    print(f"pseudo R2 = {m.prsquared:.4f} | LL = {m.llf:.2f} | n = {int(m.nobs)}")
    return m


def main():
    df = prepare()
    print("=" * 70)
    print(f"SURVIVAL MODEL | n={len(df)} | "
          f"שחקנים ייחודיים={df['player_code'].nunique()} | "
          f"שרידות={df['survived'].mean():.1%}")
    print("=" * 70)

    m1 = fit(df, ["min_per_game"], "דקות בלבד")
    m2 = fit(df, ["min_per_game", "age_c"], "דקות + גיל לינארי")
    m3 = fit(df, ["min_per_game", "age_c", "age_c2"], "דקות + גיל ריבועי")

    print("\n--- האם כל תוספת משתלמת? ---")
    print(f"דקות -> +גיל:        ΔLL = {m2.llf - m1.llf:+.2f}")
    print(f"+גיל -> +ריבוע:      ΔLL = {m3.llf - m2.llf:+.2f}")
    print("(ΔLL קטן מ-2 בערך = התוספת לא נושאת את עצמה)")

    df["p"] = m3.predict(sm.add_constant(df[["min_per_game", "age_c", "age_c2"]]))

    # --- כיול: המבחן האמיתי ---
    # מודל יכול להפריד היטב ועדיין להיות מוטה. כאן נבדק אם ההסתברות
    # שהוא מנפיק תואמת את השיעור שנצפה בפועל.
    print("\n--- כיול: חזוי מול נצפה, לפי עשירונים ---")
    df["dec"] = pd.qcut(df["p"], 10, labels=False, duplicates="drop")
    cal = df.groupby("dec").agg(n=("survived", "size"),
                                predicted=("p", "mean"),
                                observed=("survived", "mean")).round(3)
    cal["gap"] = (cal["predicted"] - cal["observed"]).round(3)
    print(cal.to_string())
    print(f"\nפער מוחלט מרבי: {cal['gap'].abs().max():.3f}")

    # --- אימות מחוץ למדגם: אימון על 2022-23, מבחן על 2024 ---
    tr, te = df[df["season"] < 2024], df[df["season"] == 2024]
    cols = ["min_per_game", "age_c", "age_c2"]
    mo = sm.Logit(tr["survived"], sm.add_constant(tr[cols])).fit(disp=0)
    te_p = mo.predict(sm.add_constant(te[cols]))
    print(f"\n--- מחוץ למדגם (אימון 2022-23, מבחן 2024, n={len(te)}) ---")
    print(f"ממוצע חזוי {te_p.mean():.3f} מול נצפה {te['survived'].mean():.3f}")

    # --- עקומת הגיל בדקות קבועות ---
    print("\n--- P(שורד) לפי גיל, ב-20 דקות למשחק ---")
    grid = pd.DataFrame({"min_per_game": 20.0,
                         "age_c": np.arange(20, 39) - AGE_CENTER})
    grid["age_c2"] = grid["age_c"] ** 2
    grid["p"] = m3.predict(sm.add_constant(grid, has_constant="add"))
    grid["age"] = grid["age_c"] + AGE_CENTER
    print(grid[["age", "p"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()