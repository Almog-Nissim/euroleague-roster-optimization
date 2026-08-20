"""
score_to_wins.py  (Day 9)
-------------------------
**המספר היחיד בפרויקט שאפשר להגיד למישהו מבחוץ.**

--------------------------------------------------------------------
למה זה נדרש
--------------------------------------------------------------------
"המנוע מייצר סגל עם ניקוד גבוה ב-17.8%" לא אומר כלום למאמן, ולא
למנהל מקצועי, ולא לבוחן. הניקוד הוא יחידה פנימית שהמצאנו.

"המנוע היה מוסיף 3 ניצחונות" — זה משפט שאפשר לבדוק, להתווכח איתו,
ולהיעלב ממנו.

וזה גם המבחן האמיתי לשאלה אם בכלל שווה להמשיך: אם +17.8% בניקוד
שווה חצי ניצחון, התקרה של הפרויקט קרובה מאוד.

--------------------------------------------------------------------
שני תרגומים בלתי תלויים
--------------------------------------------------------------------
**א. ברמת המדד שלנו (n=38).** לכל עונת-מועדון: הניקוד של הסגל
   האמיתי מול מספר הניצחונות בפועל. השיפוע נותן "ניצחונות ליחידת
   ניקוד", ומכפילים בפער שהמנוע מייצר.

**ב. ברמת ה-PIR הגולמי (n=158).** אותה שאלה על כל הדאטה, בלי
   תלות בפונקציית הניקוד שלנו. אם שני התרגומים נותנים מספרים
   דומים — התוצאה יציבה.

הכל מנורמל **בתוך עונה**: 2016-2023 שיחקו 30-34 מחזורים ו-2025
שיחקה 38. בלי נרמול הרגרסיה מודדת את לוח המשחקים.

--------------------------------------------------------------------
⚠️ האזהרה שחייבת ללוות כל מספר שייצא מכאן
--------------------------------------------------------------------
הקשר ניקוד->ניצחונות נאמד **בין מועדונים**, לא בתוך מועדון. מועדון
עם ניקוד גבוה הוא גם מועדון עשיר, עם מאמן טוב יותר, עם תשתית
טובה יותר. השיפוע סופג את כל אלה.

להחיל אותו על **סגל נגדי לאותו מועדון** זו קפיצה סיבתית. המספר
שיצא הוא **חסם עליון** על התרומה של ההקצאה, לא אומדן שלה.

זו לא הסתייגות פורמלית: זו הסיבה שהמספר יהיה גדול מדי.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
PRED_CLAUDE = dict(
    wins="+2 עד +4 ניצחונות בעונה של 34-38 משחקים",
    r2="0.35 .. 0.50   הניקוד מסביר פחות מחצי מהשונות",
    agreement="שני התרגומים יתנו מספרים בטווח של 30% זה מזה",
)
PRED_ALMOG = dict()
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
import optimizer_backtest as ob
from league_backtest import build_pool, club_side, REPL, SEASONS
from optimise_consistent import optimise_v2
from roster_membership_audit import score_rows
from final_day7 import MIN_LEGAL_ROSTER

SEP = "=" * 92


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def z(x):
    return (x - x.mean()) / x.std(ddof=1)


def build_38():
    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                        dtype={"player_code": str})
    rows = []
    for train_max, test in SEASONS:
        cand, _ = build_pool(test, train_max, feat, anch, pos, ps)
        gmax = float(ps[ps.season == test].games.max())
        for club in sorted(split[split.season == test].club.unique()):
            keep, _ = club_side(cand, split, club, test, gmax, posmap)
            if len(keep) < MIN_LEGAL_ROSTER:
                continue
            B = float(keep.cost.sum())
            sel, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
            if sel is None:
                continue
            rows.append(dict(
                season=test, team=club,
                q_club=score_rows(keep, "ppm_true", "avail_true", REPL)[0],
                q_eng=score_rows(cand[sel], "ppm_true", "avail_true",
                                 REPL)[0]))
    return pd.DataFrame(rows)


def slope_ci(x, y, n=4000, seed=0):
    rng = np.random.default_rng(seed)
    b = []
    for _ in range(n):
        i = rng.integers(0, len(x), len(x))
        b.append(np.polyfit(x.values[i], y.values[i], 1)[0])
    return np.percentile(b, [2.5, 97.5])


def main():
    print(SEP)
    print("score_to_wins — כמה ניצחונות שווה היתרון")
    print("תחזיות ננעלו. ראו ראש הקובץ.")
    print(SEP)

    ts = pd.read_csv(PROCESSED_DIR / "team_season.csv")

    # ---------------------------------------------------------------
    h("א. התרגום על המדד שלנו   (n=38)")
    d = build_38().merge(
        ts[["season", "team", "wins", "win_pct", "team_games"]],
        on=["season", "team"], how="inner")
    print(f"  n = {len(d)}   משחקים בעונה: "
          f"{sorted(d.team_games.unique())}")
    d["qz"] = d.groupby("season").q_club.transform(z)
    d["wz"] = d.groupby("season").win_pct.transform(z)
    r, p = stats.pearsonr(d.qz, d.wz)
    print(f"  קורלציה (ניקוד המועדון , אחוז ניצחונות) = {r:+.3f} "
          f"(p={p:.2g})   R² = {r**2:.3f}")

    # שיפוע ביחידות טבעיות: ניצחונות לנקודת ניקוד, בתוך עונה
    d["w_dev"] = d.wins - d.groupby("season").wins.transform("mean")
    d["q_dev"] = d.q_club - d.groupby("season").q_club.transform("mean")
    sl = float(np.polyfit(d.q_dev, d.w_dev, 1)[0])
    lo, hi = slope_ci(d.q_dev, d.w_dev)
    print(f"  שיפוע: {sl:.3f} ניצחונות לנקודת ניקוד   "
          f"CI95 [{lo:.3f}, {hi:.3f}]")

    gap = float((d.q_eng - d.q_club).median())
    gap_pct = float((d.q_eng / d.q_club - 1).median())
    print(f"\n  פער הניקוד שהמנוע מייצר: {gap:+.1f} נקודות "
          f"({gap_pct:+.1%}, חציון)")
    print(f"  -> **{sl*gap:+.2f} ניצחונות**   "
          f"CI95 [{lo*gap:+.2f}, {hi*gap:+.2f}]")
    g0 = float(d.team_games.median())
    print(f"     כלומר {sl*gap/g0:+.1%} מהמשחקים בעונה של {g0:.0f}")

    # ---------------------------------------------------------------
    h("ב. תרגום בלתי תלוי — PIR גולמי   (n=158)")
    t2 = ts.dropna(subset=["sum_pir", "wins"]).copy()
    t2["pz"] = t2.groupby("season").pir_per_round.transform(z)
    t2["wz"] = t2.groupby("season").win_pct.transform(z)
    r2_, p2 = stats.pearsonr(t2.pz, t2.wz)
    print(f"  n = {len(t2)}   קורלציה = {r2_:+.3f} (p={p2:.2g})   "
          f"R² = {r2_**2:.3f}")
    t2["w_dev"] = t2.wins - t2.groupby("season").wins.transform("mean")
    t2["p_dev"] = (t2.pir_per_round
                   - t2.groupby("season").pir_per_round.transform("mean"))
    sl2 = float(np.polyfit(t2.p_dev, t2.w_dev, 1)[0])
    lo2, hi2 = slope_ci(t2.p_dev, t2.w_dev)
    print(f"  שיפוע: {sl2:.3f} ניצחונות ל-PIR למחזור   "
          f"CI95 [{lo2:.3f}, {hi2:.3f}]")
    # הניקוד שלנו הוא PIR למשחק בקירוב -> הפער מתורגם ישירות
    print(f"  אותו פער של {gap:+.1f} -> **{sl2*gap:+.2f} ניצחונות**   "
          f"CI95 [{lo2*gap:+.2f}, {hi2*gap:+.2f}]")

    # ---------------------------------------------------------------
    h("ג. בדיקת שפיות — כמה ניצחונות מפרידים בין המועדונים בפועל")
    for s, g in d.groupby("season"):
        print(f"  {s}: ניצחונות {g.wins.min():.0f}-{g.wins.max():.0f} "
              f"(ס\"ת {g.wins.std():.1f})   "
              f"ניקוד {g.q_club.min():.0f}-{g.q_club.max():.0f} "
              f"(ס\"ת {g.q_club.std():.1f})")
    print(f"\n  אם הפער שהמנוע מייצר ({gap:+.1f} נקודות) קטן מסטיית")
    print("  התקן של הניקוד בין מועדונים — הוא בתוך הרעש, ולא משנה")
    print("  מה השיפוע אומר.")

    # ---------------------------------------------------------------
    h("ד. אזהרה — הכיוון שבו המספר מוטה")
    print("  השיפוע נאמד **בין מועדונים**. מועדון עם ניקוד גבוה הוא")
    print("  גם עשיר יותר, עם מאמן טוב יותר ותשתית טובה יותר, והשיפוע")
    print("  סופג את כל אלה. להחיל אותו על סגל נגדי **לאותו מועדון**")
    print("  זו קפיצה סיבתית.")
    print("\n  בדיקה: כמה מהשיפוע נשאר אחרי בקרת תקציב?")
    bud = pd.read_csv(PROCESSED_DIR / "club_budgets_gemini.csv")
    MAP = {"ברצלונה": "BAR", "צסקא מוסקבה": "CSK", "ריאל מדריד": "MAD",
           "חימקי": "KHI", "מילאנו": "MIL", "פנרבחצה": "ULK",
           "זניט": "DYR", "אנדולו אפס": "IST", 'מכבי ת"א': "TEL",
           "באיירן": "MUN", "באסקוניה": "BAS", "אולימפיאקוס": "OLY",
           "ולנסיה": "PAM", "פנאתינייקוס": "PAN", "ז'לגיריס": "ZAL",
           "ASVEL": "ASV", "אלבה ברלין": "BER", "הכוכב האדום": "RED",
           "מונקו": "MCO", "פרטיזן": "PAR", "וירטוס": "VIR",
           "פריז": "PRS", 'הפועל ת"א': "HTA", "דובאי": "DUB"}
    bud["team"] = bud.club.map(MAP)
    m = d.merge(bud[["season", "team", "gross_eur"]].dropna(),
                on=["season", "team"], how="inner")
    if len(m) >= 10:
        m["lb"] = np.log(m.gross_eur)
        for c in ("q_club", "lb", "wins"):
            m[c + "_d"] = m[c] - m.groupby("season")[c].transform("mean")
        m1 = sm.OLS(m.wins_d, sm.add_constant(m[["q_club_d"]])).fit()
        m2 = sm.OLS(m.wins_d, sm.add_constant(m[["q_club_d", "lb_d"]])).fit()
        print(f"    n={len(m)}   בלי בקרה: {m1.params.q_club_d:.3f}   "
              f"עם בקרת תקציב: {m2.params.q_club_d:.3f}")
        keep_pct = m2.params.q_club_d / m1.params.q_club_d
        print(f"    נשאר {keep_pct:.0%} מהשיפוע   ->  "
              f"**{sl*gap*keep_pct:+.2f} ניצחונות** אחרי הבקרה")
    else:
        print(f"    רק {len(m)} מועדונים עם תקציב — לא ניתן לבקר.")

    h("מול התחזיות של קלוד")
    for k, v in PRED_CLAUDE.items():
        print(f"  {k:<12} {v}")
    print(SEP)


if __name__ == "__main__":
    main()