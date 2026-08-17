"""
curse_redistribution.py  (Day 7 -> 8)
-------------------------------------
כמה מקללת המנצח היא ממצא, וכמה היא ארטיפקט של מודד שלא מחליף
שחקן.

--------------------------------------------------------------------
השאלה
--------------------------------------------------------------------
`score_rows` — המודד ששימש לכל מספרי הבקטסט — נותן לכל שחקן

    take(i) = min(32, נותר, תקרת_עמדה) · avail(i)

כלומר שחקן שנעדר **מאבד את הדקות** והן נופלות לרמת מחליף.
זה מודד שלא יודע להחליף שחקן.

`avail_uncertainty` (יום 7) גילה שהמונטה קרלו, שכן מחלק דקות
מחדש, כמעט אינו מושפע מאי-ודאות בזמינות — גם עם rho=0.30
(ס"ת 0.228 סביב שיעור של 0.78) הניקוד זז ב-0.5% בלבד, כי סגל
של 12 ממלא 200 דקות ב-93% מהמשחקים.

**אלמוג:** *"מאמן אמיתי סופג ונותן לשחקנים מוכחים יותר דקות
מאשר לשחקנים פחות טובים."*

אם הוא צודק, אז שגיאות זמינות שהמודד הדטרמיניסטי מעניש עליהן
פשוט לא היו קורות — והקללה שדיווחנו מנופחת.

--------------------------------------------------------------------
המבחן
--------------------------------------------------------------------
אותו סגל, שני מודדים, ארבעה ניקודים:

                    לפי המודל          לפי המציאות
    דטרמיניסטי      ppm, avail         ppm_true, avail_true
    מחלק מחדש       ppm, avail         ppm_true, avail_true

`ppm_sd = 0` בשני המקרים — מבודדים את **מנגנון הזמינות** ולא
מוסיפים רעש תפוקה.

--------------------------------------------------------------------
תחזיות — ננעלו לפני ההרצה
--------------------------------------------------------------------
"""

# ====================================================================
# ננעל ב-17.8.2026, לפני ההרצה. אין לערוך בדיעבד.
# ====================================================================
PRED_ALMOG = "half_disappears"
PRED_ALMOG_COACH = "to_proven"

PRED_CLAUDE = "converge_not_shrink"
PRED_CLAUDE_WHY = (
    "הקללה לא תתכווץ אחידה — היא תתכנס. בפירוק של יום 7 רכיב "
    "הזמינות תרם בסימנים הפוכים: +3.2 אצל מכבי, -2.0 אצל הפועל. "
    "אם חלוקה מחדש בולעת אותו, נשארת קללת ה-ppm בלבד, והיא כמעט "
    "זהה בשניהם (הטיית בחירה -0.048 מול -0.040). לכן: מכבי "
    "**תגדל** מ--7.3%, הפועל **תתכווץ** מ--11.1%, ושתיהן ינחתו "
    "בין -7% ל--10%."
)
PRED_CLAUDE_COACH = "to_proven_but_position_caps_divert_20_30pct"
PRED_CLAUDE_COACH_WHY = (
    "מסכים עם אלמוג בכיוון, אבל תקרות העמדה חוסמות: אם סנטר "
    "נעדר, אי אפשר להעביר את דקותיו לגארד מוכח (תקרה C<=28.2%). "
    "צופה ש-20-30% מהדקות המשוחררות יורדות לשחקן חלש יותר "
    "**באותה עמדה**."
)

CONVERGE_MAX_GAP = 0.04   # פער בין התרחישים מתחת לזה = התכנסות
# ====================================================================

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
from final_day7 import prep, bench, MIN_LEGAL_ROSTER

SEP = "=" * 78
DRAWS = 600
GAMES = ro.GAMES_PER_SEASON
SEED = 20260817
REPL = 0.127


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def redistribute(ppm, avail, positions, repl, rng, draws=DRAWS,
                 games=GAMES, keep_minutes=False):
    """מודד שמחלק דקות מחדש: בכל משחק, מי שנוכח מקבל דקות לפי
    סדר ה-ppm עד תקרה של 32 ותקרות עמדה. מה שנשאר — רמת מחליף.

    זה מה ש`ro.simulate` עושה, בלי רעש התפוקה. הפרמטר היחיד
    שמשתנה מול `score_rows` הוא **מה קורה לדקות של הנעדר**.
    """
    n = len(ppm)
    caps = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
            for g in ro.POS_MAX_SHARE}
    order = np.argsort(-np.asarray(ppm))
    pp = np.asarray(ppm)[order]
    av = np.clip(np.asarray(avail, float), 0, 1)[order]
    pos = np.asarray(positions)[order]

    out = np.empty(draws)
    mins_by_absent = {}          # מס' נעדרים -> סכום דקות לפי דירוג
    cnt_by_absent = {}
    for k in range(draws):
        a = rng.random((games, n)) < av
        total_left = np.full(games, ro.MINUTES_PER_GAME)
        grp_left = {g: np.full(games, caps[g]) for g in caps}
        q = np.zeros(games)
        used = np.zeros(games)
        M = np.zeros((games, n))
        for j in range(n):
            g = pos[j]
            take = np.minimum(np.minimum(ro.MAX_MIN_PLAYER, total_left),
                              grp_left[g]) * a[:, j]
            M[:, j] = take
            q += take * pp[j]
            used += take
            total_left -= take
            grp_left[g] -= take
        q += (ro.MINUTES_PER_GAME - used) * repl
        out[k] = q.mean()
        if keep_minutes:
            # 🔴 תיקון: חייבים להתנות על כך שהשחקן **נוכח**.
            # הגרסה הראשונה מיצעה על כל המשחקים, כולל אלה שבהם
            # השחקן עצמו נעדר ודקותיו 0 — כלומר ערבבה "נעדר" עם
            # "נוכח ומשחק פחות", ואז כל שורה ירדה והמבחן היה
            # חסר משמעות.
            absent = (~a).sum(axis=1)
            for lvl in np.unique(absent):
                m = absent == lvl
                pres = a[m]                       # (games_lvl, n) בוליאני
                mins_by_absent[lvl] = (mins_by_absent.get(lvl, 0)
                                       + (M[m] * pres).sum(axis=0))
                cnt_by_absent[lvl] = (cnt_by_absent.get(lvl, 0)
                                      + pres.sum(axis=0))
    if keep_minutes:
        prof = {int(l): np.divide(mins_by_absent[l], cnt_by_absent[l],
                                  out=np.full(n, np.nan),
                                  where=cnt_by_absent[l] >= 40)
                for l in mins_by_absent
                if float(np.nansum(cnt_by_absent[l])) >= 200}
        return out, prof, pos
    return out


def main():
    print(SEP)
    print("קללת המנצח — ממצא או ארטיפקט של מודד?")
    print("תחזיות ננעלו לפני ההרצה. ראו ראש הקובץ.")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    posmap = pos.set_index(pos.player_code.astype(str)).position
    rows = []

    for club, train_max, test in [("TEL", 2023, 2024), ("HTA", 2024, 2025)]:
        cand = prep(club, train_max, test, feat, anch, pos, ps)
        r = cr.roster_df(club, test)
        B = float(r.salary.dropna().sum()) + cr.budget_only_total(club, test)
        sel, _ = optimise_v2(cand, B, MIN_LEGAL_ROSTER)
        rr = cand[sel]
        bq, _, _, _, _ = bench(club, test, ps, posmap, REPL)

        # --- דטרמיניסטי ---
        d_mod, _, _ = score_rows(rr, "ppm", "avail", REPL)
        d_real, _, _ = score_rows(rr, "ppm_true", "avail_true", REPL)

        # --- מחלק מחדש ---
        rg = lambda: np.random.default_rng(SEED)          # noqa: E731
        r_mod = float(np.median(redistribute(
            rr.ppm.values, rr.avail.values, rr.position.values, REPL, rg())))
        r_real = float(np.median(redistribute(
            rr.ppm_true.values, rr.avail_true.values, rr.position.values,
            REPL, rg())))

        h(f"{club} {test}   סגל {len(rr)}   מועדון {bq:.1f}")
        print(f"  {'מודד':<16}{'לפי המודל':>12}{'לפי המציאות':>14}"
              f"{'קללה':>10}")
        print(f"  {'דטרמיניסטי':<16}{d_mod:>12.1f}{d_real:>14.1f}"
              f"{d_real / d_mod - 1:>+9.1%}")
        print(f"  {'מחלק מחדש':<16}{r_mod:>12.1f}{r_real:>14.1f}"
              f"{r_real / r_mod - 1:>+9.1%}")
        rows.append(dict(club=club, det=d_real / d_mod - 1,
                         red=r_real / r_mod - 1))

        # --- מבחן המאמן ---
        _, prof, pcs = redistribute(
            rr.ppm_true.values, rr.avail_true.values, rr.position.values,
            REPL, rg(), keep_minutes=True)
        # ניגוד מייצג ולא הזנב: מעט נעדרים מול בינוני.
        # 7 נעדרים מתוך 12 משאיר חמישה שחקנים — זה לא "מאמן
        # שסופג", זו קבוצה משותקת.
        lvls = sorted(prof)
        lo_l = lvls[0]
        hi_l = min([l for l in lvls if l >= lo_l + 3] or [lvls[-1]])
        base, many = prof[lo_l], prof[hi_l]
        k = min(3, len(base))
        print(f"\n  מבחן המאמן — דקות **בתנאי שהשחקן נוכח**:")
        print(f"    {'דירוג':>6}{'עמדה':>7}{str(lo_l) + ' נעדרים':>12}"
              f"{str(hi_l) + ' נעדרים':>12}{'שינוי':>9}")
        for j in range(min(7, len(base))):
            if np.isnan(base[j]) or np.isnan(many[j]):
                continue
            print(f"    {j + 1:>6}{pcs[j]:>7}{base[j]:>12.1f}"
                  f"{many[j]:>12.1f}{many[j] - base[j]:>+9.1f}")
        d = np.nan_to_num(many - base)
        top_gain = float(np.sum(np.maximum(d[:k], 0)))
        rest_gain = float(np.sum(np.maximum(d[k:], 0)))
        tot = top_gain + rest_gain
        if tot > 0:
            print(f"\n    מהדקות שנוספו: {top_gain / tot:.0%} ל-{k} "
                  f"המובילים | {rest_gain / tot:.0%} לשאר "
                  f"(סה\"כ {tot:.1f} דק')")
        else:
            print("\n    אף שחקן לא הרוויח דקות — כולם כבר בתקרה.")

    h("הכרעת התחזיות")
    df = pd.DataFrame(rows)
    print(df.to_string(index=False, float_format=lambda v: f"{v:+.1%}"))
    gap_det = abs(df.det.iloc[0] - df.det.iloc[1])
    gap_red = abs(df.red.iloc[0] - df.red.iloc[1])
    print(f"\n  פער בין התרחישים: דטרמיניסטי {gap_det:.1%} -> "
          f"מחלק מחדש {gap_red:.1%}")
    shrink = [1 - abs(b) / abs(a) for a, b in zip(df.det, df.red)]
    print(f"  שיעור הקללה שנעלם: "
          + " | ".join(f"{c} {s:+.0%}" for c, s in zip(df.club, shrink)))
    print(f"\n  אלמוג ניבא : {PRED_ALMOG} (כחצי תיעלם)")
    print(f"  קלוד ניבא  : {PRED_CLAUDE} (התכנסות, לא כיווץ)")
    if gap_red < gap_det and gap_red < CONVERGE_MAX_GAP:
        print("  -> התרחישים התכנסו. **קלוד צדק.**")
    elif all(s > 0.35 for s in shrink):
        print("  -> הקללה התכווצה מהותית בשניהם. **אלמוג צדק.**")
    else:
        print("  -> אף אחת מהתחזיות לא מתאשרת נקי.")
    print(SEP)


if __name__ == "__main__":
    main()
