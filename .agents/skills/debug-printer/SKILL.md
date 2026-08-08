---
name: debug-printer
description: Debug printer communication, serial connection, or hardware control issues. Use when the user reports connection failures, commands not working, temperature reading errors, print failures, or any serial/hardware problems.
argument-hint: [symptom description]
allowed-tools: Read, Grep, Glob, Bash, Task
---

# PrintForge Printer Debugger

Systematically diagnose issues in the printer communication stack: serial connection -> protocol -> command queue -> controller -> API -> WebSocket -> frontend.

## Steps

1. Parse `$ARGUMENTS` for the symptom description. Common symptoms:
   - "Can't connect to printer"
   - "Commands not working"
   - "Temperature readings wrong"
   - "Print stops mid-way"
   - "WebSocket disconnecting"
   - If no arguments, ask the user to describe what's happening

2. **Run diagnostics in order** based on the symptom:

### Stage 1: Serial Connection

Check the physical connection layer:

- Read `printforge/backend/app/serial/connection.py`:
  - `SerialConnection` class with async pyserial
  - Default baud rate: 115200
  - Connection startup wait (printer resets on USB connect)
- Check if the serial port exists: look for `/dev/ttyUSB0`, `/dev/ttyACM0`, or `/dev/printforge` (udev symlink)
- Check udev rules in `printforge/scripts/udev/99-printforge.rules`
- Common issues: USB cable (data vs charge-only), permissions (`dialout` group), port busy

### Stage 2: Marlin Protocol

Check the communication protocol:

- Read `printforge/backend/app/serial/protocol.py`:
  - `MarlinProtocol` handles send-acknowledge flow
  - Waits for `ok` after each command
  - Parses temperature from response lines
  - Line numbering + checksums for print jobs
  - Resend recovery on `Resend:` responses
- Check timeout settings (how long before a command is considered failed)
- Check if firmware version is detected (M115 response)
- Common issues: baud rate mismatch, firmware not Marlin-compatible, USB 5V power issue

### Stage 3: Command Queue

Check command flow:

- Read `printforge/backend/app/serial/command_queue.py`:
  - Priority levels: SYSTEM > USER > PRINT
  - Queue overflow handling
  - Command timeout/retry logic
- Check if commands are getting queued but not sent
- Check if print commands are blocking user commands
- Common issues: queue full, command priority inversion, timeout too short

### Stage 4: Printer Controller

Check the orchestration layer:

- Read `printforge/backend/app/printer/controller.py`:
  - `PrinterController` singleton
  - State machine: disconnected -> idle -> printing -> paused -> finishing
  - Temperature monitoring setup (M155 auto-report)
  - Safety monitor integration
  - Timelapse trigger on layer change
- Check state transitions (is the printer stuck in a state?)
- Common issues: state not updating, safety monitor false positive, temperature callback failure

### Stage 5: Safety Monitor

Check safety systems:

- Read `printforge/backend/app/serial/safety.py`:
  - Thermal runaway detection
  - Serial watchdog (detects communication loss)
  - Auto-pause on safety alert
- Check if safety alerts are being triggered incorrectly
- Common issues: thermal runaway false alarm during fast heating, watchdog timeout too aggressive

### Stage 6: WebSocket / Frontend

Check the real-time communication:

- Read `printforge/backend/app/api/websocket.py`:
  - `ConnectionManager` broadcasts state at 1Hz
  - Terminal line relay
  - Client message handling
- Read `printforge/frontend/src/lib/websocket.ts`:
  - Auto-reconnect with exponential backoff (1s to 30s)
  - API key in query parameter
- Check if state updates are reaching the frontend
- Common issues: WebSocket auth failure, CORS, proxy misconfiguration

### Stage 7: Camera (if applicable)

- Read `printforge/backend/app/main.py` for camera proxy endpoints
- Read `printforge/frontend/src/lib/components/CameraFeed.svelte`:
  - Three modes: snapshot polling, MJPEG direct, MJPEG proxied
  - Auto-retry with fallback between modes
- Check ustreamer service: `systemctl status ustreamer`

3. **Report findings** as a structured diagnostic:

```
## Printer Diagnostic Report

### Serial Connection: OK / ISSUE
- Port: /dev/ttyUSB0 (or not found)
- Baud: 115200
- Permissions: OK / needs dialout group

### Protocol: OK / ISSUE
- Firmware detected: yes/no (M115)
- Send-acknowledge: working/failing
- Temperature parsing: OK/broken

### Command Queue: OK / ISSUE
- Queue depth: X
- Priority handling: OK

### Controller State: OK / ISSUE
- Current state: idle/printing/error
- State transitions: normal/stuck

### Safety: OK / ISSUE
- Thermal runaway: not triggered / triggered
- Watchdog: OK / timeout

### WebSocket: OK / ISSUE
- Connected: yes/no
- State broadcast: working/failing
- Auth: OK/failing

### Root Cause: [summary]
### Recommended Fix: [specific action]
```

## Common Issues & Fixes

| Symptom | Likely Cause | Fix |
|---|---|---|
| "Connection refused" | Wrong port/baud | Check `ls /dev/tty*`, try 115200 baud |
| "Permission denied" | User not in dialout | `sudo usermod -aG dialout $USER` |
| Commands ignored | Printer not idle | Check `printer_controller.state.status` |
| Temp reads 0 | M155 not set | Check auto-temp-report setup in controller |
| Print stops randomly | USB power issue | Tape over USB pin 1 (see USB_POWER_WARNING.md) |
| WebSocket drops | Auth key mismatch | Check API key in localStorage vs backend |
| "Thermal runaway" | Fast heating + tight threshold | Adjust safety thresholds in config |
| Camera black | ustreamer not running | `systemctl status ustreamer` |

## Critical Rules

- **DO NOT modify code** during debugging -- only read and diagnose
- **DO NOT send G-code commands** during debugging unless the user explicitly asks
- **ALWAYS** check the USB power warning for hardware-related issues (`docs/USB_POWER_WARNING.md`)
- Present findings objectively with specific file paths and line numbers
- Always check the simplest cause first (cable > permissions > configuration > code bug)
