"""
budget_curve.py — בהינתן תקציב, מה הסגל הטוב ביותר. 10 עד 40 מיליון.

השינוי בשאלה
------------
עד היום הבנצ'מרק שאל "האם המנוע מנצח את המועדון". התקציב היה
נגזרת של הסגל שהמועדון העמיד, ולכן כל תוצאה נשאה איתה את קללת
המנצח — כל היום עסקנו בשאלה אם היתרון אמיתי או ארטיפקט של
ההשוואה.

כאן **אין יריב.** ציר תקציב רציף, ולכל נקודה הסגל הטוב ביותר.
אין מה לנצח ואין מה לזייף.

וזו השאלה מיום 3 בניסוחה המקורי: *"בהינתן מבנה עלות, איך ההקצאה
מגיבה וכמה היא רגישה למבנה."*

תחזיות שננעלו לפני ההרצה
------------------------
    נקודת הרוויה   אלמוג: ~35 מיליון   ·   קלוד: ~16 מיליון
    קלוד בנוסף: הפרש הניקוד בין 25 ל-40 מיליון < 3 נקודות

הנימוק של קלוד: r=−0.900 בין איכות המועדון ליתרון (יום 9) אומר
שהמנוע נוחת תמיד על אותו מקום — וזה איך שרוויה נראית.

אם העקומה עולה לאורך כל הטווח, יש כלי תכנון. אם היא מתיישרת,
**הממצא הוא שמעל סף מסוים כסף אינו הפתרון לבניית קבוצה מנצחת** —
וזו מסקנה בפני עצמה.

⚠️ שלוש מגבלות שנשארות
-----------------------
1. **הקיר לא נעלם, הוא נעשה גלוי יותר.** הסגלים על העקומה יישבו
   על ppm ~0.6 כשהמקסימום ההיסטורי ביורוליג הוא 0.509. אין נקודת
   ייחוס אמפירית לאף נקודה על העקומה.
2. **מודל העלות כויל על מכבי.** β₁=0.220 מול 0.148 בשוק, ו-β₁ נע
   פי 3.6 בין מועדונים **עם התקציב** (0.302 מכבי, 0.083
   אולימפיאקוס). ככל שנתרחק ממכבי על הציר, המחירים שגויים יותר
   ובאופן שיטתי. **הקצה העליון הוא הכי פחות אמין, והוא המעניין.**
3. האילוץ `Σ eᵢ·usageᵢ ≤ 20·Σ eᵢ` נכנס. בלעדיו העקומה מתארת
   סגלים שאינם יכולים להתקיים, וזה מחמיר ככל שהתקציב עולה — יותר
   כסף, יותר צירים.

🔴 סקאלת התקציב
---------------
`build_pool` בונה את המאגר עם `mean_salary=1.0`, כלומר המחירים
**יחסיים ולא במיליונים**. הזנת 10..40 ישירות לא תתאר מיליונים.

לכן הסקריפט **מודד** את הסקאלה במקום להניח אותה: `--calibrate`
מדפיס את התקציבים היחסיים של 38 המועדונים ואת מה שיש
ב-club_budgets_gemini, ומחשב את היחס. בלי סקאלה מאומתת הוא לא
ירוץ. זה הלקח החוזר של יום 10 — מודדים, לא מנחשים.

הרצה:
    python src/budget_curve.py --calibrate      # קודם
    python src/budget_curve.py --scale <ערך>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import optimizer_backtest as ob  # noqa: E402
from paths import PROCESSED_DIR  # noqa: E402
from roster_membership_audit import score_rows  # noqa: E402
from optimise_consistent import optimise_v2  # noqa: E402
from league_backtest import build_pool, club_side, REPL, SEASONS  # noqa: E402
from usage_constrained import optimise_capped, attach_usage, wusage  # noqa: E402

MIN_ROSTER = 12
SEP = "=" * 78


def hdr(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


# ------------------------------------------------------------------ כיול
def calibrate(feat, anch, pos, ps, split, posmap) -> None:
    """
    מדפיס את התקציבים היחסיים של 38 המועדונים, ומצליב מול כל קובץ
    תקציבים אמיתי שנמצא. בלי זה אי אפשר לדעת מה '10 מיליון' אומר
    בסקאלה של המאגר.
    """
    hdr("כיול הסקאלה — מה '1 יחידה' שווה במיליונים")

    rows = []
    for train_max, test in SEASONS:
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        gmax = float(ps[ps.season == test].games.max())
        for club in sorted(split[split.season == test].club.unique()):
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_ROSTER:
                continue
            rows.append({"season": test, "club": club,
                         "budget_rel": float(keep.cost.sum())})
    rel = pd.DataFrame(rows)

    print(f"  {len(rel)} עונות-מועדון · תקציב יחסי:")
    print(f"    מינימום {rel.budget_rel.min():.2f} · חציון "
          f"{rel.budget_rel.median():.2f} · מקסימום {rel.budget_rel.max():.2f}")

    for name in ("club_budgets_gemini.csv", "salary_anchors.csv"):
        p = PROCESSED_DIR / name
        if not p.exists():
            print(f"\n  {name}: לא נמצא")
            continue
        df = pd.read_csv(p)
        print(f"\n  {name}: {len(df)} שורות · עמודות {list(df.columns)}")
        with pd.option_context("display.max_columns", None, "display.width", 200):
            print(df.head(4).to_string())

    print("\n  🔴 מה שצריך: יחס מיליונים ליחידה יחסית.")
    print("     אם התקציב היחסי החציוני הוא X והתקציב האמיתי החציוני")
    print(f"     הוא Y מיליון, אז --scale = Y/X.")
    print(f"\n     לדוגמה, אם החציון האמיתי ~20M:  --scale "
          f"{20 / max(rel.budget_rel.median(), 1e-9):.4f}")

    out = PROCESSED_DIR / "budget_relative.csv"
    rel.to_csv(out, index=False)
    print(f"\n  נשמר: {out}")


# ------------------------------------------------------------------ סריקה
def sweep(cand, budgets_rel, budgets_m, capped: bool, label: str) -> pd.DataFrame:
    fn = optimise_capped if capped else optimise_v2
    rows = []
    print(f"\n  {label}")
    print(f"  {'תקציב M':>9}{'אמת':>9}{'מנובא':>10}{'סגל':>6}{'נוצל':>9}"
          f"{'usage':>8}{'שוליים':>9}{'ש.מנובא':>10}")
    prev_q = prev_p = None
    for b_rel, b_m in zip(budgets_rel, budgets_m):
        sel, mins = fn(cand, b_rel, MIN_ROSTER)
        if sel is None:
            print(f"  {b_m:>9.0f}   אין פתרון")
            continue
        r = cand[sel]
        q, _, _ = score_rows(r, "ppm_true", "avail_true", REPL)
        # 🔴 הניקוד שה-LP באמת ממקסם — על ppm המנובא.
        # אם q_pred עולה מונוטונית ו-q (על ppm_true) מרעיד, המנוע
        # תקין וכל הרעידה היא שגיאת הניבוי. אם גם q_pred מרעיד,
        # יש באג. זו ההבחנה שקובעת אם העקומה קריאה.
        q_pred, _, _ = score_rows(r, "ppm", "avail", REPL)
        spent = float(r.cost.sum())
        u = wusage(r, mins[sel]) if "usage_prior" in r else np.nan
        marg = (q - prev_q) if prev_q is not None else np.nan
        marg_p = (q_pred - prev_p) if prev_p is not None else np.nan
        rows.append({"budget_m": b_m, "budget_rel": b_rel, "q": q,
                     "q_pred": q_pred, "n": int(sel.sum()), "spent_rel": spent,
                     "used_pct": spent / b_rel, "usage_w": u,
                     "marginal": marg, "marginal_pred": marg_p, "capped": capped})
        print(f"  {b_m:>9.0f}{q:>9.1f}{q_pred:>10.1f}{int(sel.sum()):>6}"
              f"{spent / b_rel:>8.1%}{u:>8.2f}"
              + (f"{marg:>+9.2f}" if prev_q is not None else f"{'—':>9}")
              + (f"{marg_p:>+10.2f}" if prev_p is not None else f"{'—':>10}"))
        prev_q, prev_p = q, q_pred
    return pd.DataFrame(rows)


def find_saturation(d: pd.DataFrame, thresh: float = 0.5):
    """
    נקודת הרוויה: התקציב הראשון שממנו והלאה התשואה השולית נשארת
    מתחת לסף. סף של 0.5 נקודות ניקוד למיליון.
    """
    d = d.dropna(subset=["marginal"]).sort_values("budget_m")
    for i in range(len(d)):
        if (d["marginal"].iloc[i:] < thresh).all():
            return float(d["budget_m"].iloc[i])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--scale", type=float, default=None,
                    help="מיליונים ליחידה יחסית")
    ap.add_argument("--lo", type=float, default=10.0)
    ap.add_argument("--hi", type=float, default=40.0)
    ap.add_argument("--step", type=float, default=1.0)
    ap.add_argument("--usage", default="data/processed/usage_curve_results.csv")
    ap.add_argument("--no-cap", action="store_true",
                    help="להריץ גם בלי אילוץ הכדור, להשוואה")
    args = ap.parse_args()

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    if args.calibrate:
        calibrate(feat, anch, pos, ps, split, posmap)
        return 0

    if args.scale is None:
        print("🔴 חסר --scale. הרץ קודם:  python src/budget_curve.py --calibrate")
        print("   המאגר נבנה עם mean_salary=1.0, כלומר מחירים יחסיים.")
        print("   בלי סקאלה מאומתת '10 מיליון' אינו אומר כלום.")
        return 1

    budgets_m = np.arange(args.lo, args.hi + 1e-9, args.step)
    budgets_rel = budgets_m / args.scale

    hdr("עקומת התקציב — בהינתן תקציב, הסגל הטוב ביותר")
    print(f"  טווח {args.lo:.0f}-{args.hi:.0f}M בקפיצות {args.step:.0f}M "
          f"= {len(budgets_m)} נקודות")
    print(f"  סקאלה: 1 יחידה = {args.scale:.4f}M · מינימום סגל {MIN_ROSTER}")
    print(f"  תחזיות: אלמוג ~35M · קלוד ~16M")

    upath = Path(args.usage)
    if not upath.is_absolute():
        upath = Path(__file__).resolve().parents[1] / upath

    frames = []
    for train_max, test in SEASONS:
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        cand = attach_usage(cand, upath, test)
        print(f"\n  עונה {test} · מאגר {len(cand)}")

        d = sweep(cand, budgets_rel, budgets_m, True, "עם אילוץ הכדור")
        d["season"] = test
        frames.append(d)

        if args.no_cap:
            d2 = sweep(cand, budgets_rel, budgets_m, False, "בלי אילוץ")
            d2["season"] = test
            frames.append(d2)

    d = pd.concat(frames, ignore_index=True)

    hdr("התוצאה")
    cap = d[d.capped]
    for season, g in cap.groupby("season"):
        sat = find_saturation(g)
        q_lo = float(g[g.budget_m == args.lo].q.iloc[0]) if (g.budget_m == args.lo).any() else np.nan
        q_hi = float(g[g.budget_m == args.hi].q.iloc[0]) if (g.budget_m == args.hi).any() else np.nan
        print(f"\n  עונה {season}")
        print(f"    ניקוד ב-{args.lo:.0f}M : {q_lo:.1f}")
        print(f"    ניקוד ב-{args.hi:.0f}M : {q_hi:.1f}")
        print(f"    עלייה כוללת    : {q_hi - q_lo:+.1f} נקודות")
        print(f"    🔴 נקודת רוויה : "
              + (f"{sat:.0f}M" if sat else "לא זוהתה — העקומה עולה לכל האורך"))
        g25 = g[g.budget_m == 25]
        if len(g25) and not np.isnan(q_hi):
            print(f"    25M -> {args.hi:.0f}M : {q_hi - float(g25.q.iloc[0]):+.1f} נקודות")
        print(f"    גודל סגל       : {int(g.n.min())} .. {int(g.n.max())}")
        print(f"    ניצול תקציב    : {g.used_pct.min():.1%} .. {g.used_pct.max():.1%}")

    hdr("🔴 מונוטוניות — האם המנוע מחזיר את הסגל הטוב ביותר")
    print("  תקציב גדול יותר מכיל את כל מה שהיה בקטן. לכן הניקוד")
    print("  **שה-LP ממקסם** חייב לעלות או להישאר. אם הוא יורד — באג.\n")
    for (season, cp), g in d.groupby(["season", "capped"]):
        g = g.sort_values("budget_m")
        v_pred = int((g["marginal_pred"] < -1e-6).sum())
        v_true = int((g["marginal"] < -1e-6).sum())
        worst_p = float(g["marginal_pred"].min())
        worst_t = float(g["marginal"].min())
        tag = "מאולץ" if cp else "חופשי"
        print(f"  {season} {tag:<7} מנובא: {v_pred:>2} ירידות (מקס {worst_p:+.2f})"
              f"   ·   אמת: {v_true:>2} ירידות (מקס {worst_t:+.2f})")
    tot_pred = int((d["marginal_pred"] < -1e-6).sum())
    if tot_pred == 0:
        print("\n  ✅ הניקוד המנובא מונוטוני לחלוטין. **המנוע תקין.**")
        print("     כל הרעידה בעמודת האמת היא שגיאת מודל התפוקה,")
        print("     והיא ניתנת לכימות: זהו רוחב הרעש של הניבוי.")
        sd = float(d.groupby(["season", "capped"])["marginal"].std().mean())
        print(f"     ס\"ת התשואה השולית באמת: {sd:.2f} נקודות למיליון.")
    else:
        print(f"\n  🔴 {tot_pred} ירידות גם בניקוד המנובא — יש באג ב-LP.")
        print("     אל תקרא את העקומה עד שזה נפתר.")

    hdr("מול התחזיות")
    sats = [find_saturation(g) for _, g in cap.groupby("season")]
    sats = [s for s in sats if s]
    if sats:
        avg = float(np.mean(sats))
        print(f"  נקודת רוויה ממוצעת: {avg:.0f}M")
        print(f"    אלמוג ~35M  {'✅' if 30 <= avg <= 40 else '❌'}")
        print(f"    קלוד  ~16M  {'✅' if 13 <= avg <= 19 else '❌'}")
    else:
        print("  לא זוהתה רוויה — העקומה עולה לכל האורך.")
        print("  ❌ שתי התחזיות. יש כלי תכנון, ולא מסקנה על גבול הכסף.")

    print("\n  ⚠️ הזכר: כל נקודה על העקומה יושבת מעל הטווח הנצפה")
    print("     היסטורית (ppm ~0.6 מול מקסימום 0.509), ומודל העלות")
    print("     כויל על מכבי — הקצה העליון הוא הכי פחות אמין.")

    out = PROCESSED_DIR / "budget_curve.csv"
    d.to_csv(out, index=False)
    print(f"\n  נשמר: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())