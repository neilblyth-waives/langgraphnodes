.PHONY: help setup start stop logs clean test migrate shell db-shell redis-shell scale-test

help:
	@echo "DV360 Multi-Agent System - Make Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          - Initial setup (copy .env.example)"
	@echo ""
	@echo "Development:"
	@echo "  make start          - Start all services"
	@echo "  make stop           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - Follow logs for all services"
	@echo "  make logs-backend   - Follow backend logs only"
	@echo ""
	@echo "Database:"
	@echo "  make migrate        - Run database migrations"
	@echo "  make db-shell       - Open PostgreSQL shell"
	@echo "  make redis-shell    - Open Redis shell"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run all tests"
	@echo "  make test-unit      - Run unit tests"
	@echo "  make test-integration - Run integration tests"
	@echo "  make scale-test     - Start production mode with 5 replicas"
	@echo ""
	@echo "Utilities:"
	@echo "  make shell          - Open backend container shell"
	@echo "  make clean          - Stop and remove all containers/volumes"
	@echo "  make rebuild        - Rebuild and restart services"
	@echo "  make health         - Check service health"

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env file from .env.example"; \
		echo "⚠ Please edit .env with your credentials"; \
	else \
		echo "✓ .env file already exists"; \
	fi

start:
	cd infrastructure && docker-compose up -d
	@echo "✓ Services started"
	@echo "  API: http://localhost:8000"
	@echo "  Docs: http://localhost:8000/docs"
	@echo "  Health: http://localhost:8000/health"

stop:
	cd infrastructure && docker-compose down
	@echo "✓ Services stopped"

restart: stop start

logs:
	cd infrastructure && docker-compose logs -f

logs-backend:
	cd infrastructure && docker-compose logs -f backend

migrate:
	docker exec -it dv360-backend alembic upgrade head
	@echo "✓ Migrations complete"

db-shell:
	docker exec -it dv360-postgres psql -U dv360_user -d dv360_agents

redis-shell:
	docker exec -it dv360-redis redis-cli

shell:
	docker exec -it dv360-backend /bin/bash

test:
	docker exec -it dv360-backend pytest tests/

test-unit:
	docker exec -it dv360-backend pytest tests/unit/ -v

test-integration:
	docker exec -it dv360-backend pytest tests/integration/ -v

scale-test:
	cd infrastructure && docker-compose -f docker-compose.prod.yml up -d --scale backend=5
	@echo "✓ Production mode started with 5 backend replicas"
	@echo "  Load Balanced API: http://localhost:8000"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana: http://localhost:3001"

clean:
	cd infrastructure && docker-compose down -v
	@echo "✓ All containers and volumes removed"

rebuild:
	cd infrastructure && docker-compose down
	cd infrastructure && docker-compose build --no-cache
	cd infrastructure && docker-compose up -d
	@echo "✓ Services rebuilt and restarted"

health:
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health | python -m json.tool
