# CONTEXT

Vocabulary for this repo. Terms here are resolved: use these names, not synonyms.

## Money and price

**`cost`** — the price of a player in the optimizer's budget constraint.
It is **dimensionless**. `league_backtest.build_pool` calls `ob.build(..., mean_salary=1.0)`,
so `cost = exp(β₀ + β₁·pir_lag_shrunk + β₂·el_seasons) · smear`, i.e. a ratio to the
calibration club's mean salary. It is not euros and never has been in the sweep path.

Do not read a `cost` value as money. A player at `cost = 1.355` is priced at 1.355×
a squad-average player, in whatever price structure the cost model was calibrated on.

`roster_optimizer.py` (single-club demo path) multiplies by `mean_sal` and *is* in euros
of `TARGET_CLUB`. The dashboard does not use that path. Two different units share one name.

**`budget`** — the right-hand side of the LP constraint `Σ cost_i · x_i ≤ B`.
Same dimensionless units as `cost`. Sweep grid is `B_LO=8.0` to `B_HI=40.0`, step `0.5`.
Not to be confused with `net_eur` (below).

**`net_eur`** — a club's real annual player budget in euros, from `club_budgets_gemini.csv`.
An external input. It does **not** enter the cost model. It is used only for `fit_eur`
and for the Day 9 diagnostic of how β₁ varies with club wealth.

**`gross_eur`** — deprecated. Empty for every 2025 row. Still silently filters rows in
`score_to_wins.py` via an inner join. Do not use; remove the dependency.

**`salary_mid`** — a real observed player salary in euros, from `salary_anchors.csv`
(4 clubs, verified player codes) or `salary_external_2025.csv` (16 clubs, name-matched).
This is ground truth. It is the only "salary" in the repo that means what it says.

**`fit_eur`** — an affine display map from `budget` to `net_eur`, fit on 20 club points:
`a = 0.7639`, `b = -2.1195`, `R² = 0.753`, `MAE = €2.15M`, valid on `budget ∈ [12.9, 36.9]`.
**Club level only.** Applying it to a single player is out of scope for the fit and
empirically fails: on the 11 displayed players with known 2025 salaries, MAE is €1.35M
and Spearman rank correlation with real salary is 0.571.

## Seasons

**`SEASON` / `season`** — always the **opening year**. `season = 2025` means the 2025/26
season. Display strings are derived: `f"{SEASON}/{(SEASON + 1) % 100:02d}"`.

Never write a season as a hard-coded string. `salary_external_2025.csv` stores
`"2025-2026"` in a `season` column and an opening year in `yr`; the `yr` column is the
canonical one.

## Calibration and evaluation splits

**`usage`** — column in `salary_anchors.csv` controlling how a salary row may be used.

| value | rows | clubs | meaning |
|---|---|---|---|
| `calibrate` | 39 | TEL only | cost model is fit on these |
| `test` | 19 | HTA only | held out; never touched by a fit |
| `structure_only` | 51 | — | used for squad structure, not for pricing |

Splits are **by club, not by row**. A club goes entirely to one side. This exists because
the market specification uses club fixed effects, so a club appearing on both sides leaks
its own price level into its own evaluation.

Any new salary source must be assigned a `usage` value before it touches a model.
`salary_external_2025.csv` currently has none.

## Advantage metrics

**`adv_free`** — engine roster quality vs. actual club, no usage constraint.
Median 0.1826 over n=38 club-seasons. 0 negatives.

**`adv_cap`** — same, under the ball-identity usage constraint.
Median 0.0652 over n=38. 7 negatives.

`adv_cap` is the headline metric. It is what the dashboard shows and what the
project defends.

**Do not** compare the engine's `q` against a club's *predicted* `q`. That inflates by
roughly 12 percentage points and produces a spurious ~30% figure. Use
`usage_constrained_results.csv`. This is recorded in `meta.fair_compare_warning`.

## Price curve

**`β₁`** — the coefficient on `pir_lag_shrunk` in the cost model. It controls how steeply
price rises with production, and therefore carries essentially all of the price dispersion:
across the 2025 pool, `pir_lag_shrunk` spans 4.48–17.81, so β₁ contributes ~3.09 log units
of spread against ~0.31 from `el_seasons`. **β₁ is the only coefficient that meaningfully
changes which players the LP selects.**

Everything else in the cost model — the intercept, `smear`, `mean_salary` — is a scalar
multiplier on every player at once. Scaling all costs and the budget by the same factor
leaves the LP's feasible set unchanged, so it cannot change the selection.
