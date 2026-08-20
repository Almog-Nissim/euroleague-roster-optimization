"""
usage_feasibility.py — האם האילוץ בכלל אפשרי, והאם הוא חוסם.

נכתב **לפני** התיקון באופטימייזר, ולא אחריו.

המחלוקת שנעלה
-------------
  אלמוג : יימצאו הרבה יותר מ-12 מועמדים עם usage נמוך.
          האילוץ לא יחסום בפועל.
  קלוד  : הוא כן יחסום — usage ו-ppm מתואמים חיובית (+0.35..+0.55),
          ולכן ויתור על נתח כדור הוא ויתור על איכות.

שתי הגרסאות ניתנות למדידה, ולשתיהן משמעות הפוכה:
אם אלמוג צודק — הפרת מגבלת הכדור **אינה** מקור היתרון.
אם קלוד צודק — הניקוד יירד בסדר הגודל שחושב (~3.5 נקודות).

⚠️ הבחנה שקל לפספס: להירשם מתחת ל-20% זה קל, כל שחקן תפקידי עומד
בזה. השאלה היא **כמה ppm המנוע מוותר** כשהוא נאלץ לקחת אותם.

מה נבדק
-------
א. המתאם usage↔ppm במאגר — הבסיס להשערה כולה
ב. כמה מועמדים עם usage < 20% קיימים לכל עונה
ג. מה ה-ppm שלהם מול אלה שהמנוע בחר בפועל
ד. סימולציה: אילו 12 היה בוחר תחת האילוץ, כמה ppm הוא מפסיד

הרצה:  python src/usage_feasibility.py
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

TARGET = 20.0
ROSTER = 12


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


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
    real = (use.groupby(["Season", "key"])
               .agg(usage=("usage", "mean"), minutes=("minutes", "sum")).reset_index())

    # ⚠️ המאגר האמיתי הוא cand מתוך league_backtest, שאינו נשמר.
    #    כאן משמש כל מי שמופיע בסגלים כלשהם באותה עונה — קירוב
    #    תחתון למאגר, ולכן הבדיקה **מחמירה** כלפי אלמוג.
    pool = (ros.merge(real, left_on=["season", "key"],
                      right_on=["Season", "key"], how="left")
              .dropna(subset=["usage"])
              .drop_duplicates(["season", "key"]))
    print(f"מאגר מקורב: {len(pool):,} שחקנים-עונה "
          f"({pool.groupby('season').size().to_dict()})")

    # ---------------------------------------------------------- א
    hdr("א. המתאם usage ↔ ppm — הבסיס להשערה")
    print("  אם חיובי, ויתור על נתח כדור הוא ויתור על איכות.\n")

    for season, g in pool.groupby("season"):
        r = float(g["usage"].corr(g["ppm_true"]))
        print(f"  {season}: r = {r:+.3f}   n={len(g)}")
    r_all = float(pool["usage"].corr(pool["ppm_true"]))
    print(f"\n  כולל: r = {r_all:+.3f}   n={len(pool)}")

    if r_all > 0.3:
        print("\n  🔴 מתאם חיובי ממשי — האילוץ יעלה ב-ppm.")
    elif r_all > 0.1:
        print("\n  ⚠️ מתאם חיובי חלש — האילוץ יעלה מעט.")
    else:
        print("\n  ✅ אין מתאם ממשי — האילוץ כמעט חינם.")

    # ---------------------------------------------------------- ב
    hdr("ב. כמה מועמדים עם usage מתחת ל-20%")

    tab = pool.groupby("season").apply(
        lambda g: pd.Series({
            "במאגר": len(g),
            "usage<20": int((g["usage"] < TARGET).sum()),
            "usage<18": int((g["usage"] < 18).sum()),
            "usage<20 ו-ppm מעל חציון":
                int(((g["usage"] < TARGET) & (g["ppm_true"] > g["ppm_true"].median())).sum()),
        }), include_groups=False)
    print(tab.to_string())

    min_ok = int(tab["usage<20"].min())
    print(f"\n  המינימום לעונה: {min_ok} מועמדים (נדרש {ROSTER})")
    if min_ok >= ROSTER * 2:
        print("  ✅ יש בשפע. האילוץ **אפשרי** — כפי שאלמוג צפה.")
    elif min_ok >= ROSTER:
        print("  ⚠️ יש בדיוק מספיק. האילוץ אפשרי אך צר.")
    else:
        print("  🔴 אין מספיק. האילוץ בלתי אפשרי בעונות מסוימות.")

    # ---------------------------------------------------------- ג
    hdr("ג. ppm של המועמדים מול מי שנבחר בפועל")

    picked = (ros[ros.side == "engine"]
              .merge(real, left_on=["season", "key"],
                     right_on=["Season", "key"], how="left")
              .dropna(subset=["usage"]))
    low = pool[pool["usage"] < TARGET]

    print(f"  {'קבוצה':<28}{'n':>6}{'ppm חציוני':>14}{'usage חציוני':>15}")
    print("  " + "-" * 64)
    for name, g in [("שנבחרו בפועל", picked), ("usage<20 במאגר", low),
                    ("כל המאגר", pool)]:
        print(f"  {name:<28}{len(g):>6}{g['ppm_true'].median():>14.3f}"
              f"{g['usage'].median():>15.2f}")

    gap = float(picked["ppm_true"].median() - low["ppm_true"].median())
    print(f"\n  פער ה-ppm החציוני: {gap:+.3f} לדקה")
    print(f"  על 200 דקות: {gap * 200:.1f} נקודות — חסם עליון גס על העלות")

    # ---------------------------------------------------------- ד
    hdr("ד. סימולציה — 12 הטובים תחת האילוץ")
    print("  בחירה חמדנית לפי ppm, בדחייה של מי שמפר את התקרה.")
    print("  ⚠️ בלי תקציב ובלי עמדות — חסם עליון על העלות בלבד.\n")

    rows = []
    for season, g in pool.groupby("season"):
        g = g.sort_values("ppm_true", ascending=False)

        free = g.head(ROSTER)
        u_free = float(free["usage"].mean())
        p_free = float(free["ppm_true"].mean())

        sel, u_sum = [], 0.0
        for _, r in g.iterrows():
            if len(sel) >= ROSTER:
                break
            if (u_sum + r["usage"]) / (len(sel) + 1) <= TARGET + 1e-9:
                sel.append(r)
                u_sum += r["usage"]
        con = pd.DataFrame(sel)
        ok = len(con) == ROSTER
        rows.append({
            "season": season, "אפשרי": ok,
            "ppm חופשי": p_free, "ppm מאולץ": float(con["ppm_true"].mean()) if ok else np.nan,
            "usage חופשי": u_free,
            "usage מאולץ": float(con["usage"].mean()) if ok else np.nan,
        })

    sim = pd.DataFrame(rows)
    print(sim.round(3).to_string(index=False))

    if sim["אפשרי"].all():
        loss = float((sim["ppm חופשי"] - sim["ppm מאולץ"]).mean())
        print(f"\n  ✅ האילוץ אפשרי בכל העונות.")
        print(f"  אובדן ppm ממוצע: {loss:.4f} לדקה = {loss * 200:.1f} נקודות")
        print(f"  ירידת usage    : {float((sim['usage חופשי'] - sim['usage מאולץ']).mean()):.2f} נק'")
        print(f"\n  להשוואה — הפער שנמדד היה +1.80, וסדר הגודל שחושב")
        print(f"  לפי β היה 6.7 נקודות.")
    else:
        print(f"\n  🔴 האילוץ בלתי אפשרי ב-{int((~sim['אפשרי']).sum())} עונות.")

    hdr("הכרעה")
    print(f"  מועמדים מינימלי לעונה : {min_ok}  (אלמוג: 'הרבה יותר מ-12')")
    print(f"  מתאם usage↔ppm        : {r_all:+.3f}  (קלוד: '+0.35..+0.55')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())