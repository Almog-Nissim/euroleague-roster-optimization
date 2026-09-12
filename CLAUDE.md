# CLAUDE.md

EuroLeague roster optimization: LP engine plus React/Vercel dashboard. The goal now is
to close the project for a portfolio. The plan is in `docs/closing-plan.md`.

## Start of every session

Read `CONTEXT.md`, `docs/adr/`, `docs/closing-plan.md`, and the newest file in
`docs/handoff/` before touching code. Do not re-open anything an ADR marks as settled.

## Talking to Almog

Reply in informal Hebrew. Put code, identifiers, paths and formulas in code blocks,
because mixed Hebrew/English lines break right-to-left rendering. Prefer pushback to
agreement.

## Rules for any claim or run

- **Predictions before every run.** Lock them from both sides, Almog's and yours, before
  anything executes. Do not explain why a result makes sense before it is out.
- **Declare parameters before any sensitivity analysis.**
- **Every claim needs a generating script and a tracked results file.**
  `data/processed/*` is gitignored; whitelist each new results file in `.gitignore` in the
  same commit.
- **Scripts print their guards (✅/❌).** No silent success.
- **Fix bugs at the source, and write complete files.**

## Git

- Commit before the session closes. Stage explicit paths only; never `git add -A`.
- Before every commit, run `git status` and check for stray files in the repo root.
- `COST_SPEC=market` is production. Never run the `club_relative` chain in place: it
  overwrites tracked result files. Use a scratch worktree for that.

## Scope

- The model freezes at tag `v1.0` (closing plan, stage 1).
- After that, only bug fixes go into the engine. New ideas go to the v2 list in the
  closing plan.

## Skills

- `/grill-me` — before any design decision.
- `/domain-modeling` — ADRs and `CONTEXT.md`.
- `/tdd` — any change to the LP or the scorer.
- `/code-review` — before every commit.
- `/handoff` — at session end. Save the result under `docs/handoff/`.
