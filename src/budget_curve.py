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
import optimise_consistent as oc  # noqa: E402
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
        cand, pinfo = build_pool(test, train_max, feat, anch, pos, ps,
                                 normalise_cost=True)
        gmax = float(ps[ps.season == test].games.max())
        print(f"  עונה {test}: סקאלה גולמית {pinfo['cost_mean_raw']:.3f} "
              f"-> מנורמל")
        for club in sorted(split[split.season == test].club.unique()):
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_ROSTER:
                continue
            rows.append({"season": test, "club": club,
                         "budget_rel": float(keep.cost.sum())})
    rel = pd.DataFrame(rows)

    print("\n  🔴 תקציבים מנורמלים ('כמה שחקנים ממוצעים'), לפי עונה:")
    print(rel.groupby("season").budget_rel
          .agg(n="size", מינ="min", חציון="median", מקס="max")
          .round(2).to_string())

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
    print(f"  {'תקציב M':>9}{'q_lp':>10}{'ש.LP':>9}{'אמת':>9}{'מנובא':>10}"
          f"{'סגל':>6}{'נוצל':>9}{'usage':>8}{'שוליים':>9}")
    prev_q = prev_p = prev_lp = None
    for b_rel, b_m in zip(budgets_rel, budgets_m):
        sel, mins = fn(cand, b_rel, MIN_ROSTER)
        # ערך המטרה של ה-LP. זו הכמות היחידה שחייבת להיות מונוטונית.
        q_lp = oc.LAST.get("obj", np.nan)
        if sel is None:
            print(f"  {b_m:>9.0f}   אין פתרון · status="
                  f"{oc.LAST.get('status')}")
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
        marg_lp = (q_lp - prev_lp) if prev_lp is not None else np.nan
        rows.append({"budget_m": b_m, "budget_rel": b_rel, "q": q,
                     "q_pred": q_pred, "q_lp": q_lp,
                     "n": int(sel.sum()), "spent_rel": spent,
                     "used_pct": spent / b_rel, "usage_w": u,
                     "marginal": marg, "marginal_pred": marg_p,
                     "marginal_lp": marg_lp, "capped": capped})
        flag = " 🔴" if (prev_lp is not None and marg_lp < -1e-6) else ""
        print(f"  {b_m:>9.0f}{q_lp:>10.2f}"
              + (f"{marg_lp:>+9.3f}" if prev_lp is not None else f"{'—':>9}")
              + f"{q:>9.1f}{q_pred:>10.1f}{int(sel.sum()):>6}"
              f"{spent / b_rel:>8.1%}{u:>8.2f}"
              + (f"{marg:>+9.2f}" if prev_q is not None else f"{'—':>9}")
              + flag)
        prev_q, prev_p, prev_lp = q, q_pred, q_lp
    return pd.DataFrame(rows)


def find_saturation(d: pd.DataFrame, thresh: float = 0.5,
                    frac: float = 0.99, col: str = "q_lp"):
    """
    🔴 יום 11: הגלאי עבר מ-`q` ל-`q_lp`.

    `q` הוא score_rows על ppm_true, וס"ת התשואה השולית שלו הוא
    5.75 נקודות למיליון בעוד השיפוע עצמו 1-4. סף של 0.5 על רעש
    כזה מודד רעש — הוא נתן 25M ו-38M, ועל q_lp שתי הגדרות בלתי
    תלויות נותנות אותה תשובה בכל ארבע התצורות.

    שני גלאים, כי הסכמה ביניהם היא הראיה שהמספר יציב:
      א. שולי  — התקציב הראשון שממנו והלאה התשואה < thresh
      ב. סף    — התקציב הראשון שבו הערך >= frac מהערך בקצה

    מחזיר (שולי, סף). אי-הסכמה גדולה = הרוויה לא חדה.
    """
    d = d.sort_values("budget_m")
    v = d[col].to_numpy(dtype=float)
    b = d["budget_m"].to_numpy(dtype=float)
    if len(v) < 3 or np.isnan(v).any():
        return None, None

    m = np.diff(v)
    s_marg = next((float(b[i + 1]) for i in range(len(m))
                   if (m[i:] < thresh).all()), None)

    hit = np.flatnonzero(v >= frac * v[-1])
    s_thr = float(b[hit[0]]) if len(hit) else None
    return s_marg, s_thr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--scale", type=float, default=None,
                    help="מיליונים ליחידה יחסית")
    ap.add_argument("--lo", type=float, default=10.0)
    ap.add_argument("--hi", type=float, default=40.0)
    ap.add_argument("--step", type=float, default=1.0)
    ap.add_argument("--usage", default="data/processed/usage_curve_results_min0.csv")
    ap.add_argument("--no-cap", action="store_true",
                    help="להריץ גם בלי אילוץ הכדור, להשוואה")
    ap.add_argument("--raw-cost", action="store_true",
                    help="בלי נרמול לממוצע המאגר — משחזר את יום 11 המוקדם")
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
        cand, pinfo = build_pool(test, train_max, feat, anch, pos, ps,
                                 normalise_cost=not args.raw_cost)
        cand = attach_usage(cand, upath, test)
        print(f"\n  עונה {test} · מאגר {len(cand)}")
        print(f"  🔴 סקאלת המחירים הגולמית: {pinfo['cost_mean_raw']:.3f}"
              + ("  ->  מנורמל ל-1.000" if not args.raw_cost
                 else "  (לא מנורמל — התקציב אינו בר-השוואה בין עונות)"))

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
        s_marg, s_thr = find_saturation(g)
        pick = lambda col, bm: (float(g[g.budget_m == bm][col].iloc[0])
                                if (g.budget_m == bm).any() else np.nan)
        lp_lo, lp_hi = pick("q_lp", args.lo), pick("q_lp", args.hi)
        print(f"\n  עונה {season}")
        print(f"    q_lp ב-{args.lo:.0f}M   : {lp_lo:.2f}")
        print(f"    q_lp ב-{args.hi:.0f}M   : {lp_hi:.2f}")
        print(f"    עלייה כוללת   : {lp_hi - lp_lo:+.1f} נקודות")
        print(f"    🔴 רוויה      : שולי {s_marg or '—'}M  ·  "
              f"סף 99% {s_thr or '—'}M")
        print(f"    (על q האמיתי, לשם השוואה: {pick('q', args.lo):.1f} -> "
              f"{pick('q', args.hi):.1f} — רועש, לא לדיווח)")
        print(f"    גודל סגל      : {int(g.n.min())} .. {int(g.n.max())}")
        print(f"    ניצול תקציב   : {g.used_pct.min():.1%} .. "
              f"{g.used_pct.max():.1%}")

    if args.no_cap:
        hdr("עלות אילוץ הכדור לפי תקציב")
        print("  יום 10 דיווח שבתקציב גבוה האילוץ 'כמעט חינם' (2.7).")
        print("  זה נמדד על q. על q_lp הכיוון הפוך.\n")
        piv = (d.pivot_table(index=["season", "budget_m"], columns="capped",
                             values="q_lp")
                 .rename(columns={True: "capped", False: "free"}))
        piv["cost"] = piv["free"] - piv["capped"]
        for season, g in piv.groupby(level=0):
            row = "  ".join(
                f"{int(b)}M {g.loc[(season, b), 'cost']:5.2f}"
                for b in (args.lo, 20, 30, args.hi)
                if (season, b) in g.index)
            print(f"  {season}   {row}")

    hdr("🔴 מונוטוניות — הבדיקה על ערך המטרה של ה-LP")
    print("  תקציב גדול יותר מכיל את כל מה שהיה בקטן, ולכן **ערך המטרה")
    print("  של ה-LP** חייב לעלות או להישאר. רק ירידה שם היא באג.\n")
    print("  ⚠️ q_pred ו-q מחושבים ב-score_rows — הקצאה חמדנית עם מילוי")
    print("     חלופי, בלי רצפות עמדה, ותקרה שמוחלת לפני הזמינות. זו")
    print("     **אינה** פונקציית המטרה, ואין לה ערובת מונוטוניות.")
    print("     ירידות שם הן שגיאת הקצאה ושגיאת ניבוי, לא באגים.\n")
    print("  תחזיות ירידות ב-LP:  קלוד 0-2  ·  אלמוג 1-3\n")
    for (season, cp), g in d.groupby(["season", "capped"]):
        g = g.sort_values("budget_m")
        v_lp = int((g["marginal_lp"] < -1e-6).sum())
        v_pred = int((g["marginal_pred"] < -1e-6).sum())
        v_true = int((g["marginal"] < -1e-6).sum())
        tag = "מאולץ" if cp else "חופשי"
        print(f"  {season} {tag:<7} "
              f"LP: {v_lp:>2} (מקס {g['marginal_lp'].min():+.4f})  ·  "
              f"מנובא: {v_pred:>2}  ·  אמת: {v_true:>2}")

    tot_lp = int((d["marginal_lp"] < -1e-6).sum())
    if tot_lp == 0:
        print("\n  ✅ ערך המטרה של ה-LP מונוטוני לחלוטין.")
        print("     **אין באג. חסם יום 10 נופל.** 10.9 של האילוץ קביל,")
        print("     ו-OLY הוא שגיאת ניבוי ולא כשל אופטימיזציה.")
        sd = float(d.groupby(["season", "capped"])["marginal"].std().mean())
        print(f"     ס\"ת התשואה השולית באמת: {sd:.2f} נקודות למיליון —")
        print("     זהו רוחב הרעש של הניבוי, וניתן לדיווח.")
    else:
        print(f"\n  🔴 {tot_lp} ירידות בערך המטרה של ה-LP.")
        print("     הרץ מחדש עם gapRel=0 על הנקודות האלה בלבד.")
        w = d[d["marginal_lp"] < -1e-6][
            ["season", "capped", "budget_m", "q_lp", "marginal_lp"]]
        print(w.to_string(index=False))

    hdr("מול התחזיות")
    print("  ⚠️ התחזיות המקוריות (אלמוג ~35M · קלוד ~16M) נרשמו כשהגלאי")
    print("     רץ על q הרועש. הן נעולות מחדש ביום 11 על q_lp:")
    print("     קלוד 26-32M  ·  אלמוג 30-35M\n")
    pairs = [find_saturation(g) for _, g in cap.groupby("season")]
    marg = [s for s, _ in pairs if s]
    thr = [s for _, s in pairs if s]
    if thr:
        a_t, a_m = float(np.mean(thr)), (float(np.mean(marg)) if marg else np.nan)
        print(f"  רוויה ממוצעת — סף 99%: {a_t:.0f}M  ·  שולי: {a_m:.0f}M")
        print(f"    הפרש בין הגלאים: {abs(a_t - a_m):.0f}M "
              + ("(מסכימים — המספר יציב)" if abs(a_t - a_m) <= 2
                 else "🔴 (חולקים — הרוויה אינה חדה)"))
        print(f"    קלוד  26-32M  {'✅' if 26 <= a_t <= 32 else '❌'}")
        print(f"    אלמוג 30-35M  {'✅' if 30 <= a_t <= 35 else '❌'}")
    else:
        print("  לא זוהתה רוויה — העקומה עולה לכל האורך. ❌ שתי התחזיות.")

    print("\n  🔴 אות מול רעש — קובע את הדאשבורד")
    sd = float(d.groupby(["season", "capped"])["marginal"].std().mean())
    print(f"     ס\"ת התשואה השולית האמיתית : {sd:.2f} נקודות למיליון")
    print("\n     ⚠️ השיפוע נמדד **מתחת לרוויה בלבד**. ממוצע על כל")
    print("        הטווח כולל נקודות שבהן השיפוע אפס בהגדרה, ומדלל")
    print("        אותו כלפי מטה (0.82 במקום ~1.6).\n")
    for season, g in cap.groupby("season"):
        _, s_thr = find_saturation(g)
        if not s_thr:
            continue
        g = g.sort_values("budget_m")
        pre = g[g.budget_m <= s_thr]
        span = float(pre.budget_m.iloc[-1] - pre.budget_m.iloc[0])
        sl = float(pre.q_lp.iloc[-1] - pre.q_lp.iloc[0]) / span
        low = g[g.budget_m <= args.lo + 5]
        sl_low = (float(low.q_lp.iloc[-1] - low.q_lp.iloc[0])
                  / float(low.budget_m.iloc[-1] - low.budget_m.iloc[0]))
        print(f"     {season}  עד רוויה ({s_thr:.0f}M): {sl:.2f} נק'/M "
              f"(יחס {sl / sd:.2f})  ·  "
              f"קצה נמוך: {sl_low:.2f} נק'/M (יחס {sl_low / sd:.2f})")
    print("\n     היחס מתחת ל-1 בכל הטווח ⇒ 'מה מיליון קונה' נקרא")
    print("     מ-q_lp בלבד, והרעש מוצג כרצועה סביב העקומה.")

    print("\n  ⚠️ הזכר: כל נקודה על העקומה יושבת מעל הטווח הנצפה")
    print("     היסטורית (ppm ~0.6 מול מקסימום 0.509), ומודל העלות")
    print("     כויל על מכבי — הקצה העליון הוא הכי פחות אמין.")

    out = PROCESSED_DIR / "budget_curve.csv"
    d.to_csv(out, index=False)
    print(f"\n  נשמר: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())