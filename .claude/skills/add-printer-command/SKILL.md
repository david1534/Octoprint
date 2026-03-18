---
name: add-printer-command
description: Add a new printer control command (G-code) to PrintForge across the full stack -- backend API, frontend API client, and UI control. Use when the user wants to add a new printer action, G-code command, or hardware control feature.
argument-hint: <command-name> <description>
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Task
---

# PrintForge Printer Command Builder

Add a new printer command that flows through the full stack: backend API endpoint -> frontend API method -> UI button/control.

## Steps

1. Parse `$ARGUMENTS`:
   - First word = command name in **kebab-case** (e.g. `auto-tune-pid`, `mesh-level`)
   - Remaining words = description
   - If missing, ask the user

2. **Research before writing.** Read these files to understand the command flow:
   - `printforge/backend/app/printer/controller.py` -- existing commands (home, jog, setTemp, etc.)
   - `printforge/backend/app/serial/protocol.py` -- how commands are sent to the printer
   - `printforge/backend/app/serial/command_queue.py` -- command priority system
   - `printforge/backend/app/api/printer.py` -- existing API endpoints for printer commands
   - `printforge/frontend/src/lib/api.ts` -- frontend API methods
   - `printforge/frontend/src/routes/control/+page.svelte` -- control UI

3. **Add the controller method** in `printforge/backend/app/printer/controller.py`:
   ```python
   async def new_command(self, param1: float, param2: str = "default"):
       """Description of what this command does."""
       if not self.state.status == "idle":
           raise ValueError("Printer must be idle")
       gcode = f"G28 X{param1}"
       await self.protocol.send_command(gcode, priority="user")
       logger.info("Sent new_command: %s", gcode)
   ```

4. **Add the API endpoint** in `printforge/backend/app/api/printer.py`:
   ```python
   @router.post("/new-command")
   async def new_command(req: NewCommandRequest):
       try:
           await printer_controller.new_command(req.param1, req.param2)
           return {"status": "ok"}
       except Exception as e:
           raise HTTPException(status_code=500, detail=str(e))
   ```

5. **Add the frontend API method** in `printforge/frontend/src/lib/api.ts`:
   ```typescript
   async newCommand(param1: number, param2?: string): Promise<{ status: string }> {
     return this.request('/api/printer/new-command', {
       method: 'POST',
       body: JSON.stringify({ param1, param2 }),
     });
   },
   ```

6. **Add the UI control** in the appropriate page (usually `/control` or dashboard).

7. **Verify** the backend: `cd printforge/backend && python -c "from app.api.printer import router; print('OK')"`

## Command Priority System

Commands go through a priority queue:
```
SYSTEM (highest) -- emergency stop, safety commands
USER             -- manual commands from UI
PRINT (lowest)   -- G-code file lines during printing
```

Use `priority="user"` for UI-triggered commands, `priority="system"` for safety-critical ones.

## Common G-code Reference

| G-code | Purpose | Example |
|---|---|---|
| `G28` | Home axes | `G28 X Y Z` or `G28` (all) |
| `G1` | Linear move | `G1 X100 Y100 Z10 F3000` |
| `G92` | Set position | `G92 E0` (reset extruder) |
| `M104` | Set hotend temp | `M104 S200` |
| `M140` | Set bed temp | `M140 S60` |
| `M106` | Set fan speed | `M106 S255` (0-255) |
| `M112` | Emergency stop | `M112` |
| `M155` | Auto temp report | `M155 S1` (every 1s) |
| `G29` | Auto bed level | `G29` |
| `M420` | Bed mesh on/off | `M420 S1` (enable) |
| `M503` | Report settings | `M503` |

## Serial Protocol Pattern

The `MarlinProtocol` handles:
- Send-acknowledge flow (waits for `ok` from printer)
- Line numbering and checksums (for print G-code)
- Resend recovery on communication errors
- Temperature parsing from `ok T:200 /200 B:60 /60` responses

Commands sent via `protocol.send_command()` return after the printer acknowledges.

## UI Button Pattern

```svelte
<button
  class="btn-primary inline-flex items-center justify-center gap-2 min-h-[44px]"
  onclick={handleCommand}
  disabled={!!loading || !connected}
>
  {#if loading === 'command'}
    <span class="animate-spin rounded-full h-4 w-4 border-2 border-accent/30 border-t-white"></span>
  {:else}
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="..." />
    </svg>
  {/if}
  Command Label
</button>
```

## Critical Rules

- **ALWAYS** check printer state before sending commands (connected? idle? printing?)
- **ALWAYS** add loading states to UI buttons that trigger commands
- **ALWAYS** show toast feedback on success/failure
- **ALWAYS** add `disabled` state when loading or disconnected
- **NEVER** send raw G-code directly from the frontend -- always go through the API
- **NEVER** add commands that could damage the printer without a confirmation dialog
- Safety-critical commands (anything involving motors/heaters) should use `confirmAction()` first
- Use `min-h-[44px]` on touch-target buttons for mobile usability
