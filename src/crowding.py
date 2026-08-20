"""
crowding.py  (Day 9)
--------------------
**ההנחה שלא בדקנו מעולם, והיא זו ששוברת את המבחן.**

--------------------------------------------------------------------
מה נשלל קודם
--------------------------------------------------------------------
המנוע ניצח 38 מתוך 38 בחציון +18.3%. שלושת החשודים המבניים
נבדקו ונפלו:

    גודל הסגל          ->  שווה 3.4 נקודות בלבד
    רצפות העמדות       ->  אפס (התיקון אף העלה את היתרון)
    ניצול תקציב        ->  המנוע מוציא 99.3% מהתקציב. האילוץ כובל.
    ארטיפקט ניקוד      ->  **נשלל.** סגל אקראי באותו גודל ובאותו
                           תקציב **מפסיד** למועדונים ב-5.5% ומנצח
                           רק ב-24%. לפונקציית הניקוד יש אות אמיתי.

--------------------------------------------------------------------
מה כן קורה
--------------------------------------------------------------------
ניקוד המנוע: טווח 115.0-133.6, ס"ת **4.2**
ניקוד מועדון: טווח  83.9-125.0, ס"ת **8.2**
קורלציה (איכות מועדון , יתרון המנוע) = **-0.900**

המנוע נוחת כמעט תמיד על ~124, לא משנה מול מי ולא משנה התקציב.
הוא לא בונה סגל טוב יותר — הוא בונה **את אותו סגל**, ומנצח את מי
שנפל מתחתיו.

--------------------------------------------------------------------
ההנחה השבורה
--------------------------------------------------------------------
המנוע אוסף 12 שחקנים שכל אחד מהם היה **הציר של הקבוצה שלו**,
ומניח ש-ppm הוא תכונה קבועה של השחקן שנוסעת איתו.

היא לא. PIR מורכב מנקודות, ריבאונדים ואסיסטים — וכולם **משאב
משותף**. יש כדור אחד. שחקן שקיבל 30% מההתקפות בקבוצה בינונית
לא יקבל 30% כשלצידו עוד שבעה כאלה.

--------------------------------------------------------------------
המדידה
--------------------------------------------------------------------
על 723 זוגות עונות עוקבות (300+ דקות בשתיהן), ו-204 מהן
**מעברי מועדון**:

    Δppm מול Δאיכות-חברים,  כל המקרים :  r = -0.180  (p=1e-06)
    Δppm מול Δאיכות-חברים,  מעברים    :  r = -0.302  (p=1e-05)

שחקן שעובר לקבוצה חזקה יותר — ה-ppm שלו **יורד**. הצפיפות
אמיתית ומדידה.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
PRED_CLAUDE = dict(
    beta="-0.35 .. -0.20   (מקדם הצפיפות במעברים)",
    engine_drop="-8% .. -14%   ירידה בניקוד המנוע אחרי התיקון",
    club_drop="-1% .. -3%   המועדונים כמעט לא יושפעו",
    winrate_after="70% .. 90%   (מ-100%)",
    median_after="+3% .. +8%   (מ-+18.3%)",
)
PRED_ALMOG = dict(
    engine_drop="-15%",
    club_drop="-5%",
    winrate_after="65%",
    median_after="+5%",
)
# איפה אנחנו חלוקים, ולמה זה מבחן ולא פורמליות:
#   ירידת המועדון — אלמוג -5%, קלוד -1%..-3%.
#   הטיעון שלי היה "המועדון כבר נמדד בסביבה שלו, אז אין לו קפיצה".
#   אבל זה לא מדויק: `score_rows` מנקדת רק ~10 מתוך 16 שחקני
#   המועדון, ולכן איכות-החברים **בתוך הסגל המנוקד** גבוהה מזו
#   שהשחקן חווה בפועל מול כל הסגל. כלומר גם למועדון יש קפיצה,
#   קטנה יותר. אם הירידה שלו תהיה קרובה ל-5% — אלמוג צדק והנימוק
#   שלי היה רשלני.
PRED_CLAUDE_WHY = (
    "המועדונים כמעט לא יושפעו כי הם **כבר** נמדדו בסביבה שלהם — "
    "ה-ppm שלהם הוא מה שקרה בפועל עם החברים שהיו להם. המנוע "
    "לעומת זאת מרכיב 12 צירים, ולכן איכות-החברים שלו קופצת "
    "הרבה מעל מה שכל אחד מהם חווה. שם התיקון נושך."
)
# ====================================================================

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR
import roster_optimizer as ro
import optimizer_backtest as ob
from roster_membership_audit import score_rows
from optimise_consistent import optimise_v2
from league_backtest import build_pool, club_side, REPL, SEASONS
from final_day7 import MIN_LEGAL_ROSTER

SEP = "=" * 96
MIN_MIN = 300


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def mates_panel(ps, max_season=None):
    """לכל (שחקן, עונה): ppm שלו, ו-ppm המשוקלל של **שאר** הקבוצה.

    'שאר הקבוצה' ולא 'הקבוצה' — אחרת השחקן נמצא בשני האגפים
    והקורלציה מובטחת מכנית.
    """
    p = ps[ps.min_per_game > 0].copy()
    if max_season is not None:
        p = p[p.season <= max_season]
    p["ppm"] = p.pir_per_game / p.min_per_game
    p["mt"] = p.min_per_game * p.games
    agg = p.groupby(["season", "team"]).apply(
        lambda g: pd.Series({"tp": (g.ppm * g.mt).sum(), "tm": g.mt.sum()}),
        include_groups=False)
    p = p.merge(agg, left_on=["season", "team"], right_index=True)
    p["mates"] = ((p.tp - p.ppm * p.mt) /
                  (p.tm - p.mt).replace(0, np.nan))
    return p


def fit_crowding(ps, max_season):
    """Δppm = α + β·Δmates, על מעברי מועדון בעונות אימון בלבד.

    ההפרש הראשון מנטרל את **כל** מה שקבוע בשחקן — כישרון, עמדה,
    סגנון. מה שנשאר הוא תגובת התפוקה לשינוי בסביבה.

    מוגבל למעברים: שם ה-Δ בסביבה גדול ואקסוגני יחסית. בתוך אותו
    מועדון שינוי בחברים לרוב **נובע** מהשחקן עצמו.
    """
    p = mates_panel(ps, max_season).sort_values(["player_code", "season"])
    g = p.groupby("player_code")
    for c in ("ppm", "mates", "team", "season", "mt", "age"):
        p[c + "_l"] = g[c].shift(1)
    d = p[(p.season - p.season_l == 1) & p.ppm_l.notna() & p.mates.notna()
          & p.mates_l.notna() & (p.mt > MIN_MIN) & (p.mt_l > MIN_MIN)].copy()
    mv = d[d.team != d.team_l].copy()
    mv["dppm"] = mv.ppm - mv.ppm_l
    mv["dmates"] = mv.mates - mv.mates_l
    mv["dage"] = mv.age - mv.age_l
    # 🔴 בקרת חזרה לממוצע. בלעדיה β עלול להיות מזויף: שחקן עם עונה
    #    חריגה כלפי מעלה נחתם בקבוצה חזקה (Δחברים חיובי) וגם נסוג
    #    לממוצע — וזה ייצר β<0 בלי שום מנגנון צפיפות.
    #    נבדק: הקורלציה (ppm קודם גבוה , מעבר לקבוצה חזקה) = +0.023
    #    (p=0.74), ו-β כמעט לא זז: -0.604 -> -0.584. החשש נשלל,
    #    אבל הבקרה נשארת.
    lg = float((mv.ppm_l * mv.mt_l).sum() / mv.mt_l.sum())
    mv["ppm_l_dev"] = mv.ppm_l - lg
    X = sm.add_constant(mv[["dmates", "dage", "ppm_l_dev"]].astype(float))
    m = sm.OLS(mv.dppm, X).fit()
    r, pv = stats.pearsonr(mv.dmates, mv.dppm)
    return m, mv, r, pv


def _alloc(ppm, av, pos):
    """הדקות ש-score_rows מקצה בפועל. אותה לוגיקה בדיוק."""
    caps = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
            for g in ro.POS_MAX_SHARE}
    left, m = ro.MINUTES_PER_GAME, np.zeros(len(ppm))
    for j in np.argsort(-ppm):
        t = max(min(ro.MAX_MIN_PLAYER, left, caps[pos[j]]) * av[j], 0.0)
        m[j] = t
        left -= t
        caps[pos[j]] -= t
    return m


def apply_crowding(roster, beta, ppm_col, ref_col="mates_ref"):
    """ppm מתוקן לסביבה החדשה: ppm_i + β·(חברים_חדשים − חברים_ישנים).

    🔴 תיקון אחרי ההרצה הראשונה. הגרסה הקודמת שקללה את
       "איכות החברים" ב-`avail·32` — כלומר כאילו **כל** שחקן בסגל
       מקבל 32 דקות. `mates_ref` לעומת זאת משוקלל בדקות **בפועל**.
       שתי יחידות שונות.

       התוצאה: לסגל עמוק (16-20 שחקנים) הזנב הארוך נכנס לממוצע
       במשקל מלא, "איכות החברים" יצאה נמוכה מהאמת, ו-β<0 **העלה**
       למועדונים את ה-ppm. משם +2.1% למועדון — תיקון צפיפות שמשפר
       את מי שסובל מצפיפות. חסר היגיון, וזה מה שהסגיר אותו.

       עכשיו המשקל הוא הדקות ש-score_rows מקצה בפועל. חבריו של
       שחקן הם מי שעל הפרקט איתו, לא מי שרשום בסגל.
    """
    base = roster[ppm_col].values.astype(float)
    ref = roster[ref_col].values.astype(float)
    av = roster.avail_true.values.astype(float)
    pos = roster.position.values
    v = base.copy()
    for _ in range(80):
        w = _alloc(v, av, pos)
        tp, tm = (v * w).sum(), w.sum()
        mates = np.where(w > 0, (tp - v * w) / np.maximum(tm - w, 1e-9),
                         tp / max(tm, 1e-9))
        nv = base + beta * (mates - ref)
        if np.max(np.abs(nv - v)) < 1e-7:
            v = nv
            break
        v = 0.5 * v + 0.5 * nv
    return np.maximum(v, 0.0)


def main():
    print(SEP)
    print("crowding — האם ppm נוסע עם השחקן?")
    print("תחזיות ננעלו לפני ההרצה. ראו ראש הקובץ.")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})

    rows = []
    for train_max, test in SEASONS:
        m, mv, r, pv = fit_crowding(ps, train_max)
        beta = float(m.params["dmates"])
        h(f"עונה {test}   —   מקדם הצפיפות מאומן על <= {train_max}")
        print(f"  n מעברים {len(mv)}   r={r:+.3f} (p={pv:.2g})")
        print(f"  β = {beta:+.3f}   ר\"ס {m.bse['dmates']:.3f}   "
              f"t={m.tvalues['dmates']:+.2f}   R²={m.rsquared:.3f}")
        print(f"  קריאה: עלייה של 0.10 ב-ppm של החברים מורידה "
              f"{-beta*0.10:.3f} מה-ppm של השחקן")

        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        pan = mates_panel(ps)
        ref = pan[pan.season == test].set_index(
            pan[pan.season == test].player_code.astype(str)).mates
        cand["mates_ref"] = cand.pc.map(ref)
        cand["mates_ref"] = cand.mates_ref.fillna(cand.mates_ref.median())

        gmax = float(ps[ps.season == test].games.max())
        print(f"\n  {'מועדון':<7}{'n':>4}{'מועדון':>9}{'מנוע':>9}"
              f"{'יתרון':>9}   |{'מוע.מתוקן':>11}{'מנוע מתוקן':>12}"
              f"{'יתרון':>9}{'חברים':>9}")
        for club in sorted(split[split.season == test].club.unique()):
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                continue
            keep = keep.copy()
            keep["mates_ref"] = keep.pc.map(ref)
            keep["mates_ref"] = keep.mates_ref.fillna(cand.mates_ref.median())
            B = float(keep.cost.sum())
            sel, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
            if sel is None:
                continue
            eng = cand[sel].copy()

            qc, _, _ = score_rows(keep, "ppm_true", "avail_true", REPL)
            qe, _, _ = score_rows(eng, "ppm_true", "avail_true", REPL)

            for df in (keep, eng):
                df["ppm_adj"] = apply_crowding(df, beta, "ppm_true")
            qca, _, _ = score_rows(keep, "ppm_adj", "avail_true", REPL)
            qea, _, _ = score_rows(eng, "ppm_adj", "avail_true", REPL)

            w = _alloc(eng.ppm_true.values.astype(float),
                       eng.avail_true.values.astype(float),
                       eng.position.values)
            mates_new = float((eng.ppm_true * w).sum() / w.sum())
            jump = mates_new - float(eng.mates_ref.mean())

            rows.append(dict(season=test, club=club, n=len(keep), qc=qc, qe=qe,
                             qca=qca, qea=qea, jump=jump, beta=beta))
            print(f"  {club:<7}{len(keep):>4}{qc:>9.1f}{qe:>9.1f}"
                  f"{qe/qc-1:>+9.1%}   |{qca:>11.1f}{qea:>12.1f}"
                  f"{qea/qca-1:>+9.1%}{jump:>+9.3f}")

    d = pd.DataFrame(rows)
    d.to_csv(PROCESSED_DIR / "crowding_results.csv", index=False)
    d["adv"] = d.qe / d.qc - 1
    d["adv_adj"] = d.qea / d.qca - 1

    h("התוצאה")
    print(f"  n = {len(d)}\n")
    print(f"  {'':<22}{'מנצח':>9}{'חציון':>10}{'ממוצע':>10}")
    print(f"  {'לפני תיקון':<22}{float((d.adv>0).mean()):>9.0%}"
          f"{d.adv.median():>+10.1%}{d.adv.mean():>+10.1%}")
    print(f"  {'אחרי תיקון':<22}{float((d.adv_adj>0).mean()):>9.0%}"
          f"{d.adv_adj.median():>+10.1%}{d.adv_adj.mean():>+10.1%}")
    print(f"\n  ירידת ניקוד המנוע  : {(d.qea/d.qe-1).median():+.1%}")
    print(f"  ירידת ניקוד המועדון: {(d.qca/d.qc-1).median():+.1%}")
    print(f"  קפיצת איכות-החברים בסגל המנוע: "
          f"{d.jump.median():+.3f} ppm (חציון)")
    print("\n  מול התחזיות של קלוד:")
    for k, v in PRED_CLAUDE.items():
        print(f"    {k:<16} {v}")
    print(SEP)


if __name__ == "__main__":
    main()