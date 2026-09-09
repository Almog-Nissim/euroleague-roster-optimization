# ADR 0001 — Price the candidate pool at a league-average club

Status: accepted
Date: 2026-09-09

## Context

The cost model is fit on `usage='calibrate'` rows of `salary_anchors.csv`. Those rows are:

```
TEL 2023 (12) · TEL 2024 (12) · TEL 2025 (15)
```

One club. The fitted shape is Maccabi Tel Aviv's price curve, reproduced from the
committed data as:

```
log(salary / squad_mean) ~ pir_lag_shrunk + el_seasons
const −2.2133 · pir_lag_shrunk 0.2317 · el_seasons 0.1026 · n=27 · R² 0.619
```

Day 9 (`salary_market.py`) estimated the same slope on the market — 74 salaries across
14 clubs, club fixed effects — and got **β₁ = 0.148** (R² 0.642, t = 6.43). It also
estimated β₁ per club:

```
TEL 0.302 · HTA 0.263 · PAN 0.161 · MAD 0.119 · OLY 0.083
```

The calibration club is the steepest of the five, by a factor of 3.6 over the flattest.

The product claim is "given this much money, what roster can you build". That claim has no
club-specific reading. Pricing the whole league on one club's curve — and the most extreme
one — makes the answer a statement about Maccabi's price structure rather than the league's.

## Decision

Refit the cost model on the market sample using the `salary_market.py` specification:

```
log(salary) = α_club + β₁·pir_lag_shrunk + β₂·el_seasons
```

Club fixed effects absorb price *level*; the slope is estimated within club and shared.
Candidate-pool players are priced at the **mean α**, i.e. at a league-average club.

Fixed effects are required rather than preferred: `salary_external_2025.csv` gives 16 clubs
but between 1 and 14 players each, so a per-club mean salary — which the current
`log(salary/squad_mean)` specification needs — cannot be computed from it.

## Alternatives rejected

**Rescale `mean_salary` to a league average.** Provably a no-op. Costs and budget scale by
the same factor, the LP's feasible set is unchanged, and the selection is identical. This
was the first reading of "recalibrate" and it does not do what it sounds like it does.

**Make β₁ club-conditional.** See ADR 0002.

## Consequences

- The 65 sweep budget points and the 6 `FROZEN` values in `export_dashboard.py` will move.
  For this run, breaking the md5 hash is the intended outcome, not a failure.
- The interpretation of the budget axis changes from "money at TEL prices" to "money at
  league-average prices". `fit_eur` must be refit afterwards; its current coefficients
  describe the old axis.
- The direction of the effect on `adv_cap` is not obvious. The current model is *steeper*
  than the market (0.2317 vs 0.148), meaning it overprices stars. Flattening makes stars
  cheaper and the LP will want more of them. If `adv_cap` rises, that is a finding — it
  says the measured advantage was not resting on generous pricing.
- Held-out evaluation must survive the change. `test` is currently HTA only, and
  `salary_external_2025.csv` contains 14 HTA rows. Assigning `usage` by club before the
  refit is a precondition, not a follow-up.
