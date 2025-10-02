.PHONY: help install dev-setup start stop restart clean test db-up db-down db-reset migrate seed logs shell format lint

# Variables
PYTHON = python3
VENV = venv
VENV_BIN = $(VENV)/bin
DOCKER_COMPOSE = docker-compose

# Colors for output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

help: ## Show this help message
	@echo "$(GREEN)OneDocs Auth Service - Makefile Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Install dependencies
	@echo "$(GREEN)Installing dependencies...$(NC)"
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements.txt
	@echo "$(GREEN)Dependencies installed successfully!$(NC)"

dev-setup: install db-up migrate seed ## Complete development setup
	@echo "$(GREEN)Development environment ready!$(NC)"
	@echo "Run 'make start' to start the application"

start: ## Start the application
	@echo "$(GREEN)🚀 Starting OneDocs Auth Service...$(NC)"
	@if ! docker ps | grep -q onedocs-auth-db; then \
		echo "$(YELLOW)⚠️  PostgreSQL not running. Starting...$(NC)"; \
		$(DOCKER_COMPOSE) up -d; \
		echo "$(YELLOW)⏳ Waiting for PostgreSQL...$(NC)"; \
		sleep 3; \
	fi
	@echo "$(GREEN)🌐 Starting FastAPI server...$(NC)"
	@echo "$(GREEN)📚 API Documentation: http://localhost:8000/docs$(NC)"
	@echo "$(GREEN)📖 ReDoc: http://localhost:8000/redoc$(NC)"
	@echo ""
	$(VENV_BIN)/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

stop: ## Stop all services
	@echo "$(YELLOW)Stopping services...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)Services stopped!$(NC)"

restart: stop start ## Restart all services

db-up: ## Start PostgreSQL database
	@echo "$(GREEN)Starting PostgreSQL database...$(NC)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(YELLOW)Waiting for PostgreSQL to be ready...$(NC)"
	@sleep 5
	@echo "$(GREEN)Database is ready!$(NC)"
	@echo "$(GREEN)PgAdmin: http://localhost:5050$(NC)"

db-down: ## Stop PostgreSQL database
	@echo "$(YELLOW)Stopping PostgreSQL database...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)Database stopped!$(NC)"

db-reset: ## Reset database (WARNING: deletes all data)
	@echo "$(RED)⚠️  WARNING: This will delete all data!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(DOCKER_COMPOSE) down -v; \
		echo "$(GREEN)Database reset complete!$(NC)"; \
		$(MAKE) db-up; \
		$(MAKE) migrate; \
	else \
		echo "$(YELLOW)Cancelled.$(NC)"; \
	fi

migrate: ## Run database migrations
	@echo "$(GREEN)Running database migrations...$(NC)"
	$(VENV_BIN)/alembic upgrade head
	@echo "$(GREEN)Migrations complete!$(NC)"

migrate-create: ## Create a new migration (use msg="description")
	@echo "$(GREEN)Creating new migration...$(NC)"
	$(VENV_BIN)/alembic revision --autogenerate -m "$(msg)"
	@echo "$(GREEN)Migration created!$(NC)"

migrate-rollback: ## Rollback last migration
	@echo "$(YELLOW)Rolling back migration...$(NC)"
	$(VENV_BIN)/alembic downgrade -1
	@echo "$(GREEN)Rollback complete!$(NC)"

seed: ## Seed database with initial data
	@echo "$(GREEN)Seeding database...$(NC)"
	@if [ -f "seed.sh" ]; then \
		bash seed.sh; \
	else \
		echo "$(YELLOW)No seed.sh file found$(NC)"; \
	fi
	@echo "$(GREEN)Database seeded!$(NC)"

test: ## Run tests
	@echo "$(GREEN)Running tests...$(NC)"
	$(VENV_BIN)/pytest -v
	@echo "$(GREEN)Tests complete!$(NC)"

test-cov: ## Run tests with coverage
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	$(VENV_BIN)/pytest --cov=app --cov-report=html --cov-report=term
	@echo "$(GREEN)Coverage report generated in htmlcov/$(NC)"

logs: ## View application logs
	$(DOCKER_COMPOSE) logs -f

shell: ## Open Python shell with app context
	$(VENV_BIN)/python -i -c "from app.main import app; from app.db.session import SessionLocal; db = SessionLocal()"

db-shell: ## Open database shell
	docker exec -it onedocs-auth-db psql -U $$(grep POSTGRES_USER .env | cut -d '=' -f2) -d $$(grep POSTGRES_DB .env | cut -d '=' -f2)

format: ## Format code with black
	@echo "$(GREEN)Formatting code...$(NC)"
	$(VENV_BIN)/black app tests
	@echo "$(GREEN)Code formatted!$(NC)"

lint: ## Lint code
	@echo "$(GREEN)Linting code...$(NC)"
	$(VENV_BIN)/flake8 app tests
	@echo "$(GREEN)Linting complete!$(NC)"

clean: ## Clean up temporary files
	@echo "$(YELLOW)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	rm -rf htmlcov/ .coverage
	@echo "$(GREEN)Cleanup complete!$(NC)"

clean-all: clean ## Clean everything including venv and database
	@echo "$(RED)⚠️  WARNING: This will delete venv and database!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf $(VENV); \
		$(DOCKER_COMPOSE) down -v; \
		echo "$(GREEN)Deep cleanup complete!$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled.$(NC)"; \
	fi

.DEFAULT_GOAL := help
