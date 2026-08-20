"""
roster_usage.py — ממוצע ה-usage של הסגלים שהמנוע בנה, מול הסגלים האמיתיים.

זו הבדיקה שנעלו עליה תחזיות: אלמוג 25-27%, קלוד 23-26%.

הזהות שנבדקת
------------
`usage` הוא נתח ההחזקות של השחקן מתוך אלה של קבוצתו. לכן הממוצע
המשוקלל-דקות בכל קבוצה **חייב** להיות 20.0% — חמישה על המגרש,
כדור אחד. זהות, לא אמידה.

סגל שממוצעו 25% אינו "פחות יעיל". הוא **לא יכול להתקיים**.
זו אותה משפחה שתפסה אותנו שלוש פעמים ביום 9 — הקצה של כל מרווח
בנפרד: תקרת 32 דקות נכונה לשחקן בודד, והמודל העמיד שמונה.

⚠️ הקצאת הדקות משוחזרת, לא נמדדת
---------------------------------
`score_rows` מחזירה שני סקלרים — לא מערך דקות. ההקצאה אינה נשמרת
בשום מקום, ולכן היא משוחזרת כאן מהחוק החמדני:
מיון לפי ppm יורד, כל שחקן מקבל `32·avail` עד למיצוי 200 דקות.

**בדיקת השפיות שמכריעה אם השחזור תקף:** הניקוד שהוא מייצר חייב
להיות זהה ל-`q` שכבר שמור ב-league_backtest_results.csv, ב-38
עונות-מועדון. אם הוא סוטה — השחזור נפסל והסקריפט עוצר.

ובכל מקרה מדווחות **שתי גרסאות** — משוקלל ולא-משוקלל. הפער ביניהן
הוא בדיוק מה שהקונטרריאן הצביע עליו (0.512 מול 123.7).

הרצה:  python src/roster_usage.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_paths import repo_root, resolve  # noqa: E402
from player_id import canonical  # noqa: E402
import roster_optimizer as ro  # noqa: E402

REPL = 0.127


def hdr(t: str) -> None:
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def allocate(df: pd.DataFrame):
    """
    שכפול מדויק של הלולאה ב-score_rows. לא שחזור מהזיכרון — העתקה.

    שלושה דברים שהניחוש הקודם פספס:
      1. `repl` **אינו מחוסר** — הוא מתווסף על הדקות שלא הוקצו:
         q = Σ e·ppm + (200 − Σe)·repl
      2. התקרה מוחלת **לפני** הזמינות: min(32, left, cap)·av, ולא
         min(32·av, left). לכן `left` לעולם אינו מתאפס והסגל אף פעם
         אינו ממלא 200 דקות אמיתיות.
      3. יש **תקרות עמדה** — POS_MAX_SHARE[g]·200 — שמתרוקנות תוך
         כדי. את אלה פספסתי לגמרי.

    מחזיר (דקות לכל שחקן, q, used, filled).
    """
    ppm = df["ppm_true"].to_numpy(dtype=float)
    av = df["avail_true"].to_numpy(dtype=float)
    pos = df["position"].to_numpy()

    order = np.argsort(-ppm)
    caps = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME for g in ro.POS_MAX_SHARE}
    left = float(ro.MINUTES_PER_GAME)
    out = np.zeros(len(df))
    q = 0.0
    used = 0.0

    for j in order:
        g = pos[j]
        if g not in caps:
            continue
        take = max(min(ro.MAX_MIN_PLAYER, left, caps[g]) * av[j], 0.0)
        out[j] = take
        q += take * ppm[j]
        left -= take
        caps[g] -= take
        used += take

    filled = left * REPL if left > 0 else 0.0
    return out, q + filled, used, filled


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rosters", default="data/processed/engine_rosters.csv")
    ap.add_argument("--usage", default="data/processed/usage_curve_results.csv")
    ap.add_argument("--results", default="data/processed/league_backtest_results.csv")
    args = ap.parse_args()

    print(f"שורש הריפו: {repo_root()}")
    ros = pd.read_csv(resolve(args.rosters), dtype={"player_code": str}, low_memory=False)
    use = pd.read_csv(resolve(args.usage), low_memory=False)
    res = pd.read_csv(resolve(args.results), low_memory=False)
    print(f"סגלים: {len(ros):,} שורות · usage: {len(use):,} · תוצאות: {len(res)}")

    # ------------------------------------------------------ שחזור
    hdr("א. שחזור הקצאת הדקות — ואימות מול q השמור")
    print("  אם הניקוד המשוחזר אינו זהה ל-q, השחזור נפסל.\n")

    ros["minutes_rec"] = np.nan
    qmap = {}
    for (s, c, side), g in ros.groupby(["season", "club", "side"]):
        mins, q, used, filled = allocate(g)
        ros.loc[g.index, "minutes_rec"] = mins
        qmap[(s, c, side)] = {"q": q, "used": used, "filled": filled}

    qdf = pd.DataFrame([{"season": k[0], "club": k[1], "side": k[2], **v}
                        for k, v in qmap.items()])
    # שם העמודה 'club' מתנגש עם קוד המועדון, לכן לא משתמשים ב-unstack
    eng_rec = (qdf[qdf.side == "engine"][["season", "club", "q"]]
               .rename(columns={"q": "q_eng_rec"}))
    club_rec = (qdf[qdf.side == "club"][["season", "club", "q"]]
                .rename(columns={"q": "q_club_rec"}))
    cmp = (res[["season", "club", "q_club", "q_eng"]]
           .merge(eng_rec, on=["season", "club"])
           .merge(club_rec, on=["season", "club"]))
    cmp["d_eng"] = cmp["q_eng_rec"] - cmp["q_eng"]
    cmp["d_club"] = cmp["q_club_rec"] - cmp["q_club"]

    print(f"  n = {len(cmp)} עונות-מועדון")
    print(f"  סטייה במנוע  : חציון {cmp.d_eng.abs().median():.4f} · "
          f"מקס {cmp.d_eng.abs().max():.4f}")
    print(f"  סטייה במועדון: חציון {cmp.d_club.abs().median():.4f} · "
          f"מקס {cmp.d_club.abs().max():.4f}")

    print("\n  דקות שהוקצו בפועל (used) מול 200:")
    for side, g in qdf.groupby("side"):
        print(f"    {side:<8} חציון {g.used.median():6.1f} · "
              f"מילוי חלופי {g.filled.median():5.2f}")
    print("\n  ⚠️ המנוע (12 שחקנים) מקצה פחות דקות אמיתיות מהמועדון,")
    print("     ולכן מקבל יותר מילוי ברמת שחקן חלופי.")

    ok = cmp.d_eng.abs().max() < 0.05 and cmp.d_club.abs().max() < 0.05
    if ok:
        print("\n  ✅ השחזור מייצר את אותו ניקוד. ההקצאה תקפה.")
    else:
        print("\n  🔴 השחזור אינו תואם. חוק ההקצאה שונה ממה שהנחתי.")
        print(cmp.nlargest(5, "d_eng")[
            ["season", "club", "q_eng", "q_eng_rec", "d_eng"]].to_string(index=False))
        print("\n  ⚠️ הממוצע המשוקלל למטה **אינו תקף**. רק הלא-משוקלל.")

    # ------------------------------------------------------ צירוף
    hdr("ב. צירוף ל-usage")

    use["key"] = use["Player_ID"].map(canonical)
    ros["key"] = ros["player_code"].map(canonical)
    umap = (use.groupby(["Season", "key"])["usage"].mean()
               .rename("usage").reset_index())

    m = ros.merge(umap, left_on=["season", "key"], right_on=["Season", "key"], how="left")
    cov = m.groupby("side")["usage"].apply(lambda s: s.notna().mean())
    print("  כיסוי ה-usage לפי צד:")
    for side, v in cov.items():
        print(f"    {side:<8} {v:.1%}")
    print("\n  ⚠️ הכיסוי חלקי כי usage_curve_results מסונן ל->=600 דקות.")
    print("     שחקני שוליים חסרים משני הצדדים באותה מידה.")

    # ------------------------------------------------------ תוצאה
    hdr("ג. 🔴 ממוצע ה-usage של הסגל")

    def summarise(g):
        d = g.dropna(subset=["usage"])
        if not len(d):
            return pd.Series({"w": np.nan, "u": np.nan, "n": 0})
        w = d["minutes_rec"].to_numpy()
        return pd.Series({
            "w": float(np.average(d["usage"], weights=w)) if w.sum() else np.nan,
            "u": float(d["usage"].mean()),
            "n": len(d),
        })

    per = m.groupby(["season", "club", "side"]).apply(
        summarise, include_groups=False).reset_index()

    tab = per.groupby("side").agg(
        משוקלל=("w", "mean"), לא_משוקלל=("u", "mean"), שחקנים=("n", "mean"))
    print(tab.round(2).to_string())

    eng_w = float(per[per.side == "engine"]["w"].mean())
    clb_w = float(per[per.side == "club"]["w"].mean())
    eng_u = float(per[per.side == "engine"]["u"].mean())
    clb_u = float(per[per.side == "club"]["u"].mean())

    print(f"\n  משוקלל-דקות : מנוע {eng_w:.2f}%  ·  מועדון {clb_w:.2f}%  "
          f"·  הפרש {eng_w - clb_w:+.2f}")
    print(f"  לא-משוקלל   : מנוע {eng_u:.2f}%  ·  מועדון {clb_u:.2f}%  "
          f"·  הפרש {eng_u - clb_u:+.2f}")

    print("\n  לפי עונה (משוקלל):")
    print(per.pivot_table(index="season", columns="side", values="w")
             .round(2).to_string())

    # ------------------------------------------------------ קריאה
    hdr("קריאת התוצאה")
    excess = eng_w - clb_w if ok else eng_u - clb_u
    basis = "משוקלל" if ok else "לא-משוקלל (השחזור נפסל)"
    print(f"  בסיס: {basis}")

    if excess < 1.5:
        print(f"  ✅ עודף של {excess:+.2f} נק' בלבד — המנוע כמעט אינו")
        print("     מפר את מגבלת הכדור. ההשערה נופלת.")
    else:
        print(f"  🔴 עודף של {excess:+.2f} נק' אחוז מעל הסגל האמיתי.")
        print(f"\n  סדר גודל לפי β=+0.0186:")
        print(f"     {excess:.2f} × 0.0186 × 200 = {excess * 0.0186 * 200:.1f} נקודות")
        print("     היתרון הבלתי מוסבר ביום 9: ~11.7 נקודות מתוך ~124.")
        print("\n  ⚠️ זו הכפלה של שלושה אומדנים שאף אחד לא נועד לכך.")
        print("     סדר גודל שמתיישב, לא כימות.")

    print("\n  התחזיות שננעלו: אלמוג 25-27%  ·  קלוד 23-26%")
    print(f"  התוצאה (מנוע, משוקלל): {eng_w:.2f}%")

    out = resolve("data/processed/roster_usage.csv")
    per.to_csv(out, index=False)
    print(f"\n  נשמר: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())