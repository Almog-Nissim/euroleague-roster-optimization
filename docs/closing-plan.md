# Closing plan — portfolio v1.0

Stage 1 blocks everything else. Stages 2 and 3 can run in parallel. Stages 4 and 5 come
last. Estimate: 3–4 sessions.

## 1. Freeze the model (one session)

- **ADR 0005 — the top-k minutes-shape constraint.** The model gives its top six 192
  minutes; the most concentrated real club gave 145.3 (`minute_profile.py`, Day 9).
  - Order of work: grill, locked predictions, failing tests, then the run.
  - The nesting tests from ADR 0004 carry over. T1: a fully slack constraint reproduces
    today's LP exactly.
  - Accept whatever number comes out.
- **Fix `refit_acceptance.py` condition 1.** It checks the normalised `a` instead of the
  euro-level `a`. The verdict is unaffected.
- **Update FROZEN in `export_dashboard.py` and tag `v1.0`.**
- **Rule from here on:** the engine gets bug fixes only. New ideas go to the v2 list below.

**Done when:** there is a final headline number with a CI, tagged in git.

## 1b. Queued behind the running solve — code fixed, regeneration owed

Three fixes are committed as code but **not verified by a run**, because each needs
`build_pool` and two of them overwrite tracked result files. They are owed a run once the
ADR 0006 solve finishes and the CPU is free.

- **`engine_rosters.csv` → fills `minutes_alloc`.** The column was empty in 456 of 456 rows
  because `extract_minutes` searched the return value of `score_rows` for an array, and
  `score_rows` returns three scalars. `dump_rosters.py` now takes the LP's own minute
  vector for the engine side and the minutes played for the club side, the ADR 0006
  convention. Five scripts read this file. Re-run `src/dump_rosters.py`.
- **`refit_acceptance.py` condition 1.** Now gated on the euro-level axis instead of the
  normalised one. The verdict does not change — `b` fails on both axes — but the printed
  `a` and the tracked `refit_acceptance.csv` will. Re-run and commit the new CSV.
- **`score_to_wins.py` budget control.** Switched from `gross_eur`, empty for all 20 clubs
  of 2025, to `net_eur`, complete at 56/56. This changes one of the three refutations, so
  **lock a prediction before re-running it.** It writes no CSV.

**Status:** `dump_rosters` done (`engine_rosters.csv` regenerated) · `refit_acceptance` done
(`e4a670b`, `46abf3d`) · `score_to_wins` waiting on a prediction from both sides.

**Found while regenerating:** `engine_rosters.csv` was committed on day 10 and never
regenerated after the market refit (ADR 0001, day 15), so it held engine rosters from the
previous cost model — all 38 differed. Two tracked results are derived from it and are
therefore stale: `roster_usage.csv` and `usage_decompose.csv` (the "21.83% against 20.03%"
usage gap quoted in `usage_constrained.py`). Neither is on the headline path. Regenerate
them or mark them historical — not a v1.0 blocker.

**Done when:** all three have run, their outputs are committed, and no document quotes a
number from before the fix.

## 2. Dashboard

- Cut `B_HI` from 40 to about 24, at the saturation point.
- Remove the per-player euro figure: one player currently displays a negative amount.
- Show three caveats visibly:
  - depth: the engine carries 12 players, real clubs 15–20;
  - fatigue is not modelled (ADR 0004);
  - extrapolation outside the data is greyed out.
- Check the Vercel link, including on mobile.

**Done when:** a stranger understands what they see within 30 seconds.

## 3. Repo

- **New README:** one claim, how it was measured, the three caveats, the run order to
  reproduce, a dashboard link, and one figure.
- **Tidy the root:** move the day summaries and patches to `docs/archive/`, and decide what
  to do with `.agents/`, `.claude/` and `skills-lock.json`.
- **`METHODS.md`:** update it to the market spec, or mark it historical.

**Done when:** someone who clones the repo reproduces the headline from the README alone.

## 4. CV

- **One or two bullets with the final number.** Shape: LP roster-construction engine for
  the EuroLeague → backtest on 38 club-seasons → X extra wins per season on the same
  budget, with its CI → three alternative explanations refuted.
- **Tools line:** Python, PuLP, statistical testing, React/Vercel.

## 5. LinkedIn post

- **Shape:** question (can you buy wins without adding money?) → approach in two sentences
  → result → what surprised me → link.
- **The surprises carry the post:**
  - Past a point, money stops buying improvement.
  - I rejected my own feature on evidence, with a decision rule declared in advance.
  - Three alternative explanations of the headline were tested and refuted.
- **Visual:** a dashboard screenshot. **Length:** 150–250 words.
- **Language:** open — decide by audience.
- **Never write:** "fatigue doesn't exist", per-player euro figures, or a win number
  without its caveat.

## v2 list (not before v1.0)

- Monte Carlo depth-insurance scoring (expected to lower the headline).
- Fatigue with a within-game design (play-by-play stints), if ever.
- Regenerate the 10 `unsourced` before-values in a scratch worktree.
