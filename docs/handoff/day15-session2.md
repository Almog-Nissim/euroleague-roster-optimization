# Day 15, session 2 — handoff

Fatigue tiers designed, estimated, and rejected. Day-15 provenance debt paid. Docs cleaned.
Read before starting: `CONTEXT.md`, `docs/adr/0004-fatigue-tiers-gated-on-measured-delta.md`,
`docs/refit-day15-diff.md`. This file does not repeat them.

## Where it stands

| commit | what |
|---|---|
| `8661308` | original `usage_curve_results_min0.csv` tracked; curse outputs |
| `cc6bb2c` | regenerated `price_error_*`, `refit_acceptance`, `refit_player_check`, `display_money_check` — all documented values reproduced |
| `944e32a` | `src/refit_diff.py` → `refit_day15_diff.csv`; handoff provenance note |
| `6e1374e` | `src/fatigue_delta.py` + ADR 0004: δ refuted by the declared rule, tiers out, cap stays 32 |
| this commit | docs cleanup: diff doc rendered from the CSV, CONTEXT without stale numbers, dashboard caveat fixed |

The LP and the headline are unchanged this session: `adv_cap` 0.1414, 4.26 wins.

The fatigue-delta results committed from the local machine are byte-identical to a sandbox
run. Every input is tracked, so the sandbox is trustworthy for that script.

## Open items, in the order I would take them

1. **ADR 0005 — the top-k minutes-shape constraint** (Day 9, `minute_profile.py`). This is
   the error that was actually measured: 192 minutes for the model's top six against 145.3
   in reality. Grill it before any code.
2. **Product decisions still open:** cut `B_HI` from 40 to about 24; remove or rework the
   per-player euro figure (one player displays a negative amount).
3. **`refit_acceptance.py` condition 1** checks the normalised `a` (1.443) instead of the
   euro-level `a` (1.087). The verdict is unaffected, because `b` fails on both axes. Fix
   it at the source.
4. **Monte Carlo depth-insurance scoring** (day-15 HANDOFF, step 3). It is expected to
   *lower* the headline. Lock predictions first.
5. **Ten `unsourced` before-values** in `refit_day15_diff.csv`. Regenerate them only in a
   scratch worktree: running the `club_relative` chain in place overwrites tracked result
   files.
6. **Untracked tooling directories** (`.agents/`, `.claude/`, `skills-lock.json`): decide
   whether to ignore or commit them. Never use `git add -A` meanwhile.

## Working with this machine (not recorded elsewhere)

- **Commands.** Almog runs every command in PowerShell. Pasted lines run one by one, so a
  `throw` stops only its own line. Every run block must:
  - be wrapped in `& { … }`;
  - pin the repo path and check the `origin` remote before doing anything;
  - use `-ErrorAction Stop` on file cmdlets;
  - check `$LASTEXITCODE` after every `git` and `python` call.
- **File transfer.**
  - Attachments download to `C:\Users\a9lmo\Downloads`. Place them in the repo by SHA-256,
    never by name.
  - Do not transfer files as base64 typed into a reply: a single mistyped character
    corrupted one transfer, and only the hash check caught it.
  - New files dropped into the repo root have twice been committed by accident, in the two
    commits titled "יאלה". Check `git status` for strays before every commit.
- **Line endings.** `core.autocrlf` is on. Compute md5 values on git blobs, not on
  working-tree files.

## Suggested skills

- `mattpocock-skills:grill-me` — ADR 0005 design.
- `mattpocock-skills:domain-modeling` — writing ADR 0005, and keeping `CONTEXT.md`
  current.
- `mattpocock-skills:tdd` — if the top-k constraint is implemented. The step-4 test list
  in ADR 0004 (T1 nesting, T7 scorer consistency) carries over.
- `mattpocock-skills:code-review` — before each commit.
- `mattpocock-skills:diagnosing-bugs` — only if something breaks.
