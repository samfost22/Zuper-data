.PHONY: install install-dev install-dashboard test clean dashboard jobs export help

# Default target
help:
	@echo "Zuper Connector - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install           Install base package"
	@echo "  make install-dashboard Install with dashboard support"
	@echo "  make install-dev       Install with dev tools"
	@echo ""
	@echo "Usage:"
	@echo "  make test              Test API connection"
	@echo "  make jobs              List recent jobs"
	@echo "  make dashboard         Run NetSuite dashboard"
	@echo "  make export            Export jobs to CSV"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean             Remove cache files"
	@echo "  make update            Pull latest changes"
	@echo ""
	@echo "Before using, set your API key:"
	@echo "  export ZUPER_API_KEY='your_api_key_here'"

# Installation
install:
	pip install -e .

install-dashboard:
	pip install -e ".[dashboard]"

install-dev:
	pip install -e ".[dev,dashboard]"

# Usage commands
test:
	@python -m zuper_connector.cli test

jobs:
	@python -m zuper_connector.cli jobs

dashboard:
	@streamlit run dashboard/netsuite_dashboard.py

export:
	@python -m zuper_connector.cli export jobs_export.csv

# Maintenance
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf *.egg-info build dist .pytest_cache

update:
	git pull origin main
