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
