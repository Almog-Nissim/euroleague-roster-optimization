"""
real_returns.py — האם למועדוני יורוליג אמיתיים יש תשואה פוחתת לכסף.

השאלה
-----
ההשערה של אלמוג: **יש סכום אידיאלי לקבוצה אירופית, ומעליו הכסף
מתפזר גרוע יותר.**

⚠️ זו טענה שלא ניתן לבדוק על המנוע. אופטימייזר אינו "מתפזר" — הוא
פותר. אם סגל שעולה 35 מיליון קיבל ניקוד גבוה יותר מסגל שנבחר
ב-36, זה אומר שהמנוע לא מצא את מה שהיה זמין לו, לא שהכסף הזיק.

**אבל על מועדונים אמיתיים היא כן ניתנת לבדיקה**, וזו טענה חזקה
בהרבה: היא נמדדת על מה שקרה במציאות, ולא על סגלים היפותטיים
שיושבים מעל כל מה שנצפה בעשור.

מה שנבדק
--------
א. הקשר תקציב → איכות אצל 38 עונות-המועדון. ליניארי מול קמור.
ב. יחס `ניקוד/תקציב` — האם יורד מעל סף.
ג. ⚠️ בקרת התאמת-יתר: מודל ריבועי תמיד מתאים טוב יותר. הבדיקה
   היא אם השיפור מובהק, לא אם הוא קיים.
ד. חלוקה לשלישים — האם השליש העליון בתקציב מקבל פחות תמורה.

מגבלה שנרשמת מראש
------------------
n=38, ומהן 21 מועדונים ייחודיים בלבד על פני שתי עונות. כל טענה
כאן היא היפותזה, לא הוכחה. ⚠️ ובנוסף: התקציב נגזר ממודל העלות
שכויל על מכבי, ו-β₁ נע פי 3.6 בין מועדונים **עם התקציב** — כלומר
שגיאת התמחור עצמה עולה עם הציר שאנחנו בודקים.

הרצה:  python src/real_returns.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import repo_root, resolve  # noqa: E402


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def ols(X: np.ndarray, y: np.ndarray):
    """OLS פשוט. מחזיר מקדמים, שאריות, R², ו-se."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    dof = max(n - k, 1)
    s2 = float((resid ** 2).sum() / dof)
    cov = s2 * np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float((resid ** 2).sum()) / ss_tot if ss_tot else np.nan
    return beta, se, r2, resid, dof


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="data/processed/league_backtest_results.csv")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")
    d = pd.read_csv(resolve(args.results), low_memory=False)
    d = d.dropna(subset=["budget", "q_club"]).copy()
    print(f"נטען: {len(d)} עונות-מועדון · {d.club.nunique()} מועדונים ייחודיים")

    b = d["budget"].to_numpy(float)
    q = d["q_club"].to_numpy(float)

    hdr("א. תקציב מול איכות — ליניארי מול ריבועי")
    print(f"  תקציב: {b.min():.1f} .. {b.max():.1f} · חציון {np.median(b):.1f}")
    print(f"  ניקוד: {q.min():.1f} .. {q.max():.1f} · חציון {np.median(q):.1f}\n")

    one = np.ones_like(b)
    bl, sel_, r2l, _, _ = ols(np.column_stack([one, b]), q)
    print(f"  ליניארי : q = {bl[0]:.2f} + {bl[1]:.3f}·B"
          f"   (se {sel_[1]:.3f}, t {bl[1] / sel_[1]:+.2f})   R²={r2l:.3f}")

    bc = b - b.mean()
    bq, seq, r2q, _, dofq = ols(np.column_stack([one, bc, bc ** 2]), q)
    tq = bq[2] / seq[2]
    print(f"  ריבועי  : מקדם ריבועי {bq[2]:+.4f}"
          f"   (se {seq[2]:.4f}, t {tq:+.2f})   R²={r2q:.3f}")

    print(f"\n  שיפור ב-R²: {r2q - r2l:+.3f}")
    print("  ⚠️ מודל ריבועי תמיד מתאים טוב יותר. השאלה היא המובהקות.")

    if abs(tq) > 1.96 and bq[2] < 0:
        print("\n  🔴 קמירות שלילית מובהקת — תשואה פוחתת.")
        peak = b.mean() - bq[1] / (2 * bq[2])
        print(f"     שיא העקומה: {peak:.1f}M")
        if not (b.min() <= peak <= b.max()):
            print("     ⚠️ אבל השיא **מחוץ לטווח הנצפה** — אקסטרפולציה.")
    elif abs(tq) > 1.96:
        print("\n  ⚠️ קמירות חיובית מובהקת — תשואה **עולה**, הפוך מההשערה.")
    else:
        print("\n  ✅ הקמירות אינה מובהקת. הקשר ליניארי בטווח הנצפה.")
        print("     ההשערה על 'סכום אידיאלי' אינה נתמכת בדאטה הזה.")

    hdr("ב. יחס ניקוד לתקציב")
    d["ratio"] = q / b
    r_rank = float(pd.Series(b).corr(d["ratio"], method="spearman"))
    print(f"  היחס יורד מכנית עם התקציב (מכנה גדל), ולכן מדווח")
    print(f"  לצד הקשר עצמו ולא כראיה עצמאית.\n")
    print(f"  corr(תקציב, יחס) ספירמן = {r_rank:+.3f}")

    hdr("ג. שלישים")
    d["tercile"] = pd.qcut(b, 3, labels=["נמוך", "בינוני", "גבוה"])
    t = d.groupby("tercile", observed=True).agg(
        n=("q_club", "size"), תקציב=("budget", "mean"),
        ניקוד=("q_club", "mean"), יחס=("ratio", "mean"))
    t["ניקוד למיליון נוסף"] = np.nan
    prev_b = prev_q = None
    for i, (idx, row) in enumerate(t.iterrows()):
        if prev_b is not None:
            t.loc[idx, "ניקוד למיליון נוסף"] = (row["ניקוד"] - prev_q) / (row["תקציב"] - prev_b)
        prev_b, prev_q = row["תקציב"], row["ניקוד"]
    print(t.round(3).to_string())

    print("\n  אם 'ניקוד למיליון נוסף' יורד בין השלישים —")
    print("  זו תשואה פוחתת בצורתה הישירה ביותר.")

    hdr("ד. לפי עונה בנפרד")
    for season, g in d.groupby("season"):
        bb = g["budget"].to_numpy(float)
        qq = g["q_club"].to_numpy(float)
        if len(g) < 8:
            continue
        o = np.ones_like(bb)
        bl2, se2, r22, _, _ = ols(np.column_stack([o, bb]), qq)
        print(f"  {season}: n={len(g)} · שיפוע {bl2[1]:+.3f} "
              f"(t {bl2[1] / se2[1]:+.2f}) · R²={r22:.3f}")

    hdr("מסקנה")
    print("  ⚠️ n=38 על 21 מועדונים ייחודיים. היפותזה, לא הוכחה.")
    print("  ⚠️ התקציב נגזר ממודל העלות שכויל על מכבי, ושגיאת התמחור")
    print("     עולה עם הציר שנבדק (β₁ נע פי 3.6 עם התקציב).")

    out = resolve("data/processed/real_returns.csv")
    d.to_csv(out, index=False)
    print(f"\n  נשמר: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())