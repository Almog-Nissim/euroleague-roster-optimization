# Refit run — old vs new, day 15

Implements ADR 0001, steps 2–5 of `refit-run-spec.md`. Step 1 was already
committed (`b93e383`) and was not re-run.

Generating scripts: `cost_market.py`, `refit_acceptance.py`,
`display_money_check.py`. Results file: `data/processed/refit_day15_diff.csv`.

## What changed in the model

The cost model no longer fits `log(salary / squad_mean)` on Maccabi alone. It
fits `log(salary) = α_club + γ_season + β₁·pir_lag_shrunk + β₂·el_seasons`
on every `usage='calibrate'` club, and prices the pool at the mean α.

Two parameters had to be decided and are declared in `cost_market.py`:

- **`SALARY_MAX_SEASON = "test"`** — salary observations up to the test season
  are admissible. Under the old rule (`<= TRAIN_MAX`) the 2024 test season
  would have been calibrated on TEL 2023 alone, 12 rows and one club, so half
  of the 38 club-seasons would have kept the single-club specification and the
  pooled `adv_cap` would have mixed two models. β₁ under the other rule is
  printed on every run: **0.2060** against 0.1727.
- **`UNIT`** — see the acceptance test below.

## The euro axis was tested and rejected

Pricing at mean α produces a euro level, so the axis could have been labelled
in euros directly. Three thresholds were declared before the run
(`refit_acceptance.py`) and all three failed:

| threshold | required | measured |
|---|---|---|
| `fit_eur` slope/intercept | a ∈ [0.85, 1.15], \|b\| ≤ 2.0 | a = 1.087, b = −10.52 |
| `fit_eur` MAE | ≤ 2.15 M€ | 2.21 M€ |
| player-level, HTA·OLY·BAS | ρ ≥ 0.60 and MAE ≤ 1.35 M€ | ρ = 0.489, MAE = 0.66 M€ |

Reading the axis as euros gives MAE 8.57 M€ against real club budgets: the
model prices every club at league-average α, so between-club dispersion is
compressed by construction. BAS is priced at 23.2 and pays 8.5; ASV at 16.8
and pays 5.0. The player-level MAE passes comfortably — the level is roughly
right per player — but the ranking (ρ = 0.489) does not clear the bar.

**Consequence, as agreed in advance:** internal prices are unchanged, the axis
is divided by the season's pool mean (scale 1.328 for 2025), and one axis unit
is "one average pool player". `fit_eur` stays a display mapper. The failure is
itself a finding: the market refit corrects the *shape* of the price curve, not
its *level* across clubs.

## Side by side

| quantity | before            | after                          |
|---|-------------------|--------------------------------|
| β₁ | 0.2317            | **0.1727** (se 0.0298, t 5.81) |
| calibration sample | n = 27, 1 club    | n = 61, 13 clubs, R² 0.813     |
| most expensive pool player | 10.24× mean       | 4.68× mean                     |
| median 2025 club budget | 20.25             | 17.41                          |
| saturation | 25.0              | **22.5**                       |
| spend ceiling | —                 | **23.43 from budget 23.5**     |
| `fit_eur` a, b | 0.7639, −2.1195   | 1.4430, −10.5159               |
| `fit_eur` MAE | 2.15 M€           | 2.21 M€                        |
| `adv_free` median | +18.26 %          | +16.82 %                       |
| `adv_cap` median | +6.52 %           | **+14.1 %**                    |
| clubs the engine loses to | 7 / 38            | 1 / 38                         |
| `q_cap > q_free` on `ppm_true` | 4 / 38            | **18 / 38**                    |
| `headline_capped_wins` | 2.03              | 4.26                           |
| `headline_free_wins` | 5.17              | 4.90                           |
| `gap_random_club_wins` | −1.65             | −1.72                          |
| `gap_free_random_wins` | 6.84              | 6.61                           |
| `wasted_budget_share` | 0.269             | 0.308                          |
| displayed money vs real salary | MAE 1.279, ρ 0.610 | MAE 0.893, ρ 0.895             |
| `roster_sweep.json` md5 | `c285173871cf`    | `f26e57f601b2`                 |
| `dashboard_data.json` md5 | `e5bbe2f8285b`    | `15fde5d0ee64`                 |
| 's_partial/s_raw | 0.42              | 0.636                          |

Roster changes at the median club budget (each specification at its own median
club budget, i.e. the same real basket): **5 of 12** in, 5 out, 7 unchanged.
At the same nominal grid point (20.0), 3 of 12 — but that compares different
baskets, because the axis moved.

## Saturation flipped regime

The old note said the slider flattens because money stops buying improvement
while the pool is still being spent — "diminishing returns, not exhaustion",
supported by 99.1 % utilisation above 25.

Under the new prices that is false. `q_LP` stops rising at 22.5 and spending
freezes at 23.43 from budget 23.5 onward: the engine holds the best 12 players
the pool allows under the minutes constraint, roster churn is zero, and
utilisation falls to 58.6 % at the top of the grid. 36 of 65 slider points are
flat. The guard in `roster_sweep.py` caught this and stopped the build twice
before the note was rewritten; it now classifies the regime and checks the
claim that matches it.

**Open product decision, not implemented:** `B_HI = 40.0` now leaves more than
half the slider dead. It should probably come down to about 24.

## What was not verified

`usage_curve_results_min0.csv` is not in the repo — `.gitignore` whitelists
`usage_curve_results.csv` but not the `_min0` variant. It was regenerated here
with `usage_curve.py --min-minutes 0`, and the regenerated file is **not**
identical to the one used on day 14: re-running the old model with it reproduces
the free side exactly (`lp_free` to 1e-12, `adv_free` median 0.18259 unchanged)
but gives `adv_cap` median 0.0796 instead of 0.0652, with 4 negatives instead
of 7. The weighted usage of an identical roster differs, so the input differs,
not the solver.

Everything downstream of the capped path therefore carries an offset of roughly
+1.4 percentage points on `adv_cap` before the refit is counted:
`adv_cap_median`, `headline_capped_wins`, and `gap_random_club_wins` /
`gap_free_random_wins`. Measured on one consistent usage file, the refit moves
`adv_cap` from 0.0796 to 0.1724. **The authoritative numbers must come from a
local run with the real usage file.** Commit that file, or the pipeline is not
reproducible.
