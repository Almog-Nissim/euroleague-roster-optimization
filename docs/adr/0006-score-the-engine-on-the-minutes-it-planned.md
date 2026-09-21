# ADR 0006 — Score the engine on the minutes it planned, not on a hindsight reallocation

Status: adopted — the rule fired "rises, ≤ 50%" (see Result). The v1.0 number is the
exact re-run's (see Follow-up); corrections after code review at the end
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

Status of this ADR is now: **adopted. The declared rule fired "rises, ≤ 50%" — reportable
only together with the decomposition. Not a second stop.** `src/shape_run.py` →
`usage_constrained_shape.csv`, `shape_binding.csv`, `shape_minutes.csv`. 38 club-seasons,
10.7 hours, exit 0.

### The grid

```
                          engine reallocated      engine on its plan
  club greedy             0.1414  (A)             0.0423  (E)
  club as played          0.3232  (B, stopped)    0.1906  (F)

  with the shape constraint:
  club greedy             0.1235  (C)             0.0478  (E_shape)
  club as played          0.2878  (D, stopped)    0.1892  (F_shape)  <- specification
```

**Cell A reproduced `0.1414` exactly.** The grid and the baseline come from one run.

### The decomposition the rule requires

```
  the denominator alone       A -> B    +18.18 pp   the club is no longer flattered
  removing hindsight          A -> E     -9.91 pp   the engine no longer knows the outcome
  the shape constraint        A -> C     -1.79 pp
  the specification           A -> Fs    +4.78 pp   +33.8% relative
```

`0.1892` is **not** "the engine improved". It is two opposed accounting corrections that
nearly cancel: the club stopped receiving a minute allocation it never chose, and the engine
stopped receiving knowledge of the outcome and an unrealistic concentration of minutes.
Quoting `0.1892` without these three lines misleads by omission.

### What it means

- **The original headline was conservative, not inflated.** The flattery of the club was
  larger than the engine's unfair advantages. With hindsight removed from both sides the
  advantage is higher.
- **But most of the original advantage, as originally measured, was the engine's
  hindsight.** Remove it from the engine alone and `0.1414` falls to `0.0423`; win rate falls
  from 100% to 63%. Roughly two thirds of what the old number measured was the engine
  knowing who to give minutes to, not the engine picking better players.
- **The shape constraint barely moves the headline** — `−1.79 pp`. The error that looked
  largest in the model was not the one that mattered most.
- **The advantage survives paying for its own thin roster.** Median 28.5 of 200 planned
  minutes (14.2%, max 43.0) went to players who were not available and fell to `REPL`. The
  engine carries 12 against real clubs' 15–20, pays that price, and still wins 38 of 38.

### Predictions

```
                                          predicted         got
  q_cap falls, reallocated -> planned      11%-18%           7.67%    ❌ cost overestimated
  adv_cap · cell F with shape              [0.09, 0.17]      0.1892   ❌ just above
  adv_cap · cell E                         [0.02, 0.09]      0.0423   ✅
  minutes clipped, median of 200           20-32             28.5     ✅
  win rate in cell F                       75%-95%           100%     ❌
  verdict fires "rises" again              ~55%              rises    ✅ direction
  roster size                              12, unchanged     12       ✅
```

Almog deferred on the numeric rows; one prediction, not two dressed as two.

### Deviations from the declared procedure

1. **The result is not reproducible to the digit, and this blocks `v1.0`.** The same
   computation on the same data, in two runs:

   ```
     A   0.1414  ->  0.1414   no caps, no gap: deterministic
     C   0.1205  ->  0.1235   shape solves at gapRel = 0.005
     D   0.2807  ->  0.2878
   ```

   The declared 0.5% per-solve gap, and CBC not being deterministic, propagate into a ~2.5%
   swing in the median. Not a bug, and inside what was declared — but the closing plan asks
   for a final number, and a number that moves between identical runs is not final. Resolved
   by the exact re-run below.
2. **Runtime is a lottery, not a property of one club-season.** In the ADR 0005 run 2024 TEL
   took 40,332 s; in this run it took 166 s, and 2025 PAM took 30,894 s instead. The
   "pathological club" explanation in ADR 0005 is withdrawn. Roughly one in 38 no-shape
   solves balloons, and which one is chance.
3. **Per-solve timing was promised for this run and not delivered.** It was added to the
   code after the run launched. It applies from the exact re-run on.
4. **Minute vectors are saved.** `shape_minutes.csv`, 1,543 rows — so any future rescoring of
   these LP solutions costs nothing.

### What remains open, and is not licensed by this result

- **38 of 38 is a reason for suspicion before it is a reason for pride.** One candidate
  source is known and unchecked: the club side is restricted to players in the pool and
  newcomers leave both sides. Symmetric on paper; possibly harsher on the club. To be checked
  before the number reaches a CV.
- Two test seasons. 38 club-seasons are not 38 independent observations.
- No wins figure. `wins_conversion.py` has not run on this cell and is not assumed linear.

## Follow-up — the exact re-run, locked before it ran

**Scope.** Only the capped LP with the shape constraint is re-solved, at `gap = 0`. Cells A
and E need no new solve: the no-shape LP is deterministic (A reproduced exactly) and its
minute vectors are already in `shape_minutes.csv`. 38 solves, not 152, and none of them the
un-time-limited no-shape solves where the runtime lottery lives.

**Time limit 1,800 s per solve.** A solve that hits it is reported as not exact, by club,
and the headline is not claimed exact until none do.

**Predictions, locked:**

```
  adv_cap · F_shape, exact      [0.184, 0.194]   inside the observed run-to-run spread
  solves hitting 1,800 s        0                ~75% confident
  win rate                      38/38
  exact vs 0.5%-gap run         |Δ median| ≤ 0.005
```

## Corrections after code review — 2026-09-21

A two-axis review (standards, spec) of everything since `3a2d3ec`, run as the gate before
`v1.0`, found defects that touch the runs reported above. Each is listed with what it did to
the numbers. Fixes are in `7af1ddc` unless noted, test-first: three tests confirmed red on
the old code, then green (22/22).

| # | Defect | What it touched | Headline F? |
|---|---|---|---|
| 1 | `optimise_v3` never wrote `oc.LAST`. T12 compared v2 with itself; `lp_free_shape` holds `lp_cap` in 38/38 rows. | The equivalence claim in ADR 0005 was unmeasured. Measured now: it holds exactly. The column is invalid. | No |
| 2 | `solver_guard` checked `status == "Optimal"` only. A CBC stop on `timeLimit` with a feasible incumbent also reports Optimal; only `sol_status` (2) tells. `optimise_v2`/`optimise_capped` never called the guard. | Every shape solve in both gap runs (`timeLimit=120`, `gapRel=0.005`) could have stopped unproven, silently. Cells C, D, E_shape, F_shape of the gap runs carry this. Plausibly part of the run-to-run swing (C 0.1205 → 0.1235). | The gap-run F: yes. The exact re-run guards on `sol_status == 1` and is not affected. |
| 3 | `score_shape` fell back silently: dropped position floors, then greedy. | Measured on the saved vectors (reproducing `q_cap_shape` to 2.8e-14): floors dropped on **9 of 38** engine shape rosters, greedy 0. Floors met on predicted availability become infeasible on true availability. Cells C and D, mildly in the engine's favour. | No — F does not reallocate |
| 4 | T9 tested an infeasible LP, never a time-limit stop. | The declared "time limit raises" was not tested. T9b added. | — |
| 5 | T11 checked `"gap" in LAST`, and LAST stored the declared `gapRel`, not the achieved gap. | "Gap printed per solve, max < 0.5%" was never verified. **Open.** | — |
| 6 | T13/T15 test the engine side only; T10b tests a stand-in greedy, not `score_rows`. | Partial coverage of what the ADR declared. **Open.** | — |
| 7 | `shape_run --clubs` / `--slack` write the tracked `usage_constrained_shape.csv` and `shape_minutes.csv` incrementally. | A sanity or sensitivity run would overwrite the headline files with a subset. Did not happen in a committed state. **Open; must be fixed before the SLACK run.** | — |
| 8 | `dump_rosters` fills `minutes_alloc` from the free LP without shape, unclipped. | Not the ADR 0006 convention the closing plan claims. **Open.** | — |

**What stands.** The specification cell F is computed by `score_planned` — no reallocation,
no floors, no fallback — on the plan of the capped+shape LP. Defect 2 means the *gap-run*
value of F (0.1892) rests on solves that were not proven within the gap; that is exactly what
the exact re-run replaces. The v1.0 number is the exact re-run's, not 0.1892.

### Follow-up result — the exact re-run

`src/headline_exact.py` → `data/processed/headline_exact.csv`. 38 solves at `gap = 0`,
46 minutes, median 56 s, max 261 s.

```
  adv_cap · F_shape, exact     0.1892    identical to the 0.5%-gap run   Δ +0.0000
  adv_cap · E_shape, exact     0.0478
  win rate                     38/38
  proven optimal               38/38   (sol_status == 1, none near the 1,800 s limit)
```

All four locked predictions hit: F in [0.184, 0.194], no solve at the limit, 38/38, and
|Δ| ≤ 0.005.

**The median did not move, but six club-seasons did:**

```
  PAR   +14.16% -> +0.22%   Δ -13.93      VIR   +27.66% -> +37.30%   Δ +9.64
  BER   +39.82% -> +33.21%  Δ  -6.62      ULK   +25.51% -> +29.81%   Δ +4.30
  PAM   +12.98% -> +12.37%  Δ  -0.61      PRS    +4.99% ->  +9.17%   Δ +4.18
```

A 0.5% gap on an objective computed on *predicted* `ppm` can select a different roster, and
scored on `ppm_true` the difference per club-season is far larger than 0.5%. It cancels at
the median here, which is why the gap run's 0.1892 happened to be right. The run-to-run
swing seen earlier lived in cells C and D, not F.

**This is the v1.0 headline: `adv_cap = 0.1892`, proven, with the decomposition that must
accompany it.** It supersedes the gap-run value, which rested on shape solves that could not
be shown to be within the gap (corrections, defect 2).
