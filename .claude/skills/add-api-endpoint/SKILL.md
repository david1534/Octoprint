---
name: add-api-endpoint
description: Add a new FastAPI REST endpoint to the PrintForge backend. Use when the user asks to create a new API route, endpoint, or backend feature. Handles router creation, models, and registration in main.py.
argument-hint: <endpoint-name> <description>
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Task
---

# PrintForge API Endpoint Builder

Add a new FastAPI endpoint following PrintForge's backend patterns.

## Steps

1. Parse `$ARGUMENTS`:
   - First word = endpoint name in **snake_case** (e.g. `filament`, `power`)
   - Remaining words = description
   - If missing, ask the user

2. **Research before writing.** Read these files:
   - `printforge/backend/app/main.py` -- router registration, middleware, lifespan
   - `printforge/backend/app/config.py` -- settings pattern
   - `printforge/backend/app/api/printer.py` -- reference router pattern
   - `printforge/backend/app/api/files.py` -- file upload pattern
   - `printforge/backend/app/printer/controller.py` -- PrinterController access
   - `printforge/backend/app/storage/models.py` -- database access pattern

3. **Create the router** at `printforge/backend/app/api/<name>.py`

4. **Register the router** in `printforge/backend/app/main.py`:
   ```python
   from app.api import new_router
   app.include_router(new_router.router)
   ```

5. **Add frontend API methods** in `printforge/frontend/src/lib/api.ts` if the user needs frontend access.

6. **Verify** the backend imports: `cd printforge/backend && python -c "from app.main import app; print('OK')"`

## Router Pattern

```python
"""<Description> API endpoints."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/<name>", tags=["<name>"])


class CreateItemRequest(BaseModel):
    name: str
    value: float


@router.get("/")
async def list_items():
    """List all items."""
    try:
        # Access PrinterController via import
        from app.printer.controller import printer_controller
        return {"items": []}
    except Exception as e:
        logger.error("Failed to list items: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_item(req: CreateItemRequest):
    """Create a new item."""
    try:
        return {"status": "ok"}
    except Exception as e:
        logger.error("Failed to create item: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
```

## Database Access Pattern (SQLite via aiosqlite)

```python
from app.storage.models import DataStore

store = DataStore()

# Settings
await store.get_setting("key", default="value")
await store.set_setting("key", "value")

# Print jobs
await store.get_print_jobs(limit=50, offset=0, status=None)
await store.create_print_job({...})

# Filament spools
await store.get_spools()
await store.create_spool({...})
await store.deduct_filament(spool_id, grams)
```

## PrinterController Access

The singleton `printer_controller` orchestrates all printer interaction:

```python
from app.printer.controller import printer_controller

# Connection
await printer_controller.connect(port, baud)
await printer_controller.disconnect()

# Commands
await printer_controller.send_command("G28")  # Raw G-code
await printer_controller.home(axes="XYZ")
await printer_controller.jog(x=0, y=0, z=10)
await printer_controller.set_temperature(tool=200, bed=60)

# State
state = printer_controller.get_state()  # Returns PrinterState
```

## Frontend API Client Pattern

Add to `printforge/frontend/src/lib/api.ts`:

```typescript
// Inside the api object:
async getItems(): Promise<Item[]> {
  return this.request<Item[]>('/api/items');
},

async createItem(data: { name: string; value: number }): Promise<{ status: string }> {
  return this.request('/api/items', {
    method: 'POST',
    body: JSON.stringify(data),
  });
},
```

The `request<T>()` method handles auth headers, timeouts, and error formatting.

## Authentication

All API routes are protected by the auth middleware in `app/middleware/auth.py`:
- `Authorization: Bearer <api-key>` header
- Or `?api_key=<key>` query parameter
- SHA-256 hashed comparison
- Health/system endpoints may be exempt

## Critical Rules

- **ALWAYS** register the router in `main.py`
- **ALWAYS** use `async def` for all route handlers
- **ALWAYS** add proper error handling with HTTPException
- **ALWAYS** add logging via `logger = logging.getLogger(__name__)`
- **ALWAYS** add type hints on all function parameters
- **NEVER** access serial port directly -- always go through `printer_controller`
- **NEVER** block the event loop -- use `await` for all I/O operations
- Use Pydantic `BaseModel` for request bodies
