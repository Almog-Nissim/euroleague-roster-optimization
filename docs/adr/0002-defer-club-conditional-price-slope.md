# ADR 0002 — Defer a club-conditional price slope

Status: accepted (deferral)
Date: 2026-09-09

## Context

Day 9 measured β₁ separately per club and found it moves with club wealth:

```
TEL  €16M  0.302
HTA  €23M  0.263
PAN  €32M  0.161
MAD  €24M  0.119
OLY  €37M  0.083
```

A factor of 3.6, ordered roughly against budget. Rich clubs face flatter price curves:
the premium they pay for a star, relative to their own squad average, is smaller.

ADR 0001 adopts a single shared slope across the league. That is knowingly at odds with
this measurement, so the reason for adopting it anyway belongs in writing.

## Decision

Keep one shared β₁ for now. Do not make β₁ a function of budget or club.

## Why

The alternative is not identified by the available data. Fitting β₁ = f(budget) means
estimating at least two parameters from **five** club-level slope estimates, each itself
noisy. That is curve-fitting through five points, not a model, and it would be presented
alongside a headline result that people are meant to trust.

Revisit when there are enough clubs with enough salary coverage to estimate a slope per
club with a usable standard error. `salary_external_2025.csv` adds clubs but at 1–14
players each, which is not enough for a within-club slope.

## Consequences — read this before defending the headline

This deferral is not cosmetic. If the true price curve flattens as budget rises, then a
fixed curve **overprices stars at the rich end of the budget axis**. The LP therefore buys
fewer stars than a rich club really could, and the measured marginal return on money is
biased downward at the top.

The saturation point — currently reported at `budget = 25.0`, roughly €20M net after the
normalization correction — sits at exactly that end of the axis. It is therefore possible
that saturation is partly an artifact of holding the price slope constant, rather than a
property of the market.

This does not invalidate the finding. It means the finding carries a known, named,
directional caveat, and that caveat should appear wherever saturation is claimed.
