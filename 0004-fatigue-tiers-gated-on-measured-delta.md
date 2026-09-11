# ADR 0004 — Fatigue tiers replace the 32-minute cap, gated on a measured δ

Status: rejected on evidence — step 2 verdict `refuted`; tiers do not enter, the 32-minute cap stays
Date: 2026-09-11
Everything above "Result" was written before the δ estimation ran. The result is appended at the end.

## Context

The LP caps every player at `e(i) ≤ 32·avail(i)·x(i)`. Day 9 (`minute_profile.py`) traced 32
to the **maximum observed season-average minutes**, not a rule of the game: over 2,553
player-seasons the maximum is 34.0, P99 is 30.6, and 8 exceed 32. Players do play 40 in a
single game, but `e(i)` is a season expectation, so "players play 40" is a per-game fact
applied to a per-season variable.

The proposal (HANDOFF day 15, next step 2) replaces the hard cap with two linear minute
tiers per player: full production up to a threshold, production discounted by δ above it.
The objective stays concave for δ ≥ 0, so the LP fills the first tier before the second
with no binaries and PuLP solves it unchanged.

The same Day-9 script found a different error that per-player constraints cannot touch:
the LP lets six players take 192 minutes between them, while the most concentrated real
club in ten seasons gave its top six 145.3, and no club had more than one player above 30
on season average. That is a constraint on the **shape** of the rotation.

## Decision

```
e1(i) <= 30·avail(i)·x(i)
e2(i) <= (34 − 30)·avail(i)·x(i)
objective term:  ppm(i)·e1(i) + (1 − δ)·ppm(i)·e2(i)
Σ (e1 + e2) <= 200 · position caps apply to e1 + e2
usage identity: e2 carries the same usage_prior as e1
```

- **Threshold 30**, fixed and not fitted. Fitting threshold and δ together puts two knobs
  on one curve. Thresholds 28 and 32 are declared as sensitivity: reported, never used to
  choose.
- **Ceiling 34**, the observed maximum season average. Not 40.
- **One δ for every player.** G/F/C estimates are printed as a diagnostic only, with no
  switch to position-specific δ in this change.
- **The scorer changes with the LP.** Both copies of `score_rows`
  (`optimizer_backtest.py`, `roster_membership_audit.py`) sort minute *segments* —
  tier 1 at `ppm`, tier 2 at `(1−δ)·ppm` — instead of players. Real clubs are scored by the
  same function, so both sides of `adv` move. Diagnostics stay on `MAX_MIN_PLAYER = 32`.
- **δ is read from `data/processed/fatigue_delta.csv`, never typed.** The LP reads δ and the
  verdict from that file. Unless the verdict is `enters`, the tiers are off and the model is
  exactly today's.

### How δ is estimated

```
Valuation_ig = r_is · ( min(m_ig, 30) + (1−δ)·max(m_ig − 30, 0) ) + ε_ig
i player · g game · s season — one rate per player-season
dependent: total Valuation per game, not per minute (division bias)
δ: profile over grid [-0.30, 0.60] step 0.005; r_is closed-form given δ
CI: bootstrap clustered by player, B = 1000, seed 20260911
sample: 2016–2025, m > 0, regulation only (team minutes <= 201)
P  = all games · S1 = |final margin| <= 10 · S2 = drop player-games with 5+ fouls
```

Confounders, with the direction each pushes δ, declared before the run:
- **Blowouts:** stars sit when the lead is large, so a high rate goes with low minutes.
  This pushes δ up.
- **Foul trouble:** PIR subtracts fouls, and fouls also cut minutes, so a low rate goes with
  low minutes. This pushes δ down.
- **Hot hand:** the coach keeps the player who is playing well, so a high rate goes with
  high minutes. This pushes δ down.

The directions are opposed. No specification is clean, which is why S1 and S2 exist.

### Decision rule, declared before the run

With `δ_min = 0.10`:

| outcome | condition | consequence |
|---|---|---|
| `enters` | P: δ̂ ≥ δ_min and CI lower bound > 0, and δ̂ > 0 in S1 and in S2 | tiers go into the LP (step 4, test-first) |
| `refuted` | P: CI upper bound < δ_min | tiers do not go in. A legitimate result |
| `not_identified` | anything else | tiers do not go in. Reported as not identified, **not** as refuted |

A negative δ̂ never enters, whatever its interval. With δ < 0 the LP would fill tier 2
before tier 1, and the formulation would need binaries.

## Considered options

- **Ceiling 40** (HANDOFF). Rejected. A season average above 34 has no observation in ten
  seasons. δ is measured on in-game minutes 30–40, and using it to license season averages
  of 35–40 is extrapolation inside the model. The project greys out extrapolation
  everywhere else.
- **"δ ≈ 0 → falsified"** (HANDOFF). Replaced by the three-outcome rule. A wide interval
  means the data did not identify δ, which is a different finding from δ being zero.
- **The top-k minutes-shape constraint** (Day 9). Deferred, not rejected. It addresses the
  error that was actually measured; tiers address one that is hypothesised. One change at a
  time, so the effect of δ is measurable on its own. Candidate for ADR 0005.

## Consequences

- **Tiers are not a tightening of today's model.** They relax 32 → 34 and discount 30–32.
  "A tighter constraint cannot raise the objective" is therefore not the right test. The
  step-4 tests are:
  - **T1 nesting:** δ = 0 with C = 32 reproduces today's LP exactly.
  - **T2:** the objective is non-increasing in δ.
  - **T3:** the objective is non-decreasing in C.
  - **T4 fill order:** with δ > 0, no player has e2 > 0 while e1 is below its cap.
  - **T5 minutes:** Σ(e1+e2) ≤ 200.
  - **T6 ceiling:** e1 + e2 ≤ 34·avail for every player.
  - **T7 consistency:** the scorer on the LP roster reproduces the LP objective.
  - **T8 guard:** δ < 0 raises instead of solving.
- **Tiers are not claimed to give depth value.** Whether minutes spread depends on δ. If
  (1−δ)·ppm of a star still beats the marginal player, stars go from 32 to 34 and minutes
  concentrate. The claim that "depth has value" cannot be attributed to this change.
- **Known approximation.** δ is an in-game quantity applied to season averages. By Jensen,
  a player averaging 30 plays some games above 30, so on averages the discount starts
  earlier than the tier says. Applied to averages, δ understates fatigue.
- **The curse-cost prediction is locked after δ is known and before the LP run.** It has two
  parts: mechanism M1, the top-6 minutes of the free roster; and outcome M2, the free curse
  cost, baseline `0.0966` (`curse_selection_market.csv`).

## Predictions for step 2, locked before the run

```
Claude: δ̂ ∈ [-0.05, +0.05] · 95% CI half-width <= 0.04
        verdict refuted ~60% · not_identified ~25% · enters ~15% · sign unstable across P/S1/S2
Almog:  δ̂ ∈ [0.02, 0.08]
```

Almog's interval lies wholly below δ_min. If it holds, the tiers do not enter under either
prediction.

## Result — appended after the run

`src/fatigue_delta.py` → `data/processed/fatigue_delta.csv`, `fatigue_delta_buckets.csv`

```
spec   δ̂        95% CI              n games   > 30
P     -1.155   [-1.435, -0.930]     62,637   4,838
S1    -1.290   [-1.600, -1.000]     35,769   3,247
S2    -1.115   [-1.375, -0.880]     61,156   4,747
T28   -1.095 · T32 -1.275 · G -1.360 · F -1.095 · C -0.535 [-1.000, -0.110]
declared rule → refuted (P ci_hi -0.930 < 0.10); δ̂ < 0 never enters
```

**The label stays as the declared rule produced it.** It is not relabelled after the fact.
What it licenses is narrower than the word suggests.

### What the number is

In the fitted model, δ̂ = −1.155 means a minute above 30 is worth 2.16 minutes below it.
That is not a physiological quantity.

The model is proportional through the origin: `V = r·z`. Within a player-season,
production per minute is not proportional to minutes. A descriptive profile, added after
the run and outside the declared design, shows per-minute production relative to the
player's own season rate:

```
minutes   ≤10    10–15   15–20   20–25   25–30   30–34   34–40
ratio     0.316  0.707   0.933   1.040   1.083   1.105   1.108
```

Short games are selected: foul trouble, injury, benching, garbage time. δ absorbs that
curvature. Two of the three confounders declared above, foul trouble and the coach riding
the hot hand, push δ down, and together they dominate. The design measured how minutes are
allocated, not fatigue.

### What this licenses

- **It licenses:** the tiers do not enter, and the LP is unchanged. Step 4 does not happen.
- **It licenses, descriptively:** box scores show no decline in per-minute production
  above 30 relative to the player's own season rate (1.083 → 1.105 → 1.108).
- **It does not license:** "fatigue does not exist", or "minutes above 30 are free".
  Game-total data cannot separate fatigue from the coach keeping a player who is playing
  well. Do not write either claim on the dashboard or in the README.
- **Revisit only with a within-game design.** That means play-by-play stints: the same
  player's production in minutes 30–40 of a game against his earlier minutes in the same
  game. That removes the game-level selection. Game totals cannot.

### Deviations from the declared procedure

1. **Grid extended.** The declared grid was [−0.30, 0.60]. The first run put every
   specification on the lower edge with a degenerate CI, and the edge guard stopped it.
   Extending the grid to [−2.00, 0.60] is the remedy for an edge hit. It cannot change the
   verdict, because no δ̂ < 0 enters.
2. **Synthetic guard re-specified.** "±0.02 on one noisy draw" tested precision, not bias:
   two draws gave 0.090 and 0.185. It is now two checks:
   - exact recovery without noise: 0.150;
   - the mean of 100 draws within ±0.02 of δ_true: 0.146, with SD 0.063.
   That SD is the design's resolution. It already implied a CI half-width near 0.12 before
   the real data was touched.
3. **Bugs fixed at source during the run:**
   - The player and team `Points` columns clashed.
   - In 2018 and 2021, the `Total` rows carry full team names while the player rows carry
     codes. The `Total`-row guard caught 12,001 player-games, and the key moved to
     `(Gamecode, Home)`.
   - There were 2 empty `Total` stubs.
   - Position codes had been read as strings, so the position join matched nothing.
4. **Added outside the declared design:** the bucket profile above. It is descriptive only
   and does not enter the verdict.
5. **Column naming.** The declared column `n_players_both_sides` is implemented as
   `n_groups_both_sides`, which counts player-seasons, plus `n_players`.

### Predictions

```
Claude  δ̂ ∈ [-0.05, 0.05]       -1.155   ❌
Almog   δ̂ ∈ [0.02, 0.08]        -1.155   ❌
Claude  CI half-width ≤ 0.04     0.253    ❌
Claude  verdict refuted          refuted  ✅  (mechanically — see above)
Claude  sign unstable            negative in all 8 specs   ❌
```

### Consequences

- The curse-cost lock (M1/M2) is moot, because no LP run follows.
- The Day-9 top-k minutes-shape constraint remains the open candidate for the error that
  was actually measured: 192 minutes for the top six in the model against 145.3 in reality.
  It would be ADR 0005.

