"""
price_structure.py — למה הרוויה ב-21M ב-2024 וב-29M ב-2025.

הרקע
----
מבחן הדילול שלל את הסבר עומק המאגר: 2025 מדולל מ-335 ל-295 ול-260
לא הזיז את הרוויה כלל (29 -> 30 -> 30), ו-2024 מדולל מ-295 ל-260
נשאר על 21. **שני קווי ראיה, אותה מסקנה.** נשארו המחירים.

הרעיון
------
המחירים מנורמלים ל-`mean_salary=1.0` **בכל עונה בנפרד**. לכן
"29 מיליון" פירושו 29 פעמים השכר הממוצע של אותה עונה, ואינפלציה
כבר מנוטרלת.

רוויה מגיעה כשאפשר לקנות את הסגל הטוב ביותר במלואו. אז השאלה
מצטמצמת לחישוב אחד: **כמה עולה הסגל הטוב ביותר, ביחידות של שכר
ממוצע?** אם זה 21 ב-2024 ו-29 ב-2025, הפער מוסבר לחלוטין במבנה
המחירים — וזו תופעה, לא באג.

ארבעה חלקים
-----------
    א. עלות הצמרת    — כמה עולים 12 הטובים, ביחידות ממוצע
    ב. צורת ההתפלגות — p90/חציון, נתח העשירון העליון, ג'יני
    ג. מקור הפער     — פיזור pir_lag_shrunk, המניע היחיד במודל
    ד. מודל מול שוק  — האם המחירים בכלל נכונים

⚠️ מגבלות שנרשמות מראש
-----------------------
1. חלק ד' מוציא את `usage == "calibrate"` — 39 עוגני מכבי שעליהם
   מודל העלות נאמד. השוואה שם היא טאוטולוגיה.
2. **אחרי ההוצאה נשארים 13 עוגנים ל-2024 מול 57 ל-2025.** צד 2024
   חלש מדי להשוואת הטיות בין עונות. מדווח, לא מוסתר.
3. העוגנים מוטים לצמרת — סוכנים מדליפים על כוכבים. ההטיה שתימדד
   היא על החלק העליון של השוק ולא על כולו.

תחזיות שננעלו לפני ההרצה
------------------------
    א. עלות 12 הטובים   קלוד: 2024~20 · 2025~28   אלמוג: 2025~30
    ב. p90/חציון        קלוד: עולה     אלמוג: עולה חזק
    ג. מקור             שניהם: פיזור pir_lag
    ד. מודל מול שוק     שניהם: המודל מתמחר בחסר את הצמרת
    ה. כמה מ-8M         קלוד: <8 (שני מנגנונים)  אלמוג: 4-5M

הרצה:  python src/price_structure.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import optimizer_backtest as ob  # noqa: E402
import roster_optimizer as ro  # noqa: E402
from paths import PROCESSED_DIR  # noqa: E402
from league_backtest import build_pool, SEASONS  # noqa: E402

SEP = "=" * 78
FX = 1.168          # USD -> EUR, נמדד יום 8, ס"ת 0.0016
# רוויה ביחידות **מנורמלות**: 21/0.966 ו-29/1.239.
# ההמרה מדויקת — הכפלת מחירים ותקציב באותו קבוע = LP זהה.
SAT = {2024: 21.7, 2025: 23.4}


def hdr(t: str) -> None:
    print("\n" + SEP + f"\n{t}\n" + SEP)


def gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, float))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def main() -> int:
    feat, anch, pos, ps = ob.load_all()
    pools, raw = {}, {}
    for train_max, test in SEASONS:
        cand, info = build_pool(test, train_max, feat, anch, pos, ps,
                                normalise_cost=True)
        pools[test] = cand.reset_index(drop=True)
        raw[test] = info["cost_mean_raw"]
        print(f"  עונה {test}: מאגר {len(cand)} · סקאלה גולמית "
              f"{info['cost_mean_raw']:.3f} -> מנורמל "
              f"{cand.cost.mean():.3f}")
    print(f"\n  🔴 יחס הסקאלות בין העונות: "
          f"{raw[2025] / raw[2024]:.3f}  — זה מה שהיה מעורבב")
    print("     בציר התקציב עד יום 11.")

    # ---------------------------------------------------------- א
    hdr("א. עלות הצמרת — כמה עולה הסגל הטוב ביותר, ביחידות ממוצע")
    print("  תחזיות: קלוד 2024~20 / 2025~28  ·  אלמוג 2025~30")
    print("  הרוויה מנורמלת: 2024 21.7 · 2025 23.4 (גולמי 21 ו-29)\n")
    print(f"  {'עונה':<7}{'top12 ppm':>11}{'top14 ppm':>11}"
          f"{'top12 יעיל':>12}{'רוויה':>8}{'יחס':>8}")
    A = []
    for s, c in pools.items():
        t12 = float(c.nlargest(12, "ppm").cost.sum())
        t14 = float(c.nlargest(14, "ppm").cost.sum())
        eff = float(c.assign(r=c.ppm / c.cost).nlargest(12, "r").cost.sum())
        A.append({"season": s, "top12": t12, "top14": t14,
                  "top12_eff": eff, "sat": SAT[s]})
        print(f"  {s:<7}{t12:>11.1f}{t14:>11.1f}{eff:>12.1f}"
              f"{SAT[s]:>8.0f}{t12 / SAT[s]:>8.2f}")
    A = pd.DataFrame(A)
    g_top = float(A.top12.iloc[1] - A.top12.iloc[0])
    g_sat = float(A.sat.iloc[1] - A.sat.iloc[0])
    print(f"\n  🔴 פער עלות הצמרת : {g_top:+.1f} יחידות")
    print(f"     פער הרוויה     : {g_sat:+.1f}M")
    print(f"     מוסבר          : {g_top / g_sat:.0%}")
    if abs(g_top - g_sat) <= 2:
        print("\n  ⇒ **מבנה המחירים מסביר את הפער כמעט במלואו.**")
        print("     הרוויה אינה תכונה של המנוע אלא של השוק: הצמרת")
        print("     יקרה יותר יחסית לממוצע ב-2025, ולכן צריך יותר")
        print("     כפולות של שכר ממוצע כדי לקנות אותה.")
    elif g_top < 0.3 * g_sat:
        print("\n  ⇒ **עלות הצמרת אינה ההסבר.** לא עומק ולא מחירי")
        print("     צמרת. הפער נשאר בלתי מוסבר — לדווח ככזה.")
    else:
        print("\n  ⇒ **הסבר חלקי.** מבנה המחירים מסביר חלק מהפער.")

    # ---------------------------------------------------------- ב
    hdr("ב. צורת התפלגות המחירים")
    print(f"  {'עונה':<7}{'חציון':>9}{'p90':>9}{'p99':>9}"
          f"{'p90/חצי':>10}{'נתח עש׳ עליון':>14}{'ג׳יני':>8}")
    for s, c in pools.items():
        v = c.cost.values
        q50, q90, q99 = np.percentile(v, [50, 90, 99])
        top = v[v >= q90].sum() / v.sum()
        print(f"  {s:<7}{q50:>9.3f}{q90:>9.3f}{q99:>9.3f}"
              f"{q90 / q50:>10.2f}{top:>13.1%}{gini(v):>8.3f}")

    # ---------------------------------------------------------- ג
    hdr("ג. מקור הפער — pir_lag_shrunk הוא המניע היחיד במודל")
    print(f"  מודל העלות: log(שכר/ממוצע) ~ {' + '.join(ro.COST_FEATURES)}\n")
    print(f"  {'עונה':<7}{'ממוצע':>9}{'ס״ת':>9}{'p90':>9}{'p90-חציון':>11}"
          f"{'el_seas ממוצע':>15}")
    for s, c in pools.items():
        x = c["pir_lag_shrunk"].astype(float)
        e = c["el_seasons"].astype(float).mean() if "el_seasons" in c else np.nan
        print(f"  {s:<7}{x.mean():>9.3f}{x.std():>9.3f}"
              f"{x.quantile(.9):>9.3f}{x.quantile(.9) - x.median():>11.3f}"
              f"{e:>15.2f}")
    print("\n  ס\"ת גדול יותר ⇒ המודל פורש את המחירים רחב יותר,")
    print("  והצמרת מתייקרת יחסית לממוצע. זו התחזית של שנינו.")

    # ---------------------------------------------------------- ד
    hdr("ד. מודל מול שוק — האם המחירים בכלל נכונים")
    a = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                    dtype={"player_code": str})
    a = a[(a.usage != "calibrate") & a.player_code.notna()
          & a.salary_mid.notna()].copy()
    a["eur"] = np.where(a.currency.eq("USD"), a.salary_mid / FX, a.salary_mid)
    print("  ⚠️ calibrate (מכבי) הוצא — המודל נאמד עליו.\n")

    for s, c in pools.items():
        sub = a[a.season == s].merge(
            c[["pc", "cost", "ppm"]].rename(columns={"pc": "player_code"}),
            on="player_code", how="inner")
        if len(sub) < 5:
            print(f"  {s}: {len(sub)} עוגנים — מעט מדי לדיווח.")
            continue
        # שניהם מנורמלים לחציון של עצמם, כדי להשוות **צורה** ולא רמה
        m = np.log(sub.cost / sub.cost.median())
        k = np.log(sub.eur / sub.eur.median())
        b = float(np.polyfit(m, k, 1)[0])
        r = float(np.corrcoef(m, k)[0, 1])
        print(f"  {s}  n={len(sub):<3} שיפוע שוק~מודל {b:5.2f} · r={r:5.2f}")
        sub["tier"] = pd.qcut(sub.cost, min(3, sub.cost.nunique()),
                              labels=["תחתון", "אמצע", "עליון"][
                                  :min(3, sub.cost.nunique())])
        sub["resid"] = k.values - b * m.values
        print(sub.groupby("tier", observed=True)["resid"]
              .agg(n="size", חציון="median").round(3).to_string())
        print()
    print("  שיפוע < 1 ⇒ המודל **פורש רחב מדי** (מגזים בהפרשים)")
    print("  שיפוע > 1 ⇒ המודל **דוחס** — מתמחר בחסר את הצמרת")
    print("  שארית חיובית בשכבה העליונה ⇒ תמחור בחסר שם")

    p = PROCESSED_DIR / "price_structure.csv"
    A.to_csv(p, index=False)
    print(f"\n  נשמר: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())