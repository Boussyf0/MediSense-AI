.DEFAULT_GOAL := help

.PHONY: help test cov cov-html lint install-hooks

help:
	@echo "make test          Run tests + 80% coverage gate (XML report)"
	@echo "make cov           Tests + term-missing: shows every uncovered line"
	@echo "make cov-html      Tests + HTML report, opens in browser"
	@echo "make lint          ruff check app/ tests/"
	@echo "make install-hooks Install pre-push git hook (run once per clone)"

test:
	KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 POSTGRES_HOST=localhost REDIS_HOST=localhost python -m pytest --cov=app --cov-config=.coveragerc --cov-report=xml --cov-fail-under=80 --tb=short

cov:
	KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 POSTGRES_HOST=localhost REDIS_HOST=localhost python -m pytest --cov=app --cov-config=.coveragerc --cov-report=term-missing --cov-fail-under=80 --tb=short

cov-html:
	KMP_DUPLICATE_LIB_OK=TRUE OMP_NUM_THREADS=1 POSTGRES_HOST=localhost REDIS_HOST=localhost python -m pytest --cov=app --cov-config=.coveragerc --cov-report=html --cov-fail-under=80 --tb=short
	@open htmlcov/index.html 2>/dev/null || echo "Open htmlcov/index.html in your browser"

lint:
	ruff check app tests

install-hooks:
	cp ../scripts/hooks/pre-push ../.git/hooks/pre-push
	chmod +x ../.git/hooks/pre-push
	@echo "Pre-push hook installed. It will run the coverage gate before every push."
