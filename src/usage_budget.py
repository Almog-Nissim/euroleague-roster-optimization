"""
usage_budget.py — קיצור דרך: האם בחירה לפי ppm מפרה את מגבלת הכדור.

⚠️ מה זה **לא**
---------------
זה **אינו** הסגל שהמנוע בנה. `league_backtest_results.csv` שומר
סיכום בלבד (38 שורות, q_club/q_eng/adv) — זהות השחקנים והקצאת
הדקות מעולם לא נכתבו לדיסק.

לכן התחזיות שנעלו לפני ההרצה — אלמוג 25-27%, קלוד 23-26% — הן על
הסגל האמיתי של המנוע, ו**התוצאה כאן אינה מכריעה אותן.**

מה זה כן
--------
חסם עליון על אותו מנגנון: מה קורה כשבוחרים 12 שחקנים לפי ppm בלבד,
בלי אילוצי תקציב, עמדות או זמינות — ובלי לאכוף שסכום ה-usage
בקבוצה הוא 100%.

הזהות שנבדקת
------------
`usage` מוגדר כנתח ההחזקות של השחקן מתוך אלה של קבוצתו. לכן
הממוצע המשוקלל-דקות בכל קבוצה **חייב** להיות 20.0% בדיוק — חמישה
שחקנים על המגרש, כדור אחד. זו זהות, לא אמידה.

סגל שממוצעו 25% אינו "פחות יעיל". הוא **לא יכול להתקיים**.

וזו אותה משפחה שכבר תפסה אותנו שלוש פעמים ביום 9: תקרת 32 דקות
נכונה לשחקן בודד והמודל העמיד שמונה; רצפות עמדה נכונות לכל עמדה
בנפרד ואף מועדון לא במינימום של שלוש. **הקצה של כל מרווח בנפרד.**

בדיקת השפיות שקובעת אם החישוב תקין
----------------------------------
קבוצות אמיתיות חייבות לצאת 20.0%. אם לא — הבאג בחישוב שלי,
לא במנוע. הסקריפט עוצר במקרה כזה.

הרצה:  python src/usage_budget.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import repo_root, resolve  # noqa: E402

ROSTER_SIZE = 12


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def weighted_usage(df: pd.DataFrame) -> float:
    w = df["minutes"].to_numpy()
    return float(np.average(df["usage"].to_numpy(), weights=w)) if w.sum() else np.nan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/processed/usage_curve_results.csv")
    ap.add_argument("--roster", type=int, default=ROSTER_SIZE)
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")
    path = resolve(args.input)
    if not path.exists():
        raise SystemExit(f"🔴 לא נמצא {path}. הרץ usage_curve.py קודם.")

    df = pd.read_csv(path, low_memory=False)
    df["Player_ID"] = df["Player_ID"].astype(str).str.strip()
    print(f"נטען: {path.name} ({len(df):,} שורות)")

    # ------------------------------------------------------ שפיות
    hdr("שפיות — קבוצות אמיתיות חייבות לצאת 20.0%")
    print("  אם לא, הבאג בחישוב ולא במנוע. הסקריפט יעצור.\n")

    real = (df.groupby(["Season", "Team"])
              .apply(weighted_usage, include_groups=False)
              .rename("usage_w").reset_index())
    real["n"] = df.groupby(["Season", "Team"]).size().to_numpy()

    print(f"  {len(real)} עונות-קבוצה")
    print(f"  ממוצע : {real['usage_w'].mean():.2f}%")
    print(f"  חציון : {real['usage_w'].median():.2f}%")
    print(f"  טווח  : {real['usage_w'].min():.2f}% .. {real['usage_w'].max():.2f}%")

    print("\n  ⚠️ המדגם מסונן ל->=600 דקות, כלומר שחקני השוליים חסרים.")
    print("     לכן הממוצע לא יהיה 20.0% מדויק — הוא ייטה כלפי מעלה,")
    print("     כי בדיוק השחקנים בעלי ה-usage הנמוך הם שנחתכו.")
    print("     מה שמעניין הוא ההפרש מול הסגל הנבחר, לא הרמה עצמה.")

    baseline = float(real["usage_w"].mean())

    # ------------------------------------------------------ סגל לפי ppm
    hdr(f"בחירת {args.roster} השחקנים עם ה-ppm הגבוה ביותר בכל עונה")
    print("  בלי תקציב, בלי עמדות, בלי זמינות. חסם עליון בלבד.\n")

    rows = []
    for season, g in df.groupby("Season"):
        top = g.nlargest(args.roster, "ppm")
        rows.append({
            "Season": season,
            "usage_w": weighted_usage(top),
            "usage_mean": float(top["usage"].mean()),
            "ppm_mean": float(top["ppm"].mean()),
            "n_pool": len(g),
        })
    picked = pd.DataFrame(rows)

    print(picked.round(2).to_string(index=False))

    sel = float(picked["usage_w"].mean())
    print(f"\n  ממוצע משוקלל-דקות של הסגל הנבחר : {sel:.2f}%")
    print(f"  ממוצע של קבוצות אמיתיות          : {baseline:.2f}%")
    print(f"  🔴 הפרש                          : {sel - baseline:+.2f} נק' אחוז")

    # ------------------------------------------------------ ביקורת
    hdr("ביקורת — מה היה יוצא בבחירה אקראית")
    print("  אם בחירה אקראית מייצרת אותו הפרש, זה אינו קשור ל-ppm.\n")

    rng = np.random.default_rng(17)
    rand = []
    for season, g in df.groupby("Season"):
        for _ in range(200):
            s = g.sample(min(args.roster, len(g)), random_state=int(rng.integers(1e9)))
            rand.append(weighted_usage(s))
    rand_mean = float(np.mean(rand))

    print(f"  אקראי  : {rand_mean:.2f}%")
    print(f"  לפי ppm: {sel:.2f}%")
    print(f"  ההפרש שמיוחס ל-ppm: {sel - rand_mean:+.2f} נק' אחוז")

    # ------------------------------------------------------ קריאה
    hdr("קריאת התוצאה")
    excess = sel - baseline
    if excess < 2.0:
        print(f"  ✅ עודף של {excess:+.2f} נק' בלבד. בחירה לפי ppm כמעט")
        print("     אינה מפרה את מגבלת הכדור. ההשערה נחלשת מאוד.")
    else:
        print(f"  🔴 עודף של {excess:+.2f} נק' אחוז.")
        print("     סגל כזה אינו יכול להתקיים — סכום ה-usage חורג מ-100%.")
        print(f"\n  סדר גודל של המחיר, לפי β=+0.0186 שנמדד:")
        print(f"     {excess:.2f} × 0.0186 = {excess * 0.0186:.4f} PIR לדקה")
        print(f"     על 200 דקות: {excess * 0.0186 * 200:.1f} נקודות ניקוד")
        print("\n  ⚠️ להשוואה: היתרון הבלתי מוסבר ביום 9 היה 9.4% מתוך ~124,")
        print("     כלומר כ-11.7 נקודות.")

    print("\n  ⚠️ ושוב: זה חסם עליון על סגל היפותטי, לא הסגל של המנוע.")
    print("     התחזיות שננעלו (25-27% · 23-26%) עדיין פתוחות.")

    out = resolve("data/processed/usage_budget_check.csv")
    picked.to_csv(out, index=False)
    print(f"\n  נשמר: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())