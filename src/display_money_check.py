"""display_money_check.py — שלב 5 של docs/refit-run-spec.md.

--------------------------------------------------------------------
למה הקובץ הזה קיים
--------------------------------------------------------------------
CONTEXT.md מצטט "MAE €1.35M, Spearman 0.571 על 11 שחקנים" — **בלי
קובץ מייצר ובלי קובץ תוצאות**. לפי הכלל של הפרויקט זו היפותזה,
לא ממצא, ואי אפשר להשוות אליה תוצאה חדשה. כאן שני הצדדים נמדדים
באותו קוד.

מה נבדק: הסכום ש**מוצג למשתמש** ליד שם שחקן, מול שכר אמיתי.
הנוסחה מועתקת מ-RosterBuilder.jsx:

    מוצג_i = ( a · (cost_i · 12) + b ) / 12 = a · cost_i + b/12

כלומר `fit_eur`, שנאמד ברמת **מועדון**, מוחל על שחקן בודד. זה
מחוץ לתחום התוקף של הכיול, וזו בדיוק הטענה שנבדקת.

⚠️ הטיית המדגם, מועתקת מהספק: השחקנים המוצגים הם מי שה-LP בחר,
   ולכן מוטים לכיוון מי שהמודל מתמחר **בחסר**. תקף לשיפוט
   התצוגה; **לא** תקף לאמידת שיפוע השוק.

נקודת התקציב מוצהרת: תקציב המועדון החציוני של אותה עונה, כלומר
אותו סל אמיתי בשני המפרטים — נקודת רשת נומינלית זהה הייתה משווה
סלים שונים, כי הציר עצמו זז.

הרצה:
    python src/display_money_check.py data/dashboard/roster_sweep.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paths import PROCESSED_DIR  # noqa: E402
import salary_market as smk  # noqa: E402

SEASON = 2025
ROSTER_SLOTS = 12          # המכפיל בממשק
SEP = "=" * 74


def real_salaries() -> pd.DataFrame:
    """כל שכר 2025 אמיתי, משני המקורות. עוגן גובר על חיצוני."""
    a = pd.read_csv(PROCESSED_DIR / "salary_anchors.csv",
                    dtype={"player_code": str})
    a["salary"] = pd.to_numeric(a.salary_mid, errors="coerce")
    a = a[(a.season == SEASON) & a.player_code.notna() & a.salary.notna()]
    rows = [pd.DataFrame({"code": a.player_code.astype(str),
                          "real": a.salary / 1e6, "src": "anchor"})]

    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    s = pd.read_csv(PROCESSED_DIR / "salary_external_2025.csv")
    s = s[s.yr == SEASON].copy()
    s["key"] = s.player.astype(str).str.split("/").str[0].map(smk.norm)
    p = ps.dropna(subset=["player_name"]).copy()
    p["key"] = (p.player_name.str.split(",").str[1].fillna("")
                + p.player_name.str.split(",").str[0]).map(smk.norm)
    kmap = p.drop_duplicates("key").set_index("key").player_code.astype(str)
    s["code"] = s.key.map(kmap)
    s.loc[s.code.isna(), "code"] = s.loc[s.code.isna(), "key"].map(smk.ALIAS)
    s = s[s.code.notna()]
    rows.append(pd.DataFrame({"code": s.code.astype(str),
                              "real": pd.to_numeric(s.salary,
                                                    errors="coerce") / 1e6,
                              "src": "external"}))
    d = pd.concat(rows, ignore_index=True)
    return (d[d.real.notna()].sort_values("src")
            .drop_duplicates("code", keep="first").set_index("code"))


def check(path: Path) -> dict:
    D = json.load(open(path, encoding="utf-8"))
    eur = D["meta"]["eur"]
    a, b = float(eur["a"]), float(eur["b"])
    budgets = sorted(c["budget"] for c in D["clubs"])
    n = len(budgets)
    med = (budgets[n // 2 - 1] + budgets[n // 2]) / 2 if n % 2 == 0 \
        else budgets[n // 2]
    pt = min(D["free"], key=lambda p: abs(p["budget"] - med))

    real = real_salaries()

    def rows_for(rosters):
        seen, rows = set(), []
        for rr in rosters:
            for r in rr:
                if r["code"] in seen or r["code"] not in real.index:
                    continue
                seen.add(r["code"])
                rows.append(dict(code=r["code"], name=r["name"],
                                 cost=r["cost"],
                                 shown=a * r["cost"] + b / ROSTER_SLOTS,
                                 real=float(real.loc[r["code"], "real"]),
                                 src=real.loc[r["code"], "src"]))
        return pd.DataFrame(rows)

    # ⚠️ המדגם הראשי הוא **כל** שחקן שהסליידר מציג אי-פעם, ולא
    #    סגל אחד: סגל בודד נותן 4-5 הצלבות, ו-Spearman על n=4 אינו
    #    מספר. נקודת החציון נשמרת כתת-מדגם לתיעוד.
    d = rows_for([p["roster"] for p in D["free"]])
    d_med = rows_for([pt["roster"]])
    for t in (d, d_med):
        t["err"] = t.shown - t.real
    rho, p_rho = st.spearmanr(d.shown, d.real)
    rho_m, _ = st.spearmanr(d_med.shown, d_med.real) if len(d_med) > 2 \
        else (np.nan, np.nan)
    return dict(path=path.name, saturation=D["meta"]["saturation"],
                regime=D["meta"].get("saturation_regime", "—"),
                eur_a=a, eur_b=b, eur_mae=eur["mae"],
                budget=pt["budget"], median_club_budget=round(med, 2),
                n_roster=pt["n"], n_matched=len(d),
                mae=round(float(d.err.abs().mean()), 3),
                bias=round(float(d.err.median()), 3),
                rho=round(float(rho), 3), p=round(float(p_rho), 4),
                n_med=len(d_med), mae_med=round(float(d_med.err.abs().mean()), 3),
                rho_med=round(float(rho_m), 3),
                n_negative=int((d.shown < 0).sum()),
                table=d)


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]] or \
        [PROCESSED_DIR.parent / "dashboard" / "roster_sweep.json"]
    print(SEP)
    print("display_money_check — הכסף שמוצג ליד שחקן מול שכר אמיתי")
    print(SEP)
    out = []
    for p in paths:
        r = check(p)
        print(f"\n--- {r['path']}")
        print(f"  תקציב מועדון חציוני {r['median_club_budget']} -> "
              f"נקודת רשת {r['budget']} · סגל {r['n_roster']}")
        print(f"  מדגם: {r['n_matched']} שחקנים מוצגים עם שכר ידוע "
              f"(בנקודת החציון בלבד: {r['n_med']})")
        print(f"  fit_eur: a={r['eur_a']:.4f} b={r['eur_b']:+.4f} "
              f"(MAE מועדון {r['eur_mae']}M€)")
        t = r.pop("table")
        print(f"  {'שחקן':<26}{'עלות':>7}{'מוצג':>8}{'אמת':>8}{'שגיאה':>9}")
        for x in t.sort_values("real", ascending=False).head(12).itertuples():
            print(f"  {str(x.name)[:25]:<26}{x.cost:>7.2f}{x.shown:>8.2f}"
                  f"{x.real:>8.2f}{x.err:>+9.2f}")
        print(f"  MAE {r['mae']}M€ · הטיה חציונית {r['bias']:+.2f}M€ · "
              f"Spearman {r['rho']:+.3f} (p={r['p']})")
        print(f"  בנקודת החציון בלבד: n={r['n_med']} · MAE {r['mae_med']} · "
              f"ρ={r['rho_med']}")
        if r["n_negative"]:
            print(f"  🔴 {r['n_negative']} שחקנים מוצגים בסכום **שלילי** — "
                  f"התצוגה שבורה, לא רק לא מדויקת.")
        out.append(r)

    res = pd.DataFrame(out)
    dst = PROCESSED_DIR / "display_money_check.csv"
    res.to_csv(dst, index=False)
    print(f"\n  נשמר: {dst.name}")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
