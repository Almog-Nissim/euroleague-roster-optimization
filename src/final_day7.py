"""
final_day7.py  (Day 7)
----------------------
ההרצה המסכמת: כל התיקונים של היום ביחד, ושתי הגרסאות זו מול זו.

מה נכנס:
  1. סגלים מפורשים    — club_rosters, נמסרו על ידי אלמוג
  2. עמדות מלאות      — 9 שחקנים שנוספו היום (6 הפועל + 3 מכבי)
  3. רמת מחליף מדודה  — ונסרקת, כי המדידה אינה יציבה
  4. מטרה מיושרת      — optimise_v2, שבה LP == ניקוד

הרצה:
    python src/final_day7.py
"""

import io
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster_optimizer as ro
import optimizer_backtest as ob
import club_rosters as cr
from roster_membership_audit import score_rows
from optimise_consistent import optimise_v2
from replacement_level import load as load_repl, measure

SCENARIOS = [("TEL", 2023, 2024), ("HTA", 2024, 2025)]
REPL_GRID = [0.03, 0.09, 0.127, 0.18]

# חוק יורוליג (אלמוג, יום 7): מינימום 12 שחקנים רשומים.
# אימות: 158 קבוצות-עונה בדאטה, מינימום 12, אפס חריגים.
MIN_LEGAL_ROSTER = 12
SEP = "=" * 78


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def prep(club, train_max, test, feat, anch, pos, ps):
    ob.TRAIN_MAX, ob.TEST, ob.TARGET_CLUB = train_max, test, club
    with contextlib.redirect_stdout(io.StringIO()):
        cm, smear, agg, am, pm, PF, lagged = ob.fit_models(ps, feat, anch)
        cand = ob.build(lagged, feat, pos, cm, smear, agg, am, pm, PF,
                        ob.scale_for(anch, club, test))
    cand["ppm_true"] = cand.pir_per_game / cand.min_per_game
    cand["avail_true"] = cand.frac
    return cand


_SPLIT = None


def _split_table():
    """player_club_season — סטטיסטיקה לפי (שחקן, מועדון, עונה).

    נוצר על ידי split_multiclub מבוקסקור ברמת משחק. אם הקובץ
    חסר, נופלים חזרה למצרפי ומדווחים על כך — לא בשקט.
    """
    global _SPLIT
    if _SPLIT is None:
        p = Path(__file__).resolve().parents[1] / "data" / "processed" \
            / "player_club_season.csv"
        _SPLIT = (pd.read_csv(p, dtype={"player_code": str})
                  if p.exists() else pd.DataFrame())
    return _SPLIT


def bench(club, season, ps, posmap, repl):
    """הבנצ'מרק של המועדון, מנוקד על מה שהמועדון **באמת קיבל**.

    לשחקן שעבר מועדון באמצע העונה נלקחת השורה של המועדון הזה
    בלבד — גם ב-ppm וגם בזמינות. שחקן שהיה במועדון 8 מתוך 34
    משחקים תרם 8/34 מהעונה, ואת השאר שיחק מישהו אחר.
    """
    r = cr.roster_df(club, season)
    gmax = float(ps[ps.season == season].games.max())
    sr = ps[(ps.season == season) & (ps.min_per_game > 0)].copy()
    sr["pc"] = sr.player_code.astype(str)
    sr["ppm_true"] = sr.pir_per_game / sr.min_per_game
    sr["avail_true"] = sr.games / gmax
    sr["position"] = sr.pc.map(posmap)
    d = sr[sr.pc.isin(set(r.player_code)) & sr.position.notna()].copy()

    sp = _split_table()
    n_split, n_zero = 0, 0
    if len(sp):
        season_rows = sp[sp.season == season]
        seen = set(season_rows.player_code.astype(str))
        mine = season_rows[season_rows.club == club]
        s = mine.set_index(mine.player_code.astype(str))
        drop = []
        for i in d.index:
            pc = d.at[i, "pc"]
            if pc in s.index:
                row = s.loc[pc]
                if not np.isclose(float(row.games), d.at[i, "avail_true"]
                                  * gmax):
                    n_split += 1
                d.at[i, "ppm_true"] = float(row.ppm)
                d.at[i, "avail_true"] = float(row.games) / gmax
            elif pc in seen:
                # 🔴 השחקן שיחק בעונה הזו — אבל **לא במועדון הזה**.
                #    קבוקלו הוא המקרה: `player_season` מסמן אותו
                #    `HTA;DUB`, ובפועל כל 11 משחקיו היו בדובאי.
                #    הפועל שילמה 1.2M וקיבלה אפס דקות יורוליג.
                #    הגרסה הקודמת **נפלה לאחור למצרפי** וזיכתה את
                #    הפועל בדקות של דובאי. תרומה למועדון = אפס.
                #    השכר נשאר בתקציב — המועדון שילם.
                drop.append(i)
                n_zero += 1
        if drop:
            d = d.drop(index=drop)
    q, used, _ = score_rows(d, "ppm_true", "avail_true", repl)
    return q, len(d), len(r), used, (n_split, n_zero)


def main():
    print(SEP)
    print("יום 7 — ההרצה המסכמת")
    print("סגלים מפורשים · עמדות מלאות · מחליף נסרק · מטרה מיושרת")
    print(SEP)

    d = load_repl()
    lo, _ = measure(d, max_games=5)
    hi, _ = measure(d, max_games=15)
    print(f"\n  טווח רמת המחליף הנמדד: {lo:.3f} .. {hi:.3f}   "
          f"(שני המקרים של אלמוג: 0.122)")

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    summary = []

    for club, train_max, test in SCENARIOS:
        cand = prep(club, train_max, test, feat, anch, pos, ps)
        r = cr.roster_df(club, test)
        B = float(r.salary.dropna().sum()) + cr.budget_only_total(club, test)

        _, nb, nr, _, (nsp, nz) = bench(club, test, ps, posmap, 0.127)
        h(f"{club} {test}   תקציב {B:,.0f}   סגל מועדון {nr} "
          f"(מהם מנוקדים {nb})")
        print(f"  פיצול רב-מועדוני: {nsp} תוקנו · "
              f"{nz} הוצאו (שיחקו בעונה אך לא במועדון הזה)")

        # 🔴 יום 7, אלמוג: **חוק יורוליג** — כל מועדון חייב לרשום
        # לפחות 12 שחקנים. אומת מול הדאטה: 158 קבוצות-עונה,
        # מינימום 12, אפס חריגים, ההתפלגות מתחילה בדיוק שם.
        # כל סגל קטן מ-12 אינו חוקי, וכל סווייפ העומק שרץ עד
        # עכשיו — כולל זה של יום 6 — בדק אזור אסור.
        sols = {}
        for mr in range(MIN_LEGAL_ROSTER, 17):
            sel, _ = optimise_v2(cand, B, mr)
            if sel is not None:
                sols[mr] = cand[sel]

        # ⚠️ תיקון יום 7, אחרי שאלמוג הריץ: העמודה הקודמת הודפסה
        # בשם "סגל טוב" אבל הכילה את min_roster, לא את גודל הסגל.
        # וגרוע מכך — הבחירה נעשית לפי ניקוד המודל, שהוכח מונוטוני
        # יורד ב-min_roster. כלומר הזוכה הוא תמיד האילוץ הרופף
        # ביותר, והמבחן לא יכול היה להראות דבר אחר. ראו depth_by_size.
        print(f"\n  {'repl':<8}{'min_roster':>11}{'גודל בפועל':>11}"
              f"{'מודל':>9}{'מציאות':>10}{'קללה':>9}{'מועדון':>9}"
              f"{'יתרון':>9}")
        for rp in REPL_GRID:
            bq, _, _, _, _ = bench(club, test, ps, posmap, rp)
            best = max(sols, key=lambda m: score_rows(
                sols[m], "ppm", "avail", rp)[0])
            rr = sols[best]
            qp, _, _ = score_rows(rr, "ppm", "avail", rp)
            qt, _, _ = score_rows(rr, "ppm_true", "avail_true", rp)
            mark = " <-- מרכז" if abs(rp - 0.127) < 1e-9 else ""
            print(f"  {rp:<8.3f}{best:>11}{len(rr):>11}{qp:>9.1f}"
                  f"{qt:>10.1f}{qt / qp - 1:>+8.1%}{bq:>9.1f}"
                  f"{qt / bq - 1:>+8.1%}{mark}")
            if abs(rp - 0.127) < 1e-9:
                summary.append(dict(club=club, n=len(rr), model=qp, real=qt,
                                    curse=qt / qp - 1, bench=bq,
                                    adv=qt / bq - 1))

        # --- שאלת העומק, על הניקוד האמיתי ---
        by_size = {}
        for mr, rr in sols.items():
            qp, _, _ = score_rows(rr, "ppm", "avail", 0.127)
            qt, _, _ = score_rows(rr, "ppm_true", "avail_true", 0.127)
            by_size.setdefault(len(rr), (qp, qt))
        bm = max(by_size, key=lambda n: by_size[n][0])
        bt = max(by_size, key=lambda n: by_size[n][1])
        reals = np.array([v[1] for v in by_size.values()])
        print(f"\n  שאלת העומק — ניקוד אמיתי לפי גודל סגל:")
        print("    " + "  ".join(f"{n}:{by_size[n][1]:.0f}"
                                 for n in sorted(by_size)))
        print(f"    לפי המודל {bm} | לפי המציאות {bt} | "
              f"פיזור {reals.std() / reals.mean():.1%}")
        if bm != bt:
            print(f"    🔴 המודל בוחר {bm}, המציאות מעדיפה {bt} — "
                  f"פער {by_size[bt][1] / by_size[bm][1] - 1:+.1%}")

    h("סיכום — ברמת מחליף 0.127")
    s = pd.DataFrame(summary)
    print(s.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print("\n  להשוואה, מה שדיווחתי הבוקר (לפני התיקונים של אלמוג):")
    print("    TEL  מול המועדון +9.4%   קללה -6.2%")
    print("    HTA  מול המועדון +11.2%  קללה -11.9%")
    print(SEP)


if __name__ == "__main__":
    main()
