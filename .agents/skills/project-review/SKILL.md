---
name: project-review
description: Full-project code review and cleanup audit of PrintForge — hunts real bugs, over-complexity, dead code, and stale files in both the repo and on the Pi itself. Report-only; produces a findings report plus deletion manifests and changes nothing without approval. Use when the user asks for a code review, project audit, or cleanup pass.
argument-hint: [optional focus — backend | frontend | scripts | pi | all]
allowed-tools: Bash, Read, Glob, Grep
---

# PrintForge Full Code Review

Review the entire PrintForge project. The goal: code that is **simple, error-free, and professional** — a project a stranger could read and assume was maintained by a careful senior engineer. Anything redundant or unneeded gets flagged for deletion, including files on the Pi, not just the repo.

Priorities, in order:
1. **Correctness** — real bugs, races, unsafe printer behavior.
2. **Simplicity** — redundant code, duplicated logic, over-abstraction.
3. **Cleanliness** — dead code and stale files to delete (repo AND Pi).
4. **Professionalism** — consistency, naming, error handling, accurate docs.

`$ARGUMENTS` may narrow scope to one phase; default is everything.

## Ground rules

- **Report-only.** Do not edit, delete, restart, or deploy anything during the review. The deliverable is a report; the user approves changes afterward.
- **The Pi is live hardware.** Production (`:8000`) drives a real printer that may be mid-print. All SSH during the review is strictly read-only: `ls`, `cat`, `du`, `find`, `diff`, `systemctl status`, `systemctl list-unit-files`. Never `rm`, never restart/stop services, never write files, never send G-code.
- **Every claim needs evidence.** Bugs need `file:line` plus a concrete failure scenario ("if X happens while Y, then Z"). Every "unused, delete it" claim needs the searches that came up empty — grep the repo, deploy scripts, skills, docs, and systemd units for references before calling something dead. If you can't fully verify, mark it "needs confirmation" instead of asserting.
- **Read whole files before judging them.** `controller.py` is ~850 lines; excerpts mislead. Batch SSH commands to minimize round trips.
- **Track coverage.** End the report with the list of files reviewed and anything skipped, so gaps are visible.

## Intentional patterns — do NOT flag these

- Svelte 5 runes (`$state`, `$derived`, `$props`, `onclick=`) — correct, not a mistake. The *reverse* (Svelte 4 syntax: `on:click`, `export let`, `$:`, `<slot />`) IS a bug.
- Tailwind **v3** patterns: `@apply` in `@layer components`, custom `surface-*` scale, dark-only theme. Light backgrounds are the bug, not the dark theme.
- Python 3.9 target: `from __future__ import annotations` at top of modules is required, not clutter. The *reverse* — 3.10+ syntax that would crash on the Pi — is a deploy-breaking bug.
- Serial quirks: 2–3s delay after connect (USB resets the printer), send-and-wait-for-`ok` flow, tolerance for garbage echo on connect, checksums/line numbers only during print jobs.
- `app.mount("/", StaticFiles(...))` registered last in `main.py` — must stay last.
- `bun` locally but `npm run build` in deploy scripts — both intentional.
- Mock serial + separate data dir on staging; amber staging banner.
- Camera: browser connects directly to ustreamer with proxy/snapshot fallback chain.

## Phase 0 — Baseline

- `git status` and `git diff` — review uncommitted working-tree changes **first**; they are the newest, least-reviewed code. Note anything half-finished.
- `git log --oneline -15` for recent context (recent commits show where bugs clustered: serial races, promote flow, LCD-modal hangs).

## Phase 1 — Repo hygiene

Known suspects — rule each in or out, then sweep for more:
- `_ul` (repo root) — 46-byte junk file containing a stray bash error message. Confirm and list for deletion.
- `Images/` — untracked screenshots (Dashboard/Control/Mesh). Referenced by any README/doc? If yes, commit and wire in; if no, delete or move out of the repo.
- `.dev-data/` — local dev was removed from the workflow; is this leftover?
- `.Codex/worktrees/`, `.Codex/scheduled_tasks.lock` — should be gitignored and/or deleted.
- Build artifacts: is `printforge/frontend/build/` or `.svelte-kit/` tracked in git? Generated output should be ignored, not committed.
- Sweep: `git ls-files` for tracked files that are generated, orphaned, or shipped by no deploy path; check `.gitignore` covers what it should.

## Phase 2 — Backend (`printforge/backend/app/`) — every file

Bug hunt, targeted at this project's real risk areas:
- **Serial/async**: blocking serial I/O on the event loop, missing `await`s, races between auto-connect, manual connect, and an active print job (this class of bug has already happened — see git log).
- **Lock and state hygiene**: error paths that leave locks held or the state machine stuck in PAUSED/PRINTING; G90/G91 absolute/relative tracking across pause/resume; resume restoring temperature and position correctly.
- **Safety guards**: jog/extrude/home rejected during active prints; thermal limits; `command_guard.py` coverage actually matching every dangerous endpoint in `api/*.py` — look for endpoints that bypass the guard.
- **Auth**: every mutating route behind the auth middleware; WebSocket auth enforced at connect; `octoprint_compat.py` endpoints held to the same standard.
- **Exceptions**: bare/broad `except` that swallows serial errors silently; failures that never surface to the frontend.
- **Python 3.9**: any `X | None` or other 3.10+ syntax in a module missing `from __future__ import annotations`.

Redundancy hunt:
- Endpoints in `api/*.py` called by neither `frontend/src/lib/api.ts` nor the slicer shim — dead API surface.
- Duplicated logic between routers and `controller.py`; the controller should own printer logic, routers should be thin.
- `serial/mock.py` vs `serial/mock_connection.py` — two mock implementations? Determine which one staging actually uses; flag the other for deletion.
- Dead config options in `config.py`, unused models in `storage/models.py`, unused helpers/imports anywhere.

## Phase 3 — Frontend (`printforge/frontend/src/`) — every component, route, store

- **Svelte 4 syntax that slipped in**: `on:click`, `export let`, `$:` reactives, `<slot />` — each one is a finding.
- **Unused code**: components never imported by any route or component (22 exist; docs claim 18 — something drifted), `api.ts` methods never called, stores/props/exports never read, CSS classes defined but unused.
- **Tailwind v3 validity**: classes that don't exist (e.g. `duration-250`), raw hex/named colors instead of `surface-*` tokens, any light-mode background in this dark-only app.
- **Consistency**: `.card` / `.btn-*` / `.input` usage, `focus-visible` rings and transitions on interactive elements, loading states and toast feedback on every printer action.

## Phase 4 — Scripts, config, docs

- The 8 files in `printforge/scripts/` — overlap and staleness. Does anything still reference go2rtc now that `ustreamer.service` exists? Does `install.sh` match current reality (staging setup, Node-from-tarball on armhf)? Is `sync-prod-config-to-staging.sh` still part of any documented flow?
- `requirements.txt` vs actual imports, both directions: packages installed but never imported, imports with no pinned package. Same for `package.json`.
- Docs accuracy — `AGENTS.md`, `AGENTS.md`, `SETUP.md`. Known drift to fix: component count (docs say 18, actual 22), skills count (docs say 5, actual 7), and the camera stack (older notes say go2rtc, current says ustreamer — verify which is truly running on the Pi and align every doc). Flag any instruction that no longer matches the code.
- `.pre-commit-config.yaml` — do the hooks actually pass on the current tree?

## Phase 5 — Pi filesystem audit (read-only SSH)

Target: `david1534@100.108.194.105`. Batch commands.
- **Inventory**: `/opt/printforge/` (deployed app), `~/printforge/` and `~/printforge-staging/` (data dirs), with `du -sh` per subdirectory.
- **Orphaned deploy files**: files under `/opt/printforge/` that no longer exist in the repo — repeated scp/rsync without `--delete` leaves ghosts of renamed or deleted modules, and a stale `.py` file can shadow or confuse imports. Diff the deployed tree against `git ls-files`. Include stale `__pycache__`/old frontend build hashes.
- **Install debris**: leftover `/tmp/*.sh` install scripts, Node tarballs, old venvs, and any pre-PrintForge OctoPrint remnants (`~/OctoPrint`, `~/oprint`, octoprint services).
- **Services**: `systemctl list-unit-files | grep -iE 'printforge|go2rtc|ustreamer|octoprint|webcam'` — anything stale, failed, or superseded. Is go2rtc still installed/enabled even though ustreamer took over? Is `/opt/printforge/go2rtc.yaml` still present?
- **Data growth**: oversized logs, timelapse frames never cleaned up, top-10 largest files in the data dirs. (User G-code files are the user's data — list them but deletion needs explicit per-file approval.)
- **Config drift**: diff the live systemd units (`/etc/systemd/system/printforge*.service`) against the copies in `printforge/scripts/`; diff production vs staging deployed trees for unexplained divergence.

## Phase 6 — Verification

Run and record results verbatim (failures are findings):
```bash
cd printforge/frontend && bun run build
cd printforge/backend && python -c "from app.main import app; print('OK')"
cd printforge/backend && python -m pytest tests/
```

## Report format

One report, ordered by severity:
1. **Bugs** — `file:line`, what breaks, concrete failure scenario, suggested fix.
2. **Security / auth gaps** — same format.
3. **Simplifications** — what's redundant or overbuilt, the simpler shape, and why behavior is preserved.
4. **Deletion manifest — repo** — table: path | what it is | evidence it's unused | risk if wrong.
5. **Deletion manifest — Pi** — same columns, kept separate because Pi deletions aren't recoverable from git.
6. **Polish** — naming, comments, logging, stale docs.
7. **Coverage** — files reviewed; anything skipped and why.

End the report with: **"Nothing has been changed or deleted. Tell me which sections to apply."**

## After approval (not during the review)

- Apply approved fixes → re-run Phase 6 verification → commit with conventional-commit messages → push → deploy to **staging** for the user to verify before any promote.
- Repo deletions: normal `git rm` in a commit (recoverable).
- Pi deletions: per-item approval only; prefer moving files into `~/trash-<date>/` on the Pi over `rm` so there's an undo window. Never touch the production service or data dirs while a print is active.
