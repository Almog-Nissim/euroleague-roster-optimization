"""
why_100.py  (Day 9)
-------------------
**המנוע ניצח 26 מתוך 26. זו לא תוצאה — זו אזהרה.**

שתי התחזיות נפלו לא בכיוון של "טעינו במעט" אלא בכיוון של "המבחן
לא בדק את מה שחשבנו". תוצאה של 100% עם חציון +15.5% בזמן
שהמועדונים האלה מנצחים ומפסידים זה לזה ביורוליג אמיתית — פירושה
שיש למנוע יתרון **מבני**, שאינו קשור לאיכות ההקצאה.

הקובץ הזה מודד שלושה חשודים. כל אחד מהם נבדק בנפרד.

====================================================================
חשוד א' — גודל הסגל. **א-סימטריה ישירה בתקציב.**
====================================================================
בכל 26 המקרים המנוע בחר **בדיוק 12** שחקנים. המועדונים החזיקו
12-18 (חציון 14).

התקציב מוגדר כסך עלות הסגל שהמועדון העמיד. כלומר:

    מכבי  שילמה 12.94 עבור 18 שחקנים
    המנוע קיבל  12.94 עבור 12 שחקנים

וחשוב מזה: `score_rows` מחלקת 200 דקות, תקרה 32 לשחקן. בזמינות
טיפוסית ~0.8 זה אומר ש**כ-8 שחקנים בולעים את כל הדקות**. שחקן
מספר 9 ואילך לא תורם לניקוד — אבל המועדון שילם עליו.

    תקציב לשחקן מנקד:  מועדון B/18  ·  מנוע B/12   ->  +50%

====================================================================
חשוד ב' — רצפות העמדות אינן מציאותיות
====================================================================
נמדד על 38 עונות-מועדון אמיתיות (נתח דקות):

                בפועל (ממוצע)   טווח אמיתי    האילוץ במודל
        G           43.7%       24.1-59.5%       >= 16.3%
        F           38.6%       19.4-58.1%       >= 14.6%
        C           17.7%        7.8-40.2%       >=  4.3%

הרצפות נקבעו כ**מינימום הנצפה** בכל עמדה בנפרד. אבל שום מועדון
אמיתי לא נמצא במינימום של שלוש העמדות **בו-זמנית** — וזה בדיוק
מה שאופטימייזר עושה. הוא מעמיד סנטר אחד ל-8.6 דקות משחק.

====================================================================
חשוד ג' — פרופיל הדקות. **התפיסה של אלמוג.**
====================================================================
"מאיפה הגיע הגבול של 32 דקות?" — הוא נקבע כמקסימום הנצפה של
ממוצע עונתי (34.0 בפועל, 8 מקרים מתוך 2,553 עברו 32). כמספר
בודד הוא בסדר. אבל הוא חל על כל שחקן **בנפרד**, והניקוד מחלק
בחמדנות — ולכן שישה-שבעה שחקנים מגיעים אליו בו-זמנית.

סך התרומה של k המובילים (מתוך 200), על 38 עונות-מועדון:

        k=1   מקס נצפה  31.2   ·  המודל מרשה  32
        k=4   מקס נצפה 104.9   ·  המודל מרשה 128
        k=6   מקס נצפה 145.3   ·  המודל מרשה 192
        k=8   מקס נצפה 176.9   ·  המודל מרשה 200

אף קבוצה לא העמידה יותר משני שחקנים מעל 28 דקות. המודל מעמיד
שמונה. `score_realistic` מנקדת את **שני הצדדים** תחת התקרה
המצטברת הנצפית.

⚠️ הבחירה כאן עדיין נעשית ב-optimise_v2, כלומר המנוע ממטב מול
   החוק הרופף ומנוקד תחת החוק ההדוק. זה **לרעת המנוע**, ולכן
   יתרון ששורד את התרחיש הזה הוא יתרון אמיתי. (optimise_v3
   ב-minute_profile פותר את זה נכון, אבל 90-120 שניות לפתרון —
   לא מעשי ל-35 מועדונים.)

====================================================================
חשוד ד' — מודל האפס
====================================================================
המבחן המכריע. אם סגל **אקראי חוקי** באותו גודל ובאותו תקציב גם
הוא מנצח את המועדון ב-100% מהמקרים — אז אין כאן אופטימיזציה
בכלל, רק ארטיפקט של פונקציית הניקוד.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
PRED_CLAUDE = dict(
    matched_size_median="+8% .. +11%   (מ-+15.5%)",
    matched_size_and_pos="+3% .. +7%",
    realistic_minutes="+2% .. +6%",
    random_winrate="55% .. 75%",
    random_median="+2% .. +6%",
    which_suspect="גודל הסגל הוא הגדול מהשניים",
)
PRED_ALMOG = dict()   # למילוי לפני ההרצה
PRED_CLAUDE_WHY = (
    "גודל הסגל הוא חשבון ישיר: 50% יותר תקציב לשחקן מנקד, "
    "ובמודל עלות מעריכי זה קונה שחקן טוב בהרבה. רצפות העמדות "
    "משפיעות פחות כי הפער ב-ppm בין סנטרים לכנפיים אינו עצום. "
    "מודל האפס ינצח את המועדונים ברוב המקרים — כי הוא נהנה "
    "מאותה א-סימטריה — אבל **לא** ב-100%, וזה הפער שבאמת שייך "
    "לאופטימיזציה."
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
from league_backtest import build_pool, club_side, SEASONS, REPL
from final_day7 import MIN_LEGAL_ROSTER
from minute_profile import observed_caps, score_realistic

SEP = "=" * 96
N_DRAWS = 300
RNG = np.random.default_rng(20260818)


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def real_pos_shares(split, pos):
    """נתח הדקות בפועל לפי עמדה, על כל עונות-המועדון בדאטה."""
    s = split.copy()
    s["position"] = s.player_code.astype(str).map(
        pos.set_index(pos.player_code.astype(str)).position)
    s = s.dropna(subset=["position"])
    r = s.groupby(["season", "club", "position"]).minutes.sum().unstack("position")
    return r.div(r.sum(axis=1), axis=0)


def scoring_players(df, ppm_col, avail_col):
    """מי מקבל דקות בפועל ב-score_rows. לא כל הסגל מנקד."""
    ppm, av, p = df[ppm_col].values, df[avail_col].values, df.position.values
    caps = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
            for g in ro.POS_MAX_SHARE}
    left, mins = ro.MINUTES_PER_GAME, np.zeros(len(df))
    for j in np.argsort(-ppm):
        take = max(min(ro.MAX_MIN_PLAYER, left, caps[p[j]]) * av[j], 0.0)
        mins[j] = take
        left -= take
        caps[p[j]] -= take
    return mins


def random_roster(pool, budget, n, floors, tries=400):
    """סגל אקראי חוקי: n שחקנים, בתוך התקציב, מקיים רצפות עמדה.

    דגימה בלי החזרה + דחייה. שיעור ההצלחה מדווח — אם הוא נמוך,
    התקציב הוא האילוץ הכובל ולא ההקצאה.
    """
    cost = pool.cost.values
    posv = pool.position.values
    idx = np.arange(len(pool))
    for _ in range(tries):
        order = RNG.permutation(idx)
        take, spent, cnt = [], 0.0, {"G": 0, "F": 0, "C": 0}
        for i in order:
            if len(take) >= n:
                break
            if spent + cost[i] <= budget:
                take.append(i)
                spent += cost[i]
                cnt[posv[i]] += 1
        if len(take) == n and all(cnt[g] >= f for g, f in floors.items()):
            return pool.iloc[take]
    return None


def main():
    print(SEP)
    print("why_100 — למה המנוע ניצח 26 מתוך 26")
    print("שלושה חשודים. תחזיות ננעלו. ראו ראש הקובץ.")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    caps, capmean, ncs = observed_caps(split, ps)
    h("חשוד ג' — פרופיל הדקות מול המציאות")
    print(f"  {'k':>3}{'ממוצע':>10}{'מקס נצפה':>12}{'המודל מרשה':>14}")
    for k in sorted(caps):
        print(f"  {k:>3}{capmean[k]:>10.1f}{caps[k]:>12.1f}"
              f"{min(ro.MAX_MIN_PLAYER*k, ro.MINUTES_PER_GAME):>14.1f}")

    shares = real_pos_shares(split, pos)
    h("חשוד ב' — רצפות העמדות מול המציאות")
    print(f"  {'':4}{'ממוצע':>9}{'חציון':>9}{'אחוזון 10':>11}"
          f"{'מינימום':>10}{'הרצפה':>9}")
    new_floor = {}
    for g in ["G", "F", "C"]:
        c = shares[g].dropna()
        p10 = float(np.percentile(c, 10))
        new_floor[g] = round(p10, 3)
        print(f"  {g:<4}{c.mean():>9.1%}{c.median():>9.1%}{p10:>11.1%}"
              f"{c.min():>10.1%}{ro.POS_MIN_SHARE[g]:>9.1%}")
    print(f"\n  רצפה מציאותית (אחוזון 10 של המציאות): {new_floor}")
    print(f"  הרצפה הנוכחית:                        {ro.POS_MIN_SHARE}")
    orig_floor = dict(ro.POS_MIN_SHARE)
    orig_max = ro.MAX_ROSTER

    rows = []
    for train_max, test in SEASONS:
        cand, info = build_pool(test, train_max, feat, anch, pos, ps)
        gmax = float(ps[ps.season == test].games.max())
        clubs = sorted(split[split.season == test].club.unique())
        h(f"עונה {test}   מאגר {len(cand)}")
        print(f"  {'מועדון':<7}{'n':>4}{'תקציב':>9}{'מועדון':>9}"
              f"{'מנוע12':>9}{'מנוע=n':>9}{'+עמדות':>9}"
              f"{'אקראי':>9}{'אקר.נצח':>9}{'מנקדים':>9}")
        for club in clubs:
            keep, lost = club_side(cand, split, club, test, gmax, posmap)
            n = len(keep)
            if n < MIN_LEGAL_ROSTER:
                continue
            B = float(keep.cost.sum())
            q_club, _, _ = score_rows(keep, "ppm_true", "avail_true", REPL)

            def solve(min_r, floors, max_r):
                ro.POS_MIN_SHARE.update(floors)
                ro.MAX_ROSTER = max_r
                s, _ = optimise_v2(cand, B, min_r)
                ro.POS_MIN_SHARE.update(orig_floor)
                ro.MAX_ROSTER = orig_max
                if s is None:
                    return None, np.nan
                r = cand[s]
                return r, score_rows(r, "ppm_true", "avail_true", REPL)[0]

            _, q12 = solve(MIN_LEGAL_ROSTER, orig_floor, orig_max)
            rn, qn = solve(n, orig_floor, max(orig_max, n))
            rnp, qnp = solve(n, new_floor, max(orig_max, n))
            # חשוד ג': אותה בחירה, ניקוד תחת תקרת הצורה — לשני הצדדים
            q_club_r = score_realistic(keep, "ppm_true", "avail_true",
                                       REPL, caps)[0]
            qm = (score_realistic(rnp, "ppm_true", "avail_true", REPL, caps)[0]
                  if rnp is not None else np.nan)

            # --- מודל האפס: אותו גודל, אותו תקציב ---
            draws = [random_roster(cand, B, n, ro.POS_FLOOR)
                     for _ in range(N_DRAWS)]
            ok = [d for d in draws if d is not None]
            qr = np.array([score_rows(d, "ppm_true", "avail_true", REPL)[0]
                           for d in ok]) if ok else np.array([np.nan])
            rand_win = float((qr > q_club).mean()) if ok else np.nan

            mins = scoring_players(keep, "ppm_true", "avail_true")
            n_scoring = int((mins > 0.5).sum())
            cost_wasted = float(keep.cost[mins <= 0.5].sum() / B)

            rows.append(dict(season=test, club=club, n=n, B=B, q_club=q_club,
                             q_club_r=q_club_r, qm=qm,
                             q12=q12, qn=qn, qnp=qnp, q_rand=np.nanmedian(qr),
                             rand_win=rand_win, n_scoring=n_scoring,
                             cost_wasted=cost_wasted, n_ok=len(ok)))
            print(f"  {club:<7}{n:>4}{B:>9.2f}{q_club:>9.1f}{q12:>9.1f}"
                  f"{qn:>9.1f}{qnp:>9.1f}{np.nanmedian(qr):>9.1f}"
                  f"{rand_win:>9.0%}{n_scoring:>9}")

    d = pd.DataFrame(rows)
    d.to_csv(PROCESSED_DIR / "why_100_results.csv", index=False)
    for c in ("q12", "qn", "qnp", "q_rand"):
        d[c + "_adv"] = d[c] / d.q_club - 1
    d["qm_adv"] = d.qm / d.q_club_r - 1      # שני הצדדים תחת תקרת הצורה

    h("התוצאה")
    print(f"  n = {len(d)} עונות-מועדון\n")
    print(f"  {'תרחיש':<28}{'מנצח':>8}{'חציון':>10}{'ממוצע':>10}")
    for c, lab in [("q12", "מנוע 12 (ההרצה שלך)"),
                   ("qn", "מנוע בגודל הסגל"),
                   ("qnp", "מנוע + רצפות מציאותיות"),
                   ("qm", "+ פרופיל דקות מציאותי"),
                   ("q_rand", "סגל אקראי, אותו גודל")]:
        a = d[c + "_adv"]
        print(f"  {lab:<28}{float((a>0).mean()):>8.0%}"
              f"{a.median():>+10.1%}{a.mean():>+10.1%}")

    print(f"\n  שחקנים שבאמת מנקדים בסגל המועדון: "
          f"חציון {d.n_scoring.median():.0f} מתוך {d.n.median():.0f}")
    print(f"  חלק התקציב שהמועדון משלם על שחקנים שאינם מנקדים: "
          f"חציון {d.cost_wasted.median():.1%}")

    print("\n  --- פירוק היתרון ---")
    tot = d.q12_adv.median()
    size = d.q12_adv.median() - d.qn_adv.median()
    posf = d.qn_adv.median() - d.qnp_adv.median()
    rand = d.q_rand_adv.median()
    print(f"  היתרון שנמדד             {tot:+.1%}")
    print(f"    מזה: גודל סגל          {size:+.1%}")
    print(f"    מזה: רצפות עמדה        {posf:+.1%}")
    print(f"    מזה: פרופיל דקות      "
          f"{d.qnp_adv.median()-d.qm_adv.median():+.1%}")
    print(f"    נשאר אחרי שלושתם       {d.qm_adv.median():+.1%}")
    print(f"    מזה סגל אקראי משיג     {rand:+.1%}")
    print(f"  ** מה ששייך לאופטימיזציה: {d.qm_adv.median()-rand:+.1%} **")

    print("\n  מול התחזיות של קלוד:")
    for k, v in PRED_CLAUDE.items():
        print(f"    {k:<22} {v}")
    print(SEP)


if __name__ == "__main__":
    main()