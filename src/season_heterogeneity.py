"""season_heterogeneity.py — יום 12.

השאלה: כמה מהקשר ניקוד->ניצחונות הוא **הקצאה** ולא **כסף**.

    s_raw     = מקדם הניקוד ברגרסיה  wins_z ~ q_z
    s_partial = אותו מקדם עם בקרת log(תקציב נטו)
    היחס      = כמה נשאר אחרי ניכוי הכסף

יום 9 מדד 0.42 ורשם "58% מהקשר הוא תקציב". יום 12 מצא שהמספר הזה
אינו יציב בין עונות, ולכן נבדק על **שלוש** עונות ולא שתיים.

--------------------------------------------------------------------
למה 2019 דורשת קוד נפרד
--------------------------------------------------------------------
1. `player_club_season.csv` קיים ל-2024 ו-2025 בלבד. חברות בסגל
   ל-2019 נגזרת מהבוקסקורים: הקבוצה שבה השחקן צבר הכי הרבה דקות.
   ⚠️ בקרת תקפות: השחזור של 2024 בשיטה הזו מכסה **98.0%** מהקובץ
   המפורש (287 מתוך 293). זו הסיבה שמותר להשתמש בה.

2. עוגני שכר קיימים מ-2023 ואילך בלבד, ולכן **אין מודל עלות
   ל-2019**. המודלים נאמדים על <=2023.
   ⚠️ זו הצצה קדימה, והיא נסבלת כאן **רק** משום ש-`q_club` מחושב
   מ-`ppm_true`/`avail_true` — התוצאות בפועל. המודלים משפיעים
   על חברות במאגר בלבד, לא על הניקוד.
   ⛔ מסיבה זו אין `q_free` ל-2019. הקובץ הזה מכייל את המקדם,
      ואינו מרחיב את הבנצ'מרק.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
    היחס ב-2019:   אלמוג 0.30-0.45  ·  קלוד 0.20-0.40
    שניהם נשענו על "פיזור תקציב רחב => הכסף מסביר יותר".
    התוצאה: 0.837 — שניהם ❌, והמנגנון נשלל.

הרצה:  python src/season_heterogeneity.py
"""

import contextlib
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import league_backtest as lb                       # noqa: E402
import optimizer_backtest as ob                    # noqa: E402
from player_id import canonical                    # noqa: E402
from roster_optimizer import PROCESSED_DIR         # noqa: E402
RAW_DIR = PROCESSED_DIR.parent / "raw"
from roster_membership_audit import score_rows     # noqa: E402

# (עונת מבחן, train_max). 2019 מאומנת על <=2023 — ראו הערה למעלה.
SEASONS = [(2019, 2023), (2024, 2023), (2025, 2024)]
MIN_ROSTER = 12
SEP = "=" * 74

NAME2CODE = {
    "ברצלונה": "BAR", "צסקא מוסקבה": "CSK", "ריאל מדריד": "MAD",
    "חימקי": "KHI", "מילאנו": "MIL", "פנרבחצה": "ULK", "זניט": "DYR",
    "אנדולו אפס": "IST", 'מכבי ת"א': "TEL", "באיירן": "MUN",
    "באסקוניה": "BAS", "אולימפיאקוס": "OLY", "ולנסיה": "PAM",
    "פנאתינייקוס": "PAN", "ז'לגיריס": "ZAL", "ASVEL": "ASV",
    "אלבה ברלין": "BER", "הכוכב האדום": "RED", "מונקו": "MCO",
    # ⚠️ PAR = פרטיזן (מ-2022) · PRS = פריז (מ-2024). אומת מול
    #    team_season לפי עונת ההצטרפות. ההיפוך היה באג ביום 12.
    "פרטיזן": "PAR", "וירטוס": "VIR", "פריז": "PRS",
    'הפועל ת"א': "HTA", "דובאי": "DUB",
}


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def derive_membership(year: int, ps: pd.DataFrame) -> pd.DataFrame:
    """חברות בסגל מהבוקסקורים — הקבוצה עם הכי הרבה דקות."""
    bs = pd.read_csv(RAW_DIR / f"boxscore_player_{year}.csv",
                     low_memory=False)
    bs["pc"] = bs.Player_ID.map(canonical)
    bs["mn"] = pd.to_numeric(
        bs.Minutes.astype(str).str.split(":").str[0],
        errors="coerce").fillna(0)
    top = (bs.groupby(["pc", "Team"]).mn.sum().reset_index()
           .sort_values("mn").groupby("pc").tail(1))
    d = top.rename(columns={"Team": "club"})[["pc", "club"]]
    p = ps[ps.season == year][
        ["pc", "pir_per_game", "min_per_game", "games"]].copy()
    p["ppm"] = p.pir_per_game / p.min_per_game
    d = d.merge(p, on="pc", how="inner")
    d["season"] = year
    d["player_code"] = d.pc
    return d


def validate_derivation(ps: pd.DataFrame) -> None:
    """בלי הבקרה הזו הגזירה היא ניחוש."""
    ex = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                     dtype={"player_code": str})
    der = derive_membership(2024, ps)
    a = set(zip(ex[ex.season == 2024].player_code.map(canonical),
                ex[ex.season == 2024].club))
    b = set(zip(der.pc, der.club))
    cov = len(a & b) / len(a)
    print(f"  בקרת תקפות (2024): מפורש {len(a)} · נגזר {len(b)} · "
          f"כיסוי {cov:.1%}")
    if cov < 0.95:
        raise SystemExit("⛔ הגזירה אינה משחזרת את הקובץ המפורש.")


def zs(df, col):
    g = df.groupby("season")[col]
    return (df[col] - g.transform("mean")) / g.transform("std")


def fit(s, tag):
    s = s.copy()
    s["lb"] = np.log(s.net_eur)
    for a, b in [("q_club", "qz"), ("wins", "wz"), ("lb", "lbz")]:
        s[b] = zs(s, a)
    r = sm.OLS(s.wz, sm.add_constant(s[["qz"]])).fit()
    p = sm.OLS(s.wz, sm.add_constant(s[["qz", "lbz"]])).fit()
    sr, sp = float(r.params.iloc[1]), float(p.params.iloc[1])
    print(f"  {tag:<14}n={len(s):>2}  s_raw={sr:.3f}  s_par={sp:.3f}  "
          f"יחס={sp / sr:.3f}  β_תקציב={float(p.params.iloc[2]):+.3f} "
          f"(p={float(p.pvalues.iloc[2]):.3f})")
    return dict(tag=tag, n=len(s), s_raw=sr, s_par=sp, ratio=sp / sr)


def main() -> int:
    print(SEP)
    print("season_heterogeneity — כמה מהקשר הוא הקצאה, על שלוש עונות")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    ps = ps.copy()
    ps["pc"] = ps.player_code.astype(str).map(canonical)

    h("0. בקרת הגזירה")
    validate_derivation(ps)

    h("1. ניקוד המועדונים")
    rows = []
    for year, train_max in SEASONS:
        split = derive_membership(year, ps)
        with contextlib.redirect_stdout(io.StringIO()):
            cand, _ = lb.build_pool(year, train_max, feat, anch, pos, ps)
        gmax = float(ps[ps.season == year].games.max())
        n = 0
        for club in sorted(split.club.unique()):
            keep, _ = lb.club_side(cand, split, club, year, gmax, posmap)
            if len(keep) < MIN_ROSTER:
                continue
            rows.append(dict(
                season=year, club=club, n_roster=len(keep),
                q_club=score_rows(keep, "ppm_true", "avail_true",
                                  lb.REPL)[0]))
            n += 1
        print(f"  {year}: {n} מועדונים · מאגר {len(cand)}")
    d = pd.DataFrame(rows)
    d.to_csv(PROCESSED_DIR / "qclub_3seasons.csv", index=False)

    ts = pd.read_csv(PROCESSED_DIR / "team_season.csv")
    d = d.merge(ts[["season", "team", "wins"]].rename(
        columns={"team": "club"}), on=["season", "club"])
    bud = pd.read_csv(PROCESSED_DIR / "club_budgets_gemini.csv")
    bud["club"] = bud.club.map(NAME2CODE)
    m = d.merge(bud[["season", "club", "net_eur"]].dropna(subset=["club"]),
                on=["season", "club"]).dropna(subset=["net_eur"])

    h("2. היחס — כמה נשאר אחרי ניכוי הכסף")
    out = [fit(m, "שלוש עונות")]
    print()
    for y in sorted(m.season.unique()):
        out.append(fit(m[m.season == y], str(y)))

    h("3. פיזור התקציב — ההסבר שנשלל")
    print("  ההשערה: פיזור רחב => הכסף מסביר יותר => יחס נמוך.\n")
    print(f"  {'עונה':<8}{'n':>4}{'ס\"ת log':>10}{'טווח M€':>16}{'יחס':>8}")
    rmap = {o["tag"]: o["ratio"] for o in out}
    for y, g in m.groupby("season"):
        print(f"  {y:<8}{len(g):>4}{np.log(g.net_eur).std(ddof=1):>10.3f}"
              f"{f'{g.net_eur.min():.1f}–{g.net_eur.max():.1f}':>16}"
              f"{rmap[str(y)]:>8.3f}")
    print("\n  ⛔ 2019 הכי מפוזר ו-2025 הכי צר — ושניהם נתנו 0.837.")
    print("     המנגנון נשלל. 2024 היא החריגה, לא 2025.")

    pd.DataFrame(out).to_csv(
        PROCESSED_DIR / "season_heterogeneity.csv", index=False)
    print(f"\n  נשמר: {PROCESSED_DIR / 'season_heterogeneity.csv'}")
    print(SEP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())