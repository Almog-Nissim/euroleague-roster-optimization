# src/

Research code for the EuroLeague roster engine. Scripts are run directly
(`python src/<name>.py`) and import each other by name, so they all live in one
folder. The engine is frozen at `v1.0`: only bug fixes from here.

Every script prints its guards (✅/❌). A script that writes a tracked results file
is the only source of the numbers in that file.

## Headline path — start here

Run in this order to reproduce the v1.0 number (see the root README).

- `scoring.py` — shape caps, the shape constraint, and the scoring conventions (ADR 0005/0006)
- `shape_constraint_test.py` — 24 tests on the LP and the scorer
- `headline_exact.py` — the headline: 38 exact solves at gap = 0
- `wins_conversion.py` — production gap -> wins, with the bootstrap CI
- `export_dashboard.py` — checks every frozen value, then writes dashboard_data.json

## The engine

Imported by the headline path.

- `usage_constrained.py` — the headline LP: budget, roster, positions, ball identity, shape
- `optimise_consistent.py` — the LP without the usage constraint
- `minute_profile.py` — minute caps and the top-k shape profile of real clubs
- `cost_market.py` — the market cost model (ADR 0001), production
- `roster_optimizer.py` — shared LP helpers and the single-club demo path

## Dashboard and figures

- `roster_sweep.py` — the builder curve: the headline engine at every budget
- `readme_figure.py` — figures/headline_advantage.svg
- `methods_pdf.py` — docs/methods-he.md -> PDF

## Checks behind the claim

Refutations, sensitivity and audits quoted in the README and the ADRs.

- `score_to_wins.py` — production -> wins with a budget control
- `pool_restriction_check.py` — is 38/38 an artefact of the pool? (no)
- `slack_sensitivity.py` — sensitivity of the headline to the shape caps
- `shape_run.py` — the full ADR 0005/0006 grid, 152 solves
- `null_to_wins.py` — random roster under the same constraints -> wins
- `fatigue_delta.py` — the fatigue estimate rejected in ADR 0004
- `refit_acceptance.py` — the euro axis acceptance test (failed)
- `refit_diff.py` — before/after table for the ADR 0001 refit
- `fair_compare.py` — why predicted-vs-predicted inflates the result
- `why_100.py` — why the usage identity is 100%
- `dump_rosters.py` — engine and club rosters, for inspection
- `roster_membership_audit.py` — who is on each roster, and why

## Data pipeline

Pulls box scores from the EuroLeague API and builds the tracked tables in data/processed.

`el_api` · `fetch_boxscores` · `fetch_boxscores_v2` · `fetch_all_accumulated` · `fetch_phases` · `game_index` · `team_games` · `verify_boxscores` · `build_team_season` · `build_player_season` · `build_features` · `build_positions` · `positions_probe` · `positions_merge` · `fix_positions` · `split_multiclub` · `id_seam` · `fetch_israeli_league` · `match_israeli_league` · `build_anchors` · `tag_external_usage` · `add_budgets_2025`

## Models

Inputs to the engine.

`production_model` · `avaliabillity_model` · `avail_uncertainty` · `salary_market` · `replacement_level` · `newcomer_pool` · `club_rosters` · `cost_model`

## Shared helpers

`paths` · `el_paths` · `player_id` · `club_codes`

## Earlier stages and diagnostics

How the project got here: earlier backtests, curse and depth studies, scale and
season checks, one-off fixes. Kept because their outputs are quoted in the ADRs, the
archive or the day notes. Not needed to reproduce v1.0. `cost_model.py` above is the
retired `club_relative` spec, kept to reproduce the day-14 numbers (see `CONTEXT.md`).

`Oos_hapoel` · `absence_position_test` · `avail_denominator_check` · `backtest` · `backtest_diagnostics` · `benchmark_matched` · `beta_decomp` · `boxscore_row_profile` · `budget_curve` · `club_usage_bias` · `cost_reality` · `crowding` · `crowding_extrapolation` · `curse_decomp` · `curse_redistribution` · `curse_selection` · `decode_score` · `depth_sweep` · `depth_value` · `depth_vs_budget` · `diagnose_2018` · `dilution_test` · `display_money_check` · `final_day7` · `final_fix` · `index_audit` · `index_invariance_test` · `league_backtest` · `league_conversion_test` · `league_jump_test` · `lock_regularization` · `oly_split` · `optimizer_backtest` · `pessimism_sweep` · `price_error_by_type` · `price_structure` · `quota_cost` · `ratio2025` · `real_returns` · `roster_usage` · `scale_regression` · `scale_sensitivity` · `season_gap_test` · `season_heterogeneity` · `sensitivity_concentration` · `share_roster_size` · `spec_nim_lag` · `stochastic_avail` · `stochastic_crn` · `usage_budget` · `usage_curve` · `usage_decompose` · `usage_feasibility` · `usage_power_check` · `v0_pipeline`
