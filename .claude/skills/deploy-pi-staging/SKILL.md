---
name: deploy-pi-staging
description: Deploy in-progress PrintForge changes to the Pi's STAGING instance (port 8001, mock-serial mode). Safe during active prints — never touches production or the real printer. Use when the user says "deploy to staging", "test on staging", "push to staging", or wants to preview a change on the Pi without affecting their current print.
argument-hint: [optional: backend | frontend | full (default)]
allowed-tools: Bash, Read, Glob
---

# Deploy to PrintForge Staging (port 8001)

Deploy WIP code to the Pi's staging service. This is the "try it on the Pi without breaking production" path.

## When to use this skill

- User says "deploy to staging" / "push to staging" / "test on the Pi"
- A print is in progress and you still need to validate a change on real hardware paths (without touching the printer itself — staging runs in mock-serial mode)
- Any feature where the user wants to preview before promoting to production

## When NOT to use

- User says "deploy" (unqualified) → use `deploy-pi` (production)
- User says "promote" / "apply to production" → use `promote-staging.sh` (described below)

## Pre-flight

1. Verify Pi is reachable:
   ```bash
   ssh -o ConnectTimeout=5 david1534@100.108.194.105 "echo OK"
   ```

2. Verify staging service exists (one-time setup was done):
   ```bash
   ssh david1534@100.108.194.105 "systemctl list-unit-files | grep printforge-staging"
   ```
   If it returns nothing, the user needs to run `install-staging.sh` on the Pi first:
   ```bash
   scp printforge/scripts/{install-staging.sh,printforge-staging.service} david1534@100.108.194.105:/tmp/
   ssh david1534@100.108.194.105 "bash /tmp/install-staging.sh"
   ```

## Deploy

From the repo root:

```bash
bash printforge/scripts/deploy-staging.sh $ARGUMENTS
```

Where `$ARGUMENTS` is one of: `backend`, `frontend`, `full` (default). The script handles:
- Local frontend build (if frontend in scope)
- SCP to `/opt/printforge-staging/`
- Permission fix (OneDrive strips write bits)
- Restart `printforge-staging.service`
- Smoke check — prints the systemd status

## Verify

After the script exits, confirm by:

```bash
curl -s http://100.108.194.105:8001/api/system/health | python -m json.tool
```

Expected: `"environment": "staging"`, `"mockSerial": true`.

The staging UI is at `http://100.108.194.105:8001` — the amber "Staging environment · simulated printer" banner confirms you're not on production.

## Promoting staging → production

Once the user has verified the feature works on staging, apply it to production:

```bash
bash printforge/scripts/promote-staging.sh
```

The script refuses by default if a print is in progress. Pass `--force` only if the user explicitly asks to interrupt the print.

## Success Criteria

1. `systemctl is-active printforge-staging` → `active`
2. `http://100.108.194.105:8001/api/system/health` returns JSON with `environment: staging`
3. No `SyntaxError`, `ModuleNotFoundError`, or `CRITICAL` in `journalctl -u printforge-staging -n 30 --no-pager`

Report the URL to the user once staging is live.
