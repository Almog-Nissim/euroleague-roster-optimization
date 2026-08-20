"""
final_fix.py  (Day 9 — ההרצה המסכמת)
------------------------------------
**שני פרמטרים שנמדדו מהדאטה, והמודל סותר אותם.**

--------------------------------------------------------------------
איך הגענו לכאן
--------------------------------------------------------------------
המנוע ניצח 38 מתוך 38 בחציון +18.3%, ובחר **בדיוק 12 שחקנים**
בכל מקרה יחיד ובכל רצפת מחיר. שש השערות נבדקו ונשללו:

    ארטיפקט ניקוד     סגל אקראי מפסיד ב-5.5%, מנצח רק ב-24%
    גודל סגל          שווה 3.4 נקודות בלבד
    רצפות עמדה        אפס (התיקון אף העלה את היתרון)
    צפיפות            אמיתית ברמת השחקן, **אפס ברמת הקבוצה**
    כוכבים זולים      השוק שטוח מהמודל (0.148 מול 0.220)
    מילוי חינמי       האחוזון הראשון במאגר עולה 42% מהחציון

`depth_value` על 1,372 משחקי-קבוצה סגר את זה:

    b1 = -0.159 (p=0.033)  ->  **84% מהאובדן בהיעדרות נספג**

ומדידה ישירה הסבירה למה:

    דירוג דקות בקבוצה      ppm       דקות/משחק
    1-5 (חמישייה)         0.497         21.8
    6-8                   0.433         14.7
    9-12                  0.391          8.9
    13+                   0.371          3.8

    ppm ממוצע בליגה       0.458
    **REPLACEMENT במודל   0.127**

--------------------------------------------------------------------
שתי הטעויות
--------------------------------------------------------------------
**א. רמת המחליף נמוכה פי שלושה.** 0.127 מול ~0.39 שנמדד. אפילו
   האחוזון העשירי של הליגה הוא 0.208.

**ב. חלוקת הדקות תלולה מדי.** `score_rows` נותנת 200 דקות
   לשמונת הראשונים ואפס לשאר. הפרופיל האמיתי נותן לשחקנים 9-12
   כמעט 9 דקות למשחק כל אחד — **17.5% מדקות הקבוצה**.

שתיהן דוחפות לאותו כיוון: הן הופכות עומק לחסר ערך **במודל**, בזמן
שבמציאות שחקנים 9-12 מייצרים 79% מהפותחים. ולכן האופטימייזר, שהוא
רציונלי, קונה 12 ונעצר.

--------------------------------------------------------------------
מה הקובץ מריץ
--------------------------------------------------------------------
    A. בסיס            optimise_v2 · score_rows · repl=0.127
    B. + מחליף מתוקן   המטרה נעשית Σ(ppm−repl)·e · repl נמדד
    C. + פרופיל דקות   optimise_v3 עם תקרות מצטברות · score_realistic
    D. שניהם

⚠️ ב-B ואילך **המטרה של ה-LP משתנה יחד עם הניקוד**. דקה שאינה
   מוקצית שווה `repl` בניקוד, ולכן היא חייבת להיות במטרה:
   max Σppm·e + repl·(200−Σe) = const + Σ(ppm−repl)·e.
   בלי זה חוזרים לחטא של יום 6 — המנוע ממטב פונקציה אחת ונמדד
   באחרת.

**גיזום שליטה:** אילוץ הצורה מוסיף ~8n משתני עזר ופתרון לקח 115
שניות. שחקן שקיים אחר באותה עמדה עם ppm וזמינות גבוהים או שווים
ועלות נמוכה או שווה — לעולם לא ייבחר. הסרתם מקטינה את המאגר
מ-295 ל-94 ואת זמן הפתרון ל-5 שניות, **בלי לשנות את הפתרון**.

--------------------------------------------------------------------
תחזיות — ננעלו. שנינו מסכימים.
--------------------------------------------------------------------
"""

# ====================================================================
PRED_BOTH = dict(
    advantage="+4% .. +9%   (מ-+18.3%)",
    roster_size="14-16   (לראשונה מחוץ ל-12)",
    losses="המנוע יפסיד ל-5 עד 10 מועדונים, לא ל-4",
    why="ברגע שלשחקן 9-12 יש ערך אמיתי, סגל צר נעשה יקר",
)
# ====================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR
import roster_optimizer as ro
import optimizer_backtest as ob
from league_backtest import build_pool, club_side, SEASONS
from optimise_consistent import optimise_v2
from roster_membership_audit import score_rows
from minute_profile import observed_caps, optimise_v3, score_realistic
from final_day7 import MIN_LEGAL_ROSTER
from depth_value import load_games

SEP = "=" * 100
REPL_OLD = 0.127


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def measure_replacement():
    """רמת המחליף = ppm של שחקנים בדירוג 9-12 בתוך הקבוצה.

    לא אחוזון שרירותי ולא שחקנים עם מעט משחקים (הקבוצה ההיא
    מוטה) — אלא בדיוק מי שנכנס כשמישהו נעדר.
    """
    fr = []
    for s in (2024, 2025):
        b = load_games(s)
        p = b.groupby(["Team", "pc"]).agg(
            tm=("min", "sum"), tp=("pir", "sum")).reset_index()
        ng = b.groupby("Team").gid.nunique().rename("cg")
        p = p.merge(ng, on="Team")
        p["mpg"] = p.tm / p.cg
        p["ppm"] = p.tp / p.tm.replace(0, np.nan)
        p = p[p.tm >= 60].dropna(subset=["ppm"])
        p["rk"] = p.groupby("Team").mpg.rank(ascending=False, method="first")
        fr.append(p)
    a = pd.concat(fr)
    out = {}
    for lo, hi, lab in [(1, 5, "1-5"), (6, 8, "6-8"),
                        (9, 12, "9-12"), (13, 99, "13+")]:
        g = a[(a.rk >= lo) & (a.rk <= hi)]
        out[lab] = float((g.ppm * g.tm).sum() / g.tm.sum())
    return out


def prune(c):
    """הסרת שחקנים נשלטים. לא משנה את הפתרון, מקצר פי 20.

    שחקן i נשלט אם קיים j באותה עמדה עם ppm>=, זמינות>=, עלות<=,
    ולפחות אחד מהם ממש. אז j תמיד מחליף אותו בלי לפגוע.
    """
    keep = []
    for _, g in c.groupby("position"):
        a = g[["ppm", "avail", "cost"]].values
        idx = g.index.values
        for i in range(len(a)):
            ge = ((a[:, 0] >= a[i, 0]) & (a[:, 1] >= a[i, 1])
                  & (a[:, 2] <= a[i, 2]))
            st = ((a[:, 0] > a[i, 0]) | (a[:, 1] > a[i, 1])
                  | (a[:, 2] < a[i, 2]))
            ge[i] = False
            if not (ge & st).any():
                keep.append(idx[i])
    return c.loc[sorted(keep)].reset_index(drop=True)


def main():
    print(SEP)
    print("final_fix — שני פרמטרים שנמדדו, והמודל סתר אותם")
    print("תחזיות ננעלו, שנינו מסכימים. ראו ראש הקובץ.")
    print(SEP)

    lv = measure_replacement()
    repl = lv["9-12"]
    h("א. רמת המחליף — נמדדת, לא מונחת")
    for k, v in lv.items():
        print(f"  דירוג {k:<6} ppm = {v:.3f}")
    print(f"\n  רמת מחליף חדשה (9-12) = {repl:.3f}")
    print(f"  רמת מחליף במודל       = {REPL_OLD:.3f}   "
          f"->  פי {repl/REPL_OLD:.1f}")

    caps, capmean, ncs = observed_caps()
    print(f"\n  תקרות הצורה, מ-{ncs} עונות-מועדון:")
    print("   " + "  ".join(f"k{k}:{caps[k]:.0f}" for k in sorted(caps)))

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    rows = []
    for train_max, test in SEASONS:
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        pool = prune(cand)
        gmax = float(ps[ps.season == test].games.max())
        clubs = sorted(split[split.season == test].club.unique())
        h(f"עונה {test}   מאגר {len(cand)} -> {len(pool)} אחרי גיזום   "
          f"מועדונים {len(clubs)}")
        print(f"  {'מועדון':<7}{'n':>4}{'מועדון':>9}"
              f"{'A בסיס':>10}{'יתרון':>8}"
              f"{'B מחליף':>10}{'יתרון':>8}"
              f"{'C פרופיל':>11}{'יתרון':>8}"
              f"{'D שניהם':>10}{'יתרון':>8}{'nD':>4}")
        om = ro.MAX_ROSTER
        for club in clubs:
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                continue
            B = float(keep.cost.sum())
            res, sizes = {}, {}

            # A — כמו שהיה
            s1, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
            res["A"] = score_rows(cand[s1], "ppm_true", "avail_true",
                                  REPL_OLD)[0] if s1 is not None else np.nan
            sizes["A"] = int(s1.sum()) if s1 is not None else 0
            qA = score_rows(keep, "ppm_true", "avail_true", REPL_OLD)[0]

            # B — רמת מחליף מתוקנת, גם במטרה וגם בניקוד
            s2, _ = optimise_v3(pool, B, MIN_LEGAL_ROSTER, {},
                                repl=repl, time_limit=60)
            res["B"] = score_rows(pool[s2], "ppm_true", "avail_true",
                                  repl)[0] if s2 is not None else np.nan
            sizes["B"] = int(s2.sum()) if s2 is not None else 0
            qB = score_rows(keep, "ppm_true", "avail_true", repl)[0]

            # C — פרופיל דקות מציאותי, רמת מחליף ישנה
            s3, _ = optimise_v3(pool, B, MIN_LEGAL_ROSTER, caps,
                                repl=REPL_OLD, time_limit=90)
            res["C"] = score_realistic(pool[s3], "ppm_true", "avail_true",
                                       REPL_OLD, caps)[0] \
                if s3 is not None else np.nan
            sizes["C"] = int(s3.sum()) if s3 is not None else 0
            qC = score_realistic(keep, "ppm_true", "avail_true",
                                 REPL_OLD, caps)[0]

            # D — שניהם
            s4, _ = optimise_v3(pool, B, MIN_LEGAL_ROSTER, caps,
                                repl=repl, time_limit=90)
            res["D"] = score_realistic(pool[s4], "ppm_true", "avail_true",
                                       repl, caps)[0] \
                if s4 is not None else np.nan
            sizes["D"] = int(s4.sum()) if s4 is not None else 0
            qD = score_realistic(keep, "ppm_true", "avail_true", repl, caps)[0]

            ro.MAX_ROSTER = om
            rows.append(dict(season=test, club=club, n=len(keep),
                             qA=qA, qB=qB, qC=qC, qD=qD, **res,
                             **{f"n{k}": v for k, v in sizes.items()}))
            print(f"  {club:<7}{len(keep):>4}{qA:>9.1f}"
                  f"{res['A']:>10.1f}{res['A']/qA-1:>+8.1%}"
                  f"{res['B']:>10.1f}{res['B']/qB-1:>+8.1%}"
                  f"{res['C']:>11.1f}{res['C']/qC-1:>+8.1%}"
                  f"{res['D']:>10.1f}{res['D']/qD-1:>+8.1%}{sizes['D']:>4}")

    d = pd.DataFrame(rows)
    d.to_csv(PROCESSED_DIR / "final_fix.csv", index=False)
    for k in "ABCD":
        d[f"adv{k}"] = d[k] / d[f"q{k}"] - 1

    h("התוצאה")
    print(f"  n = {len(d)} עונות-מועדון\n")
    print(f"  {'תרחיש':<34}{'מנצח':>8}{'חציון':>10}{'ממוצע':>10}"
          f"{'גודל סגל':>11}{'מפסיד ל-':>10}")
    for k, lab in [("A", "בסיס (כמו שהיה)"),
                   ("B", "+ רמת מחליף נמדדת"),
                   ("C", "+ פרופיל דקות"),
                   ("D", "**שניהם**")]:
        a = d[f"adv{k}"]
        print(f"  {lab:<34}{float((a>0).mean()):>8.0%}{a.median():>+10.1%}"
              f"{a.mean():>+10.1%}{d[f'n{k}'].mean():>11.2f}"
              f"{int((a<=0).sum()):>10}")

    print(f"\n  מול התחזית המשותפת:")
    md, sz = float(d.advD.median()), float(d.nD.mean())
    nl = int((d.advD <= 0).sum())
    print(f"    יתרון +4%..+9%   ->  {'✅' if 0.04 <= md <= 0.09 else '❌'}"
          f"   ({md:+.1%})")
    print(f"    גודל סגל 14-16   ->  {'✅' if 14 <= sz <= 16 else '❌'}"
          f"   ({sz:.2f})")
    print(f"    מפסיד ל-5 עד 10  ->  {'✅' if 5 <= nl <= 10 else '❌'}"
          f"   ({nl})")

    h("למי המנוע מפסיד אחרי התיקון")
    lose = d[d.advD <= 0].sort_values("advD")
    if len(lose):
        for _, r in lose.iterrows():
            print(f"    {r.season} {r.club:<5}{r.advD:>+8.1%}   "
                  f"מועדון {r.qD:6.1f}  מנוע {r.D:6.1f}  n={int(r.n)}")
    else:
        print("    לאף אחד.")
    print(SEP)


if __name__ == "__main__":
    main()