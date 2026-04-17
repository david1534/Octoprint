#!/usr/bin/env bash
#
# Sync filament_spools + settings from production → staging.
#
# Staging has its own DB so a fresh-cut staging never sees the real spool
# inventory or the user's saved preferences. This script copies only the
# config tables (spools, settings) and leaves print history / jobs alone —
# staging's print history is simulated, so it should stay isolated.
#
# Run from anywhere on the laptop; SSHes to the Pi and does the work there.
# Run with --dry-run to preview what would change without writing.
#
set -euo pipefail

PI_HOST="${PI_HOST:-david1534@100.108.194.105}"
PROD_DB="/home/david1534/printforge/data/printforge.db"
STAGE_DB="/home/david1534/printforge-staging/data/printforge.db"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=1
fi

echo "→ Syncing prod config to staging on ${PI_HOST}"
echo "  prod:    ${PROD_DB}"
echo "  staging: ${STAGE_DB}"
echo "  dry run: ${DRY_RUN}"
echo

ssh "${PI_HOST}" "DRY_RUN=${DRY_RUN} PROD_DB='${PROD_DB}' STAGE_DB='${STAGE_DB}' python3 - <<'PY'
import os
import shutil
import sqlite3
import sys
from datetime import datetime

PROD = os.environ['PROD_DB']
STAGE = os.environ['STAGE_DB']
DRY = os.environ['DRY_RUN'] == '1'

if not os.path.exists(PROD):
    print(f'ERROR: prod DB missing at {PROD}', file=sys.stderr)
    sys.exit(1)
if not os.path.exists(STAGE):
    print(f'ERROR: staging DB missing at {STAGE} — start the staging service at least once to create it', file=sys.stderr)
    sys.exit(1)

# Backup staging DB before touching it.
ts = datetime.now().strftime('%Y%m%d-%H%M%S')
backup = f'{STAGE}.bak.{ts}'
if not DRY:
    shutil.copy2(STAGE, backup)
    print(f'✓ staging backup → {backup}')

prod = sqlite3.connect(PROD)
stage = sqlite3.connect(STAGE)
prod.row_factory = sqlite3.Row
stage.row_factory = sqlite3.Row

def columns(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]

def sync_table(table, key_cols):
    prod_cols = columns(prod, table)
    stage_cols = columns(stage, table)
    if not stage_cols:
        print(f'  skip {table}: not present in staging DB')
        return
    shared = [c for c in prod_cols if c in stage_cols]
    prod_rows = prod.execute(f'SELECT {\",\".join(shared)} FROM {table}').fetchall()
    print(f'  {table}: {len(prod_rows)} rows in prod, {len(shared)} shared columns')
    if DRY:
        for r in prod_rows:
            print(f'    would sync: {dict(r)}')
        return
    # Wipe staging table, then insert prod rows. Safe because we only sync
    # config tables (spools, settings) — no print history is touched.
    stage.execute(f'DELETE FROM {table}')
    placeholders = ','.join(['?'] * len(shared))
    stage.executemany(
        f'INSERT INTO {table} ({\",\".join(shared)}) VALUES ({placeholders})',
        [tuple(r[c] for c in shared) for r in prod_rows],
    )
    print(f'  ✓ {table}: replaced with {len(prod_rows)} rows from prod')

print('→ filament_spools')
sync_table('filament_spools', ['id'])
print('→ settings')
sync_table('settings', ['key'])

if not DRY:
    stage.commit()
    print('✓ committed to staging DB')
else:
    print('(dry run — nothing written)')

prod.close()
stage.close()
PY"

echo
echo "→ Restart staging so it picks up new settings/spools"
ssh "${PI_HOST}" "sudo systemctl restart printforge-staging"
sleep 2
ssh "${PI_HOST}" "systemctl is-active printforge-staging"
echo
echo "Done. Verify at http://100.108.194.105:8001"
