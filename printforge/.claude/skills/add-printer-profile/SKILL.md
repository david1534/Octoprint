# Skill: Add Printer Profile

Guide for adding or modifying printer-specific profiles (build volume, start/end G-code, temperature limits).

## When to Use
User wants to configure PrintForge for a specific printer model (not just Ender 3 S1 Pro).

## Where Settings Live

### Backend Config
- `backend/app/config.py` — Global settings via env vars (`PRINTFORGE_*`)
  - `max_hotend_temp` (default 260) — safety cutoff
  - `max_bed_temp` (default 110) — safety cutoff
  - `serial_port`, `serial_baudrate`

### Database Settings (runtime, user-configurable)
- `backend/app/storage/models.py` — `get_setting()` / `set_setting()`
- Accessed via `backend/app/api/settings.py` — `GET/PUT /api/settings/`
- Key settings:
  - `start_gcode` — Template with `{nozzle_temp}` and `{bed_temp}` variables
  - `end_gcode` — Post-print cleanup sequence
  - `auto_connect_port` — Serial port for auto-connect
  - `auto_connect_baudrate` — Baud rate
  - `printer_name` — Display name
  - `build_volume_x/y/z` — Build volume in mm
  - `nozzle_diameter` — Nozzle size in mm

### Start/End G-code Templates
- `backend/app/printer/controller.py` — `DEFAULT_START_GCODE` and `DEFAULT_END_GCODE`
- These are Ender 3 defaults with G29 auto bed leveling
- Template variables: `{nozzle_temp}`, `{bed_temp}` — substituted from file metadata
- Modified via Settings page in the frontend

### Safety Limits
- `backend/app/serial/safety.py` — `SafetyMonitor`
  - Thermal runaway detection thresholds
  - Absolute max temp limits (from config.py)
  - Serial watchdog timeout

## Adding a New Printer Profile

### 1. Adjust Start G-code
Common differences between printers:
- **ABL probe**: G29 (Ender 3 S1), G29 P1 (UBL), or remove entirely (no probe)
- **Homing**: G28 (all), G28 X Y (partial)
- **Heating order**: Heat bed first (large thermal mass), then nozzle
- **Purge line**: Adjust X/Y coordinates for bed size

### 2. Adjust End G-code
- **Present print**: `G1 X0 Y{build_y}` — move bed forward (adjust Y for bed size)
- **Z lift**: Adjust based on build height

### 3. Adjust Safety Limits
In `config.py` or via env vars:
- All-metal hotend: `max_hotend_temp=300`
- PETG/ABS: `max_bed_temp=120`

### 4. Adjust Serial Settings
- Most Marlin printers: 115200 baud
- Some Klipper setups: 250000 baud
- USB cable: `/dev/ttyUSB0` or `/dev/ttyACM0`

### 5. Frontend Settings Page
- `frontend/src/routes/settings/+page.svelte` — All settings UI
- Build volume, nozzle diameter, printer name all editable
- Start/end G-code has a multi-line text editor

## Common Printer Profiles

| Printer | Hotend Max | Bed Max | ABL | Baud | Notes |
|---------|-----------|---------|-----|------|-------|
| Ender 3 S1 Pro | 300 | 110 | G29 (CR Touch) | 115200 | Default profile |
| Ender 3 V2 | 260 | 100 | None (manual mesh) | 115200 | Remove G29 from start |
| Prusa MK3S+ | 280 | 120 | G29 (PINDA) | 115200 | Different purge line coords |
| Voron 2.4 | 300 | 120 | G29 (Klicky/TAP) | 250000 | Klipper firmware |
| Artillery Sidewinder | 240 | 130 | G29 (BLTouch) | 115200 | Large bed (300x300) |
