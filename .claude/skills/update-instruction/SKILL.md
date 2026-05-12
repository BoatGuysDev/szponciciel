---
name: update-instruction
description: Update a CLAUDE.md file (and supporting docs/) to reflect the latest changes. Use only when the user explicitly asks to update a CLAUDE.md file.
---

CLAUDE.md is an **index**, not an encyclopedia. It surfaces only what Claude won't know from the code, standard tooling, or canonical config. Concept depth lives in `docs/<concept>.md`.

## Keep in CLAUDE.md

- Project-specific commands and gotchas (required env vars, custom module paths).
- File-path landmarks — pointers, not explanations.
- Conventions that shape every change (failure-signaling pattern, test layout, naming rules).
- One-line pointers into `docs/` when a concept warrants depth.

## Drop from CLAUDE.md (the trim test)

For each line, remove or move to `docs/` if any answer is yes:

- Derivable from the obvious source file?
- Standard framework / tooling pattern (pytest, SQLModel, LangGraph, mock.patch)?
- Already in `.env.example`, `pyproject.toml`, `alembic.ini`, etc.?
- Explanation longer than ~2 lines? → promote to `docs/<concept>.md`.

## Workflow

1. Read current `CLAUDE.md` and list `docs/`.
2. `git diff` (or `gh pr diff`) to find what changed.
3. For each change:
   - **New concept needing depth** → write `docs/<name>.md`; add a CLAUDE.md pointer only if it aids orientation.
   - **Changed concept** → edit the `docs/` file; touch CLAUDE.md only if a referenced name/path/contract changed.
   - **Project-specific gotcha** → terse line in CLAUDE.md.
   - **Standard / derivable** → don't document.
4. Run the trim test on the whole CLAUDE.md.
