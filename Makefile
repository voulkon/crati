.PHONY: help quickstart dev prod clean test lint format migrate shell logs

# Default target
help:
	@echo "Crati - Development Commands"
	@echo ""
	@echo "Setup & Start:"
	@echo "  make quickstart    Start with sample data (recommended for contributors)"
	@echo "  make dev           Start full local development environment"
	@echo "  make dev-no-db     Start without database (use remote DB)"
	@echo "  make prod          Start production environment"
	@echo ""
	@echo "Development:"
	@echo "  make test          Run all tests"
	@echo "  make lint          Check code style"
	@echo "  make format        Format code"
	@echo "  make migrate       Run database migrations"
	@echo "  make shell         Open Django shell"
	@echo "  make logs          View backend logs"
	@echo ""
	@echo "Data:"
	@echo "  make sample-data   Generate sample data"
	@echo "  make reset-db      Reset database with sample data"
	@echo ""
	@echo "Cleanup:"
	@echo "  make stop          Stop all services"
	@echo "  make clean         Remove containers and volumes"
	@echo "  make deep-clean    Remove all Docker artifacts"

# ───────────────────────── Setup & Start ─────────────────────────

quickstart:
	@echo "🚀 Starting Crati with sample data..."
	docker-compose -f docker/docker-compose.quickstart.yml up -d
	@echo ""
	@echo "✅ Crati is running!"
	@echo "   Frontend:  http://localhost"
	@echo "   Backend:   http://localhost/api"
	@echo "   RabbitMQ:  http://localhost:15672 (crati_user/crati_password)"
	@echo "   OpenSearch: http://localhost:9200"
	@echo ""
	@echo "📊 View logs: make logs"
	@echo "🛑 Stop:      make stop"

dev:
	@echo "🚀 Starting full development environment..."
	docker-compose -f docker/docker-compose.yml up -d

dev-no-db:
	@echo "🚀 Starting without database..."
	docker-compose -f docker/docker-compose-no-db.yml up -d

prod:
	@echo "🚀 Starting production environment..."
	docker-compose -f docker/docker-compose.prod.yml up -d

# ───────────────────────── Development ─────────────────────────

test:
	@echo "🧪 Running tests..."
	docker-compose -f docker/docker-compose.quickstart.yml exec backend pytest -v

test-coverage:
	@echo "🧪 Running tests with coverage..."
	docker-compose -f docker/docker-compose.quickstart.yml exec backend pytest --cov --cov-report=html

lint:
	@echo "🔍 Checking code style..."
	docker-compose -f docker/docker-compose.quickstart.yml exec backend black --check .
	docker-compose -f docker/docker-compose.quickstart.yml exec backend flake8
	docker-compose -f docker/docker-compose.quickstart.yml exec backend mypy .

format:
	@echo "✨ Formatting code..."
	docker-compose -f docker/docker-compose.quickstart.yml exec backend black .
	docker-compose -f docker/docker-compose.quickstart.yml exec backend isort .

migrate:
	@echo "🔄 Running migrations..."
	docker-compose -f docker/docker-compose.quickstart.yml exec backend python manage.py makemigrations
	docker-compose -f docker/docker-compose.quickstart.yml exec backend python manage.py migrate

shell:
	@echo "🐚 Opening Django shell..."
	docker-compose -f docker/docker-compose.quickstart.yml exec backend python manage.py shell

db-shell:
	@echo "🐚 Opening PostgreSQL shell..."
	docker-compose -f docker/docker-compose.quickstart.yml exec db psql -U crati_user -d crati_db

logs:
	@echo "📋 Backend logs (Ctrl+C to exit)..."
	docker-compose -f docker/docker-compose.quickstart.yml logs -f backend

logs-worker:
	@echo "📋 Worker logs (Ctrl+C to exit)..."
	docker-compose -f docker/docker-compose.quickstart.yml logs -f worker

# ───────────────────────── Data Management ─────────────────────────

sample-data:
	@echo "📊 Generating sample data..."
	python scripts/generate_sample_data.py --output ./sample-data --count 100

reset-db:
	@echo "🔄 Resetting database with sample data..."
	docker-compose -f docker/docker-compose.quickstart.yml down -v
	docker-compose -f docker/docker-compose.quickstart.yml up -d db
	@sleep 5
	docker-compose -f docker/docker-compose.quickstart.yml exec backend python manage.py migrate
	docker-compose -f docker/docker-compose.quickstart.yml exec backend python manage.py loaddata sample-data/decisions.json
	@echo "✅ Database reset complete!"

# ───────────────────────── Cleanup ─────────────────────────

stop:
	@echo "🛑 Stopping all services..."
	docker-compose -f docker/docker-compose.quickstart.yml down

clean:
	@echo "🧹 Cleaning up containers and volumes..."
	docker-compose -f docker/docker-compose.quickstart.yml down -v
	docker-compose -f docker/docker-compose.yml down -v
	docker-compose -f docker/docker-compose-no-db.yml down -v

deep-clean:
	@echo "🧹 Deep cleaning all Docker artifacts..."
	docker-compose -f docker/docker-compose.quickstart.yml down -v --rmi all
	docker system prune -a --volumes -f
	@echo "✅ Deep clean complete!"

# ───────────────────────── Utilities ─────────────────────────

status:
	@echo "📊 Service Status:"
	@docker-compose -f docker/docker-compose.quickstart.yml ps

psql:
	docker-compose -f docker/docker-compose.quickstart.yml exec db psql -U crati_user -d crati_db

redis-cli:
	docker-compose -f docker/docker-compose.quickstart.yml exec redis redis-cli

rabbitmq-status:
	docker-compose -f docker/docker-compose.quickstart.yml exec rabbitmq rabbitmqctl status
