.DEFAULT_GOAL := help

.PHONY: help test cov cov-html lint install-hooks

help:
	@echo "make test          Run tests + 80% coverage gate (XML report)"
	@echo "make cov           Tests + term-missing: shows every uncovered line"
	@echo "make cov-html      Tests + HTML report, opens in browser"
	@echo "make lint          ruff check app/ tests/"
	@echo "make install-hooks Install pre-push git hook (run once per clone)"

test:
	pytest -q --cov=app --cov-report=xml --cov-fail-under=80

cov:
	pytest -q --cov=app --cov-report=term-missing --cov-fail-under=80

cov-html:
	pytest -q --cov=app --cov-report=html --cov-fail-under=80
	@open htmlcov/index.html 2>/dev/null || echo "Open htmlcov/index.html in your browser"

lint:
	ruff check app tests

install-hooks:
	cp ../scripts/hooks/pre-push ../.git/hooks/pre-push
	chmod +x ../.git/hooks/pre-push
	@echo "Pre-push hook installed. It will run the coverage gate before every push."
