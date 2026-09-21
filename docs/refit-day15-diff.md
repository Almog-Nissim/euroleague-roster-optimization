# Refit run — old vs new, day 15

Implements ADR 0001. Old = `COST_SPEC=club_relative` (day 14, commit `8629441`).
New = `COST_SPEC=market`.

**The side-by-side table below is generated, not typed.** `src/refit_diff.py` reads every
value from tracked result files via `git show` and writes
`data/processed/refit_day15_diff.csv`. The table here is rendered from that CSV. If a number
changes, re-run the script and re-render; do not edit a row by hand. A hand-written version
of this table carried four errors, listed under *Corrections* below.

Generating scripts: `cost_market.py`, `refit_acceptance.py`, `display_money_check.py`,
`curse_selection.py`, `price_error_by_type.py`, `refit_diff.py`.

## What changed in the model

The cost model no longer fits `log(salary / squad_mean)` on Maccabi alone. It fits
`log(salary) = α_club + γ_season + β₁·pir_lag_shrunk + β₂·el_seasons` on every
`usage='calibrate'` row, from the anchors and the external file together, and prices the
pool at the mean α. Under the new spec, `cost` is then divided by the season's pool mean,
so one axis unit is "one average pool player". For 2025 the scale is 1.328.

Two parameters are declared in `cost_market.py`:

- **`SALARY_MAX_SEASON = "test"`** — salary observations up to the test season are
  admissible. Under the old rule (`<= TRAIN_MAX`), 2024 would have been calibrated on TEL
  2023 alone: 12 rows, one club. Half of the 38 club-seasons would then have kept the
  single-club specification, and the pooled `adv_cap` would have mixed two models. β₁ under
  the other rule is printed on every run: 0.2060, against 0.1727.
- **`UNIT`** — see the euro gate below.

## The euro axis was tested and rejected

Pricing at mean α produces a euro level, so the axis could have been labelled in euros.
Three thresholds were declared before the run (`refit_acceptance.py`), and all three
failed. `a` exists on two axes and must be labelled:

| threshold | required | measured |
|---|---|---|
| `fit_eur` slope/intercept | a ∈ [0.85, 1.15], \|b\| ≤ 2.0 | a = 1.087 on the euro-level axis (1.443 normalised), b = −10.52 |
| `fit_eur` MAE | ≤ 2.15 M€ | 2.21 M€ |
| player level, HTA·OLY·BAS | ρ ≥ 0.60 and MAE ≤ 1.35 M€ | ρ = 0.489, MAE = 0.66 M€ |

**Fixed at the source (commit `e4a670b`), verdict unaffected.** The script used to check
condition 1 against the *normalised* `a` (1.443), while the gate asks whether the euro-level
axis reads as euros. It now gates the euro-level `a` (1.0866) — condition 3 in the same file
already multiplied back by `cost_scale` with exactly that reasoning. On that axis `a` passes,
but `b` fails on both axes, so condition 1 fails either way. MAE and ρ do not depend on scale.
`refit_acceptance.csv` now carries both axes in named columns (`fit_eur_a`,
`fit_eur_a_norm`), because the first version of the fix silently broke `refit_diff.py`,
which had inferred the euro-level `a` by dividing the normalised one by `cost_scale`.

Reading the axis directly as euros gives MAE 3.69 M€ on the normalised axis and 8.57 M€ on
the euro-level axis. The 8.57 was quoted in the day-15 note with no tracked source; since
`e4a670b` it is produced by `refit_acceptance.py` as `identity_mae`. The model prices
every club at league-average α, so between-club dispersion is compressed by construction.
Per player the level is roughly right (MAE 0.66 M€), but the ranking (ρ = 0.489) does not
clear the bar.

**Consequence, as agreed in advance:** internal prices are unchanged, the axis is
dimensionless (divided by the season's pool mean), and `fit_eur` stays a display mapper.
The failure is itself a finding: the market refit corrects the *shape* of the price curve,
not its *level* across clubs.

## Side by side

Rendered from `refit_day15_diff.csv`. The source file and commit for every cell are in
the CSV. The last column says whether a *before* value has a tracked results file:

- `tracked` — it does.
- `unsourced` — a before value exists in ADR 0001, CONTEXT.md or an earlier version of
  this document, but no committed file produces it. Treat those as quoted, not reproduced.
- `after_only` — the quantity did not exist before the refit.

Curse cost is a share: ×100 gives percentage points.

| group | quantity | before | after | unit | before |
|---|---|---|---|---|---|
| cost | `beta1` | — | 0.1727 | log/pir | unsourced |
| cost | `calib_n` | — | 61 | rows | unsourced |
| cost | `calib_clubs` | — | 13 | clubs | unsourced |
| cost | `calib_r2` | — | 0.813 |  | unsourced |
| cost | `cost_scale` | — | 1.328 | pool mean | after_only |
| cost | `club_budget_median` | — | 17.408 | normalised axis | unsourced |
| euro_gate | `fit_eur_a` | — | 1.4429 | normalised axis | unsourced |
| euro_gate | `fit_eur_a` | — | 1.0866 | euro-level axis (gated) | after_only |
| euro_gate | `fit_eur_b` | — | -10.5159 | M EUR | unsourced |
| euro_gate | `fit_eur_mae` | — | 2.21 | M EUR | unsourced |
| euro_gate | `axis_read_as_euro_mae` | — | 3.687 | M EUR, normalised axis | after_only |
| euro_gate | `axis_read_as_euro_mae` | — | 8.572 | M EUR, euro-level axis | after_only |
| euro_gate | `player_rho` | — | 0.4889 | Spearman | after_only |
| euro_gate | `player_mae` | — | 0.663 | M EUR | after_only |
| euro_gate | `gates_passed` | — | 0 | of 3 | after_only |
| advantage | `adv_free_median` | 0.1826 | 0.1682 | share | tracked |
| advantage | `adv_cap_median` | 0.0652 | 0.1414 | share | tracked |
| advantage | `clubs_engine_loses_to` | 7 | 0 | of 38 | tracked |
| advantage | `q_cap_gt_q_free_on_ppm_true` | 1 | 16 | of 38 | tracked |
| advantage | `selection_bias_free_median` | -0.0278 | -0.0066 | share of pool ppm | tracked |
| advantage | `selection_bias_free_weighted_median` | -0.0605 | 0.0067 | share of pool ppm | tracked |
| advantage | `selection_bias_cap_median` | 0.0654 | -0.0359 | share of pool ppm | tracked |
| advantage | `curse_cost_free_median` | 0.0294 | 0.0966 | share (x100 = pp) | tracked |
| advantage | `curse_cost_cap_median` | 0.0553 | 0.0246 | share (x100 = pp) | tracked |
| headline | `headline_capped_wins` | 2.0333 | 4.2617 | wins | tracked |
| headline | `headline_capped_wins_lo` | 0.3843 | 0.9189 | wins | tracked |
| headline | `headline_capped_wins_hi` | 3.6777 | 7.4511 | wins | tracked |
| headline | `headline_free_wins` | 5.1733 | 4.9013 | wins | tracked |
| headline | `headline_free_wins_lo` | 1.2881 | 1.2592 | wins | tracked |
| headline | `headline_free_wins_hi` | 9.1386 | 9.0365 | wins | tracked |
| headline | `gap_random_club_wins` | -1.6519 | -1.7238 | wins | tracked |
| headline | `gap_free_random_wins` | 6.845 | 6.6088 | wins | tracked |
| headline | `wasted_budget_share` | 0.2688 | 0.3082 | share | tracked |
| sweep | `saturation` | 25 | 22.5 | normalised axis | tracked |
| sweep | `spend_ceiling` | — | 23.43 | normalised axis | after_only |
| sweep | `flat_points` | — | 36 | of 65 | after_only |
| sweep | `saturation_regime` | — | `exhausted` |  | after_only |
| sweep | `utilisation_at_top_of_grid` | 0.979 | 0.5857 | spent / budget | tracked |
| sweep | `md5 roster_sweep.json` | `c285173871cf` | `f26e57f601b2` | git blob | tracked |
| sweep | `md5 dashboard_data.json` | `e5bbe2f8285b` | `265fb5274926` | git blob | tracked |
| price_error | `price_error_slope_log_oos` | 0.0883 | 0.0288 | log per pir unit | tracked |
| price_error | `price_error_slope_log_oos_p` | 0.0169 | 0.4488 | p | tracked |
| price_error | `price_error_slope_m_oos` | 0.0807 | 0.0968 | M EUR per pir unit | tracked |
| price_error | `price_error_slope_m_oos_p` | 0.202 | 0.1267 | p | tracked |
| price_error | `picks_minus_skipped_err_median` | 0.2766 | 0.1907 | M EUR (negative = arbitrage) | tracked |
| display | `display_money_mae` | — | 0.893 | M EUR | unsourced |
| display | `display_money_rho` | — | 0.895 | Spearman | unsourced |
| display | `display_money_negative` | — | 1 | players | after_only |

Values stated on day 15 that no tracked file produces, so they are not in the table:

- the most expensive pool player: 10.24× → 4.68× the mean
- the median 2025 club budget before the refit: 20.25
- the roster change at the median club budget: 5 of 12
- `s_partial / s_raw`: 0.42 → 0.636
- displayed money before the refit: MAE 1.279, ρ 0.610

## Saturation flipped regime

The old note said the slider flattens because money stops buying improvement while the
pool is still being spent: "diminishing returns, not exhaustion". Utilisation at the top
of the grid was 0.979.

Under the new prices that is false. `q_LP` stops rising at 22.5, and spending freezes at
23.43 from budget 23.5 onward. The engine holds the best 12 players the pool allows under
the minutes constraint, roster churn is zero, and utilisation at the top of the grid falls
to 0.586. 36 of 65 slider points are flat. The guard in `roster_sweep.py` caught this and
stopped the build twice before the note was rewritten. It now classifies the regime and
checks the claim that matches it.

**Open product decision, not implemented:** `B_HI = 40.0` now leaves more than half the
slider dead. It should probably come down to about 24.

## Provenance — resolved

The day-15 refit ran first in a sandbox, on a *regenerated*
`usage_curve_results_min0.csv`. That file is not identical to the one used on day 14: it
reproduces the free side exactly but gives a day-14 `adv_cap` median of 0.0796 instead of
0.0652.

The original file was on the local machine and has been tracked since `8661308`.
`refit_diff.py` now checks, row by row, that `club_relative` on it reproduces the day-14
`usage_constrained_results.csv` (max |Δ| = 0). Every number in the table comes from the
original file.

## Corrections to the hand-written table

| row | hand-written | tracked files |
|---|---|---|
| curse cost, free | 9.7 → 2.9 | 2.9 → 9.7 pp: before and after were swapped |
| curse cost, capped | 2.5 → 5.5 | 5.5 → 2.5 pp: swapped |
| clubs the engine loses to | 7 → 1 | 7 → 0 |
| `q_cap > q_free` on `ppm_true` | 4 → 18 | 1 → 16 |
| `dashboard_data.json` md5, after | `15fde5d0ee64` | `265fb5274926` |
| `fit_eur` a | 1.087 and 1.4430 in two tables, unlabelled | the same fit on two axes; labelled above |

The 1/38, 18/38 and 4/38 values came from the sandbox run on the regenerated usage file.
