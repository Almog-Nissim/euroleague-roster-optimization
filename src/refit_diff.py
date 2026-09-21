"""
refit_diff.py — טבלת לפני/אחרי של הריפיט (ADR 0001), מקבצים שבמעקב בלבד.

--------------------------------------------------------------------
למה הסקריפט קיים
--------------------------------------------------------------------
`docs/refit-day15-diff.md` הפנה ל-`refit_day15_diff.csv` כקובץ התוצאות
של הטבלה, אבל שום סקריפט לא ייצר אותו. הטבלה נכתבה ביד, ובדיעבד
נמצאו בה:
    · שורות עלות הקללה עם לפני/אחרי מוחלפים;
    · "clubs the engine loses to" ו-"q_cap > q_free" מהסנדבוקס
      (קובץ usage משוחזר), לא מהקובץ המקורי;
    · fit_eur a על שני צירים שונים באותה טבלה בלי תיוג.
טבלה שנכתבת ביד יכולה לסתור את הקבצים שהיא מתארת. זו לא.

--------------------------------------------------------------------
איך
--------------------------------------------------------------------
כל ערך נקרא דרך `git show <ref>:<path>` — כלומר מהגרסה **שבמעקב**,
לא מעץ העבודה. "לפני" נקרא מקומיט יום 14 (האחרון לפני ADR 0001)
כשהקובץ היה קיים אז; ערכי לפני שנוצרו רק אחר כך במפרט club_relative
(קבצי הקללה ושגיאת התמחור) נקראים מ-HEAD, מהקובץ של המפרט הישן.
עמודות source_before / source_after אומרות מאיפה כל ערך הגיע.

ערך "לפני" חסר מסיבה אחת משתיים, ועמודת before_status מבדילה ביניהן:
    unsourced   — היה ערך לפני, הוא כתוב במסמך או ב-ADR, אבל אין לו
                  קובץ תוצאות שבמעקב. source_before אומר איפה הוא כתוב.
                  זה חוב, לא מידע.
    after_only  — המושג לא היה קיים לפני הריפיט (שער היורו, משטר
                  הרוויה, סקאלת הנרמול). אין מה לחפש.
הסקריפט אינו מקליד מספר אחד ביד — גם לא את ערכי ה-unsourced.

md5 מחושב על הבייטים שב-git (LF), כמו בטבלה המקורית. על עץ עבודה
ב-Windows עם autocrlf הקובץ המקומי יכול להיות CRLF ולתת hash אחר.

--------------------------------------------------------------------
שומרים — עוצרים את הריצה
--------------------------------------------------------------------
1. adv_cap בקובץ הקללה חייב להיות זהה, שורה-שורה, ל-adv_cap
   ב-usage_constrained_results.csv — במפרט הישן מול יום 14, ובחדש
   מול HEAD. אחרת שני הקבצים רצו על קבצי usage שונים (זו בדיוק
   התקלה של יום 15).
2. 38 עונות-מועדון בכל צד.
3. מדגם הנקי (HTA/OLY/BAS) בשגיאת התמחור: n=34 בשני המפרטים.

קובץ קלט עם שינוי שלא נכנס לקומיט — אזהרה, לא עצירה: הטבלה מתארת
את מה שבמעקב, והאזהרה אומרת שעץ העבודה שונה ממנו.

--------------------------------------------------------------------
פרמטרים מוצהרים
--------------------------------------------------------------------
BEFORE_REF = 8629441   יום 14, האחרון לפני הריפיט (club_relative)
AFTER_REF  = HEAD
OOS_CLUBS  = HTA, OLY, BAS  (מחוץ לכיול — כמו price_error_by_type)
TOL        = 1e-9

הרצה:  python src/refit_diff.py
פלט:   data/processed/refit_day15_diff.csv
"""

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paths import PROCESSED_DIR, ROOT_DIR  # noqa: E402

BEFORE_REF = "8629441"
AFTER_REF = "HEAD"
OOS_CLUBS = ("HTA", "OLY", "BAS")
TOL = 1e-9
N_CLUB_SEASONS = 38
N_OOS = 34

OUT = PROCESSED_DIR / "refit_day15_diff.csv"
SEP = "=" * 80

P = "data/processed/"
D = "data/dashboard/"
MINUS = "\u2212"                       # כמו ב-null_to_wins.csv

INPUTS = [
    P + "curse_selection_club_relative.csv",
    P + "curse_selection_market.csv",
    P + "usage_constrained_results.csv",
    P + "price_error_club_relative.csv",
    P + "price_error_market.csv",
    P + "refit_acceptance.csv",
    P + "display_money_check.csv",
    P + "wins_conversion.csv",
    P + "null_to_wins.csv",
    P + "why_100_results.csv",
    D + "roster_sweep.json",
    D + "dashboard_data.json",
]


# --------------------------------------------------------------------
# git
# --------------------------------------------------------------------
def git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT_DIR,
                          capture_output=True, check=False)


def blob(ref: str, rel: str) -> bytes:
    r = git("show", f"{ref}:{rel}")
    if r.returncode != 0:
        raise FileNotFoundError(f"{rel} אינו במעקב ב-{ref}")
    return r.stdout


def csv_at(ref: str, rel: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(blob(ref, rel)))


def json_at(ref: str, rel: str) -> dict:
    return json.loads(blob(ref, rel).decode("utf-8"))


def md5_at(ref: str, rel: str) -> str:
    return hashlib.md5(blob(ref, rel)).hexdigest()[:12]


def src(ref: str, rel: str) -> str:
    return f"{ref}:{rel}"


# --------------------------------------------------------------------
# שורות
# --------------------------------------------------------------------
ROWS: list[dict] = []


UNSRC_ADR1 = "unsourced: ADR 0001"
UNSRC_CTX = "unsourced: CONTEXT.md (day-14 axis, TEL prices)"
UNSRC_DOC = "unsourced: docs/refit-day15-diff.md"
AFTER_ONLY = "after-only"


def num(v):
    """ספירות נשארות int, כל השאר float."""
    return int(v) if isinstance(v, (int, np.integer)) else float(v)


def row(group, quantity, unit, before, after, sb, sa):
    if sb == AFTER_ONLY:
        status = "after_only"
    elif sb.startswith("unsourced"):
        status = "unsourced"
    else:
        status = "tracked"
    ROWS.append(dict(group=group, quantity=quantity, unit=unit,
                     before=before, after=after, before_status=status,
                     source_before=sb, source_after=sa))


def ols(d: pd.DataFrame, y: str) -> tuple[float, float]:
    X = sm.add_constant(d["pir_lag_shrunk"].astype(float))
    r = sm.OLS(d[y].astype(float), X).fit()
    return float(r.params["pir_lag_shrunk"]), float(r.pvalues["pir_lag_shrunk"])


def guard(name: str, ok: bool, detail: str) -> bool:
    print(f"  {'✅' if ok else '❌'} {name:<44} {detail}")
    return ok


# --------------------------------------------------------------------
def main() -> int:
    print(SEP)
    print(f"refit_diff — לפני {BEFORE_REF} · אחרי {AFTER_REF} · מקבצים שבמעקב")
    print(SEP)

    head = git("rev-parse", "--short", AFTER_REF).stdout.decode().strip()
    print(f"  {AFTER_REF} = {head}")

    dirty = [f for f in INPUTS
             if git("diff", "--quiet", AFTER_REF, "--", f).returncode != 0]
    if dirty:
        print("  ⚠️ שינויים שלא נכנסו לקומיט — הטבלה מתעלמת מהם:")
        for f in dirty:
            print(f"     {f}")

    ok = True
    print(f"\n{SEP}\nשומרים\n{SEP}")

    # ---------------- הקללה והיתרון ----------------
    cr_rel = P + "curse_selection_club_relative.csv"
    mk_rel = P + "curse_selection_market.csv"
    uc_rel = P + "usage_constrained_results.csv"
    cr, mk = csv_at(AFTER_REF, cr_rel), csv_at(AFTER_REF, mk_rel)
    uc_b, uc_a = csv_at(BEFORE_REF, uc_rel), csv_at(AFTER_REF, uc_rel)

    for tag, cur, uc in (("club_relative מול יום 14", cr, uc_b),
                         ("market מול HEAD", mk, uc_a)):
        m = cur.merge(uc, on=["season", "club"], suffixes=("", "_u"))
        diff = float((m.adv_cap - m.adv_cap_u).abs().max())
        ok &= guard(f"adv_cap זהה · {tag}",
                    len(m) == N_CLUB_SEASONS and diff <= TOL,
                    f"n={len(m)} · max|Δ|={diff:.1e}")

    for tag, cur in (("club_relative", cr), ("market", mk)):
        ok &= guard(f"{N_CLUB_SEASONS} עונות-מועדון · {tag}",
                    len(cur) == N_CLUB_SEASONS, f"n={len(cur)}")

    # ---------------- שגיאת תמחור ----------------
    pe_rel = {s: P + f"price_error_{s}.csv" for s in ("club_relative", "market")}
    pe = {s: csv_at(AFTER_REF, r) for s, r in pe_rel.items()}
    for s, d in pe.items():
        n = int(d.club.isin(OOS_CLUBS).sum())
        ok &= guard(f"מדגם נקי n={N_OOS} · {s}", n == N_OOS, f"n={n}")

    if not ok:
        print(f"\n  ❌ שומר נכשל. לא נכתב קובץ.\n{SEP}")
        return 1

    # ---------------- מודל העלות ושער היורו ----------------
    ra_rel = P + "refit_acceptance.csv"
    rs_rel = D + "roster_sweep.json"
    ra = csv_at(AFTER_REF, ra_rel).iloc[0]
    rs_b, rs_a = json_at(BEFORE_REF, rs_rel), json_at(AFTER_REF, rs_rel)
    cm = rs_a["meta"]["cost_model"]
    scale = float(cm["cost_scale"])
    sa_ra, sa_rs = src(head, ra_rel), src(head, rs_rel)

    row("cost", "beta1", "log/pir", np.nan, float(ra.beta1), UNSRC_ADR1, sa_ra)
    row("cost", "calib_n", "rows", np.nan, int(ra.n_fit), UNSRC_ADR1, sa_ra)
    row("cost", "calib_clubs", "clubs", np.nan, int(ra.n_clubs_fit),
        UNSRC_ADR1, sa_ra)
    row("cost", "calib_r2", "", np.nan, float(cm["r2"]), UNSRC_ADR1, sa_rs)
    row("cost", "cost_scale", "pool mean", np.nan, scale, AFTER_ONLY, sa_rs)
    row("cost", "club_budget_median", "normalised axis", np.nan,
        float(ra.club_budget_median), UNSRC_DOC, sa_ra)

    # 🔴 שני הצירים נקראים בשמם. קודם fit_eur_a פורש כמנורמל וציר היורו
    #    הוסק בחלוקה ב-scale — הנחה שנשברה בשקט כשתנאי 1 תוקן לציר היורו.
    row("euro_gate", "fit_eur_a", "normalised axis", np.nan,
        float(ra.fit_eur_a_norm), UNSRC_CTX, sa_ra)
    row("euro_gate", "fit_eur_a", "euro-level axis (gated)", np.nan,
        float(ra.fit_eur_a), AFTER_ONLY, sa_ra)
    row("euro_gate", "fit_eur_b", "M EUR", np.nan, float(ra.fit_eur_b),
        UNSRC_CTX, sa_ra)
    row("euro_gate", "fit_eur_mae", "M EUR", np.nan, float(ra.fit_eur_mae),
        UNSRC_CTX, sa_ra)
    row("euro_gate", "axis_read_as_euro_mae", "M EUR, normalised axis",
        np.nan, float(ra.identity_mae_norm), AFTER_ONLY, sa_ra)
    row("euro_gate", "axis_read_as_euro_mae", "M EUR, euro-level axis",
        np.nan, float(ra.identity_mae), AFTER_ONLY, sa_ra)
    row("euro_gate", "player_rho", "Spearman", np.nan, float(ra.player_rho),
        AFTER_ONLY, sa_ra)
    row("euro_gate", "player_mae", "M EUR", np.nan, float(ra.player_mae),
        AFTER_ONLY, sa_ra)
    row("euro_gate", "gates_passed", "of 3", np.nan,
        int(ra.t1) + int(ra.t2) + int(ra.t3), AFTER_ONLY, sa_ra)

    # ---------------- יתרון וקללה ----------------
    sb_c, sa_c = src(head, cr_rel), src(head, mk_rel)
    for q, unit, fn in [
        ("adv_free_median", "share", lambda d: d.adv_free.median()),
        ("adv_cap_median", "share", lambda d: d.adv_cap.median()),
        ("clubs_engine_loses_to", f"of {N_CLUB_SEASONS}",
         lambda d: int((d.adv_cap < 0).sum())),
        ("q_cap_gt_q_free_on_ppm_true", f"of {N_CLUB_SEASONS}",
         lambda d: int((d.q_true_cap > d.q_true_free).sum())),
        ("selection_bias_free_median", "share of pool ppm",
         lambda d: d.bias_free.median()),
        ("selection_bias_free_weighted_median", "share of pool ppm",
         lambda d: d.bias_w_free.median()),
        ("selection_bias_cap_median", "share of pool ppm",
         lambda d: d.bias_cap.median()),
        ("curse_cost_free_median", "share (x100 = pp)",
         lambda d: d.curse_pp_free.median()),
        ("curse_cost_cap_median", "share (x100 = pp)",
         lambda d: d.curse_pp_cap.median()),
    ]:
        row("advantage", q, unit, num(fn(cr)), num(fn(mk)), sb_c, sa_c)

    # ---------------- כותרת ----------------
    wc_rel, nw_rel, wb_rel = (P + "wins_conversion.csv", P + "null_to_wins.csv",
                              P + "why_100_results.csv")
    wc = {r: csv_at(r, wc_rel) for r in (BEFORE_REF, AFTER_REF)}
    nw = {r: csv_at(r, nw_rel) for r in (BEFORE_REF, AFTER_REF)}
    wb = {r: csv_at(r, wb_rel) for r in (BEFORE_REF, AFTER_REF)}

    def eng(d, key):
        return d[d.engine.str.contains(key)].iloc[0]

    def gap(d, key):
        return d[d.gap.str.contains(key, regex=False)].iloc[0]

    for q, key in (("headline_capped_wins", "מאולץ"), ("headline_free_wins", "חופשי")):
        for suffix, col in (("", "wins"), ("_lo", "lo"), ("_hi", "hi")):
            row("headline", q + suffix, "wins",
                float(eng(wc[BEFORE_REF], key)[col]),
                float(eng(wc[AFTER_REF], key)[col]),
                src(BEFORE_REF, wc_rel), src(head, wc_rel))
    for q, key in (("gap_random_club_wins", f"אקראי {MINUS} מועדון"),
                   ("gap_free_random_wins", f"חופשי {MINUS} אקראי")):
        row("headline", q, "wins",
            float(gap(nw[BEFORE_REF], key).wins),
            float(gap(nw[AFTER_REF], key).wins),
            src(BEFORE_REF, nw_rel), src(head, nw_rel))
    row("headline", "wasted_budget_share", "share",
        float(wb[BEFORE_REF].cost_wasted.median()),
        float(wb[AFTER_REF].cost_wasted.median()),
        src(BEFORE_REF, wb_rel), src(head, wb_rel))

    # ---------------- הסליידר ----------------
    sb_rs = src(BEFORE_REF, rs_rel)
    det = rs_a["meta"]["saturation_detail"]
    top_b, top_a = rs_b["free"][-1], rs_a["free"][-1]
    row("sweep", "saturation", "normalised axis",
        float(rs_b["meta"]["saturation"]), float(rs_a["meta"]["saturation"]),
        sb_rs, sa_rs)
    row("sweep", "spend_ceiling", "normalised axis", np.nan,
        float(det["spend_ceiling"]), AFTER_ONLY, sa_rs)
    row("sweep", "flat_points", f"of {det['n_points']}", np.nan,
        int(det["n_flat"]), AFTER_ONLY, sa_rs)
    row("sweep", "saturation_regime", "", np.nan, det["regime"],
        AFTER_ONLY, sa_rs)
    row("sweep", "utilisation_at_top_of_grid", "spent / budget",
        float(top_b["spent"]) / float(top_b["budget"]),
        float(top_a["spent"]) / float(top_a["budget"]), sb_rs, sa_rs)
    for rel in (rs_rel, D + "dashboard_data.json"):
        row("sweep", "md5 " + Path(rel).name, "git blob",
            md5_at(BEFORE_REF, rel), md5_at(AFTER_REF, rel),
            src(BEFORE_REF, rel), src(head, rel))

    # ---------------- שגיאת תמחור ----------------
    for q, unit, fn in [
        ("price_error_slope_log_oos", "log per pir unit",
         lambda d: ols(d[d.club.isin(OOS_CLUBS)], "err_log")[0]),
        ("price_error_slope_log_oos_p", "p",
         lambda d: ols(d[d.club.isin(OOS_CLUBS)], "err_log")[1]),
        ("price_error_slope_m_oos", "M EUR per pir unit",
         lambda d: ols(d[d.club.isin(OOS_CLUBS)], "err_m")[0]),
        ("price_error_slope_m_oos_p", "p",
         lambda d: ols(d[d.club.isin(OOS_CLUBS)], "err_m")[1]),
        ("picks_minus_skipped_err_median", "M EUR (negative = arbitrage)",
         lambda d: d[d.chosen].err_m.median() - d[~d.chosen].err_m.median()),
    ]:
        row("price_error", q, unit, float(fn(pe["club_relative"])),
            float(fn(pe["market"])),
            src(head, pe_rel["club_relative"]), src(head, pe_rel["market"]))

    # ---------------- כסף מוצג ----------------
    dm_rel = P + "display_money_check.csv"
    dm = csv_at(AFTER_REF, dm_rel).iloc[0]
    for q, unit, col, sb in (
            ("display_money_mae", "M EUR", "mae", UNSRC_DOC),
            ("display_money_rho", "Spearman", "rho", UNSRC_DOC),
            ("display_money_negative", "players", "n_negative", AFTER_ONLY)):
        v = dm[col]
        v = int(v) if col == "n_negative" else float(v)
        row("display", q, unit, np.nan, v, sb, src(head, dm_rel))

    # ---------------- פלט ----------------
    out = pd.DataFrame(ROWS)
    out.to_csv(OUT, index=False)

    h = f"{'group':<12}{'quantity':<40}{'before':>14}{'after':>14}  unit"
    print(f"\n{SEP}\nהטבלה\n{SEP}\n  {h}")

    def fmt(v):
        if isinstance(v, str):
            return v
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "—"
        return f"{v:.4f}" if isinstance(v, float) else str(v)

    for r in ROWS:
        print(f"  {r['group']:<12}{r['quantity']:<40}"
              f"{fmt(r['before']):>14}{fmt(r['after']):>14}  {r['unit']}")

    def label(r):
        return r["quantity"] + (f" [{r['unit']}]" if r["unit"] else "")

    for status, title in (("unsourced", "לפני קיים אבל בלי קובץ תוצאות — חוב"),
                          ("after_only", "לפני לא קיים — מושג חדש, אין חוב")):
        rs = [r for r in ROWS if r["before_status"] == status]
        print(f"\n  {title} ({len(rs)}):")
        for r in rs:
            where = (f"  ← {r['source_before'].split(': ', 1)[1]}"
                     if status == "unsourced" else "")
            print(f"     {label(r)}{where}")
    print(f"\n  נשמר: {OUT.name} · {len(ROWS)} שורות")
    print(SEP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
