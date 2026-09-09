# Refit run spec — market-calibrated cost model

Implements ADR 0001. Predictions below are locked before the run.

## Locked predictions

| Quantity | Almog | Claude |
|---|---|---|
| β₁ after refit | shrinks (no digit given) | 0.175 |
| `adv_cap` median after refit | ~10% | 7.5–9% |
| Roster changes at median budget, of 16 | 3–4 | 5–7 |

Current values for reference: β₁ = 0.2317, `adv_cap` median = 0.0652, `adv_free`
median = 0.1826, n = 38.

Note on consistency: 3–4 swaps out of 16 is a modest change. A jump from 6.5% to 10% is a
1.5× move in the headline metric. If both land, that is worth explaining rather than
celebrating — it would mean a small number of swaps carried an unusually large share of
the advantage.

## Order of work

**1. Assign `usage` to every new salary row — before any fit.**

By club, whole clubs to one side. Non-negotiable precondition: `test` is HTA only today,
and `salary_external_2025.csv` contains 14 HTA rows. Fitting on them destroys the only
held-out evaluation in the project.

- TEL stays `calibrate`. HTA stays `test`.
- Split the 14 new clubs. Take roughly three high-budget and three low-budget clubs to
  `test`, since budget is the axis along which β₁ actually varies.
- Automatic rule, applied by club. Not row-by-row manual review — that reintroduces the
  bias the split exists to prevent. (Manual work on Day 9 was *name matching*, which is a
  different task and one a machine does worse.)
- Tag season too. `salary_external_2025.csv` mixes `yr` 2024 (17), 2025 (41), 2026 (8).
  Do not pool them in one regression without a season dummy.
- All 66 external rows are `basis = Net`, matching the anchors. No net/gross mixing to
  worry about.

**2. Swap the cost model specification.**

Replace the `log(salary / squad_mean)` fit in `roster_optimizer.fit_models` with the
`salary_market.fit` specification: `log(salary) = α_club + β₁·pir_lag_shrunk + β₂·el_seasons`,
club fixed effects, fit on `usage='calibrate'` across all calibrate clubs.

Price pool players at the mean α. Record β₁, β₂ and n in the run output.

**3. Re-run the sweep, expect the hash to break.**

`export_dashboard.py` will fail its `FROZEN` assertions. That is the intended outcome of
this run. Record the old and new values side by side before updating the frozen set —
the diff is the result.

**4. Refit `fit_eur`.**

Its current coefficients (`a = 0.7639`, `b = -2.1195`) describe the old budget axis and
become meaningless once the axis is rescaled.

**5. Re-run the display check.**

Compare displayed player money against `salary_anchors` 2025 again. Baseline to beat:
MAE €1.35M, Spearman 0.571, on n = 11 matched players. Anything at or below that
correlation means the per-player money display should be removed rather than corrected.

Caveat on that sample: those 11 are the players the LP chose, so they are biased toward
whatever the model underprices. Valid for judging the display; **not** valid for
estimating the market slope. The slope estimate comes from the 74 unselected observations.

## Out of scope for this run

- 2026/27 forecast mode. Correct the price curve and validate it on a season with real
  results first; applying a known-wrong slope to a season that cannot be checked would
  build an unverifiable layer on an unverified base.
- Club-conditional β₁ (ADR 0002).
- `club_budgets_gemini.csv` has no 2026 rows — only 2019 (18), 2024 (18), 2025 (20).
  Locating or rebuilding the 26/27 budgets is a prerequisite for forecast mode, not for
  this run.
