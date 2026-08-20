"""
club_usage_bias.py — האם 21.52% הוא הטיה, וכמה היא גדולה.

הבעיה
-----
צד המועדון יצא 21.52% משוקלל-דקות. **הזהות מחייבת 20.0%** —
usage הוא נתח ההחזקות מתוך אלה של הקבוצה, חמישה על המגרש, כדור
אחד. קבוצה אמיתית לא יכולה לחרוג.

והפער הזה, 1.52, כמעט זהה להפרש שמדדנו בין המנוע למועדון: 1.61.
**אי אפשר לדווח ממצא שגודלו שווה לרעש שידוע עליו.**

המקור החשוד
-----------
ההקצאה החמדנית ב-score_rows נותנת אפס דקות לזנב הסגל — ובדיוק שם
יושבים בעלי ה-usage הנמוך. וזה פוגע יותר בסגל של 17 מאשר בסגל של
12, כלומר **ההטיה פועלת לטובת המסקנה שלנו.**

המבחן
-----
לחשב את ה-usage המשוקלל של המועדון לפי **הדקות שהוא באמת שיחק**,
מהבוקסקורים, במקום לפי ההקצאה החמדנית.

  · אם יוצא 20.0% — ההטיה מאושרת, וההפרש האמיתי **גדול** מ-1.61.
  · אם נשאר 21.5% — יש משהו אחר, וצריך למצוא אותו לפני שמדווחים.

⚠️ הערה: המנוע אינו קיים במציאות ולכן אין לו דקות אמיתיות. ההשוואה
ההוגנת היא **מועדון-אמיתי מול מועדון-מוקצה** — כמה ההקצאה לבדה
מזיזה את המספר. את אותו הסחף צריך להחיל על צד המנוע.

הרצה:  python src/club_usage_bias.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import repo_root, resolve  # noqa: E402
from player_id import canonical  # noqa: E402
from roster_usage import allocate  # noqa: E402


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def wavg(v, w) -> float:
    v, w = np.asarray(v, float), np.asarray(w, float)
    ok = np.isfinite(v) & np.isfinite(w) & (w > 0)
    return float(np.average(v[ok], weights=w[ok])) if ok.any() else np.nan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rosters", default="data/processed/engine_rosters.csv")
    ap.add_argument("--usage", default="data/processed/usage_curve_results.csv")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")
    ros = pd.read_csv(resolve(args.rosters), dtype={"player_code": str}, low_memory=False)
    use = pd.read_csv(resolve(args.usage), low_memory=False)

    use["key"] = use["Player_ID"].map(canonical)
    ros["key"] = ros["player_code"].map(canonical)

    # דקות אמיתיות + usage, לכל שחקן-עונה. סכימה על פני מועדונים
    # במקרה של מעבר באמצע עונה.
    real = (use.groupby(["Season", "key"])
               .agg(usage_real=("usage", "mean"), minutes_real=("minutes", "sum"))
               .reset_index())

    m = ros.merge(real, left_on=["season", "key"], right_on=["Season", "key"], how="left")

    # ההקצאה החמדנית, כפי ש-score_rows מבצעת אותה
    m["minutes_alloc"] = np.nan
    for _, g in m.groupby(["season", "club", "side"]):
        mins, *_ = allocate(g)
        m.loc[g.index, "minutes_alloc"] = mins

    hdr("א. כיסוי")
    cov = m.groupby("side")["usage_real"].apply(lambda s: s.notna().mean())
    for side, v in cov.items():
        print(f"  {side:<8} {v:.1%}")
    print(f"\n  דקות אמיתיות חסרות: {int(m['minutes_real'].isna().sum()):,} שורות")

    hdr("ב. 🔴 שלוש דרכי שקלול")
    print("  real   — הדקות שהמועדון באמת שיחק (הזהות מחייבת 20.0%)")
    print("  alloc  — ההקצאה החמדנית של score_rows")
    print("  flat   — לא-משוקלל\n")

    rows = []
    for (s, c, side), g in m.groupby(["season", "club", "side"]):
        d = g.dropna(subset=["usage_real"])
        if not len(d):
            continue
        rows.append({
            "season": s, "club": c, "side": side,
            "real": wavg(d["usage_real"], d["minutes_real"]),
            "alloc": wavg(d["usage_real"], d["minutes_alloc"]),
            "flat": float(d["usage_real"].mean()),
            "n": len(d),
            "n_zero_alloc": int((d["minutes_alloc"] <= 0).sum()),
        })
    per = pd.DataFrame(rows)

    tab = per.groupby("side")[["real", "alloc", "flat", "n", "n_zero_alloc"]].mean()
    print(tab.round(2).to_string())

    club = per[per.side == "club"]
    eng = per[per.side == "engine"]

    hdr("ג. האם ההטיה מאושרת")
    real_club = float(club["real"].mean())
    alloc_club = float(club["alloc"].mean())
    print(f"  מועדון לפי דקות אמיתיות : {real_club:.2f}%")
    print(f"  מועדון לפי ההקצאה       : {alloc_club:.2f}%")
    print(f"  🔴 סחף ההקצאה            : {alloc_club - real_club:+.2f} נק' אחוז")

    if abs(real_club - 20.0) < 0.6:
        print("\n  ✅ הדקות האמיתיות מחזירות ~20.0% — הזהות מתקיימת,")
        print("     והסחף כולו מההקצאה החמדנית.")
    else:
        print(f"\n  ⚠️ גם לפי דקות אמיתיות יוצא {real_club:.2f}% ולא 20.0%.")
        print("     מקור אפשרי: הסגל אינו מכוסה במלואו, או שחקנים")
        print("     שעברו מועדון באמצע עונה. הפער אינו מוסבר בהקצאה בלבד.")

    print(f"\n  שחקנים שקיבלו אפס דקות בהקצאה:")
    print(f"    מועדון {club['n_zero_alloc'].mean():.1f} מתוך {club['n'].mean():.1f}")
    print(f"    מנוע   {eng['n_zero_alloc'].mean():.1f} מתוך {eng['n'].mean():.1f}")

    hdr("ד. ההפרש מנוע-מועדון, אחרי תיקון")
    print("  ⚠️ למנוע אין דקות אמיתיות — הוא לא קיים במציאות.")
    print("     ההשוואה ההוגנת היא **תחת אותו שקלול לשני הצדדים**.\n")

    for col, label in [("alloc", "לפי ההקצאה (כפי שדווח)"),
                       ("flat", "לא-משוקלל")]:
        e, c = float(eng[col].mean()), float(club[col].mean())
        print(f"  {label:<28} מנוע {e:5.2f}%  מועדון {c:5.2f}%  "
              f"הפרש {e - c:+.2f}")

    e_alloc = float(eng["alloc"].mean())
    print(f"\n  ואם מתקנים את צד המועדון לזהות (20.0%):")
    print(f"    מנוע {e_alloc:.2f}% מול 20.0%  ->  הפרש {e_alloc - 20.0:+.2f}")
    print("\n  ⚠️ אבל זה לא הוגן: הסחף שפועל על המועדון פועל גם על")
    print("     המנוע. אם שני הצדדים סובלים ממנו באותה מידה, ההפרש")
    print("     שדווח (+1.61) הוא כבר התיקון הנכון.")

    hdr("מסקנה")
    drift = alloc_club - real_club
    gap = float(eng["alloc"].mean() - club["alloc"].mean())
    print(f"  סחף ההקצאה בצד המועדון : {drift:+.2f}")
    print(f"  ההפרש שמדדנו           : {gap:+.2f}")
    if abs(drift) > abs(gap) * 0.7:
        print("\n  🔴 הסחף בסדר גודל של הממצא. אי אפשר לדווח את ההפרש")
        print("     בלי לכמת כמה ממנו הוא ארטיפקט של ההקצאה.")
    else:
        print("\n  ✅ הסחף קטן מהממצא. ההפרש שורד.")

    out = resolve("data/processed/club_usage_bias.csv")
    per.to_csv(out, index=False)
    print(f"\n  נשמר: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())