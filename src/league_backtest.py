"""
league_backtest.py  (Day 9)
---------------------------
**המעבר מ-n=2 ל-n=38.**

--------------------------------------------------------------------
למה זה לא נעשה עד היום
--------------------------------------------------------------------
הבקטסט רץ על שני מועדונים בלבד — מכבי 2024 והפועל 2025 — כי רק
להם היו **עוגני שכר ברמת שחקן**. בלי שכר אמיתי אי אפשר היה לקבוע
את התקציב, ובלי תקציב אין אילוץ ואין השוואה.

--------------------------------------------------------------------
מה שובר את החסם
--------------------------------------------------------------------
להשוואה **מנוע מול מועדון** לא נדרש שכר אמיתי. נדרש רק ש**שני
הצדדים יתומחרו באותו מודל מחירים**:

    תקציב המועדון := סך העלות שמודל העלות מייחס לסגל שהמועדון
                     באמת העמיד.

    המנוע בונה סגל מאותו מאגר, באותם מחירים, תחת אותו תקציב.

הסקלה של מודל העלות (mean_salary) **מתבטלת** — היא מכפילה את שני
הצדדים באותו קבוע. לכן היא נקבעת ל-1.0 והמחירים הם יחסיים בלבד.

זו לא הנחה מקלה. היא מחמירה: היא מנטרלת לחלוטין את היתרון
שהמנוע היה יכול לקבל מכך שהמחירים שלו מדויקים יותר או פחות
מהמחירים שהמועדון שילם בפועל. נשארת **רק שאלת ההקצאה**.

--------------------------------------------------------------------
מה זה עדיין לא בודק
--------------------------------------------------------------------
- ⚠️ אם מודל העלות שוגה **באופן שיטתי לפי סוג שחקן** (למשל מתמחר
  כוכבים בזול), המנוע ינצל את השגיאה והיתרון יהיה מנופח. זה בדיוק
  מה שיימדד ביום 9 בקללת המנצח בצד העלות. **התוצאה כאן היא חסם
  עליון, לא אומדן.**
- זמינות בשוק: המנוע קונה כל שחקן ביורוליג. מועדון אמיתי לא יכול.
- הסגל האמיתי מימש 100% בהגדרה.

--------------------------------------------------------------------
א-סימטריה ידועה ומדווחת
--------------------------------------------------------------------
צד המועדון מנוקד על מה שהמועדון **באמת קיבל** (פיצול רב-מועדוני
מ-player_club_season). צד המנוע מנוקד על ppm של העונה המלאה.
לשחקן שעבר מועדון באמצע עונה זה **מיטיב עם המנוע**. מספר
הנרכשים-המפוצלים מדווח בכל שורה.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
PRED_CLAUDE_WINRATE = (0.60, 0.75)
PRED_ALMOG_WINRATE = (0.55, 0.65)      # "יותר לכיוון ה-60 מאשר ה-75"
PRED_BOTH_MEDIAN_ADV = "< +9.4%"        # היתרון במכבי 2024 היה חריג
PRED_WHY = (
    "מכבי 2024/25 סיימה 15 מתוך 18 בשכר ו-11 ניצחונות. קל לנצח "
    "מועדון חלש. על 38 מועדונים, שרובם הקצו את תקציבם סבירות, "
    "היתרון החציוני אמור להצטמצם. אם הוא **גדל** — סימן שמודל "
    "העלות מייצר ארביטראז' מלאכותי ולא שהמנוע טוב."
)
# ====================================================================

import io
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR
import roster_optimizer as ro
import optimizer_backtest as ob
from roster_membership_audit import score_rows
from optimise_consistent import optimise_v2
from final_day7 import MIN_LEGAL_ROSTER
from newcomer_pool import build_newcomer_rows

SEP = "=" * 96
REPL = 0.127
SEASONS = [(2023, 2024), (2024, 2025)]


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def build_pool(test, train_max, feat, anch, pos, ps, with_newcomers=True):
    """מאגר המועמדים לעונת test, מתומחר בסקלה 1.0 (מחירים יחסיים).

    כל המודלים מאומנים על עונות <= train_max. אין הצצה ל-test.

    with_newcomers: מוסיף שחקנים בלי עונת יורוליג קודמת, עם
    פריורים מכווצים לחלוטין. ראו newcomer_pool. בלי זה 20.6%
    מדקות הליגה מחוץ למאגר וההשוואה אינה מוגדרת היטב.
    """
    import statsmodels.api as sm
    ob.TRAIN_MAX, ob.TEST, ob.TARGET_CLUB = train_max, test, None
    with contextlib.redirect_stdout(io.StringIO()):
        cm, smear, agg, am, pm, PF, lagged = ob.fit_models(ps, feat, anch)
        cand = ob.build(lagged, feat, pos, cm, smear, agg, am, pm, PF,
                        mean_salary=1.0)
    cand["is_newcomer"] = False

    info = {}
    if with_newcomers:
        new, info = build_newcomer_rows(ps, feat, lagged, test, train_max)
        new = new.merge(pos[["player_code", "position"]], on="player_code",
                        how="left").dropna(subset=["position"])
        if len(new):
            # מתומחר ומנובא ב**אותם מודלים בדיוק**
            new["cost"] = np.exp(cm.predict(sm.add_constant(
                new[ro.COST_FEATURES].astype(float),
                has_constant="add"))) * smear * 1.0
            new["avail"] = am.predict(sm.add_constant(
                new[ro.AVAIL_FEATURES].astype(float), has_constant="add"))
            new["ppm"] = pm.predict(sm.add_constant(
                new[PF].astype(float), has_constant="add"))
            new["ppm_sd"] = 0.0
            cand = pd.concat([cand, new[cand.columns.intersection(
                new.columns)]], ignore_index=True, sort=False)
        info["n_new_kept"] = len(new)

    cand["ppm_true"] = cand.pir_per_game / cand.min_per_game
    cand["avail_true"] = cand.frac
    cand["pc"] = cand.player_code.astype(str)
    return cand.reset_index(drop=True), info


def club_side(cand, split, club, test, gmax, posmap):
    """הסגל שהמועדון באמת העמיד — מוגבל למאגר, מנוקד על מה שקיבל.

    ההגבלה למאגר היא **סימטריה**: המנוע יכול לקנות רק מהמאגר,
    ולכן גם המועדון נמדד רק על מי שהיה שם. שחקן בלי עונה קודמת
    (עולה חדש) אינו במאגר ויוצא משני הצדדים — גם מהניקוד וגם
    מהתקציב. מספר היוצאים והדקות שאיתם מדווחים.
    """
    mine = split[(split.season == test) & (split.club == club)].copy()
    mine["pc"] = mine.player_code.astype(str)
    mine["position"] = mine.pc.map(posmap)

    in_pool = set(cand.pc)
    keep = mine[mine.pc.isin(in_pool) & mine.position.notna()].copy()
    lost = mine[~(mine.pc.isin(in_pool) & mine.position.notna())]

    keep["ppm_true"] = keep.ppm
    keep["avail_true"] = keep.games / gmax
    # המחיר של המועדון — מאותו מודל בדיוק שמתמחר את המאגר
    cmap = cand.set_index("pc").cost
    keep["cost"] = keep.pc.map(cmap)
    return keep, lost


def main():
    print(SEP)
    print("league_backtest — המנוע מול 38 מועדונים אמיתיים")
    print("שני הצדדים מתומחרים באותו מודל. הסקלה מתבטלת.")
    print("תחזיות ננעלו לפני ההרצה. ראו ראש הקובץ.")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    rows = []
    for train_max, test in SEASONS:
        cand, info = build_pool(test, train_max, feat, anch, pos, ps)
        gmax = float(ps[ps.season == test].games.max())
        clubs = sorted(split[split.season == test].club.unique())
        h(f"עונה {test}   (אימון <= {train_max})   מאגר {len(cand)}   "
          f"מהם חדשים {int(cand.is_newcomer.sum())}   "
          f"משחקים {gmax:.0f}   מועדונים {len(clubs)}")
        # 🔴 בדיקת כיסוי עמדות. בלעדיה צד המועדון מנוקד חלקית
        #    וההטיה היא **לטובת המנוע** — הכיוון שגורם למסקנה
        #    חיובית שגויה. ראו positions_worklist.
        t = ps[(ps.season == test) & (ps.min_per_game > 0)].copy()
        t["mt"] = t.min_per_game * t.games
        known = set(pos.player_code.astype(str))
        mm = t[~t.player_code.astype(str).isin(known)]
        share = mm.mt.sum() / t.mt.sum()
        print(f"  ללא עמדה: {len(mm)} שחקנים, {share:.1%} מהדקות")
        if share > 0.05:
            print(f"  ⛔ מעל 5% מהדקות בלי עמדה. הרץ positions_worklist -> "
                  f"מלא -> positions_merge. התוצאות כאן אינן תקפות.")
        print(f"  {'מועדון':<8}{'סגל':>5}{'יצאו':>6}{'תקציב':>10}"
              f"{'מועדון':>9}{'מנוע':>9}{'יתרון':>9}{'n_מנוע':>8}"
              f"{'חפיפה':>8}{'מפוצלים':>10}")
        for club in clubs:
            keep, lost = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                print(f"  {club:<8}{len(keep):>5}{len(lost):>6}"
                      f"   סגל במאגר קטן מ-{MIN_LEGAL_ROSTER} — מדולג")
                continue
            B = float(keep.cost.sum())
            q_club, _, _ = score_rows(keep, "ppm_true", "avail_true", REPL)

            sel, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
            if sel is None:
                print(f"  {club:<8}   אין פתרון תחת תקציב {B:.2f}")
                continue
            eng = cand[sel]
            q_eng, _, _ = score_rows(eng, "ppm_true", "avail_true", REPL)

            overlap = len(set(eng.pc) & set(keep.pc))
            # כמה מבחירות המנוע שיחקו ביותר ממועדון אחד באותה עונה
            multi = split[split.season == test].groupby(
                "player_code").club.nunique()
            n_split = int(sum(multi.get(p, 1) > 1 for p in eng.pc))

            adv = q_eng / q_club - 1
            rows.append(dict(season=test, club=club, n_club=len(keep),
                             n_lost=len(lost), budget=B, q_club=q_club,
                             q_eng=q_eng, adv=adv, n_eng=len(eng),
                             overlap=overlap, n_split=n_split))
            print(f"  {club:<8}{len(keep):>5}{len(lost):>6}{B:>10.2f}"
                  f"{q_club:>9.1f}{q_eng:>9.1f}{adv:>+9.1%}{len(eng):>8}"
                  f"{overlap:>8}{n_split:>10}")

    d = pd.DataFrame(rows)
    if d.empty:
        print("\nאין תוצאות.")
        return
    out = PROCESSED_DIR / "league_backtest_results.csv"
    d.to_csv(out, index=False)

    h("התוצאה")
    win = float((d.adv > 0).mean())
    print(f"  n = {len(d)} עונות-מועדון")
    print(f"  המנוע מנצח ב-  {win:.1%}  מהמקרים  ({int((d.adv>0).sum())}/{len(d)})")
    print(f"  יתרון: חציון {d.adv.median():+.1%}   ממוצע {d.adv.mean():+.1%}"
          f"   טווח {d.adv.min():+.1%} .. {d.adv.max():+.1%}")
    rng = np.random.default_rng(0)
    bs = [d.adv.sample(len(d), replace=True, random_state=int(s)).median()
          for s in rng.integers(0, 10**6, 4000)]
    print(f"  CI95 לחציון: [{np.percentile(bs,2.5):+.1%}, "
          f"{np.percentile(bs,97.5):+.1%}]")

    print(f"\n  לפי עונה:")
    for s, g in d.groupby("season"):
        print(f"    {s}  n={len(g):2d}  ניצחון {float((g.adv>0).mean()):.0%}"
              f"  חציון {g.adv.median():+.1%}")

    print(f"\n  מול התחזיות:")
    for nm, (lo, hi) in [("קלוד", PRED_CLAUDE_WINRATE),
                         ("אלמוג", PRED_ALMOG_WINRATE)]:
        ok = "✅" if lo <= win <= hi else "❌"
        print(f"    {nm:<6} {lo:.0%}-{hi:.0%}  ->  {ok}")
    print(f"    חציון < +9.4% (שניהם)  ->  "
          f"{'✅' if d.adv.median() < 0.094 else '❌'}")

    h("איפה המנוע מנצח, ואיפה לא")
    d2 = d.sort_values("adv")
    print("  החמישה שהמנוע הכי מתקשה מולם:")
    for _, r in d2.head(5).iterrows():
        print(f"    {r.season} {r.club:<5}{r.adv:>+8.1%}  "
              f"מועדון {r.q_club:6.1f}  חפיפה {int(r.overlap)}/{int(r.n_club)}")
    print("  החמישה שהמנוע הכי מנצח מולם:")
    for _, r in d2.tail(5).iloc[::-1].iterrows():
        print(f"    {r.season} {r.club:<5}{r.adv:>+8.1%}  "
              f"מועדון {r.q_club:6.1f}  חפיפה {int(r.overlap)}/{int(r.n_club)}")

    from scipy import stats
    r1, p1 = stats.pearsonr(d.q_club, d.adv)
    print(f"\n  קורלציה (איכות המועדון , יתרון המנוע) = {r1:+.3f} (p={p1:.3f})")
    print("  שלילית חזקה = המנוע מנצח בעיקר מועדונים חלשים,")
    print("  כלומר היתרון הוא **תיקון של טעויות** ולא יצירת ערך.")

    print(f"\n  נשמר: {out}")
    print(SEP)


if __name__ == "__main__":
    main()