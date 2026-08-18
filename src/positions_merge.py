"""
positions_merge.py  (Day 9)
---------------------------
קולט את `positions_missing.xlsx` אחרי שאלמוג מילא, מוסיף ל-
`player_positions.csv`, **ומודד את המסווג מול המילוי הידני**.

--------------------------------------------------------------------
זורק (לא מדפיס אזהרה) על:
--------------------------------------------------------------------
  - עמדה שאינה G/F/C
  - קוד שאינו מופיע ב-player_season
  - קוד שכבר קיים ב-player_positions (כפילות)
  - שם שאינו תואם את הדאטה  ->  אזהרה בלבד, השם הוא תצוגה

השורות הריקות **אינן שגיאה** — אפשר למלא בשלבים. הן פשוט לא
נכנסות, והכיסוי החדש מדווח.

--------------------------------------------------------------------
המבחן שמקבלים בחינם
--------------------------------------------------------------------
`positions_classifier_pred.csv` נוצר **לפני** המילוי הידני, ולכן
ההשוואה כאן היא אימות חוץ-מדגמי אמיתי. דיוק ה-CV היה 83.3%.
אם ההסכמה כאן דומה — המסווג שמיש לעונות הבאות במקום מילוי ידני.
אם היא נמוכה בהרבה — ה-CV היה אופטימי ואי אפשר לסמוך עליו.

הרצה:
    python src/positions_merge.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR

XLSX = PROCESSED_DIR.parent / "manual" / "positions_missing.xlsx"
POSCSV = PROCESSED_DIR / "player_positions.csv"
PRED = PROCESSED_DIR / "positions_classifier_pred.csv"
VALID = {"G", "F", "C"}


def main():
    if not XLSX.exists():
        raise FileNotFoundError(f"לא נמצא {XLSX} — הרץ positions_worklist קודם")
    df = pd.read_excel(XLSX, sheet_name="positions",
                       dtype={"player_code": str})
    df["player_code"] = df.player_code.astype(str).str.strip()
    df["position"] = (df.position.astype(str).str.strip().str.upper()
                      .replace({"NAN": None, "": None, "NONE": None}))

    pos = pd.read_csv(POSCSV, dtype={"player_code": str})
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    names = ps.drop_duplicates("player_code").set_index("player_code").player_name

    filled = df[df.position.notna()].copy()
    errs, warns = [], []

    bad = filled[~filled.position.isin(VALID)]
    if len(bad):
        errs.append("עמדה לא חוקית: " + ", ".join(
            f"{r.player_code}={r.position!r}" for r in bad.itertuples()))
    unknown = set(filled.player_code) - set(ps.player_code)
    if unknown:
        errs.append(f"קודים שאינם בדאטה: {sorted(unknown)}")
    dup = set(filled.player_code) & set(pos.player_code)
    if dup:
        errs.append(f"קודים שכבר קיימים: {sorted(dup)}")
    d2 = filled[filled.player_code.duplicated(keep=False)]
    if len(d2):
        errs.append(f"כפילות בגיליון: {sorted(d2.player_code.unique())}")
    for r in filled.itertuples():
        real = names.get(r.player_code)
        if real and str(r.player_name).strip().upper() != str(real).strip().upper():
            warns.append(f"  שם: {r.player_code} בגיליון "
                         f"{r.player_name!r} בדאטה {real!r}")
    if errs:
        raise ValueError("\n".join(["שגיאות:"] + errs))
    for w in warns:
        print("⚠️" + w)

    print(f"מולאו {len(filled)} מתוך {len(df)}")

    # ---- המבחן: המסווג מול המילוי הידני ----
    if PRED.exists():
        pr = pd.read_csv(PRED, dtype={"player_code": str})
        m = filled.merge(pr, on="player_code", how="inner")
        if len(m):
            agree = float((m.position == m.pred).mean())
            print(f"\nמסווג מול ידני: {len(m)} חופפים, "
                  f"הסכמה {agree:.1%}  (CV היה 83.3%)")
            print(pd.crosstab(m.position, m.pred,
                              rownames=["ידני"], colnames=["מסווג"]).to_string())
            hi = m[m.conf >= 0.7]
            if len(hi):
                print(f"  בביטחון>=0.70: {len(hi)} מקרים, "
                      f"הסכמה {float((hi.position==hi.pred).mean()):.1%}")
            gc = m[((m.position == "G") & (m.pred == "C")) |
                   ((m.position == "C") & (m.pred == "G"))]
            print(f"  בלבולי G↔C (הכי חמורים): {len(gc)}")
            if agree < 0.70:
                print("  ⛔ הסכמה נמוכה מהותית מה-CV. המסווג לא שמיש.")

    new = filled[["player_code", "player_name", "position"]]
    out = pd.concat([pos[["player_code", "player_name", "position"]], new],
                    ignore_index=True)
    out.to_csv(POSCSV, index=False)
    print(f"\nנכתב {POSCSV}: {len(pos)} -> {len(out)} שורות")

    for s in (2024, 2025):
        t = ps[(ps.season == s) & (ps.min_per_game > 0)].copy()
        t["mt"] = t.min_per_game * t.games
        miss = t[~t.player_code.isin(set(out.player_code))]
        print(f"  {s}: נותרו {len(miss)} ללא עמדה, "
              f"{miss.mt.sum()/t.mt.sum():.1%} מהדקות")


if __name__ == "__main__":
    main()