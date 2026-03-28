# PrintForge Makefile

.PHONY: dev dev-backend dev-frontend build install clean \
        test test-backend test-cov lint lint-backend lint-frontend \
        format format-backend format-frontend check typecheck

# ── Development ──────────────────────────────────────────────────

dev-backend:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev

# Run both backend and frontend in parallel
dev:
	@echo "Starting backend and frontend..."
	@$(MAKE) dev-backend & $(MAKE) dev-frontend

# ── Build ────────────────────────────────────────────────────────

build:
	cd frontend && npm install && npm run build

# ── Testing ──────────────────────────────────────────────────────

test: test-backend

test-backend:
	cd backend && python -m pytest tests/ -v

test-cov:
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing

# ── Linting ──────────────────────────────────────────────────────

lint: lint-backend lint-frontend

lint-backend:
	cd backend && python -m ruff check app/ tests/

lint-frontend:
	cd frontend && npm run lint

# ── Formatting ───────────────────────────────────────────────────

format: format-backend format-frontend

format-backend:
	cd backend && python -m ruff format app/ tests/ && python -m ruff check --fix app/ tests/

format-frontend:
	cd frontend && npm run format

# ── Type checking ────────────────────────────────────────────────

typecheck:
	cd frontend && npm run check

check: lint typecheck test
	@echo "All checks passed!"

# ── Install (Raspberry Pi) ────────────────────────────────────────

install:
	bash scripts/install.sh

# ── Cleanup ──────────────────────────────────────────────────────

clean:
	rm -rf frontend/build frontend/.svelte-kit frontend/node_modules
	find backend -type d -name __pycache__ -exec rm -rf {} +
