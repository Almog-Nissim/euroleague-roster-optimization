"""
newcomer_pool.py  (Day 9)
-------------------------
**החור שהתגלה כשניסינו לעבור ל-38 מועדונים.**

--------------------------------------------------------------------
מה נמצא
--------------------------------------------------------------------
מאגר המועמדים נבנה מ-`lagged`, כלומר **רק שחקנים עם עונת יורוליג
קודמת**. מדידה על 2024:

    שחקנים ששיחקו בעונה      295
    מהם במאגר                207   (70%)
    **הדקות שמחוץ למאגר      20.6%**

כלומר: המנוע פועל בשוק שחסר בו **חמישית מדקות הליגה** — בדיוק
החדשים. עבור מועדון אמיתי זה הכלי המרכזי (החתמה מה-NBA, מ-ACB,
מהליגה הטורקית). מכבי 2024: 10 מתוך 19 שחקנים לא היו במאגר.

בלי לסגור את החור, השוואת "מנוע מול מועדון" אינה מוגדרת היטב:
או שמצמצמים את המועדון ל-9 שחקנים (ואז הוא נענש על גודלו), או
שהמועדון מקבל תפוקה בחינם.

--------------------------------------------------------------------
הפתרון — לוגיקת הכיווץ של המודל עצמו
--------------------------------------------------------------------
לשחקן בלי דקות קודמות, נוסחת הכיווץ של המודל **כבר** נותנת את
התשובה:

    w = minutes_lag / (minutes_lag + K)  ->  w = 0
    ppm_lag_shrunk = 0·ppm_lag + 1·ממוצע_הליגה = ממוצע_הליגה

זו לא הנחה חדשה. זה המודל הקיים, מוחל באופן עקבי על מי שהמידע
עליו אפסי. אותו דבר ל-pir_lag_shrunk.

למשתני הלאג שאין להם כיווץ (min_pg_lag, frac_lag) נלקח הממוצע
האמפירי של **שחקנים בעונתם הראשונה** בתוך נתוני האימון בלבד
(el_seasons_lag == 0).

--------------------------------------------------------------------
⚠️ הטיות ידועות
--------------------------------------------------------------------
1. **הישרדות.** הממוצע של el_seasons_lag==0 מחושב על רוקים
   ש**שרדו לעונה שנייה**. רוקי שנכשל ונעלם אינו שם. לכן הפריור
   אופטימי מעט.
2. **חוסר הבחנה.** לוני ווקר שמגיע מה-NBA ולשחקן נוער בן 19
   יקבלו בדיוק אותו פריור. אין לנו נתוני חוץ-יורוליג, ולכן
   המודל **לא יכול** להבחין ביניהם. זו מגבלה אמיתית, לא זמנית.
3. לכן: החדשים במאגר הם **רעש ממורכז**, לא מידע. הם מונעים
   מהמועדון תפוקה חינם — הם לא הופכים את המנוע לחכם יותר.
"""

import numpy as np
import pandas as pd

import roster_optimizer as ro


def build_newcomer_rows(ps, feat, lagged, test, train_max):
    """שורות מאגר לשחקני עונת test שאין להם עונה קודמת.

    כל הפריורים מחושבים מנתוני אימון (<= train_max) בלבד.
    """
    tr = lagged[lagged.season <= train_max]
    # el_seasons_lag נספר על p2 לפני הסינון, ולכן השורה הראשונה של
    # כל שחקן (==0) היא זו **בלי** לאג תקף והיא מסוננת החוצה.
    # ==1 היא העונה השנייה, שהלאג שלה הוא עונת הרוקי. זה מה שרצינו.
    rookie = tr[tr.el_seasons_lag == 1]
    assert len(rookie) > 0, "אין שורות רוקי באימון — הפריורים יהיו NaN"
    prior_min_pg = float(rookie.min_pg_lag.mean())
    prior_frac = float(rookie.frac_lag.mean())

    league_ppm = float((tr.ppm_lag * tr.mins_lag).sum() / tr.mins_lag.sum())
    lp = feat[feat.season == test].league_pir_mean
    league_pir = float(lp.iloc[0]) if len(lp) else float(
        feat[feat.season <= train_max].league_pir_mean.iloc[-1])

    gmax = float(ps[ps.season == test].games.max())
    cur = ps[(ps.season == test) & (ps.min_per_game > 0)].copy()
    have = set(lagged[lagged.season == test].player_code.astype(str))
    new = cur[~cur.player_code.astype(str).isin(have)].copy()

    new["ppm"] = new.pir_per_game / new.min_per_game
    new["frac"] = new.games / gmax
    new["minutes_tot"] = new.min_per_game * new.games
    new["ppm_lag_shrunk"] = league_ppm          # w = 0
    new["pir_lag_shrunk"] = league_pir          # w = 0
    new["el_seasons"] = 0
    new["el_seasons_lag"] = 0
    new["min_pg_lag"] = prior_min_pg
    new["frac_lag"] = prior_frac
    new["gap"] = 1.0
    new["log_gap"] = 0.0
    new["age_c"] = new.age - ro.AGE_CENTER
    new["gmax"] = gmax
    new["is_newcomer"] = True
    return new, dict(prior_min_pg=prior_min_pg, prior_frac=prior_frac,
                     league_ppm=league_ppm, league_pir=league_pir,
                     n_new=len(new))