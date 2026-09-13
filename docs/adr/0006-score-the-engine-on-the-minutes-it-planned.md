# ADR 0006 — Score the engine on the minutes it planned, not on a hindsight reallocation

Status: locked, run pending — specification, decision rule, tests and predictions fixed
before any code runs
Date: 2026-09-13
Everything above "Result" was written before a single solve executed.

## Context

ADR 0005 adopted the top-k shape constraint and **stopped** its own specification cell. The
reason, found only after that run:

`score_rows` and `score_shape` allocate minutes in descending order of **`ppm_true`** — the
production that actually happened. While both sides were scored that way it was symmetric:
each got hindsight. Scoring the club on the minutes it actually played, against an engine
that keeps a hindsight — and now, after ADR 0005, LP-optimal — allocation gives the
numerator two advantages the denominator does not have: knowing who turned out good, and
allocating minutes perfectly.

The measured consequence was `adv_cap` 0.1414 → 0.2807, +98.4%, which fired the declared
`rises > 50% -> STOP` rule. The rise conflates the project's claim, better roster selection
on the same budget, with one it does not make and cannot defend: better minute management
than real coaches, with hindsight.

This ADR removes hindsight from **both** sides instead of restoring it to both.

## Decision

```
  engine:  q = Σ min(e_LP_i, 32·avail_true_i) · ppm_true_i  +  REPL · (200 − Σ ...)
           e_LP from the LP, decided on PREDICTED ppm and PREDICTED avail
  club:    q = Σ e_actual_i · ppm_true_i  +  REPL · (200 − Σ e_actual_i)
           e_actual = min_per_game · games / gmax
```

Neither side reallocates minutes with knowledge of the outcome. The engine is credited for
the plan it committed to; the club for the rotation it played.

### Realized availability is applied, and it is applied first

The LP plans against **predicted** availability, so its plan can be infeasible against what
happened. Measured on the headline path (capped curve, season 2025, B=20):

```
  EVANS, KEENAN    27.3 planned minutes    avail_true 0.026    ppm_true 0.000
  median minutes clipped by 32·avail_true: 27.3 of 200  (13.7%)
```

`avail_true = 0.026` is roughly one game in thirty-eight. Each player is therefore clipped
to `32·avail_true`, and the freed minutes fall to `REPL = 0.127`.

- **Clipping uses only realized availability**, which the club's own actual minutes already
  embed. It is the one piece of outcome information both sides carry.
- **The freed minutes are NOT reallocated to the rest of the engine's roster.** Reallocating
  them requires knowing who got injured, which is the hindsight this ADR removes.
- **Falling to `REPL` is the point.** It is the price of planning around a player who was
  not there. The club does not pay it because it played a real 200 minutes with a squad of
  16 against the engine's 12. That is depth insurance, measured instead of asserted.

### Negative `ppm_true` is allowed to subtract

Clipping is applied first, then whatever minutes survive contribute at the player's own
`ppm_true`, negative included. No floor at `REPL` and none at zero: benching a player
requires knowing he was bad.

The tail was measured before this was locked, on the 65 free-curve and 33 capped-curve
rosters of season 2025:

```
  free curve    5/65 rosters (8%) give a ppm_true<0 player more than 10 planned minutes
                worst ppm_true -0.380 · worst loss -9.04 points
  capped curve  no negative ppm_true at all; two players recorded at exactly 0.000,
                both at avail_true = 0.026, so clipping removes them first
```

8% is a tail, under the declared one-third threshold. **The ordering is what keeps it a
tail** — clip by availability, then value what survives.

### What is inherited from ADR 0005, unchanged

- The top-k shape constraint, `SLACK = 1.00`, all k from 1 to 8, caps from
  `data/processed/shape_caps.csv`. ADR 0005 is **not** superseded: its constraint was
  adopted and passed "falls < 20%". Only its denominator cell was stopped.
- `add_shape_constraint` as the single implementation, in both the free and the capped LP.
- The per-player cap `MAX_MIN_PLAYER = 32` and the position shares.

### What stops being needed

`score_shape`, the exact-LP scorer built in ADR 0005, is no longer on the headline path:
the numerator no longer reallocates anything. It stays for the symmetric-hindsight
sensitivity below, and T7 changes meaning — the numerator is `Σ e_LP · ppm_true`, which is
**not** the LP objective, because the LP maximises on predicted `ppm`.

## The new 2×2

```
                          engine reallocated      engine on its plan
                          (hindsight)             (ADR 0006)
  club greedy             0.1414  (A)             (E)
  club as played          0.2807  (D)             (F)

  A  ADR 0005 baseline, symmetric hindsight. Reproduces the tracked 0.1414
  D  ADR 0005 specification, STOPPED. Asymmetric
  E  asymmetric the other way: the club gets hindsight, the engine does not
  F  **the specification.** Neither side reallocates
```

`E` is reported because it bounds the effect from the other side. Without it, `F` cannot be
split into "the engine lost its hindsight" and "the club lost its flattery".

## Decision rule, declared before the run

Baseline `adv_cap = 0.1414`. Same table as ADR 0005, and it can fire the same way:

| outcome | consequence |
|---|---|
| falls < 20% | headline stands; CV and LinkedIn unchanged |
| falls 20%–60% | headline stands, stated with both conventions every time it appears |
| falls > 60% | the previous headline is void; the new number is the headline |
| `adv_cap ≤ 0` in over half | no claim; closing-plan sections 4 and 5 are rewritten |
| rises, ≤ 50% | reported only with the E/F decomposition |
| rises > 50% | **STOP again.** Two stops on one metric means the metric is the problem, not the convention. Then the honest move is to report `0.1414` under its stated convention and put the rest in v2 |

**The last row is new and it matters.** ADR 0005 already stopped once. If removing hindsight
from the engine still leaves the headline 50% above baseline, the conclusion is not a third
convention — it is that `adv_cap` cannot be pushed further without a design the data does
not support.

## Tests

T1–T6, T8–T12 from ADR 0005 carry over unchanged; the LP is untouched. New and changed:

```
  T13 clipping      no scored minute exceeds 32·avail_true for any player, either side
  T14 no realloc    the engine's scored minute vector equals min(e_LP, 32·avail_true)
                    element-wise — nothing is moved between players
  T15 fill          scored minutes + REPL fill = 200 on both sides
  T16 club identity the club's scored minutes equal e_actual exactly, and the club side
                    satisfies every shape cap by construction (inherits T10a)
  T17 negatives     a player with ppm_true < 0 and surviving minutes reduces q. A
                    constructed case, to pin the Q18 decision in code
  T7'  restated     the numerator is NOT the LP objective. The test is that
                    Σ e_LP·ppm (predicted) reproduces the LP objective, while
                    Σ min(e_LP, 32·avail_true)·ppm_true is the reported score, and the
                    two are different numbers
```

## Run matrix

```
  cells E and F      38 club-seasons, scoring only on the ADR 0005 LP solutions       0 solves
  with/without shape reuses the four LP solutions already stored per club-season      0 solves
  SLACK 0.95/1.05    still held                                                       —
  sweep curve        still held                                                       —
```

**This run needs no new solves.** ADR 0005's run already produced, per club-season, the LP
solutions with and without shape for both the free and the capped side. What changes is how
they are scored. The 12.8 hours are not spent again — but the per-player minute vectors were
not saved, so `shape_run.py` must be re-run to emit them. That is the one cost, and it is
the same 152 solves.

`minutes_alloc` in `engine_rosters.csv` is empty in all 456 rows — a column that was never
filled. It is populated by this run or deleted; it will not be left as a header promising
data that is not there.

## Predictions, locked before the run

Derived from `REPL = 0.127`, the 13.7% median clipping, and the 12.54% denominator drop
already measured in ADR 0005.

```
                                              Claude            Almog
  clipping cost to the engine                 8%–12% of q       —
  q_cap falls, reallocated -> planned         11%–18%           —
  adv_cap · cell F, with shape                [0.09, 0.17]      defers
  adv_cap · cell E                            [0.02, 0.09]      —
  minutes clipped, median of 200              20–32             —
  win rate (adv > 0) in cell F                75%–95%           —
  verdict fires "rises" again                 ~55% likely       —
  roster size                                 12, unchanged     —
```

**The interval on cell F straddles the baseline deliberately.** Two effects compound in
opposite directions — the engine loses 11%–18%, the denominator loses 12.54% — and their
difference is smaller than either. An honest interval here has to admit it could land on
either side of `0.1414`, and saying so in advance is the only thing that makes the verdict
mean anything.

Almog withdrew his numeric predictions for the `adv_cap` rows in ADR 0005 after his first
draft was shown to be internally inconsistent, and defers here as well. Recorded as it
happened: one prediction, not two dressed as two.

## Result — appended after the run

Pending.
