"""
fatigue_delta.py — אמידת δ: ההנחה על תפוקה בדקות שמעל הסף, בתוך משחק.
שלב 2 של ADR 0004. הסקריפט הזה מחליט אם מדרגות העייפות נכנסות ל-LP.

--------------------------------------------------------------------
המודל — אותו מבנה כמו ב-LP
--------------------------------------------------------------------
    V_ig = r_is · ( a_ig + (1−δ)·b_ig ) + ε
    a = min(m, THRESHOLD) · b = max(m − THRESHOLD, 0)
    i שחקן · g משחק · s עונה — קצב אחד לכל שחקן-עונה (Q13)
    V = Valuation (PIR) של המשחק כולו, לא לדקה — חלוקה בדקות מייצרת
        שיפוע שלילי מרעש במכנה (division bias).

בהינתן δ, r_is נפתר בצורה סגורה. עם k = 1−δ ולכל שחקן-עונה חמישה סכומים
(Va, Vb, aa, ab, bb), תרומת הקבוצה לסכום הריבועים המוסבר היא
    C_s(δ) = (Va + k·Vb)² / (aa + 2k·ab + k²·bb)
ו-δ̂ = argmax Σ_s C_s(δ) על הרשת. שחקן-עונה בלי אף משחק מעל הסף תורם
קבוע שאינו תלוי ב-δ, ולכן נשמט מהחישוב בלי לשנות את δ̂.

רווח סמך: bootstrap מקובץ לפי שחקן (כל העונות שלו יחד), percentile.

--------------------------------------------------------------------
פרמטרים מוצהרים — ADR 0004, לפני הריצה
--------------------------------------------------------------------
    SEASONS            2016–2025, כל השלבים (RS/PI/PO/FF)
    THRESHOLD          30 · רגישות 28 ו-32 מדווחת ולא בוחרת
    REG_MAX_TEAM_MIN   201 — משחק בזמן חוקי בלבד (שורת Total של הקבוצה)
    MARGIN_MAX         10  — S1: הפרש סופי בערך מוחלט
    FOUL_OUT           5   — S2: משמיט משחקי שחקן עם 5 עבירות ומעלה
    GRID               [-2.00, 0.60] צעד 0.005. הוצהר [-0.30, 0.60]; בריצה
                       הראשונה δ̂ של כל המפרטים נחת על הקצה התחתון -0.30
                       עם CI מנוון, והשומר עצר. התרופה לשומר קצה היא
                       להרחיב את הרשת, לא לשנות את השומר. ההרחבה אינה
                       יכולה לשנות את הפסק: δ̂ < 0 לעולם לא נכנס.
    B · SEED           1000 · 20260911
    DELTA_MIN          0.10

כלל ההחלטה (ADR 0004):
    enters          P: δ̂ ≥ DELTA_MIN ו-ci_lo > 0, ו-δ̂ > 0 גם ב-S1 וגם ב-S2
    refuted         P: ci_hi < DELTA_MIN
    not_identified  כל השאר — לא נכנס, ולא נקרא "מופרך"
    δ̂ < 0 לעולם לא נכנס.

--------------------------------------------------------------------
שומרים — עוצרים לפני שנכתב קובץ
--------------------------------------------------------------------
1. שחזור סינתטי, על הדקות והקבוצות האמיתיות של P, עם δ_true = 0.15:
   1a. בלי רעש — δ̂ חייב להיות δ_true בדיוק. בודק את האלגברה.
   1b. עם רעש בגודל השארית האמיתית, GUARD_REPS הגרלות — ממוצע δ̂ בטווח
       ±0.02 מ-δ_true. בודק הטיה.
   תוקן אחרי הריצה הראשונה: הניסוח המקורי דרש ±0.02 על הגרלה *אחת*,
   וזה בודק דיוק ולא הטיה. הגרלה אחת נתנה 0.090 ואחרת 0.185 — פיזור
   של ~0.05 הוא רזולוציית התכנון, לא באג. ה-SD של ההגרלות מודפס: זה
   גם הגודל הצפוי של רווח הסמך.
2. לכל משחק-קבוצה עם שחקנים יש שורת Total אחת בדיוק.
3. δ̂ של P אינו על קצה הרשת (אחרת הרשת חותכת את האומדן).

--------------------------------------------------------------------
אבחון שנוסף אחרי הריצה — לא חלק מהתכנון המוצהר
--------------------------------------------------------------------
פרופיל דקות בתוך שחקן-עונה: בכל טווח דקות, ה-PIR בפועל חלקי מה שקצב
העונה של אותו שחקן מנבא לאותן דקות. אם יש עייפות שנראית בבוקססקור,
היחס יורד מעל 30. מסונן לשחקן-עונה עם 300 דקות לפחות וקצב חיובי.
תיאורי בלבד: אינו נכנס לפסק ואינו מייצר δ חלופי.
פלט: data/processed/fatigue_delta_buckets.csv

הרצה:  python src/fatigue_delta.py
פלט:   data/processed/fatigue_delta.csv
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paths import PROCESSED_DIR, RAW_DIR  # noqa: E402

SEASONS = range(2016, 2026)
THRESHOLD = 30.0
SENS_THRESHOLDS = (28.0, 32.0)
REG_MAX_TEAM_MIN = 201.0
MARGIN_MAX = 10
FOUL_OUT = 5
GRID = np.round(np.arange(-2.00, 0.60 + 1e-9, 0.005), 3)
B = 1000
SEED = 20260911
DELTA_MIN = 0.10

GUARD_DELTA_TRUE = 0.15
GUARD_TOL = 0.02
GUARD_REPS = 100

PRED_CLAUDE = (-0.05, 0.05)
PRED_ALMOG = (0.02, 0.08)

POSITIONS = PROCESSED_DIR / "player_positions.csv"
OUT = PROCESSED_DIR / "fatigue_delta.csv"
OUT_BUCKETS = PROCESSED_DIR / "fatigue_delta_buckets.csv"
BUCKET_EDGES = (0, 10, 15, 20, 25, 30, 34, 40.01)
BUCKET_MIN_SEASON_MINUTES = 300
SEP = "=" * 78
NON_PLAYERS = {"Team", "Total"}


def h(t: str) -> None:
    print(f"\n{SEP}\n{t}\n{SEP}")


def minutes(s: pd.Series) -> pd.Series:
    mm = s.astype(str).str.strip().str.extract(r"^(\d+):(\d{2})$").astype(float)
    return mm[0] + mm[1] / 60.0


# --------------------------------------------------------------------
# נתונים
# --------------------------------------------------------------------
def load() -> pd.DataFrame:
    frames, missing_total, stubs = [], 0, 0
    for season in SEASONS:
        d = pd.read_csv(RAW_DIR / f"boxscore_player_{season}.csv")
        d["pid"] = d.Player_ID.astype(str).str.strip()
        d["team"] = d.Team.astype(str).str.strip()

        tot = d[d.pid == "Total"].copy()
        tot["team_min"] = minutes(tot.Minutes)
        # שורות Total ריקות (בלי דקות ובלי שחקנים — למשל 2018 משחק 21)
        # אינן משחק. נספרות ומודפסות, לא נבלעות.
        stubs += int(tot.team_min.isna().sum())
        tot = tot[tot.team_min.notna()]
        # המפתח הוא (Gamecode, Home) ולא שם הקבוצה: ב-2018 וב-2021 שורת
        # Total נושאת שם מלא ("REAL MADRID") והשחקנים קוד ("MAD").
        tot = tot[["Gamecode", "Home", "team_min", "Points"]].rename(
            columns={"Points": "team_pts"})
        dup = tot.duplicated(["Gamecode", "Home"]).sum()
        if dup:
            raise ValueError(f"{season}: {dup} שורות Total כפולות")
        opp = tot.assign(Home=1 - tot.Home).rename(
            columns={"team_pts": "opp_pts"})[["Gamecode", "Home", "opp_pts"]]
        tot = tot.merge(opp, on=["Gamecode", "Home"], how="inner")

        p = d[~d.pid.isin(NON_PLAYERS)].copy()
        p["m"] = minutes(p.Minutes)
        p = p[p.m > 0]
        n0 = len(p)
        p = p.merge(tot, on=["Gamecode", "Home"], how="inner")
        missing_total += n0 - len(p)

        frames.append(pd.DataFrame({
            "season": season,
            "gamecode": p.Gamecode.values,
            "team": p.team.values,
            "pid": p.pid.values,
            "m": p.m.values,
            "V": p.Valuation.astype(float).values,
            "fouls": p.FoulsCommited.astype(float).values,
            "team_min": p.team_min.values,
            "margin": (p.team_pts - p.opp_pts).abs().values,
        }))
    df = pd.concat(frames, ignore_index=True)
    df = df[df.V.notna()]
    df.attrs["missing_total"] = missing_total
    df.attrs["stubs"] = stubs
    return df


# --------------------------------------------------------------------
# האומד
# --------------------------------------------------------------------
def split_minutes(m: np.ndarray, thr: float):
    """מדרגה 1 ומדרגה 2 של אותן דקות — אותו פיצול כמו ב-LP."""
    return np.minimum(m, thr), np.maximum(m - thr, 0.0)


def player_season(df: pd.DataFrame) -> np.ndarray:
    return df.groupby(["pid", "season"], sort=False).ngroup().values


def group_sums(df: pd.DataFrame, thr: float):
    """חמשת הסכומים לכל שחקן-עונה שיש לו לפחות משחק אחד מעל הסף."""
    a, b = split_minutes(df.m.values, thr)
    V = df.V.values
    g = player_season(df)
    G = g.max() + 1
    has_b = np.bincount(g, weights=(b > 0).astype(float), minlength=G) > 0
    has_a = np.bincount(g, weights=(df.m.values <= thr).astype(float),
                        minlength=G) > 0
    S = {k: np.bincount(g, weights=w, minlength=G)[has_b]
         for k, w in (("Va", V * a), ("Vb", V * b), ("aa", a * a),
                      ("ab", a * b), ("bb", b * b))}
    gp = df.groupby(["pid", "season"], sort=False).pid.first().values[has_b]
    return S, gp, int(has_b.sum()), int((has_b & has_a).sum())


def contrib(S) -> np.ndarray:
    k = 1.0 - GRID[None, :]
    num = S["Va"][:, None] + k * S["Vb"][:, None]
    den = S["aa"][:, None] + 2 * k * S["ab"][:, None] + k * k * S["bb"][:, None]
    return num * num / den


def estimate(df: pd.DataFrame, thr: float, stream: int) -> dict:
    S, gp, n_g2, n_both = group_sums(df, thr)
    C = contrib(S)
    delta = float(GRID[np.argmax(C.sum(axis=0))])

    players, cl = np.unique(gp, return_inverse=True)
    P = len(players)
    rng = np.random.default_rng([SEED, stream])
    W = rng.multinomial(P, np.full(P, 1.0 / P), size=B)[:, cl].astype(float)
    boot = GRID[np.argmax(W @ C, axis=1)]
    lo, hi = np.percentile(boot, [2.5, 97.5])

    return dict(threshold=thr, n_player_games=len(df),
                n_tier2_games=int((df.m > thr).sum()),
                n_groups_tier2=n_g2, n_groups_both_sides=n_both,
                n_players=P, delta_hat=delta,
                ci_lo=float(lo), ci_hi=float(hi),
                at_boundary=bool(delta in (GRID[0], GRID[-1])))


def synthetic_recovery(df: pd.DataFrame) -> dict:
    """V מסומלץ על המבנה האמיתי, עם δ ידוע: בלי רעש, ועם רעש ב-GUARD_REPS הגרלות."""
    a, b = split_minutes(df.m.values, THRESHOLD)
    g = player_season(df)
    z0 = a + b
    r = (np.bincount(g, weights=df.V.values * z0)
         / np.bincount(g, weights=z0 * z0))[g]
    sd = float(np.std(df.V.values - r * z0))
    signal = r * (a + (1 - GUARD_DELTA_TRUE) * b)

    def fit(v):
        S, _, _, _ = group_sums(df.assign(V=v), THRESHOLD)
        return float(GRID[np.argmax(contrib(S).sum(axis=0))])

    rng = np.random.default_rng([SEED, 999])
    draws = np.array([fit(signal + rng.normal(0, sd, len(df)))
                      for _ in range(GUARD_REPS)])
    return dict(exact=fit(signal), mean=float(draws.mean()),
                sd=float(draws.std(ddof=1)), first=float(draws[0]),
                noise_sd=sd)


def bucket_profile(df: pd.DataFrame) -> pd.DataFrame:
    """PIR בפועל / PIR שקצב העונה של השחקן מנבא, לפי טווח דקות. תיאורי."""
    key = ["pid", "season"]
    t = df.groupby(key).agg(Vs=("V", "sum"), ms=("m", "sum"))
    t = t[(t.ms >= BUCKET_MIN_SEASON_MINUTES) & (t.Vs > 0)]
    d = df.join(t, on=key, how="inner")
    d["expected"] = d.m * d.Vs / d.ms
    d["bucket"] = pd.cut(d.m, list(BUCKET_EDGES))
    out = d.groupby("bucket", observed=True).agg(
        n_games=("V", "size"), pir=("V", "sum"), expected=("expected", "sum"))
    out["actual_over_expected"] = out.pir / out.expected
    out.index = out.index.astype(str)
    return out.reset_index()


def verdict(P: dict, S1: dict, S2: dict) -> str:
    if (P["delta_hat"] >= DELTA_MIN and P["ci_lo"] > 0
            and S1["delta_hat"] > 0 and S2["delta_hat"] > 0):
        return "enters"
    if P["ci_hi"] < DELTA_MIN:
        return "refuted"
    return "not_identified"


# --------------------------------------------------------------------
def main() -> int:
    h("fatigue_delta — שלב 2 של ADR 0004")
    print(f"  סף {THRESHOLD:g} · רשת [{GRID[0]}, {GRID[-1]}] צעד 0.005 · "
          f"B={B} · seed {SEED} · δ_min {DELTA_MIN}")

    df = load()
    reg = df[df.team_min <= REG_MAX_TEAM_MIN]
    print(f"\n  משחקי שחקן עם דקות: {len(df):,} · "
          f"בזמן חוקי: {len(reg):,} ({len(df) - len(reg):,} בהארכה הושמטו)")
    print(f"  מעל {THRESHOLD:g} דקות: {int((reg.m > THRESHOLD).sum()):,} "
          f"({(reg.m > THRESHOLD).mean():.1%}) · מעל 34: "
          f"{int((reg.m > 34).sum()):,} · מקסימום {reg.m.max():.1f}")

    h("שומרים")
    ok = True
    mt = df.attrs["missing_total"]
    print(f"  {'✅' if mt == 0 else '❌'} כל משחק-קבוצה עם שורת Total      "
          f"חסרות: {mt}")
    ok &= mt == 0
    print(f"     שורות Total ריקות שהושמטו (משחק בלי דקות): {df.attrs['stubs']}")

    syn = synthetic_recovery(reg)
    g1 = abs(syn["exact"] - GUARD_DELTA_TRUE) < 1e-9
    g2 = abs(syn["mean"] - GUARD_DELTA_TRUE) <= GUARD_TOL
    print(f"  {'✅' if g1 else '❌'} 1a שחזור בלי רעש δ_true={GUARD_DELTA_TRUE}"
          f"        δ̂={syn['exact']:+.3f}")
    print(f"  {'✅' if g2 else '❌'} 1b הטיה, {GUARD_REPS} הגרלות"
          f"                  ממוצע δ̂={syn['mean']:+.3f} (±{GUARD_TOL})")
    print(f"     SD בין הגרלות {syn['sd']:.3f} · הגרלה ראשונה {syn['first']:+.3f}"
          f" · רעש למשחק {syn['noise_sd']:.2f} PIR")
    print(f"     ⇒ רזולוציית התכנון: חצי רוחב CI צפוי ≈ {1.96 * syn['sd']:.3f}")
    ok &= g1 and g2
    if not ok:
        print(f"\n  ❌ שומר נכשל. לא נכתב קובץ.\n{SEP}")
        return 1

    h("האומדנים")
    specs = [
        ("P", reg, THRESHOLD, "all regulation games"),
        ("S1", reg[reg.margin <= MARGIN_MAX], THRESHOLD, f"|margin| <= {MARGIN_MAX}"),
        ("S2", reg[reg.fouls < FOUL_OUT], THRESHOLD, f"fouls < {FOUL_OUT}"),
    ]
    specs += [(f"T{int(t)}", reg, t, "threshold sensitivity") for t in SENS_THRESHOLDS]

    pos = pd.read_csv(POSITIONS, dtype={"player_code": str})
    pos["code"] = pd.to_numeric(pos.player_code.str.lstrip("P"), errors="coerce")
    code = pd.to_numeric(reg.pid.str.lstrip("P"), errors="coerce")
    reg_pos = reg.assign(position=code.map(
        pos.dropna(subset=["code"]).drop_duplicates("code")
           .set_index("code").position))
    cov = reg_pos.position.notna().mean()
    for p in ("G", "F", "C"):
        specs.append((f"pos_{p}", reg_pos[reg_pos.position == p], THRESHOLD,
                      "diagnostic only (ADR 0004)"))

    rows = []
    print(f"  {'spec':<7}{'n games':>9}{'>thr':>8}{'groups':>8}{'δ̂':>9}"
          f"{'95% CI':>20}  note")
    for i, (name, d, thr, note) in enumerate(specs):
        if d.empty:
            print(f"  {name:<7}{'—':>9}  ⚠️ אין שורות — המפרט דולג ({note})")
            continue
        r = estimate(d, thr, i)
        r.update(spec=name, note=note)
        rows.append(r)
        flag = "  ⚠️ קצה רשת" if r["at_boundary"] else ""
        print(f"  {name:<7}{r['n_player_games']:>9,}{r['n_tier2_games']:>8,}"
              f"{r['n_groups_tier2']:>8,}{r['delta_hat']:>+9.3f}"
              f"   [{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]  {note}{flag}")
    print(f"\n  כיסוי עמדות: {cov:.1%} ממשחקי השחקן (שורות pos_* בלבד)")

    by = {r["spec"]: r for r in rows}
    if by["P"]["at_boundary"]:
        print(f"\n  ❌ δ̂ של P על קצה הרשת — הרשת חותכת. לא נכתב קובץ.\n{SEP}")
        return 1

    v = verdict(by["P"], by["S1"], by["S2"])
    for r in rows:
        r["verdict"] = (v if r["spec"] == "P" else
                        "sensitivity" if r["spec"] in ("S1", "S2") else
                        "threshold_sensitivity" if r["spec"].startswith("T") else
                        "diagnostic")

    h("אבחון שנוסף אחרי הריצה — פרופיל דקות בתוך שחקן-עונה (תיאורי)")
    bp = bucket_profile(reg)
    print(f"  {'minutes':<14}{'games':>8}{'actual / expected':>20}")
    for _, r in bp.iterrows():
        print(f"  {r.bucket:<14}{int(r.n_games):>8,}{r.actual_over_expected:>20.3f}")
    print("  1.000 = הקצב העונתי של השחקן. עייפות שנראית בבוקססקור = ירידה מעל 30.")

    h("פסק — לפי הכלל שהוצהר ב-ADR 0004")
    P, S1, S2 = by["P"], by["S1"], by["S2"]
    print(f"  δ̂ ≥ {DELTA_MIN} ב-P            {'✅' if P['delta_hat'] >= DELTA_MIN else '❌'}"
          f"  {P['delta_hat']:+.3f}")
    print(f"  ci_lo > 0 ב-P             {'✅' if P['ci_lo'] > 0 else '❌'}"
          f"  {P['ci_lo']:+.3f}")
    print(f"  δ̂ > 0 ב-S1 וב-S2         "
          f"{'✅' if S1['delta_hat'] > 0 and S2['delta_hat'] > 0 else '❌'}"
          f"  {S1['delta_hat']:+.3f} · {S2['delta_hat']:+.3f}")
    print(f"  ci_hi < {DELTA_MIN} ב-P (מופרך) {'✅' if P['ci_hi'] < DELTA_MIN else '❌'}"
          f"  {P['ci_hi']:+.3f}")
    print(f"\n  ⇒ {v}")
    if v == "enters":
        print("     המדרגות נכנסות. שלב 4: tdd על ה-LP, מבחנים T1–T8 קודם.")
    elif v == "refuted":
        print("     המדרגות לא נכנסות. התקרה נשארת 32. תוצאה לגיטימית.")
    else:
        print("     המדרגות לא נכנסות. δ לא זוהה — זה לא 'מופרך'.")

    h("מול התחזיות")
    half = (P["ci_hi"] - P["ci_lo"]) / 2
    for who, (lo, hi) in (("קלוד", PRED_CLAUDE), ("אלמוג", PRED_ALMOG)):
        hit = lo <= P["delta_hat"] <= hi
        print(f"  {who:<6} δ̂ ∈ [{lo:+.2f}, {hi:+.2f}]  ->  {P['delta_hat']:+.3f}"
              f"   {'✅' if hit else '❌'}")
    print(f"  קלוד   חצי רוחב CI ≤ 0.04  ->  {half:.3f}   "
          f"{'✅' if half <= 0.04 else '❌'}")
    print(f"  קלוד   פסק 'refuted' (הסביר ביותר)  ->  {v}   "
          f"{'✅' if v == 'refuted' else '❌'}")
    signs = {np.sign(r["delta_hat"]) for r in (P, S1, S2)}
    print(f"  קלוד   סימן לא יציב בין P/S1/S2  ->  "
          f"{P['delta_hat']:+.3f} · {S1['delta_hat']:+.3f} · {S2['delta_hat']:+.3f}"
          f"   {'✅' if len(signs) > 1 else '❌'}")

    cols = ["spec", "threshold", "note", "n_player_games", "n_tier2_games",
            "n_groups_tier2", "n_groups_both_sides", "n_players", "delta_hat",
            "ci_lo", "ci_hi", "at_boundary", "verdict"]
    pd.DataFrame(rows)[cols].to_csv(OUT, index=False)
    bp.to_csv(OUT_BUCKETS, index=False)
    print(f"\n  נשמר: {OUT.name} · {len(rows)} שורות · {OUT_BUCKETS.name}")
    print(SEP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
