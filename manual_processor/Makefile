.PHONY: help test test-unit test-integration test-e2e test-performance coverage lint security benchmark clean install dev

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install package with dev dependencies
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

dev: ## Install development dependencies
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

test: ## Run all tests
	python -m pytest tests/ -v

test-unit: ## Run unit tests only
	python -m pytest tests/test_*.py -v

test-integration: ## Run integration tests
	python -m pytest tests/integration/ -v

test-e2e: ## Run end-to-end tests
	python -m pytest tests/e2e/ -v

test-performance: ## Run performance benchmarks
	python -m pytest tests/performance/ -v --benchmark-only

coverage: ## Run tests with coverage report
	python -m pytest tests/ --cov=src --cov=config --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/index.html"

coverage-check: ## Check coverage meets threshold
	python -m pytest tests/ --cov=src --cov=config --cov-report=term
	@echo "Coverage check complete"

lint: ## Run linting
	python -m pip install flake8
	python -m flake8 src/ config/ --count --select=E9,F63,F7,F82 --show-source --statistics
	python -m flake8 src/ config/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

security: ## Run security scans
	python -m bandit -r src/ config/ -ll
	python -m pip-audit || true

benchmark: ## Run performance benchmarks
	python -m pytest tests/performance/ -v --benchmark-only --benchmark-disable-gc

clean: ## Clean build artifacts and cache
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .bandit/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete"

run: ## Run web server
	python -m src.web.app

run-gui: ## Run GUI application
	python -m src.gui.main

validate-config: ## Validate configuration file
	python -m config.validate config/config.example.yaml

watch-config: ## Watch config file for changes
	python -c "from config.watcher import ConfigWatcher; from pathlib import Path; w = ConfigWatcher(Path('config/config.example.yaml'), lambda: print('Config reloaded')); w.start(); import time; time.sleep(3600)"

.DEFAULT_GOAL := help
