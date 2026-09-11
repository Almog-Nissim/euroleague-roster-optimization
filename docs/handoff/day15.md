> **Provenance note — added after the fact, day 15.**
> This handoff was written by a sandbox session that ran on a *regenerated*
> `usage_curve_results_min0.csv`. The original file was later found on the local
> machine and committed; `COST_SPEC=club_relative python src/usage_constrained.py`
> on it reproduces the day-14 capped baseline (6.5 %, the same 7 negative clubs;
> the regenerated file gives 7.96 % and 4).
>
> Where the numbers below differ from `docs/refit-day15-diff.md` and the committed
> results files, those win (local run, original file):
>
> | quantity | this handoff (sandbox) | local, original file |
> |---|---|---|
> | `adv_cap` median, market | 0.1724 | 0.1414 (`usage_constrained_results.csv`) |
> | sweep hash | `a3cfd56c9acd` | `f26e57f601b2` |
> | curse cost, capped roster | old 3.9 pp → new 1.9 pp | old 2.5 pp → new 5.5 pp |
>
> The "Blocking issue" section is resolved. "Next, in order" item 1 (step 1c) is
> done — pricing error by player type falsified. Item 2 (fatigue tiers) is
> superseded by the day-15 grill decisions recorded in ADR 0004: tier ceiling 34
> (observed max season-average minutes), not 40; δ enters only through a
> three-outcome rule declared in advance, not "δ ≈ 0 → falsified"; tiers are not
> claimed to give depth value (the top-k minutes-shape constraint is the deferred
> alternative).

# Day 15 handoff — where the refit stands

## Apply the work

```
git apply day15_code_only.patch      # code + docs only (24 KB)
# or
git apply day15_refit.patch          # code + regenerated data artifacts (1.8 MB)
```

New files: `src/cost_market.py`, `src/refit_acceptance.py`,
`src/display_money_check.py`, `src/curse_selection.py`,
`docs/refit-day15-diff.md`.
Modified: `optimizer_backtest.py`, `league_backtest.py`, `roster_sweep.py`,
`null_to_wins.py`, `export_dashboard.py`.

Run order after applying:

```
COST_SPEC=market python src/usage_constrained.py
COST_SPEC=market python src/roster_sweep.py
COST_SPEC=market python src/why_100.py
COST_SPEC=market python src/null_to_wins.py
COST_SPEC=market python src/wins_conversion.py
COST_SPEC=market python src/export_dashboard.py
```

`COST_SPEC=club_relative` reproduces the pre-day-15 specification.

## Blocking issue

`data/processed/usage_curve_results_min0.csv` is not in the repo — `.gitignore`
whitelists `usage_curve_results.csv` but not the `_min0` variant. Regenerating
it with `usage_curve.py --min-minutes 0` does **not** reproduce the file used
on day 14: the free side matches exactly (`lp_free` to 1e-12) but `adv_cap`
median comes out 0.0796 instead of 0.0652. **Commit the real file**, then
re-run the chain above; every capped-side number here carries that offset.

Also needs whitelisting: `refit_day15_diff.csv`, `refit_acceptance.csv`,
`refit_player_check.csv`, `display_money_check.csv`,
`curse_selection_*.csv`.

## Results — see docs/refit-day15-diff.md for the full table

β₁ 0.2317 → 0.1727. `adv_cap` median 0.0652 → 0.1724 (0.0796 → 0.1724 on one
consistent usage file). Displayed player money improved: MAE 1.279 → 0.893 M€,
Spearman 0.610 → 0.895. Sweep hash `c285173871cf` → `a3cfd56c9acd`.

The euro axis was gated on three thresholds declared before the run and failed
all three; the axis stays dimensionless, normalised by the season's pool mean.
Settled — do not re-open without new evidence.

Saturation flipped regime: `q_LP` stops rising at 22.5 and spending freezes at
23.43 from budget 23.5, with zero roster churn to the top of the grid. The old
"the pool doesn't run out" note was inverted; the guard in `roster_sweep.py`
now classifies the regime and checks the matching claim.

## Step 1 result — the winner's-curse explanation is dead

Measured on 38 club-seasons, both specifications (`curse_selection.py`):

```
selection bias, free roster:   old -2.8%   new -0.5%
weighted:                      old -6.1%   new +0.7%
pool-wide ppm overestimate:    +0.056 out of 0.373  (~+15%, both specs)
curse cost, capped roster:     old 3.9pp   new 1.9pp
```

There is no selection bias. The production model overestimates the whole pool
uniformly, which cancels in `adv` because both sides are scored on observed
production. The curse explains **0%** of the headline jump. Both sides of the
locked prediction lost except "explains less than half".

## Next, in order

1. **Step 1c — pricing error by player type.** Regress (model price − real
   salary) on `pir_lag_shrunk` for HTA/OLY/BAS under both specs. A negative
   slope means stars are underpriced and the engine is exploiting an arbitrage
   no real club could. This is the last surviving explanation for the jump.
   Predictions locked: slope old +0.05 to +0.20 M€ per pir unit; slope new
   −0.15 to +0.05; the engine's picks underpriced by ≥0.2 M€ versus the pool.
   Almog's predictions not yet given.
2. **Fatigue tiers.** Replace the hard 32-minute cap with two linear minute
   tiers per player (0–30 at full ppm, 30–40 at ppm·(1−δ)). Stays linear, PuLP
   solves it unchanged, gives depth real value, and moves the slider ceiling
   right. δ must be estimated from boxscores (within-player production per
   minute against minutes played), never assumed. If δ ≈ 0 the idea is
   falsified and does not go in.
3. Monte Carlo scoring of the sweep points (depth insurance). Expected to
   **lower** the headline, since real clubs carry 15–20 players and the engine
   carries 12. Run with predictions locked.
4. Product decisions still open: cut `B_HI` from 40 to about 24; remove the
   per-player euro figure (one player currently displays −0.14 M€).
