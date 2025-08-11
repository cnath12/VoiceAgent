.PHONY: help setup test run clean deploy format lint

help:
	@echo "Available commands:"
	@echo "  make setup    - Set up development environment"
	@echo "  make test     - Run tests"
	@echo "  make run      - Run application locally"
	@echo "  make clean    - Clean up generated files"
	@echo "  make deploy   - Deploy to Render"
	@echo "  make format   - Format code with black"
	@echo "  make lint     - Run pylint"

setup:
	./setup.sh

test:
	source venv/bin/activate && python -m pytest tests/ -v

run:
	source venv/bin/activate && python -m uvicorn src.main:app --reload

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf logs/*

deploy:
	git push origin main
	@echo "Deployment triggered on Render"

format:
	source venv/bin/activate && black src/ tests/

lint:
	source venv/bin/activate && pylint src/ 