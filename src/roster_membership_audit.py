"""
roster_membership_audit.py  (Day 7)
-----------------------------------
מי בכלל נחשב ל"סגל המועדון" בבנצ'מרק — וכמה זה משנה.

--------------------------------------------------------------------
למה הקובץ הזה קיים
--------------------------------------------------------------------
ב-optimizer_backtest, סגל מועדון היעד מוגדר כך:

    real = cand[cand.team.astype(str).str.contains("TEL")]

זו הגדרה שנשענת על **מחרוזת**, לא על חברות. אלמוג תפס את הקצה
הגלוי שלה ביום 6: ג'ורדן לויד נכנס לסגל מכבי 2024 עם 22.8 דקות
למשחק, בזמן שהוא שיחק **משחק אחד** ועזב. השורה העונתית שלו היא
MCO;TEL — צבירה על פני שני מועדונים.

הקובץ הזה מפריד את השאלה לשלוש שאלות שנמדדות בנפרד:

  א. **הגדרה**  — מי נספר כסגל, תחת ארבע הגדרות חלופיות
  ב. **ניקוד**  — כמה הניקוד של הבנצ'מרק משתנה לפי ההגדרה
  ג. **תקציב**  — האם צד הכסף וצד התפוקה מתארים את אותם אנשים

ג' הוא הכשל השיטתי מסעיף 16 של יום 6: לדווח מספר לפני שווידאתי
ששני צדי ההשוואה עומדים על אותו בסיס.

הרצה:
    python src/roster_membership_audit.py
"""

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

CLUB = "TEL"
SEASON = 2024
SEP = "=" * 78


def h(t):
    print("\n" + SEP + f"\n{t}\n" + SEP)


def score_rows(df, ppm_col, avail_col, repl):
    """אותה פונקציית ניקוד של optimizer_backtest, על DataFrame חופשי.

    משוכפלת במכוון ולא מיובאת: כאן הקלט אינו בהכרח cand, ואני רוצה
    שהאודיט לא יוכל להישבר בשקט אם החתימה שם תשתנה.
    """
    ppm = df[ppm_col].values
    av = df[avail_col].values
    pos = df.position.values
    order = np.argsort(-ppm)
    caps = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME for g in ro.POS_MAX_SHARE}
    left = ro.MINUTES_PER_GAME
    q = 0.0
    used = 0.0
    for j in order:
        g = pos[j]
        take = max(min(ro.MAX_MIN_PLAYER, left, caps[g]) * av[j], 0.0)
        q += take * ppm[j]
        left -= take
        caps[g] -= take
        used += take
    filled = 0.0
    if repl is not None and left > 0:
        filled = left * repl
        q += filled
    return q, used, filled


def main():
    print(SEP)
    print(f"ROSTER MEMBERSHIP AUDIT — {CLUB} {SEASON}")
    print("שלוש שאלות נפרדות: הגדרה / ניקוד / תקציב")
    print(SEP)

    feat, anch, pos, ps = ob.load_all()
    with contextlib.redirect_stdout(io.StringIO()):
        cm, smear, agg, am, pm, PF, lagged = ob.fit_models(ps, feat, anch)
        cand = ob.build(lagged, feat, pos, cm, smear, agg, am, pm, PF,
                        ob.scale_for(anch, CLUB, SEASON))
    cand["ppm_true"] = cand.pir_per_game / cand.min_per_game
    cand["avail_true"] = cand.frac

    # ------------------------------------------------------------------
    # א. ההגדרה
    # ------------------------------------------------------------------
    h("א. ההגדרה — מי נספר כסגל")

    a = anch[(anch.club == CLUB) & (anch.season == SEASON)]
    anchor_codes = set(a.player_code.dropna().astype(str))

    season_rows = ps[ps.season == SEASON].copy()
    season_rows["team_s"] = season_rows.team.astype(str)
    contains = season_rows[season_rows.team_s.str.contains(CLUB, na=False)]
    solo = contains[contains.team_s == CLUB]
    multi = contains[contains.team_s != CLUB]

    print(f"  עוגני שכר ל-{CLUB} {SEASON}                     {len(a):>3}")
    print(f"  שורות עונתיות שהמחרוזת מכילה {CLUB}         {len(contains):>3}")
    print(f"    מתוכן מועדון יחיד                     {len(solo):>3}")
    print(f"    מתוכן צבירה על פני מועדונים           {len(multi):>3}")

    if len(multi):
        print(f"\n  ⚠️ שורות רב-מועדוניות — הדקות וה-PIR אינם של {CLUB}:")
        print(f"    {'שחקן':<26}{'team':<12}{'משחקים':>8}{'דק/מש':>9}"
              f"{'PIR/מש':>9}{'עוגן?':>8}")
        for t in multi.sort_values("min_per_game", ascending=False).itertuples():
            flag = "כן" if str(t.player_code) in anchor_codes else "**לא**"
            print(f"    {str(t.player_name)[:24]:<26}{t.team:<12}"
                  f"{t.games:>8.0f}{t.min_per_game:>9.1f}"
                  f"{t.pir_per_game:>9.1f}{flag:>8}")

    in_cand = set(cand.player_code.astype(str))
    real_str = cand[cand.team.astype(str).str.contains(CLUB, na=False)]

    print(f"\n  הבנצ'מרק כפי שהוא היום (str.contains ∩ מאגר): "
          f"{len(real_str)} שחקנים")

    missing = a[~a.player_code.astype(str).isin(in_cand)]
    if len(missing):
        mrows = season_rows[season_rows.player_code.astype(str).isin(
            set(missing.player_code.astype(str)))]
        print(f"\n  🔴 עוגנים שנשרו מהמאגר ולכן **אינם** בבנצ'מרק: "
              f"{len(missing)}")
        print(f"    {'שחקן':<26}{'שכר':>12}{'דק/מש':>9}{'PIR/מש':>9}"
              f"  סיבת הנשירה")
        for t in missing.itertuples():
            r = mrows[mrows.player_code.astype(str) == str(t.player_code)]
            mpg = float(r.min_per_game.iloc[0]) if len(r) else float("nan")
            pir = float(r.pir_per_game.iloc[0]) if len(r) else float("nan")
            has_pos = str(t.player_code) in set(pos.player_code.astype(str))
            prev = ps[(ps.player_code.astype(str) == str(t.player_code)) &
                      (ps.season == SEASON - 1)]
            why = ("אין עונה קודמת ביורוליג" if prev.empty
                   else ("אין עמדה" if not has_pos else "אחר"))
            print(f"    {str(t.player_name_el)[:24]:<26}{t.salary_mid:>12,.0f}"
                  f"{mpg:>9.1f}{pir:>9.1f}  {why}")

    intruders = real_str[~real_str.player_code.astype(str).isin(anchor_codes)]
    if len(intruders):
        print(f"\n  🔴 בבנצ'מרק אך **אינם** עוגני שכר: {len(intruders)}")
        for t in intruders.itertuples():
            nm = season_rows[season_rows.player_code.astype(str)
                             == str(t.player_code)]
            nm = str(nm.player_name.iloc[0]) if len(nm) else str(t.player_code)
            print(f"    {nm[:24]:<26}{'team=' + str(t.team):<16}"
                  f"עלות אמודה {t.cost:>12,.0f}")

    # ------------------------------------------------------------------
    # ב. הניקוד
    # ------------------------------------------------------------------
    h("ב. הניקוד — כמה ההגדרה שווה ביחידות איכות")

    posmap = pos.set_index(pos.player_code.astype(str)).position
    base = season_rows.copy()
    base["pc"] = base.player_code.astype(str)
    gmax = float(ps[ps.season == SEASON].games.max())
    base = base[base.min_per_game > 0].copy()
    base["ppm_true"] = base.pir_per_game / base.min_per_game
    base["avail_true"] = base.games / gmax
    base["position"] = base.pc.map(posmap)

    rt = float(np.percentile(cand.ppm_true.values, ro.REPLACEMENT_PCTL))

    defs = {
        "A. str.contains (הנוכחי, ∩ מאגר)":
            cand[cand.team.astype(str).str.contains(CLUB, na=False)],
        "B. מועדון יחיד בלבד (∩ מאגר)":
            cand[cand.team.astype(str) == CLUB],
        "C. עוגני שכר ∩ מאגר":
            cand[cand.player_code.astype(str).isin(anchor_codes)],
        "D. כל עוגני השכר (מחוץ למאגר)":
            base[base.pc.isin(anchor_codes) & base.position.notna()],
    }

    print(f"  רמת החלפה (אחוזון {ro.REPLACEMENT_PCTL} של ppm בפועל) = {rt:.4f}")
    print(f"\n  {'הגדרה':<36}{'n':>4}{'ניקוד':>10}{'דק שמולאו':>12}"
          f"{'מילוי החלפה':>14}")
    scores = {}
    for lab, df in defs.items():
        if not len(df):
            print(f"  {lab:<36}{'—':>4}   ריק")
            continue
        q, used, filled = score_rows(df, "ppm_true", "avail_true", rt)
        scores[lab] = q
        print(f"  {lab:<36}{len(df):>4}{q:>10.1f}{used:>12.1f}"
              f"{filled:>14.1f}")

    kA = "A. str.contains (הנוכחי, ∩ מאגר)"
    kD = "D. כל עוגני השכר (מחוץ למאגר)"
    if kA in scores and kD in scores:
        print(f"\n  🔴 ההגדרה הנוכחית מנמיכה את מכבי ב-"
              f"{scores[kA] / scores[kD] - 1:+.1%} מול הסגל האמיתי.")
        print("     כל מספר 'מול המועדון' שדווח עד היום נמדד מול")
        print("     בנצ'מרק חסר.")

    # ------------------------------------------------------------------
    # ג. התקציב
    # ------------------------------------------------------------------
    h("ג. התקציב — האם צד הכסף וצד התפוקה הם אותם אנשים")

    known, imputed, miss = ob.fair_budget(cand, anch, CLUB, SEASON,
                                          cm, smear, None)
    B_full = float(a.salary_mid.sum())
    scored_codes = set(real_str.player_code.astype(str))
    priced_codes = set(a[a.player_code.astype(str).isin(in_cand)]
                       .player_code.astype(str))

    print(f"  שולם עליהם (known)     : {len(priced_codes):>2} שחקנים  "
          f"{known:>12,.0f}")
    print(f"  אומדן לחסרי שכר        : {len(miss):>2} שחקנים  "
          f"{imputed:>12,.0f}")
    print(f"  סה\"כ 'תקציב מושווה'    : {len(priced_codes) + len(miss):>2} "
          f"שחקנים  {known + imputed:>12,.0f}")
    print(f"  תקציב מלא (כל העוגנים) : {len(a):>2} שחקנים  "
          f"{B_full:>12,.0f}")

    only_scored = scored_codes - priced_codes
    only_priced = priced_codes - scored_codes
    print(f"\n  נוקדו אך לא שולם עליהם : {len(only_scored)}")
    print(f"  שולם עליהם אך לא נוקדו : {len(only_priced)}")
    inter = len(scored_codes & priced_codes)
    union = len(scored_codes | priced_codes)
    print(f"  חפיפה (Jaccard)        : {inter}/{union} = {inter / union:.2f}")
    if only_scored or only_priced:
        print("\n  🔴 שני צדי ההשוואה אינם אותה קבוצת אנשים.")
        print("     זה בדיוק הדפוס של סעיף 16 ביום 6.")

    print(SEP)


if __name__ == "__main__":
    main()
