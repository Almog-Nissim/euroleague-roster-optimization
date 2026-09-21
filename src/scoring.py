"""
scoring.py  (ADR 0005)
----------------------
מקום אחד לאילוץ הצורה ולשני הסקוררים שהוא מחייב.

--------------------------------------------------------------------
למה המודול הזה קיים
--------------------------------------------------------------------
תקרת 32 הדקות חלה על כל שחקן **בנפרד**, והאופטימייזר לוקח אותה
לכולם בו-זמנית: 192 דקות לשישייה, מול 145.3 של הקבוצה הכי מרוכזת
בעשור. האילוץ חייב להיות על **הצורה**.

`add_shape_constraint` הוא המימוש **היחיד** של האילוץ. גם
`optimise_capped` (מסלול הכותרת) וגם `optimise_v3` קוראות לו. שני
מימושים לאילוץ אחד זו הדרך שבה `score_rows` ו-`score()` נהיו שתי
פונקציות לאותו דבר.

--------------------------------------------------------------------
סטייה מ-ADR 0005, מתועדת
--------------------------------------------------------------------
ה-ADR אמר שהמודול הזה יחזיק את הסקורר **במקום** `score_rows`.
בפועל `score_rows` מוגדר פעם אחת ומיובא ב-22 קבצים, ו-
`optimizer_backtest.score` היא פונקציה שנייה עם אותו אלגוריתם ושם
אחר. הזזה נוגעת ב-22 קבצים שבוע לפני freeze, ולכן:

    score_rows            נשאר ב-roster_membership_audit.py. הוא
                          הסקורר החמדני, והוא המכנה **המדווח לצד**
                          הספציפיקציה — לא המכנה שנזרק
    score_shape           כאן. חמדני תחת תקרות הצורה, ומחיל אותן על
                          k הגדולים של e (לא על דירוג ppm — T8)
    score_actual          כאן. המועדון על הדקות שבאמת שוחקו

--------------------------------------------------------------------
הפירוק הליניארי
--------------------------------------------------------------------
    סכום k הגדולים של e  <=  C_k
    <=>  קיימים q, s>=0 כך ש:  k·q + Σs_i <= C_k ,  s_i >= e_i − q

זהות סטנדרטית (Nesterov). נשארת ליניארית, ולכן ה-LP לא נשבר ולא
נוספים בינאריים למטרה.
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

KMAX = 8          # מעבר לזה האילוץ אינו כובל מול 200 (k=8: 176.9)
SLACK = 1.00      # 1.00 = המקסימום הנצפה בדיוק
CAPS_CSV = PROCESSED_DIR / "shape_caps.csv"

# כמה פעמים score_shape נפל לגיבוי. קורא שמדווח תוצאה מדפיס את זה כ-guard.
FALLBACKS = {"no_pos_min": 0, "greedy": 0}


# =====================================================================
# התקרות
# =====================================================================
def observed_caps(split=None, ps=None, kmax=KMAX, slack=SLACK):
    """תקרת סכום k המובילים, מהמציאות, עם עונת-המועדון שהשיגה אותה.

    התרומה העונתית של שחקן = דקות_למשחק · זמינות, וסכומה 200
    בהגדרה. זו בדיוק היחידה שבה `e` מוגדר ב-optimise_v2/capped.

    מחזיר (caps, mean, argmax, n) — argmax נכנס ל-CSV, כי תקרה בלי
    המועדון שהשיג אותה היא מספר בלי provenance.
    """
    if split is None:
        split = pd.read_csv(PROCESSED_DIR / "player_club_season.csv",
                            dtype={"player_code": str})
    if ps is None:
        ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                         dtype={"player_code": str})
    gmax = ps.groupby("season").games.max()
    rows, keys = [], []
    for (s, c), g in split.groupby(["season", "club"]):
        e = np.sort((g.min_per_game * g.games / gmax[s]).values)[::-1]
        rows.append(np.pad(e, (0, max(0, kmax - len(e))))[:kmax])
        keys.append(f"{s} {c}")
    C = np.cumsum(np.array(rows), axis=1)
    caps = {k: float(C[:, k - 1].max()) * slack for k in range(1, kmax + 1)}
    mean = {k: float(C[:, k - 1].mean()) for k in range(1, kmax + 1)}
    amax = {k: keys[int(C[:, k - 1].argmax())] for k in range(1, kmax + 1)}
    return caps, mean, amax, len(rows)


def load_caps(path=CAPS_CSV, slack=None):
    """תקרות מהקובץ המקומט, לא מחושבות בזמן ריצה.

    כמו ש-ADR 0004 קרא את δ מקובץ ולא הקליד אותו: התקרה שה-LP רץ
    תחתיה חייבת להיות אותה תקרה שמופיעה ב-ADR.
    """
    d = pd.read_csv(path)
    caps = dict(zip(d.k.astype(int), d.cap.astype(float)))
    if slack is not None:
        caps = {k: v / SLACK * slack for k, v in caps.items()}
    return caps


def slack_caps(caps, slack):
    """אותן תקרות במכפיל אחר. לרגישות Q7 — מדווח, לא נבחר."""
    return {k: v / SLACK * slack for k, v in caps.items()}


# =====================================================================
# האילוץ ב-LP
# =====================================================================
def add_shape_constraint(p, e, caps, n, kmax=KMAX, tag=""):
    """מוסיף `סכום k הגדולים של e <= C_k` לכל k, בפירוק Nesterov.

    p    בעיית pulp
    e    רשימת משתני הדקות
    caps {k: C_k}
    מחזיר את מספר האילוצים שנוספו — הקורא מדפיס אותו כ-guard.
    """
    added = 0
    for k in sorted(caps):
        if k > kmax or k >= n:
            continue
        C = caps[k]
        q = pulp.LpVariable(f"q{tag}_{k}")          # חופשי בסימן, כנדרש
        s = [pulp.LpVariable(f"s{tag}_{k}_{i}", lowBound=0) for i in range(n)]
        p += k * q + pulp.lpSum(s) <= C
        for i in range(n):
            p += s[i] >= e[i] - q
        added += 1
    return added


def solver_guard(p, fn, allow_gap=None):
    """🔴 T9. `Not Solved` הוא time limit, לא הצלחה.

    הגרסה הקודמת ב-optimise_v3 קיבלה אותו בשקט, והפתרון המוחזר
    עלול להיות לא-אופטימלי או לא קיים. "No silent success".
    """
    st = pulp.LpStatus[p.status]
    ss = getattr(p, "sol_status", None)
    # 🔴 תוקן אחרי code review. status "Optimal" לבד אינו מספיק: CBC שנעצר
    #    על timeLimit עם פתרון אפשרי מדווח גם הוא "Optimal", ורק sol_status
    #    מבדיל — 1 הוכח (בתוך הפער המוצהר), 2 אפשרי בלבד. הגרסה הקודמת
    #    בדקה status, כלומר עברה בדיוק במקרה שהיא נכתבה לתפוס. T9b.
    if st == "Optimal" and ss in (None, 1):
        return st
    if st == "Optimal" and ss == 2:
        raise RuntimeError(
            f"❌ {fn}: CBC נעצר על time limit עם פתרון אפשרי שלא הוכח "
            f"אופטימלי (sol_status=2). הארך את timeLimit — אל תתעלם.")
    raise RuntimeError(
        f"❌ {fn}: הסולבר החזיר '{st}' ולא 'Optimal'. "
        f"אם זה time limit — הארך אותו או הרחב את הפער, אל תתעלם.")


# =====================================================================
# בדיקת הצורה על התוצאה (T3) — לא סומכים על הקידוד
# =====================================================================
def top_k_sums(mins, kmax=KMAX):
    """סכומים מצטברים של k הדקות הגדולות. מאינדקס 1: [k-1] = k."""
    e = np.sort(np.asarray(mins, dtype=float))[::-1]
    e = np.pad(e, (0, max(0, kmax - len(e))))[:kmax]
    return np.cumsum(e)


def check_shape(mins, caps, kmax=KMAX, tol=1e-6):
    """מחזיר רשימת הפרות [(k, נמצא, תקרה)]. ריק = תקין.

    נבדק מווקטור ה-e שחזר, ולא מהניסוח — זה הטסט היחיד שיתפוס
    טעות בפירוק Nesterov עצמו.
    """
    cum = top_k_sums(mins, kmax)
    bad = []
    for k in sorted(caps):
        if k > kmax:
            continue
        if cum[k - 1] > caps[k] + tol:
            bad.append((k, float(cum[k - 1]), float(caps[k])))
    return bad


# =====================================================================
# הסקוררים
# =====================================================================
def score_shape(df, ppm_col, avail_col, repl, caps, kmax=KMAX, tol=1e-9,
                pos_min=True, exact=True):
    """🔴 T7. הסקורר פותר את **אותה** בעיית הקצאה שה-LP פותר.

    הסגל קבוע, ולכן אין בינאריים וזה LP רציף קטן (12-16 משתנים).
    האילוצים זהים ל-`optimise_capped` פרט לבחירת הסגל.

    למה לא חמדני: `score_shape_greedy` מחלק לפי `ppm` בסדר יורד. תחת
    תקרות **מצטברות** יחד עם תקרות עמדה זה אינו אופטימלי — תקרת עמדה
    שוברת את היישור בין סדר ה-ppm לסדר ה-e, והחמדן נועל דקות אצל
    שחקן שחוסם שחקן טוב ממנו בהמשך. נמדד: על 3 עונות-מועדון אמיתיות
    החמדן לא שיחזר את מטרת ה-LP ב-1 מתוך 3. סקורר חמדני מול LP מדויק
    פירושו ששני הצדדים אינם על אותו סרגל, וזו בדיוק השגיאה
    ש-optimise_consistent נכתב כדי לסגור.

    pos_min: רצפות העמדה של ה-LP. `score_rows` ההיסטורי לא אכף אותן,
    ולסגל של מועדון אמיתי הן יכולות להיות בלתי אפשריות. אם אין פתרון
    איתן — הן מוסרות, וזה מדווח דרך `used`.
    """
    if not exact:
        return score_shape_greedy(df, ppm_col, avail_col, repl, caps,
                                  kmax, tol)
    ppm = df[ppm_col].values
    av = df[avail_col].values
    pos = df.position.values
    n = len(df)
    if n == 0:
        return 0.0, 0.0, np.zeros(0)

    def _solve(with_min):
        p = pulp.LpProblem("alloc", pulp.LpMaximize)
        e = [pulp.LpVariable(f"a{i}", lowBound=0) for i in range(n)]
        p += pulp.lpSum(ppm[i] * e[i] for i in range(n))
        p += pulp.lpSum(e) <= ro.MINUTES_PER_GAME
        for i in range(n):
            p += e[i] <= ro.MAX_MIN_PLAYER * av[i]
        for g in ro.POS_MAX_SHARE:
            idx = [i for i in range(n) if pos[i] == g]
            if not idx:
                continue
            p += pulp.lpSum(e[i] for i in idx) <= \
                ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
            if with_min:
                p += pulp.lpSum(e[i] for i in idx) >= \
                    ro.POS_MIN_SHARE[g] * ro.MINUTES_PER_GAME
        add_shape_constraint(p, e, caps, n, kmax)
        p.solve(pulp.PULP_CBC_CMD(msg=0))
        if pulp.LpStatus[p.status] != "Optimal":
            return None
        return np.array([e[i].value() or 0.0 for i in range(n)])

    # 🔴 תוקן אחרי code review. שתי הנפילות למטה היו שקטות, בניגוד
    #    ל-"Scripts print their guards". עכשיו כל נפילה מודפסת עם ❌
    #    ונספרת ב-FALLBACKS, והקורא מדווח את הספירה כ-guard. T18.
    out = _solve(pos_min)
    if out is None and pos_min:
        FALLBACKS["no_pos_min"] += 1
        print(f"    ❌ score_shape: רצפות העמדה בלתי אפשריות לסגל של {n} "
              f"שחקנים — מוסרות. FALLBACKS={FALLBACKS}")
        out = _solve(False)
    if out is None:
        FALLBACKS["greedy"] += 1
        print(f"    ❌ score_shape: אין פתרון LP גם בלי רצפות — נופל לחמדן. "
              f"FALLBACKS={FALLBACKS}")
        return score_shape_greedy(df, ppm_col, avail_col, repl, caps,
                                  kmax, tol)
    q = float((out * ppm).sum())
    used = float(out.sum())
    left = ro.MINUTES_PER_GAME - used
    if repl is not None and left > tol:
        q += left * repl
    return q, used, out


def score_shape_greedy(df, ppm_col, avail_col, repl, caps, kmax=KMAX,
                       tol=1e-9):
    """ניקוד תחת תקרות הצורה. חמדני ב-ppm, אבל האילוץ על e.

    🔴 T8 — הבאג שתוקן כאן. `score_realistic` המקורי חיפש
    `caps.get(rank)` לפי **דירוג ppm**. האילוץ מוגדר על k הערכים
    הגדולים של **e**, ותקרות העמדה שוברות את המונוטוניות בין
    ppm ל-e: שחקן עם ppm נמוך יכול לקבל יותר דקות משחקן מעליו אם
    העמדה של העליון נסגרה. אז התקרה הוחלה על הסדר הלא-נכון.

    התיקון: לכל שחקן, החסם על מה שהוא יכול לקחת נמצא בחיפוש בינארי
    מול `check_shape` על הווקטור **כולו**. האילוץ מונוטוני ב-take,
    ולכן החיפוש תקף.
    """
    ppm = df[ppm_col].values
    av = df[avail_col].values
    pos = df.position.values
    n = len(df)
    order = np.argsort(-ppm)
    poscap = {g: ro.POS_MAX_SHARE[g] * ro.MINUTES_PER_GAME
              for g in ro.POS_MAX_SHARE}
    e = np.zeros(n)
    left = ro.MINUTES_PER_GAME

    for j in order:
        hi = max(min(ro.MAX_MIN_PLAYER * av[j], left, poscap[pos[j]]), 0.0)
        if hi <= 0:
            continue
        # החסם הגדול ביותר שאינו מפר את הצורה, בחיפוש בינארי
        e[j] = hi
        if check_shape(e, caps, kmax, tol=tol):
            lo = 0.0
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                e[j] = mid
                if check_shape(e, caps, kmax, tol=tol):
                    hi = mid
                else:
                    lo = mid
            e[j] = lo
        take = e[j]
        left -= take
        poscap[pos[j]] -= take

    q = float((e * ppm).sum())
    used = float(e.sum())
    if repl is not None and left > tol:
        q += left * repl
    return q, used, e


def score_planned(df, ppm_col, avail_col, minutes, repl=None, tol=1e-9):
    """🔴 ADR 0006. המנוע על הדקות ש**הוא תכנן**, בלי הקצאה מחדש.

        e_i = min(e_LP_i, 32·avail_true_i)
        q   = Σ e_i·ppm_true_i  +  REPL·(200 − Σe_i)

    `e_LP` נקבע ב-LP על `ppm` **חזוי** ועל `avail` **חזוי**, ולכן התוכנית
    יכולה להיות בלתי אפשרית מול מה שקרה: נמדד `EVANS, KEENAN` עם 27.3
    דקות מתוכננות ו-`avail_true = 0.026`, כלומר משחק אחד מ-38.

    **שני דברים שהפונקציה הזאת לא עושה, וזו כל הנקודה:**

    1. **לא מחלקת מחדש.** `score_rows` ו-`score_shape` מסדרות דקות לפי
       `ppm_true` יורד — כלומר בדיעבד. זה היה סימטרי כל זמן ששני הצדדים
       קיבלו את זה. ADR 0005 מדד מה קורה כשרק המנוע מקבל: +98.4%, ו-STOP.
    2. **לא מעבירה את הדקות שהתפנו לשאר הסגל.** העברה כזאת דורשת לדעת מי
       נפצע. הן נופלות ל-`REPL`, וזה מחיר הסיכון של לתכנן סביב מי שלא היה
       שם. המועדון לא משלם אותו כי הוא שיחק 200 דקות אמיתיות עם 16
       שחקנים מול 12 של המנוע.

    הקציצה ראשונה, ורק מה ששורד תורם ב-`ppm_true` שלו — כולל שלילי, בלי
    רצפה. הסדר הזה הוא מה ששומר על הזנב השלילי קטן (8% מהסגלים), כי
    שחקני `avail≈0` נקצצים לפני שהשאלה בכלל מתעוררת.

    מחזיר (q, used, e, clipped).
    """
    ppm = df[ppm_col].values
    av = df[avail_col].values
    e_lp = np.asarray(minutes, dtype=float)
    cap = ro.MAX_MIN_PLAYER * av
    e = np.minimum(e_lp, cap)
    e = np.maximum(e, 0.0)
    clipped = float(np.maximum(e_lp - cap, 0.0).sum())
    q = float((e * ppm).sum())
    used = float(e.sum())
    left = ro.MINUTES_PER_GAME - used
    if repl is not None and left > tol:
        q += left * repl
    return q, used, e, clipped


def score_actual(df, ppm_col, minutes_col, repl=None):
    """המועדון על הדקות שבאמת שוחקו. זו ספציפיקציית המכנה.

    `score_rows` אינו מנקד מועדון על מה שהוא עשה: הוא מחלק מחדש את
    שחקניו בחמדנות ב-min(32, left, poscap)·avail, ומעניק לשישייה
    177.0 דקות בממוצע מול 125.7 שהיא שיחקה — מכנה מנופח ב-40.8%.
    המינימום שם, 148.7, גבוה מהתקרה 145.3, כלומר כל 38 המועדונים
    מפרים את האילוץ שנבנה מהמקסימום שלהם עצמם.
    """
    ppm = df[ppm_col].values
    e = df[minutes_col].values.astype(float)
    q = float((e * ppm).sum())
    used = float(e.sum())
    left = ro.MINUTES_PER_GAME - used
    if repl is not None and left > 0:
        q += left * repl
    return q, used, e


# =====================================================================
def main():
    """מייצר shape_caps.csv ומדפיס את הטבלה שב-ADR 0005."""
    caps, mean, amax, n = observed_caps()
    d = pd.DataFrame([
        dict(k=k, cap=caps[k], mean=mean[k], attained_by=amax[k],
             model_allows=min(ro.MAX_MIN_PLAYER * k, ro.MINUTES_PER_GAME),
             slack=SLACK, n_club_seasons=n)
        for k in sorted(caps)])
    CAPS_CSV.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(CAPS_CSV, index=False)

    print(f"נמדד על {n} עונות-מועדון · slack={SLACK}\n")
    print(f"{'k':>3}{'ממוצע':>9}{'תקרה':>9}{'הושגה ע\"י':>12}"
          f"{'המודל מרשה':>14}")
    for k in sorted(caps):
        print(f"{k:>3}{mean[k]:>9.1f}{caps[k]:>9.1f}{amax[k]:>12}"
              f"{min(ro.MAX_MIN_PLAYER*k, ro.MINUTES_PER_GAME):>14.1f}")

    distinct = len(set(amax.values()))
    print(f"\n  ⚠️ המעטפת מורכבת מ-{distinct} עונות-מועדון שונות. "
          f"אף קבוצה לא שיחקה את הצורה שהיא מרשה.")
    print(f"     מגבלה מוצהרת ב-ADR 0005, לא באג.")
    ok = n == 38 and abs(caps[6] - 145.3) < 0.1
    print(f"\n  {'✅' if ok else '❌'} guard: n=38 ו-cap(6)=145.3 "
          f"— {n}, {caps[6]:.1f}")
    print(f"  נכתב: {CAPS_CSV}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
