# ADR 0005 — A top-k constraint on the shape of the minute distribution

Status: locked, run pending — the specification, the decision rule, the tests and the
predictions below are fixed before any code runs
Date: 2026-09-12
Everything above "Result" was written before a single solve executed. The result is
appended at the end.

## Context

The LP caps every player at `e(i) ≤ 32·avail(i)·x(i)`. Day 9 (`minute_profile.py`) showed
the cap is sound as a single number — over 2,553 player-seasons the maximum season average
is 34.0 and P99 is 30.6 — and unsound as a *set* of numbers. It binds each player
separately, so the optimizer takes it for everybody at once. Measured over the 38
club-seasons:

```
  k     mean    cap = max observed    attained by     the model allows
  1     26.3          31.2            2024 ULK              32
  2     49.7          57.6            2024 PAN              64
  3     71.2          84.0            2024 PAN              96
  4     90.8         104.9            2024 PAN             128
  5    109.1         126.4            2025 MCO             160
  6    125.7         145.3            2025 MCO             192
  7    140.3         163.3            2025 HTA             200
  8    153.4         176.9            2025 MCO             200
```

At k=1 the constraint is nearly exact. At k=6 the model hands out 192 minutes where the
most concentrated real club in ten seasons gave 145.3 — a 32% gap. This is the third
instance of one error: position floors bind per position and the optimizer sits in all of
them; the minute cap binds per player and the optimizer gives it to everyone. An optimizer
always goes to a corner, so **the constraint has to be on the shape, not on each player.**

ADR 0004 deferred this in favour of fatigue tiers, and the tiers were refuted on evidence.
This is the error that was actually measured.

### What the grill found, and what changed because of it

**The scorer puts every real club outside the envelope the clubs themselves define.**
`score_rows` does not score a club on the minutes it played. It re-allocates the club's own
players greedily at `min(32, left, poscap)·avail`:

```
  the real club's top six          mean     min      max
  as they actually played         125.7    98.0    145.3
  as score_rows hands them out    177.0   148.7    191.2
```

A 40.8% inflation of the denominator, and the minimum, 148.7, is above the k=6 cap of
145.3: under today's scorer **all 38 real clubs violate the constraint built from their own
maximum.** So `adv_cap = 0.1414` is conservative in its denominator, and the shape error
lives in the numerator *and* the denominator. Putting the constraint only in the LP would
be a one-sided tightening.

**Two existing defects, to be fixed here.** In `score_realistic`, `cap_k` is looked up by
`ppm` rank, but the constraint is defined on the k largest values of `e`; position caps
break the monotonicity between `ppm` and `e`, so the cap can be applied to the wrong
ordering. In `optimise_v3`, solver status `Not Solved` — a time-limit hit, whose solution
may be non-optimal or absent — is accepted as success, against the rule that scripts print
their guards.

## Decision

### The constraint

Sum of the k largest, in the standard linear form (Nesterov):

```
  sum of the k largest of e  <=  C_k
  <=>  exists q, s >= 0  with   k·q + Σ s_i <= C_k ,   s_i >= e_i − q
```

It stays linear, so PuLP solves it with no binaries added to the objective.

- **One implementation.** `add_shape_constraint(p, e, caps, n)` in `src/scoring.py`. Both
  `optimise_capped` (the headline path, `usage_constrained.py`) and `optimise_v3`
  (`minute_profile.py`) call it. Two implementations of one constraint is how `score_rows`
  came to exist twice.
- **The constraint enters both LPs, free and capped.** Otherwise `adv_free` is half from
  one model and half from another.
- **Caps are the per-k maximum over the 38 club-seasons, `SLACK = 1.00`.** The exact
  observed maximum, generated into `data/processed/shape_caps.csv` with the attaining
  club-season recorded per k.
- **Declared limitation.** Four different club-seasons attain the envelope. The closest
  single club-season to it, 2024 PAN, sits at 92.7% of it at its worst k. **No real club
  played the shape the envelope permits.** The envelope is kept anyway: it is meant to
  exclude shapes, not to reproduce a club. A single club's profile would trade an assembly
  error for a sampling error at n=1.
- **All k from 1 to 8.** `KMAX = 8` still binds (176.9 against 200). The previous
  `K_USED = (1,2,3,4,6,8)` rested on "adjacent k are nearly redundant", which was never
  measured. Every k runs, the binding k is recorded per solve in
  `data/processed/shape_binding.csv`, and `K_USED` is narrowed later only if 5 and 7 bind
  nowhere.

### The scorer

- **`src/scoring.py` owns one scorer.** The deliberate duplication of `score_rows` across
  `optimizer_backtest.py` and `roster_membership_audit.py` was there so the audit could not
  break silently when the signature moved. Once the shape constraint exists, that same
  duplication is the way the two sides come to score under different models — silently.
  `minute_profile.py` keeps `score_realistic` as a one-line re-export so the two Day-9
  scripts (`final_fix.py`, `why_100.py`) keep running untouched.
- **The real club is scored on the minutes it played.** This is the specification:

```
  e_actual = min_per_game · games / gmax[season]
  q_club   = Σ e_actual_i · ppm_true_i
```

  The greedy denominator is reported beside it, not replaced by it.

### The 2×2, which is the whole result

The denominator change and the constraint move `adv_cap` in opposite directions. Neither
can be attributed without the other:

```
                        q_club greedy      q_club as played
  LP without shape         0.1414                 ?
  LP with shape              ?                    ?
```

## Considered options

- **LP only, scorer untouched.** Rejected as the specification, reported as a declared
  sensitivity. It tightens the engine and leaves the club flattered, so the whole movement
  would be an artifact of one-sidedness. ADR 0004 failed on exactly this kind of asymmetry.
- **A single club's minute profile as the cap.** Rejected. It answers the assembly
  objection and replaces it with a cap set by one club-season out of 38, which moves with
  that club's injuries and squad length.
- **The 95th percentile instead of the maximum.** Rejected. A shape that happened is legal.
  The percentile imposes a tightening the data does not support.
- **Keeping the greedy denominator and deferring the club side to v2.** Rejected, but it is
  the fallback if the 2×2 cannot be produced: it leaves the gap between what the dashboard
  claims and what was measured open across the freeze.

## Decision rule, declared before the run

Baseline: `adv_cap = 0.1414`. The wins figure follows from `wins_conversion.py` and is not
assumed linear in `adv_cap`.

| outcome | consequence |
|---|---|
| headline falls < 20% | headline stands; a valid tightening; CV and LinkedIn unchanged |
| headline falls 20%–60% | headline stands, stated with the shape constraint every time it appears |
| headline falls > 60% | the previous headline is void. The new number is the headline, unimpressive or not |
| `adv_cap ≤ 0` in over half | no claim. The project reports what broke and why. Closing-plan sections 4 and 5 are rewritten |
| headline rises | reported only together with the decomposition: how much comes from the denominator (no longer flattering the club) and how much from the constraint. Without the decomposition, 0.1414 stands |
| headline rises > 50% | **STOP.** That is not a fix, it is a measurement of something else. Back to the grill before anything is written |

The label is whatever the rule produces. It is not relabelled afterwards.

## Tests, written before the code

T8 and T9 must **fail** against today's code; both are existing defects.

```
  T1  nesting      caps={k: 1e6} on optimise_capped reproduces today's objective
                   exactly, 38/38.  Against optimise_capped, not optimise_v2
  T2  monotonic    lowering a cap cannot raise the objective, 38/38
  T3  feasible     from the returned e: sum of the k largest <= C_k for every k in
                   1..KMAX. Checked directly, not by trusting the Nesterov encoding
  T4  minutes      total minutes <= 200
  T5  per-player   e_i <= 32·avail_i·x_i — the old cap still holds
  T6  position     position caps and floors hold
  T7  consistency  the scorer on the LP roster reproduces the LP objective to within
                   the reported gap
  T8  rank bug     a case where a position cap breaks monotonicity between ppm and e:
                   the constraint must apply to the k largest of e, not to ppm rank
                   <- fails today
  T9  solver       status Not Solved / time limit raises, never returns silently
                   <- fails today
  T10 club side    38/38 clubs on minutes as played satisfy every cap; and 38/38
                   violate k=6 under the greedy scorer. The test pins that fact
  T11 gap          the optimality gap is printed per solve; its max over 38 is < 0.5%
```

T3 is the one that matters most: it checks the result, not the formulation, so it is the
only one that catches an error in the Nesterov decomposition itself.

## Run matrix

```
  a  specification   38 club-seasons × free+capped, with shape          76 solves
                     the 2×2 and the LP-only sensitivity are scoring     0
  b  SLACK 0.95/1.05 on the declared subsample of 12                    48 solves
  c  sweep           8..40 step 1.0, both curves                        66 solves
                                                                      ~190 solves
```

**The declared subsample, fixed before the run.** The backtest has two test seasons
(`SEASONS = [(2023,2024),(2024,2025)]`), not four, so it is 2 seasons × 6 clubs. Within each
season the clubs are ranked by top-six minutes as played and taken at six evenly spaced rank
positions, to span the axis the constraint acts on:

```
  2024   MUN 140.3 · PAR 133.3 · IST 127.6 · BAR 126.7 · ZAL 122.7 · BER  98.0
  2025   MCO 145.3 · DUB 131.2 · OLY 128.1 · ULK 124.2 · PAM 117.0 · PRS 102.9
```

The slack sensitivity is reported, never used to choose. It exists to answer "you picked the
threshold that gave you the number", and for that a declared subsample is as good as the
full 38, because the question is direction and not precision.

## Consequences

- **This is a tightening, so "a tighter constraint cannot raise the objective" applies** —
  unlike ADR 0004, where the tiers relaxed 32 to 34. T2 tests it, 38/38.
- **`B_HI` becomes an output of this run, not an input.** The sweep is flat from B=22.5 on
  the free curve and from B=25.0 on the capped one, which justifies cutting `B_HI` from 40
  to about 24 — but that was measured on the model being replaced. Spreading minutes needs
  more players, and more players push saturation up. So the run keeps 8..40 at step 1.0
  (33 points, the same cost as 65 points at step 0.5) and `B_HI` is set afterwards. It also
  puts both curves on one grid; today the free curve is step 0.5 and the capped one step 1.0.
- **The depth caveat changes rather than disappears.** The engine carries 12 players at
  B=24 today. The constraint will raise that. The dashboard caveat is rewritten as "the
  engine carried 12; under the shape constraint it carries N; real clubs 15–20", which is
  stronger than the original because the limitation is measured and addressed. Only if
  N ≥ 15 does it become "this gap closed" — never silently deleted.
- **Solver cost.** ~8n auxiliary variables per k. Day 9 measured 115s on a trial solve.
  Optimality gap 0.5% with a time limit, reported per solve, an order of magnitude below
  the 5%–20% differences being measured.
- **A rise in the headline is the dangerous outcome, not a fall.** "I fixed an error and my
  number went up" reads as number-shopping even when it is correct. That is what the
  decomposition requirement and the two rise rows in the decision rule are for.

## Predictions, locked before the run

```
                                      Claude           Almog
  adv_cap · shape + greedy q_club      [0.09, 0.13]     [0.085, 0.113]
  adv_cap · shape + q_club as played   [0.15, 0.21]     defers to Claude's range
  q_club falls, greedy -> as played    4%-9%            7%-11%
  roster size after the constraint     13-15            14-16
  k=6 binding                          > 90% of solves  —
  k=1 binding                          < 20% of solves  —
  k=5 or k=7 binding at all            yes, ~30%        —
  new saturation point                 22-27            —
  T8 and T9 fail against today's code  yes              —
```

**On the second row there is no independent second prediction.** Almog's first draft of the
`adv_cap` rows was internally inconsistent — "falls 20%–40%" alongside "0.11–0.14", two
ranges that meet only at their edge — and on being shown the arithmetic he withdrew his own
numbers for that cell rather than fit them to the others. That is recorded as it happened:
one prediction, not two dressed as two.

Almog's own numbers, taken together, imply `adv_cap` between 0.166 and 0.251 in the
specification cell, a rise of +17% to +77%. **The top of his own range crosses the
`rises > 50% -> STOP` line.** He was shown this before locking.

## Result — appended after the run

Pending.
