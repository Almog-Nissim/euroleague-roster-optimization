# ADR 0003 — A season is named by its opening year

Status: accepted
Date: 2026-09-09

## Context

Two conventions coexisted in the codebase, inside the same file:

```python
label = f"{SEASON-1}/{SEASON-2000}"   # treats SEASON as the closing year
SEASON, TRAIN_MAX = 2025, 2024        # comment reads "25/26" — opening year
```

The formula printed `2024/25` into JSON while the report header printed `2025/26`. The
display half was fixed on Day 14, but the convention itself was never declared, so nothing
prevents it recurring.

The display bug was the harmless symptom. The real exposure is filtering: code written
under the closing-year reading that does `df[df.season == 2025]` silently selects a
different season, with no error and no visible sign.

## Decision

`season` and `SEASON` are always the **opening year**. `season = 2025` is the 2025/26
season. Display strings are derived, never stored:

```python
f"{SEASON}/{(SEASON + 1) % 100:02d}"
```

## Alternative rejected

Closing year. Rejected because every processed CSV, every JSON key and every filename in
the repo already carries the opening year. Switching would mean rewriting the data, not
just the code.

## Consequences

- `salary_external_2025.csv` stores strings like `"2025-2026"` in `season` and an opening
  year in `yr`. `yr` is canonical; the string column is display-only and should not be
  joined on.
- Any new season column is an integer opening year. No hard-coded label strings anywhere.
