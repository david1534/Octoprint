# Temperature Fix — Deploy Instructions

## What was wrong

Temperature readings (nozzle + bed) were stuck at 0 because the printer's
auto-reported temperature data was never being read during idle periods.
The serial port was only read when a command was actively being sent, so
M155 auto-reports piled up unread in the buffer.

## What changed

Two files in `printforge/backend/app/serial/`:

- **protocol.py** — Added `drain_unsolicited()` to read buffered serial data
  (temperature reports, position updates) between commands
- **command_queue.py** — Calls `drain_unsolicited()` during idle periods so
  temperature auto-reports are processed in near-real-time (~1-2s)

## How to deploy

### Option A: Full deploy (recommended)

```bash
cd printforge
SKIP_CHECKS=true bash scripts/deploy.sh
```

This uploads everything, rebuilds the frontend on the Pi, and restarts services.

### Option B: Quick deploy (backend-only, faster)

Since only 2 backend files changed:

```bash
scp printforge/backend/app/serial/protocol.py \
    printforge/backend/app/serial/command_queue.py \
    david1534@100.108.194.105:/opt/printforge/app/serial/

ssh david1534@100.108.194.105 "sudo systemctl restart printforge"
```

### Verify it worked

1. Open PrintForge at `http://100.108.194.105:8000`
2. Connect to the printer
3. Temperature gauges should show room temp (~20-25C) within 2-3 seconds
4. The temperature graph should start plotting live data immediately

### If something goes wrong

Check the service logs:

```bash
ssh david1534@100.108.194.105 "journalctl -u printforge -n 30 --no-pager"
```

Rollback by reverting the commit:

```bash
git revert HEAD
# Then redeploy
```
