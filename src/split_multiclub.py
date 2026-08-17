"""
split_multiclub.py  (Day 7)
---------------------------
מפצל שחקנים רב-מועדוניים לפי מועדון, מבוקסקור ברמת משחק.

--------------------------------------------------------------------
הבעיה
--------------------------------------------------------------------
`player_season.csv` נותן שורה אחת לעונה, עם `team` מרובה:
`OLY;TEL`, `TEL;PAN`, `BER;TEL`. הדקות וה-PIR בשורה כזו הם של
**שני** המועדונים.

זה נכנס ישירות לבנצ'מרק. אלמוג תפס את הקצה הגלוי ביום 6 (לויד,
22.8 דקות אחרי משחק אחד) ואת הכיוון ההפוך ביום 7 (לי וגבריאל
עזבו באמצע; וויליאמס הגיע).

--------------------------------------------------------------------
המיפוי
--------------------------------------------------------------------
`Player_ID` בבוקסקור הוא `P0` + `player_code` מרופד לאפסים:

    P013383 -> 13383    P012604 -> 12604    P011219 -> 11219

אומת על ארבעה שחקנים. **לא מסתמכים על שמות** — יש התנגשויות
(שני GABRIEL שונים ב-2024).

⚠️ `Player_ID` הוא **מזהה ולא מספר**. אין `int()` עליו לשום צורך
פרט לחילוץ הקוד. זה באג 1 של יום 4, שחזר ביום 6.

--------------------------------------------------------------------
אימות
--------------------------------------------------------------------
סכום הדקות וה-PIR על פני מועדונים חייב לשחזר את `player_season`.
הפער המרבי מודפס. אם הוא אינו זניח — הפיצול שגוי ולא לשמור.

הרצה:
    python src/split_multiclub.py 2024
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import RAW_DIR, PROCESSED_DIR

SEP = "=" * 76


def parse_minutes(s):
    """'16:18' -> 16.3 דקות.  'DNP' / ריק -> 0."""
    s = str(s).strip()
    if not s or s in ("DNP", "nan", "None"):
        return 0.0
    if ":" not in s:
        return 0.0
    mm, ss = s.split(":")[:2]
    try:
        return float(mm) + float(ss) / 60.0
    except ValueError:
        return 0.0


def code_from_pid(pid):
    d = re.sub(r"\D", "", str(pid))
    return str(int(d)) if d else None


def build(season):
    b = pd.read_csv(RAW_DIR / f"boxscore_player_{season}.csv", dtype=str)
    # 🔴 הבוקסקור כולל פלייאוף ופיינל-פור; `player_season` נבנה
    # מ-`accumulated_rs_*`, כלומר **עונה סדירה בלבד**. בלי הסינון
    # הזה הפיצול מוסיף עד 7 משחקים לשחקן ואינו משחזר את המקור.
    # נתפס באימות ולא אחריו.
    phases = sorted(b.Phase.dropna().unique())
    b = b[b.Phase == "RS"].copy()
    print(f"  שלבים בקובץ: {phases} -> נשמר RS בלבד")
    b["player_code"] = b.Player_ID.map(code_from_pid)
    b["min"] = b.Minutes.map(parse_minutes)
    b["pir"] = pd.to_numeric(b.Valuation, errors="coerce").fillna(0.0)
    b = b[b.player_code.notna()].copy()
    # משחק נספר רק אם שוחקו בו דקות — כמו ב-player_season
    b["played"] = (b["min"] > 0).astype(int)

    g = b.groupby(["player_code", "Team"], as_index=False).agg(
        games=("played", "sum"), minutes=("min", "sum"),
        sum_pir=("pir", "sum"))
    g = g[g.games > 0].copy()
    g["season"] = int(season)
    g = g.rename(columns={"Team": "club"})
    g["min_per_game"] = g.minutes / g.games
    g["pir_per_game"] = g.sum_pir / g.games
    g["ppm"] = np.where(g.minutes > 0, g.sum_pir / g.minutes, np.nan)
    return g[["season", "player_code", "club", "games", "minutes",
              "sum_pir", "min_per_game", "pir_per_game", "ppm"]]


def verify(g, season):
    ps = pd.read_csv(PROCESSED_DIR / "player_season.csv",
                     dtype={"player_code": str})
    ps = ps[ps.season == int(season)]
    tot = g.groupby("player_code", as_index=False).agg(
        games=("games", "sum"), minutes=("minutes", "sum"),
        sum_pir=("sum_pir", "sum"))
    m = ps.merge(tot, on="player_code", how="inner",
                 suffixes=("_ps", "_bs"))
    m["d_games"] = (m.games_ps - m.games_bs).abs()
    m["d_min"] = (m.minutes_ps - m.minutes_bs).abs()
    m["d_pir"] = (m.sum_pir_ps - m.sum_pir_bs).abs()
    print(f"  הותאמו {len(m)} מתוך {len(ps)} שחקנים ב-player_season")
    print(f"  פער מרבי — משחקים {m.d_games.max():.1f} | "
          f"דקות {m.d_min.max():.1f} | PIR {m.d_pir.max():.1f}")
    bad = m[(m.d_games > 0.5) | (m.d_pir > 0.5)]
    if len(bad):
        print(f"  🔴 {len(bad)} שחקנים לא משוחזרים:")
        print(bad[["player_name", "games_ps", "games_bs",
                   "sum_pir_ps", "sum_pir_bs"]].head(10).to_string(
            index=False))
    else:
        print("  ✅ הפיצול משחזר את player_season במדויק")
    return len(bad) == 0


def main(seasons):
    frames = []
    for s in seasons:
        print(f"\n{SEP}\nעונה {s}\n{SEP}")
        g = build(s)
        multi = g.player_code.value_counts()
        multi = multi[multi > 1]
        print(f"  {g.player_code.nunique()} שחקנים | "
              f"{len(multi)} מהם שיחקו ביותר ממועדון אחד")
        verify(g, s)
        frames.append(g)
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(PROCESSED_DIR / "player_club_season.csv", index=False)
    print(f"\n  נכתב player_club_season.csv — {len(out)} שורות")
    return out


if __name__ == "__main__":
    main(sys.argv[1:] or ["2024"])
