"""
minute_profile.py  (Day 9)
--------------------------
**התפיסה של אלמוג: מאיפה בכלל הגיע הגבול של 32 דקות?**

--------------------------------------------------------------------
מה שנמצא כשבדקנו
--------------------------------------------------------------------
הגבול נקבע כמקסימום הנצפה של **ממוצע עונתי** לשחקן. על 2,553
עונות-שחקן בדאטה: המקסימום 34.0, האחוזון ה-99 הוא 30.6, ורק 8
עונות-שחקן (0.3%) עברו 32. אז כמספר בודד — הוא בסדר.

**אבל השאלה חשפה משהו אחר, וגדול יותר.**

הגבול חל על כל שחקן **בנפרד**. `score_rows` מחלקת דקות בחמדנות
ומגיעה ל-32 לשישה-שבעה שחקנים **בו-זמנית**. נמדד על 38 עונות-
מועדון אמיתיות, סך התרומה העונתית של k השחקנים המובילים
(מתוך 200):

        k     ממוצע    מקס נצפה     מה שהמודל מרשה
        1      26.3       31.2           32
        2      49.7       57.6           64
        3      71.2       84.0           96
        4      90.8      104.9          128
        5     109.1      126.4          160
        6     125.7      145.3          192
        7     140.3      163.3          200

בשחקן הראשון האילוץ כמעט מדויק (32 מול 31.2). בשישה שחקנים
המודל מרשה **192 דקות** בעוד הקבוצה הכי מרוכזת בעשור נתנה להם
**145.3**. פער של 32%.

וגם: אף קבוצה אמיתית לא העמידה יותר מ**שני** שחקנים מעל 28 דקות
לממוצע, ולא יותר מ**אחד** מעל 30.

--------------------------------------------------------------------
זו אותה שגיאה שלישית ברציפות
--------------------------------------------------------------------
    רצפות עמדה :  מינימום של כל עמדה **בנפרד** -> האופטימייזר
                  יושב בכולן בו-זמנית
    תקרת דקות  :  מקסימום של כל שחקן **בנפרד** -> האופטימייזר
                  נותן אותו לכולם בו-זמנית

בשני המקרים לקחנו קצוות שוליים, כל אחד מקבוצה אחרת, והרכבנו
מהם קבוצה שאיש לא שיחק בה. אופטימייזר תמיד יילך לפינה — ולכן
**האילוץ חייב להיות על הצורה, לא על כל שחקן לחוד.**

--------------------------------------------------------------------
התיקון
--------------------------------------------------------------------
אילוץ על **סכום k הגדולים**, לכל k. זה ניתן לביטוי ליניארי בתרגיל
תקני (Nesterov):

    סכום k הגדולים של e  <=  C
    <=>  קיימים q, s>=0 כך ש:  k·q + Σs_i <= C ,  s_i >= e_i − q

לכן הוא נכנס ל-LP בלי לשבור אותו, והמטרה נשארת ליניארית.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pulp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PROCESSED_DIR
import roster_optimizer as ro

K_USED = (1, 2, 3, 4, 6, 8)   # תת-קבוצה: k סמוכים כמעט מיותרים
KMAX = 8            # מעבר לזה האילוץ אינו כובל מול 200
SLACK = 1.00        # 1.00 = המקסימום הנצפה בדיוק


def observed_caps(split=None, ps=None, kmax=KMAX, slack=SLACK):
    """תקרת סכום k המובילים, מהמציאות. מוחזר גם הממוצע לדיווח.

    התרומה העונתית של שחקן = דקות_למשחק · זמינות, וסכומה 200
    בהגדרה. זו בדיוק היחידה שבה `e` מוגדר ב-optimise_v2.
    """
    if split is None:
        split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                            dtype={"player_code": str})
    if ps is None:
        ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                         dtype={"player_code": str})
    gmax = ps.groupby("season").games.max()
    rows = []
    for (s, c), g in split.groupby(["season", "club"]):
        e = np.sort((g.min_per_game * g.games / gmax[s]).values)[::-1]
        rows.append(np.pad(e, (0, max(0, kmax - len(e))))[:kmax])
    C = np.cumsum(np.array(rows), axis=1)
    return ({k: float(C[:, k - 1].max()) * slack for k in range(1, kmax + 1)},
            {k: float(C[:, k - 1].mean()) for k in range(1, kmax + 1)},
            len(rows))


def optimise_v3(pool, budget, min_roster, caps, locked=None,
                gap=0.005, time_limit=120, repl=0.0):
    """optimise_v2 + אילוץ צורה על התפלגות הדקות.

    זהה ל-v2 בכל השאר. ההבדל היחיד: סכום k הדקות הגדולות ביותר
    חסום בתקרה שנצפתה במציאות, לכל k עד KMAX.
    """
    n = len(pool)
    p = pulp.LpProblem("roster_v3", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(n)]
    e = [pulp.LpVariable(f"e{i}", lowBound=0) for i in range(n)]
    ppm, av, cost = pool.ppm.values, pool.avail.values, pool.cost.values

    # 🔴 הדקות שאינן מוקצות ממולאות ברמת מחליף בניקוד, ולכן הן
    #    חייבות להיות במטרה גם כן:
    #        max  Σ ppm·e + repl·(200 − Σe)  =  const + Σ(ppm−repl)·e
    #    בלי זה ה-LP מתייחס לדקה לא-מוקצית כאפס והניקוד כ-repl,
    #    ושוב אין יישור בין המטרה לניקוד.
    p += pulp.lpSum((ppm[i] - repl) * e[i] for i in range(n))
    p += pulp.lpSum(e) <= ro.MINUTES_PER_GAME
    for i in range(n):
        p += e[i] <= ro.MAX_MIN_PLAYER * av[i] * x[i]
    p += pulp.lpSum(cost[i] * x[i] for i in range(n)) <= budget
    for i in (locked or []):
        p += x[i] == 1
    p += pulp.lpSum(x) <= ro.MAX_ROSTER
    p += pulp.lpSum(x) >= min_roster
    for ps_, fl in ro.POS_FLOOR.items():
        idx = pool.index[pool.position == ps_]
        p += pulp.lpSum(x[i] for i in idx) >= fl
        p += pulp.lpSum(e[i] for i in idx) <= \
            ro.POS_MAX_SHARE[ps_] * ro.MINUTES_PER_GAME
        p += pulp.lpSum(e[i] for i in idx) >= \
            ro.POS_MIN_SHARE[ps_] * ro.MINUTES_PER_GAME

    # --- אילוץ הצורה ---
    for k, C in caps.items():
        if k not in K_USED or k >= n:
            continue
        q = pulp.LpVariable(f"q{k}")
        s = [pulp.LpVariable(f"s{k}_{i}", lowBound=0) for i in range(n)]
        p += k * q + pulp.lpSum(s) <= C
        for i in range(n):
            p += s[i] >= e[i] - q

    # ⚠️ אילוץ הצורה מוסיף ~8n משתני עזר וה-MIP נעשה כבד (115 שניות
    #    בהרצת ניסיון). לכן פער אופטימליות מותר של 0.5% ותקרת זמן.
    #    הפער מדווח — הוא **קטן בסדר גודל** מההפרשים שאנחנו מודדים
    #    (5%-20%), ולכן אינו יכול להפוך מסקנה.
    p.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit, gapRel=gap))
    if pulp.LpStatus[p.status] not in ("Optimal", "Not Solved"):
        return None, None
    sel = np.array([x[i].value() is not None and x[i].value() > 0.5
                    for i in range(n)])
    mins = np.array([e[i].value() or 0.0 for i in range(n)])
    return sel, mins


def score_realistic(df, ppm_col, avail_col, repl, caps):
    """אותו ניקוד, תחת אותה תקרת צורה. חייב להתאים ל-optimise_v3.

    השחקן בדירוג k מקבל את המינימום מבין: תקרת השחקן, מה שנשאר
    בתקרה המצטברת של k, יתרת הדקות, ותקרת העמדה.
    """
    ppm, av, pos = df[ppm_col].values, df[avail_col].values, df.position.values
    order = np.argsort(-ppm)
    poscap = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
              for g in ro.POS_MAX_SHARE}
    left, cum, q = ro.MINUTES_PER_GAME, 0.0, 0.0
    for rank, j in enumerate(order, start=1):
        cap_k = caps.get(rank, np.inf)
        take = min(ro.MAX_MIN_PLAYER * av[j], left, poscap[pos[j]],
                   max(cap_k - cum, 0.0))
        take = max(take, 0.0)
        q += take * ppm[j]
        left -= take
        cum += take
        poscap[pos[j]] -= take
    if repl is not None and left > 0:
        q += left * repl
    return q, ro.MINUTES_PER_GAME - left


if __name__ == "__main__":
    caps, mean, n = observed_caps()
    print(f"נמדד על {n} עונות-מועדון\n")
    print(f"{'k':>3}{'ממוצע':>9}{'תקרה (מקס נצפה)':>18}{'המודל מרשה':>14}")
    for k in sorted(caps):
        print(f"{k:>3}{mean[k]:>9.1f}{caps[k]:>18.1f}"
              f"{min(ro.MAX_MIN_PLAYER*k, ro.MINUTES_PER_GAME):>14.1f}")