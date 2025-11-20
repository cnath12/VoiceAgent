.PHONY: help install install-dev test test-unit test-integration test-cov run clean format lint type-check all-checks docker-build docker-run

help:
	@echo "Available commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make install       - Install production dependencies"
	@echo "  make install-dev   - Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make run          - Run application locally with auto-reload"
	@echo "  make format       - Format code with black and isort"
	@echo "  make lint         - Run ruff linter"
	@echo "  make type-check   - Run mypy type checker"
	@echo "  make all-checks   - Run all code quality checks"
	@echo ""
	@echo "Testing:"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Clean up generated files"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run Docker container"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	pytest

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term

run:
	uvicorn src.main:app --reload --log-level debug

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf dist
	rm -rf build

format:
	black src/ tests/
	isort src/ tests/

lint:
	ruff check src/ tests/

type-check:
	mypy src/

all-checks: lint type-check test
	@echo "✅ All checks passed!"

docker-build:
	docker build -t voiceagent -f deployment/Dockerfile .

docker-run:
	docker run -p 8000:8000 --env-file .env voiceagent 