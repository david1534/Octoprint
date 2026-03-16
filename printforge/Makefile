# PrintForge Makefile

.PHONY: dev-backend dev-frontend build install clean

# Development
dev-backend:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev

# Build frontend for production
build:
	cd frontend && npm install && npm run build

# Install on Raspberry Pi
install:
	bash scripts/install.sh

# Clean build artifacts
clean:
	rm -rf frontend/build frontend/.svelte-kit frontend/node_modules
	find backend -type d -name __pycache__ -exec rm -rf {} +
