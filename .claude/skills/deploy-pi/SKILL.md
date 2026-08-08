---
name: deploy-pi
description: Deploy PrintForge changes to the Raspberry Pi. Use after any backend or frontend code change to build, transfer, restart, and verify the service. Handles frontend build, SCP, pip install, systemd restart, and log verification.
argument-hint: [optional: what changed — backend/frontend/deps]
allowed-tools: Bash, Read, Glob
---

# Deploy PrintForge to Raspberry Pi

Deploy the current working directory to the Pi at `david1534@100.108.194.105` via Tailscale.

## Pre-flight Checks

1. **Verify clean git state** — confirm all changes are committed and pushed:
   ```bash
   git status
   git log --oneline -3
   ```
   If there are uncommitted changes, stop and tell the user. Deployment always follows a commit.

2. **Verify Pi is reachable**:
   ```bash
   ssh -o ConnectTimeout=5 david1534@100.108.194.105 "echo OK"
   ```
   If unreachable, stop and tell the user to check Tailscale (`tailscale status`).

## Determine What Changed

Parse `$ARGUMENTS` to decide the deployment scope:
- **"backend"** or no argument → deploy backend only
- **"frontend"** → deploy frontend only
- **"deps"** or **"requirements"** → deploy backend + run pip install
- **"full"** or **"both"** → deploy frontend + backend

When in doubt, deploy both (full deploy). It's always safe to over-deploy.

## Step 1: Build Frontend (if frontend changed)

Build locally first to catch errors before touching the Pi:

```bash
cd printforge/frontend && bun run build
```

If the build fails, stop immediately. Do not deploy a broken build. Fix the error first.

## Step 2: SCP Backend

```bash
scp -r printforge/backend/app david1534@100.108.194.105:/opt/printforge/
```

**Critical**: OneDrive can strip write permissions on directories (dr-x------). After SCP, always fix permissions:

```bash
ssh david1534@100.108.194.105 "chmod -R u+w /opt/printforge/app"
```

## Step 3: SCP Frontend Build (if frontend changed)

```bash
scp -r printforge/frontend/build david1534@100.108.194.105:/opt/printforge/frontend/
ssh david1534@100.108.194.105 "chmod -R u+w /opt/printforge/frontend/build"
```

## Step 4: Install New Dependencies (if deps changed)

Only run this if `requirements.txt` was modified:

```bash
ssh david1534@100.108.194.105 "~/printforge/venv/bin/pip install -r /opt/printforge/requirements.txt"
```

## Step 5: Python 3.9 Compatibility Check

Before restarting, verify the backend imports cleanly on the Pi. Python 3.9 does **not** support `X | None` union syntax — it requires `from __future__ import annotations`.

```bash
ssh david1534@100.108.194.105 "cd /opt/printforge && ~/printforge/venv/bin/python -c \"from app.main import app; print('Import OK')\""
```

If this fails with a `SyntaxError`, do NOT restart the service yet. Fix the syntax error first (add `from __future__ import annotations` to the offending file), redeploy, then verify again.

## Step 6: Restart Service

```bash
ssh david1534@100.108.194.105 "sudo systemctl restart printforge"
```

Wait 3 seconds for startup:

```bash
sleep 3
```

## Step 7: Verify Service is Running

```bash
ssh david1534@100.108.194.105 "sudo systemctl is-active printforge"
```

Expected output: `active`

If output is `failed` or `activating`, check logs immediately (Step 8).

## Step 8: Check Logs

```bash
ssh david1534@100.108.194.105 "journalctl -u printforge -n 50 --no-pager"
```

Look for:
- `Started PrintForge` — good, service is up
- `SyntaxError` — Python 3.9 compat issue, fix before proceeding
- `ModuleNotFoundError` — missing dependency, run pip install
- `Address already in use` — port conflict, check if old process is still running
- `Serial connection established` — printer connected (only if printer is powered on)
- Any `ERROR` or `CRITICAL` lines — investigate before declaring success

## Step 9: Smoke Test

```bash
curl -s http://100.108.194.105:8000/api/printer/status | python3 -m json.tool
```

Expected: JSON response with `status` field (e.g. `"disconnected"` or `"idle"`).

If `curl` times out or returns HTML (the SvelteKit 404 page), the backend is not serving the API correctly — check the log for startup errors.

## Common Failures & Fixes

| Symptom | Cause | Fix |
|---|---|---|
| `SyntaxError: unsupported syntax` | `X \| None` without `__future__` | Add `from __future__ import annotations` at top of file |
| `Permission denied` on SCP dir | OneDrive strips write bits | Run `chmod -R u+w` after SCP |
| `ModuleNotFoundError` | New dep not installed | Run `pip install -r requirements.txt` on Pi |
| Service stuck `activating` | Slow serial startup | Wait 5s, check again |
| `Address already in use` | Old process lingering | `sudo systemctl kill printforge && sudo systemctl start printforge` |
| Frontend shows old version | Build cache | Run `bun run build` fresh, verify build/ dir timestamp |
| `curl` returns SvelteKit 404 | Static mount before API routes | Check `main.py` — `app.mount("/", ...)` must be last |

## Environment Variable Reference

These are set in `/etc/systemd/system/printforge.service`. Do not change them during deploy:

- `PRINTFORGE_SERIAL_PORT` — default `/dev/ttyUSB0` (udev symlink: `/dev/printforge`)
- `PRINTFORGE_GCODE_DIR` — default `~/printforge/gcodes`
- `PRINTFORGE_DATA_DIR` — default `~/printforge/data`
- `PRINTFORGE_CAMERA_URL` — default `http://localhost:8080`
- `PRINTFORGE_LOG_LEVEL` — default `INFO`

## Success Criteria

Deployment is complete when ALL of these are true:
1. `systemctl is-active printforge` → `active`
2. No `SyntaxError`, `ModuleNotFoundError`, or `CRITICAL` in last 50 log lines
3. `curl http://100.108.194.105:8000/api/printer/status` returns valid JSON

Report the last 5 log lines and the curl response to the user as confirmation.
