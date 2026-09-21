# v1.0 closing — handoff

The closing plan has gone through ADR 0005 → ADR 0006 → the `v1.0` tag → the dashboard →
the README, then the project summary, CV and LinkedIn draft. Read `CONTEXT.md`, `docs/adr/`,
`docs/closing-plan.md` and `README.md` first; this file does not repeat them.

## Where it stands

**Headline, frozen at `v1.0` (`0690e0e`):** `adv_cap = 0.1892`, proven optimal 38/38 at
`gap = 0`. That is **+5.01 wins per season, CI95 [+1.39, +8.69]**, under ADR 0006 (no
hindsight on either side). The engine takes bug fixes only from here.

| stage (closing plan) | status |
|---|---|
| 1. Freeze the model | done — tagged `v1.0`; SLACK sensitivity run, classed "sensitive" |
| 1b. Queued regenerations | done — `dump_rosters`, `refit_acceptance`, `score_to_wins` |
| 2. Dashboard | done and live; the 30-second stranger test is **still Almog's to run** |
| 3. Repo | done — README v1.0, `METHODS.md` on the market spec, root tidied |
| 4. CV | done — outside the repo (below) |
| 5. LinkedIn | text approved in chat (below); **not yet posted** |

**This session's last commits, all pushed:**

| commit | what |
|---|---|
| `19adf5c` | dashboard stage A: plain language, pick-your-club, four one-line trust cards |
| `ab3cab7` | `docs/project-summary.md`: for a technical interviewer, in a neutral voice |
| `77af87d` | budget shown as % of the average club in its season; the builder's price-model note |

Production: <https://dashboard-mu-eight-81.vercel.app/> redeploys on every push to `main`,
in about a minute. Repo: <https://github.com/Almog-Nissim/euroleague-roster-optimization>.

## Decisions made this session (not recorded elsewhere)

- **The 30.8% "wasted budget" figure is no longer the lead.** It is computed with hindsight
  and contradicts the depth caveat, because a bench is also insurance. It now sits lower,
  under "במבט לאחור" (looking back).
- **Display unit: % of the average club's budget in that season (100% = average).**
  - This is display only: `clubs.js` → `seasonAvg`, `pct`.
  - The internal unit is unchanged (1 = average pool player).
  - Player price is shown as % of the same budget.
  - Marginal return is shown per extra 10%.
- **Recurring players in the builder are partly under-pricing, not only value.**
  - Checked against known 2025 salaries: the salary/`cost` ratio is roughly flat for
    Vezenkov, Petrusev, Campazzo and Milutinov.
  - Hernangomez is priced at about half his salary.
  - The builder says so, and the item is on the v2 list.
  - Between budget 8 and budget 26 the rosters share 1 player of 12. Above 22 the
    starting five is fixed (saturation).
- **The "why 38/38" answer in the summary is marked as an untested interpretation.**

## Outside the repo

- **CV:** `C:\Users\a9lmo\Downloads\CV\Almog_Nissim_CV.docx` and `.pdf`.
  - One page (checked in Word).
  - It adds a EuroLeague project block (4 one-line bullets) and extends the skills lines.
  - SurfCustom was merged into one bullet.
  - The originals are untouched.
  - It is built by `scratchpad/cv/build_cv.py`, which edits the docx XML; Word COM exports
    the PDF.
- **LinkedIn post (Hebrew, approved):**
  - Opening question → the engine in two sentences → +5 with its caveat.
  - Then the bug story ("like picking a lineup after you've watched the game").
  - Then money saturating at about 1.5× an average club.
  - Then fatigue ("coaches keep whoever is hot on the floor").
  - Then the two links.
  - An English version also exists in the chat.
  - Rules it follows: no win number without its caveat, no euros, never "fatigue doesn't
    exist".
- **Links for recruiters:** the repo root. For a technical interviewer, add
  `docs/project-summary.md`.

## Open items, in order

1. **The 30-second stranger test** on the live dashboard. Almog runs it. Its result decides
   item 2.
2. **Dashboard stage B**, only if the test says it is needed:
   - a "guess before you see" game;
   - a "who's out / who's in" view from `shape_minutes.csv`.
   - Run a grill first.
3. **Post on LinkedIn**, with a dashboard screenshot (the headline screen or the builder
   curve).
4. **v2 list** (`docs/closing-plan.md`). The engine does not change before it.
   - Monte Carlo depth insurance.
   - The null model and curse re-derived under ADR 0006.
   - Price-model misses.
   - Stale `roster_usage` / `usage_decompose`.
   - Duplicated scoring paths and dead scripts.
- `data/dashboard/roster_sweep_shape.json` is untracked **on purpose**. Leave it.

## Working with this machine (additions)

- **Python output:** stdout defaults to cp1255. Printing ✅/❌ crashes unless a script
  calls `sys.stdout.reconfigure(encoding="utf-8")`.
- **Bash heredocs:** mangled `\n`, backslashes and nested quotes several times. For
  multi-line edits, write a patch script to the scratchpad, where each replacement asserts
  `count == 1`, or use the Edit tool.
- **Word:** available through COM from PowerShell. Use it for docx → PDF and for page
  counts.
- **PDFs:** there is no pdftoppm or Python PDF library. The WinRT `Windows.Data.Pdf` API
  renders PDF pages to PNG.
- **Local preview:** `.claude/launch.json` defines `dashboard-preview` (`vite preview`,
  port 4173). `.claude/` is git-ignored. The Browser pane's screenshots are flaky, so
  check the DOM with JS instead.
- **Checks before any push:** after `npm run build`, confirm there is no NaN or undefined
  and no sideways scroll, on desktop and at 375 px.

## Suggested skills

- `grilling` — before dashboard stage B.
- `code-review` — before the next commit that touches `src/`.
