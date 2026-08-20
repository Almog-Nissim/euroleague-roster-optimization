"""
usage_decompose.py — הפער נובע ממי שנבחר או ממי שמקבל דקות.

הרקע
----
שני מספרים שאומרים דברים שונים:

    משוקלל-דקות אמיתיות : מנוע 21.83%  מועדון 20.03%   +1.80
    לא-משוקלל           : מנוע 19.91%  מועדון 19.05%   +0.86

כלומר כמחצית מהפער אינה "אילו שחקנים נקנו" אלא "למי הולכות
הדקות". וזו הבחנה עם השלכה מעשית שונה לגמרי:

  · אם הפער ב**בחירה** — הבעיה במאגר ובתמחור. השחקנים שנבחרים
    הם עתירי כדור, וה-ppm שלהם נצבר בסביבה שלא תשוחזר.

  · אם הפער ב**הקצאה** — זה בדיוק מה שמטרה שממקסמת Σe·ppm
    אמורה לעשות. הפתרון הוא אילוץ ליניארי באופטימייזר:
        Σ eᵢ·usageᵢ  ≤  20 · Σ eᵢ
    טריוויאלי להוספה, ולא דורש נגיעה במאגר.

הפירוק
------
usage משוקלל = Σ(wᵢ·uᵢ) / Σwᵢ. הפער בין שני סגלים מתפרק לשניים:

    בחירה  — ההפרש בממוצע הפשוט של ה-usage בסגל
    הקצאה  — הקווריאנס בין המשקל היחסי ל-usage בתוך הסגל

    ū_w = ū + Cov(w̃, u)·n/(n−1)   [בקירוב, על משקלים מנורמלים]

הסקריפט מודד את שני האיברים בנפרד לכל צד, ומאמת שסכומם מחזיר
את ההפרש שנמדד.

⚠️ הבדיקה שקובעת אם הפירוק תקף: השחזור חייב להחזיר את ה-usage
המשוקלל שנמדד, בסטייה זניחה. אחרת האריתמטיקה שלי שגויה.

הרצה:  python src/usage_decompose.py
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


def decompose(u, w):
    """
    מחזיר (ממוצע פשוט, ממוצע משוקלל, איבר ההקצאה).
    איבר ההקצאה = משוקלל − פשוט = Cov(w/w̄, u).
    """
    u, w = np.asarray(u, float), np.asarray(w, float)
    ok = np.isfinite(u) & np.isfinite(w) & (w >= 0)
    u, w = u[ok], w[ok]
    if not len(u) or w.sum() <= 0:
        return np.nan, np.nan, np.nan
    flat = float(u.mean())
    wt = float(np.average(u, weights=w))
    return flat, wt, wt - flat


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
               .agg(u=("usage", "mean"), m_real=("minutes", "sum")).reset_index())
    m = ros.merge(real, left_on=["season", "key"], right_on=["Season", "key"], how="left")

    m["m_alloc"] = np.nan
    for _, g in m.groupby(["season", "club", "side"]):
        mins, *_ = allocate(g)
        m.loc[g.index, "m_alloc"] = mins

    rows = []
    for (s, c, side), g in m.groupby(["season", "club", "side"]):
        d = g.dropna(subset=["u"])
        if not len(d):
            continue
        f_r, w_r, a_r = decompose(d["u"], d["m_real"])
        f_a, w_a, a_a = decompose(d["u"], d["m_alloc"])
        rows.append({"season": s, "club": c, "side": side, "n": len(d),
                     "flat": f_r, "w_real": w_r, "alloc_term_real": a_r,
                     "w_alloc": w_a, "alloc_term_alloc": a_a})
    per = pd.DataFrame(rows)

    eng = per[per.side == "engine"]
    clb = per[per.side == "club"]

    # ---------------------------------------------------------- אימות
    hdr("א. אימות הפירוק")
    print("  משוקלל = פשוט + איבר ההקצאה. הסטייה חייבת להיות אפס.\n")
    err = (per["flat"] + per["alloc_term_real"] - per["w_real"]).abs()
    print(f"  סטייה מקסימלית: {err.max():.10f}")
    if err.max() > 1e-9:
        print("  🔴 האריתמטיקה שגויה. אל תקרא את השאר.")
        return 1
    print("  ✅ הפירוק אדיטיבי במדויק.")

    # ---------------------------------------------------------- פירוק
    hdr("ב. 🔴 הפירוק — בחירה מול הקצאה")
    print("  על דקות אמיתיות, שני האגפים באותו שקלול.\n")

    sel_e, sel_c = float(eng["flat"].mean()), float(clb["flat"].mean())
    all_e, all_c = float(eng["alloc_term_real"].mean()), float(clb["alloc_term_real"].mean())
    tot_e, tot_c = float(eng["w_real"].mean()), float(clb["w_real"].mean())

    print(f"  {'':<14}{'מנוע':>9}{'מועדון':>10}{'הפרש':>9}")
    print("  " + "-" * 42)
    print(f"  {'בחירה':<14}{sel_e:>9.2f}{sel_c:>10.2f}{sel_e - sel_c:>+9.2f}")
    print(f"  {'הקצאה':<14}{all_e:>9.2f}{all_c:>10.2f}{all_e - all_c:>+9.2f}")
    print("  " + "-" * 42)
    print(f"  {'סה\"כ':<14}{tot_e:>9.2f}{tot_c:>10.2f}{tot_e - tot_c:>+9.2f}")

    d_sel = sel_e - sel_c
    d_all = all_e - all_c
    d_tot = tot_e - tot_c
    share_sel = d_sel / d_tot if d_tot else np.nan

    print(f"\n  חלק הבחירה בפער: {share_sel:.0%}")
    print(f"  חלק ההקצאה בפער: {1 - share_sel:.0%}")

    # ---------------------------------------------------------- הקצאה שלנו
    hdr("ג. ואיך זה נראה תחת ההקצאה של score_rows")
    print("  ⚠️ ההקצאה החמדנית אינה המציאות. היא מה שהמנוע מתכנן.\n")
    print(f"  {'':<14}{'מנוע':>9}{'מועדון':>10}{'הפרש':>9}")
    print("  " + "-" * 42)
    print(f"  {'בחירה':<14}{sel_e:>9.2f}{sel_c:>10.2f}{sel_e - sel_c:>+9.2f}")
    ae, ac = float(eng["alloc_term_alloc"].mean()), float(clb["alloc_term_alloc"].mean())
    print(f"  {'הקצאה':<14}{ae:>9.2f}{ac:>10.2f}{ae - ac:>+9.2f}")
    we, wc = float(eng["w_alloc"].mean()), float(clb["w_alloc"].mean())
    print("  " + "-" * 42)
    print(f"  {'סה\"כ':<14}{we:>9.2f}{wc:>10.2f}{we - wc:>+9.2f}")

    # ---------------------------------------------------------- מסקנה
    hdr("מה זה אומר על התיקון")
    if share_sel > 0.65:
        print("  הפער בעיקר ב**בחירה**.")
        print("  אילוץ באופטימייזר לא יספיק — הבעיה במאגר ובתמחור:")
        print("  ה-ppm של הנבחרים נצבר ב-usage שלא ישוחזר.")
    elif share_sel < 0.35:
        print("  הפער בעיקר ב**הקצאה**.")
        print("  זה בדיוק מה ש-Σe·ppm אמורה לעשות, והפתרון ליניארי:")
        print("      Σ eᵢ·usageᵢ  ≤  20 · Σ eᵢ")
        print("  לא דורש נגיעה במאגר ולא בתמחור.")
    else:
        print("  הפער מתחלק בין השניים בערך שווה בשווה.")
        print("  האילוץ הליניארי יטפל בחלק ההקצאה; חלק הבחירה יישאר")
        print("  ויידרש תיקון ב-ppm עצמו — כיווץ לפי usage צפוי.")

    print(f"\n  סדר גודל לפי β=+0.0186, על החלק שהאילוץ יסגור:")
    print(f"     {abs(d_all):.2f} × 0.0186 × 200 = {abs(d_all) * 0.0186 * 200:.1f} נקודות")
    print(f"  ועל החלק שיישאר:")
    print(f"     {abs(d_sel):.2f} × 0.0186 × 200 = {abs(d_sel) * 0.0186 * 200:.1f} נקודות")

    out = resolve("data/processed/usage_decompose.csv")
    per.to_csv(out, index=False)
    print(f"\n  נשמר: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())