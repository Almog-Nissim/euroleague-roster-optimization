# Project summary — EuroLeague roster optimization

For a technical reader who wants to know what was built, how the claim was tested, and
what went wrong along the way. The README states the claim. This file tells the story
behind it. Every number here comes from a tracked results file. The README and the ADRs
name the script that produces each one.

---

## In three lines

- A mixed-integer program builds a EuroLeague roster under a fixed budget. It is
  backtested against the rosters real clubs actually fielded, with the same budget on both
  sides.
- **Result:** +5.01 wins per season, 95% CI [+1.39, +8.69]. The engine's roster
  out-produces the club's in 38 of 38 club-seasons (2024/25 and 2025/26).
- Most of the work is in the evaluation. The headline moved sharply more than once, and
  each time the cause was how the two sides were *scored*, not the model. The largest jump
  was stopped by a rule written before the run.

---

## 1. The question

Can a club get more wins without spending more money, just by choosing different players?
That question forces three sub-problems:

1. **What will a player produce next season, and how often will he be available?**
   (prediction)
2. **What does he cost?** Salaries are mostly not public. (pricing)
3. **Given 1 and 2, which roster and which minutes?** (optimization)

And one question that decides whether anything above means anything: **how do you compare
an engine's roster to a real one fairly?** (evaluation)

---

## 2. Pipeline

```
EuroLeague API box scores  ->  player-season table  ->  features
      |                                                    |
      |              production model (WLS, shrinkage) ----+
      |              availability model (binomial GLM) ----+
      |              cost model (log-linear, club + season FE)
      v                                                    v
 real club rosters  --------------------------------->  MILP (PuLP / CBC)
                                                           |
                               scoring (ADR 0006)  <-------+
                                     |
                         production -> wins regression -> headline + CI
                                     |
                      export_dashboard.py (frozen-value guards) -> React / Vercel
```

**Production.** Weighted least squares on lagged per-minute PIR. The estimate is shrunk
toward the league mean with `w = games / (games + 40)`, so a player with 3 games is
93% league average. `k = 40` is declared, and swept at 20 and 60.

**Availability.** A binomial GLM on games available. Out of sample (train ≤ 2023, predict
2024): predicted 0.753, actual 0.740. The calibration gap is 0.054, inside a threshold
registered in advance (0.070).

**Production calibration failed its pre-registered threshold** (0.096 against 0.05). It is
reported, not hidden. Its effect on the claim is measured directly: the "winner's curse"
term (§5) is the advantage lost because the engine optimises on *predicted* production and
is scored on *real* production.

**Cost.** Salaries are public for only 175 player-seasons. 77 fit the model; the rest are
held out, or used for squad structure only. The split is by club, not by row: a club goes
entirely to one side, because the model has club fixed effects.

```
log(salary / squad_mean) ~ β₁·pir_lag_shrunk + el_seasons + club FE + season FE
β₁ = 0.148 on the market (74 salaries, 14 clubs, t = 6.43)
```

The pool is priced at a league-average club (ADR 0001), and divided by the pool mean. So
**one budget unit = one average pool player**, and no number is ever shown in euros.
The euro mapping was built, tested against three pre-declared gates, and failed all three
(`refit_acceptance.py`).

A useful fact for reasoning about the model: **β₁ is the only cost parameter that can
change which players the LP picks.** Every other term scales all prices and the budget by
the same factor, which leaves the feasible set unchanged.

---

## 3. The optimizer

A MILP per club-season. Binary `x_i` means player i is on the roster. Continuous `e_i` is
his expected minutes per game.

```
max   Σ ppm_i · e_i

s.t.  Σ cost_i · x_i                ≤ B               budget = cost of the club's real roster
      12 ≤ Σ x_i ≤ 16                                  roster size
      e_i ≤ 32 · avail_i · x_i                         per-player minute cap (observed max)
      Σ e_i = 200                                      five players × 40 minutes
      Σ e_i (per position) ≤ POS_MAX_SHARE · 200       each position within its observed share
      Σ usage_i · e_i = 0.20 · 200                     ball identity: 5 players, 1 ball
      Σ top-k(e) ≤ C_k        for k = 1..8             shape of the rotation (ADR 0005)
```

**Ball identity.** Usage is the share of possessions a player ends. Five players share one
ball, so the minutes-weighted mean usage must be exactly 20%. That is arithmetic, not an
estimate. Without it the engine stacks high-usage scorers whose usage cannot add up.

**Shape constraint.** "Sum of the k largest entries ≤ C" looks non-linear. It has an exact
linear form with one free variable `q` and slacks `s_i`:

```
k·q + Σ s_i ≤ C_k,    s_i ≥ e_i − q,    s_i ≥ 0
```

The caps `C_k` are the most concentrated rotation any of the 38 real club-seasons played.
Before this constraint, the engine gave its top six 192 minutes. The most concentrated real
club gave 145.3.

**Solver discipline.** PuLP's `LpStatus == "Optimal"` is also returned when CBC stops on
a time limit with a feasible solution. The code reads `sol_status` (1 = proven,
2 = time-limited) and refuses anything but 1 on the headline path. All 38 headline solves
run at `gap = 0` and are proven optimal. A 0.5% gap moved one club-season by up to 14 points.

---

## 4. Evaluation — where most of the work went

Both sides get the **same budget**: what the club's actual roster costs under the same
price model. Both are scored on production that **actually happened** (`ppm_true`), not
predicted. The engine only trains on seasons before the test season.

The hard question is **how much hindsight each side gets.** The final convention
(ADR 0006) gives neither side any:

- **Engine:** credited for the minute plan it committed to *before* the season, cut to
  the availability that actually happened. Minutes planned for a player who got injured are
  **not** reallocated to teammates. They go to a replacement-level player (REPL = 0.127
  PIR/min), because that is the real cost of planning around someone who is absent.
- **Club:** credited for the rotation it actually played.

**Production → wins.** A within-season regression of club wins on club production, with
the club's real net budget as a control. The CI bootstraps the slope and the production gap
together.

### The number, with its decomposition

Each row changes one thing from the previous convention. The effects interact, so the rows
are not a sum.

```
  previous convention: both sides reallocated with hindsight     adv 0.1414   4.26 wins
    score the club on what it played                                  +18.18 pp
    take the engine's hindsight away                                   −9.91 pp
    add the rotation-shape constraint                                  −1.79 pp
  v1.0 (all three)                                               adv 0.1892   5.01 wins
```

In plain terms: the old convention flattered the club *more* than it favoured the engine,
so the old headline was conservative. But most of the engine's old advantage was
hindsight. With hindsight removed from the engine alone, the advantage falls to 0.0423.

---

## 5. Alternative explanations

| If the gap were really… | Test | Result |
|---|---|---|
| …the constraints, not the choices | a random roster under the same constraints | loses to the club: −1.72 wins [−3.32, −0.35] |
| …just money | wins on production with net budget as a control | 64% of the slope survives |
| …selection bias in the engine's picks | predicted vs realised production of chosen players | bias ≈ 0; the winner's curse is reported separately |
| …the club side being restricted to the engine's pool | count real players lost to the pool filter | 0 lost (`pool_restriction_check.py`) |

Rows 1 and 3 were measured under the previous scoring convention. Re-running them under
ADR 0006 is on the v2 list.

**38 of 38 is a reason to look harder before it is a reason to be pleased.** That is why
row 4 exists.

---

## 6. Things that went wrong, and how they were caught

None of these was a crash. All of them
produced a plausible number.

| What happened | How it surfaced | What changed |
|---|---|---|
| Adding the shape constraint **doubled** the advantage (0.1414 → 0.2807, +98%). A constraint should make the engine *worse*. | A rule declared before the run: "rises > 50% → STOP". | Found an asymmetric scoring convention. The engine kept a hindsight minute allocation and the club did not. Removed hindsight from both sides (ADR 0006). |
| Comparing the engine to a club's *predicted* production inflated the result by ~12 pp, to a spurious ~30%. | Cross-checked against a fair comparison. | The rule is recorded in `CONTEXT.md` and in the exported data. |
| `score_shape` silently fell back to a greedy allocation on 9 of 38 rosters. | Code review: the fallback path had no counter. | Fallbacks are counted and printed with ❌. A non-zero count fails the run. |
| The solver guard accepted a time-limited solution as optimal. | A test that forces `sol_status = 2`. | The guard raises. The headline requires 38/38 proven. |
| `engine_rosters.csv` was empty in 456 of 456 rows for a column. It was also still built with the previous cost model. | Regenerating it for an unrelated reason: all 38 rosters differed. | A helper searched for an array in a function that returns three scalars. Fixed at the source. Two derived files are marked stale. |
| A fix to one acceptance script silently changed what a second script read. | Its numbers stopped matching. | Both scripts now name explicit columns. |
| One code path treated `season` as the closing year and another as the opening year. | A report header and a JSON label disagreed. | ADR 0003: always the opening year, and display strings are derived. The real risk was a silent `df.season == 2025` filter selecting the wrong season. |
| A euro axis was shown on the dashboard, including a negative salary for one player. | Three pre-declared acceptance gates. | All three failed, so no euros anywhere. |

**One feature was rejected on evidence.** Fatigue tiers (a production discount above
30 minutes) were designed, estimated, and rejected by a rule written before the estimate
ran (ADR 0004). Box scores cannot separate fatigue from a coach leaving a hot player on the
floor. This does **not** show that fatigue doesn't exist, and the project never claims it does.

---

## 7. How the work was run

- **Predictions locked before every run**, from two sides. A decision rule said in advance
  what each possible result would license. Misses are recorded next to hits in the ADRs.
- **Six ADRs.** Each has the context, the decision, the rule, and the result appended
  below a line written before the run.
- **Every claim has a script and a tracked results file.** Scripts print their guards
  (✅/❌). No silent success.
- **Frozen values.** `export_dashboard.py` refuses to build the dashboard if any headline
  number fails to reproduce from its source file.
- **Tests on the LP.** 24 tests on the shape constraint. They include nesting (a slack
  constraint reproduces the old LP exactly), equivalence between two code paths, and the
  solver-status guard.
- **Tagged `v1.0`.** From there the engine takes bug fixes only, and new ideas go to a
  v2 list.

---

## 8. Limits, stated where the claim is stated

1. **Depth.** The engine carries 12 players; real clubs carry 15–20. The cost is measured,
   not assumed: 14.2% of the engine's planned minutes went to players who turned out to be
   unavailable. It wins anyway.
2. **Fatigue is not modelled** (see §6).
3. **Sensitive to the shape caps.** Tightening them 5% cuts the median advantage on a
   declared 12-club subsample from 13.9% to 9.8%. Loosening them 5% doesn't raise it. The
   observed caps stay the specification, and the sensitivity is reported, never used to
   choose.
4. **Extrapolation.** The wins conversion was learned on smaller production gaps than the
   engine creates. The dashboard greys out budgets outside the range real clubs spent
   (12.5–25.3 units).
5. **Not a claim about coaching.** The engine plans minutes, but the claim is only about
   *which players*, on the same money.

---

## 9. Next steps (v2)

- **Depth as insurance:** Monte Carlo over availability, scoring a 15th player by the games
  he saves. Expected to *lower* the headline.
- Re-run the random-roster null model and the winner's-curse decomposition under ADR 0006.
- Fatigue only with play-by-play stint data (a within-game design), if ever.
- Tidy up the duplicated scoring paths and dead scripts left from earlier stages.

---

## 10. Likely questions, briefly answered

**Why an LP and not a learned policy?** The decision is small: about a dozen players from a
few hundred, under hard constraints. The constraints (budget, roster size, ball identity)
are the domain. An exact solver makes every result auditable and provably optimal. A
learned policy would add variance and hide why a player was chosen.

**Isn't 38/38 suspicious?** Yes, and it was treated that way. The random-roster null
model loses to the clubs, the pool-restriction explanation was checked (0 players lost), and
the advantage survives removing all hindsight. Why clubs leave this much on the table was
not measured. One interpretation, not tested here: clubs pay for things the model does not
price, such as depth, fit, and long-term contracts.

**Where does the uncertainty come from?** Mostly the production → wins slope and the
spread of club-level gaps. Both are bootstrapped together. A single club is noisy, so the
claim is the median over 38.

**What's the weakest link?** The production model's calibration (§2), and the fact that the
engine never pays for depth beyond 12. Both are measured and on the v2 list.

**How do you know the code does what you think?** Guards that print, frozen values that
block the build, exact-solve checks, and a test that the new constraint, when slack,
reproduces the old model exactly. Three of the bugs in §6 were caught only after a guard
was added.

---

## Stack and scale

Python (pandas, NumPy, SciPy, statsmodels, PuLP/CBC), React + Vite on Vercel.
About 110 scripts in `src/`, 6 ADRs, 24 LP tests. Built August–September 2026.
The full 2×2 grid is 152 exact solves, 10–13 hours on one machine.

- Dashboard: <https://dashboard-mu-eight-81.vercel.app/>
- Code: <https://github.com/Almog-Nissim/euroleague-roster-optimization>
