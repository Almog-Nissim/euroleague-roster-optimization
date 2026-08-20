"""
decode_score.py — איזו נוסחה בדיוק מייצרת את q.

הרקע
----
`roster_usage.py` שחזר את הקצאת הדקות והשווה ל-q השמור. הסטייה
לא הייתה מפוזרת — היא הייתה **כמעט קבועה**:

    מנוע  : חציון 24.89 · מקס 25.38
    מועדון: חציון 24.85 · מקס 25.40

וגם צד המועדון סטה באותה מידה, למרות שהוא סגל של 13-20 שחקנים
ולא 12. חוק הקצאה שגוי היה נותן סטיות שונות לשני צדדים בגדלים
שונים. סטייה קבועה היא **איבר קבוע שחסר**, לא הקצאה שגויה.

    200 × 0.127 = 25.4

וזה בדיוק המקסימום שנצפה בשני הצדדים.

ההשערה: `score_rows` מחשבת `Σ e·ppm` בלי לחסר `repl`.

⚠️ אבל שתי נוסחאות כבר נפלו היום, ולכן לא מנחשים שלישית. הסקריפט
סורק חמישה מועמדים ומדווח מי מייצר סטייה אפס — ומדפיס את קוד
המקור של `score_rows` כדי שנראה מה היא באמת עושה.

למה זה חשוב מעבר לשחזור
------------------------
זו בדיוק השאלה שהקונטרריאן העלה בסבב השני ולא נענתה: האם הניקוד
מחסר `repl`. אם לא — המטרה והמדד אינם זהים, בניגוד למה שסעיף 4
מצהיר. ואם אילוץ ה-200 נחסם בשוויון תמיד, שתי הנוסחאות נבדלות
בקבוע ולכן **שקולות לאופטימיזציה** — וההפרשים ביניהן זהים.

הסקריפט בודק גם את זה: האם סך הדקות הוא 200 בכל 38.

הרצה:  python src/decode_score.py
"""

from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from el_paths import repo_root, resolve  # noqa: E402

TOTAL_MINUTES = 200.0
MAX_PER_PLAYER = 32.0
REPL = 0.127


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def show_source() -> None:
    hdr("א. מה score_rows באמת עושה")
    try:
        from roster_membership_audit import score_rows
        print(inspect.getsource(score_rows))
    except Exception as e:
        print(f"  ⚠️ לא ניתן להציג: {type(e).__name__}: {e}")


def allocate(df: pd.DataFrame, cap_mult: float, total: float) -> np.ndarray:
    """הקצאה חמדנית לפי ppm יורד, עד למיצוי סך הדקות."""
    d = df.sort_values("ppm_true", ascending=False)
    cap = (cap_mult * d["avail_true"]).to_numpy(dtype=float)
    out = np.zeros(len(d))
    left = total
    for i, c in enumerate(cap):
        take = min(max(c, 0.0), left)
        out[i] = take
        left -= take
        if left <= 1e-9:
            break
    return pd.Series(out, index=d.index).reindex(df.index).to_numpy()


# מועמדים: (שם, מכפיל תקרה, סך דקות, האם מחסר repl)
CANDIDATES = [
    ("Σ e·(ppm−repl)   · 32·avail · 200", MAX_PER_PLAYER, 200.0, True),
    ("Σ e·ppm          · 32·avail · 200", MAX_PER_PLAYER, 200.0, False),
    ("Σ e·(ppm−repl)   · 40·avail · 200", 40.0, 200.0, True),
    ("Σ e·ppm          · 32·avail · 240", MAX_PER_PLAYER, 240.0, False),
    ("Σ e·(ppm−repl)   · 32·avail · 240", MAX_PER_PLAYER, 240.0, True),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rosters", default="data/processed/engine_rosters.csv")
    ap.add_argument("--results", default="data/processed/league_backtest_results.csv")
    ap.add_argument("--source", action="store_true", help="להדפיס את קוד score_rows")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")

    if args.source:
        show_source()

    ros = pd.read_csv(resolve(args.rosters), dtype={"player_code": str}, low_memory=False)
    res = pd.read_csv(resolve(args.results), low_memory=False)
    print(f"סגלים: {len(ros):,} · תוצאות: {len(res)}")

    hdr("ב. סריקת מועמדים — מי מייצר סטייה אפס")
    print(f"  {'נוסחה':<38}{'מנוע: חציון':>14}{'מקס':>10}{'מועדון: מקס':>14}")
    print("  " + "-" * 74)

    best = None
    for name, mult, total, sub in CANDIDATES:
        parts = []
        for (s, c, side), g in ros.groupby(["season", "club", "side"]):
            e = allocate(g, mult, total)
            base = g["ppm_true"].to_numpy(dtype=float) - (REPL if sub else 0.0)
            parts.append({"season": s, "club": c, "side": side,
                          "q_rec": float((e * base).sum())})
        rec = pd.DataFrame(parts)

        eng = rec[rec.side == "engine"].merge(
            res[["season", "club", "q_eng"]], on=["season", "club"])
        clb = rec[rec.side == "club"].merge(
            res[["season", "club", "q_club"]], on=["season", "club"])
        de = (eng["q_rec"] - eng["q_eng"]).abs()
        dc = (clb["q_rec"] - clb["q_club"]).abs()

        flag = "  ✅" if de.max() < 0.05 and dc.max() < 0.05 else ""
        print(f"  {name:<38}{de.median():>14.4f}{de.max():>10.4f}"
              f"{dc.max():>14.4f}{flag}")
        if de.max() < 0.05 and dc.max() < 0.05 and best is None:
            best = (name, mult, total, sub)

    hdr("ג. האם אילוץ ה-200 נחסם בשוויון")
    print("  אם כן, שתי הנוסחאות נבדלות בקבוע — שקולות לאופטימיזציה,")
    print("  וההפרשים ביניהן זהים. זו השאלה שהקונטרריאן העלה.\n")

    caps = ros.groupby(["season", "club", "side"]).apply(
        lambda g: float(np.minimum(MAX_PER_PLAYER * g["avail_true"], 1e9).sum()),
        include_groups=False).rename("cap_total").reset_index()
    print(f"  סך התקרות (32·avail) לסגל:")
    print(f"    מנוע  : חציון {caps[caps.side=='engine'].cap_total.median():.1f} · "
          f"מינ' {caps[caps.side=='engine'].cap_total.min():.1f}")
    print(f"    מועדון: חציון {caps[caps.side=='club'].cap_total.median():.1f} · "
          f"מינ' {caps[caps.side=='club'].cap_total.min():.1f}")
    below = int((caps.cap_total < TOTAL_MINUTES).sum())
    if below:
        print(f"\n  🔴 {below} סגלים שסך התקרות שלהם מתחת ל-200 — שם")
        print("     האילוץ **אינו** נחסם בשוויון והנוסחאות אינן שקולות.")
    else:
        print(f"\n  ✅ בכל {len(caps)} הסגלים סך התקרות מעל 200 —")
        print("     האילוץ נחסם בשוויון, והנוסחאות נבדלות בקבוע בלבד.")

    hdr("מסקנה")
    if best:
        name, mult, total, sub = best
        print(f"  ✅ הנוסחה: {name}")
        print(f"     מחסר repl: {'כן' if sub else '🔴 לא'}")
        if not sub:
            print("\n  זו תשובה לשאלה מהבוקר: הניקוד **אינו** מחסר repl,")
            print("  בניגוד למה שסעיף 4 מצהיר. אם האילוץ נחסם בשוויון")
            print("  (סעיף ג), זה לא משנה את הבחירה — רק את הרמה.")
    else:
        print("  🔴 אף מועמד לא התאים. חוק ההקצאה שונה מכולם.")
        print("     הרץ עם --source כדי לראות את הקוד עצמו.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())