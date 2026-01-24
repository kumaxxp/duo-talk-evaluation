# duo-talk-evaluation Makefile
# CI/CD and development commands

.PHONY: help test test-all test-core test-director test-evaluation \
        coverage experiment-quick experiment-director experiment-generation \
        benchmark lint format clean

# Default conda environment
CONDA_ENV ?= duo-talk
PYTHON = python

#------------------------------------------------------------------------------
# Help
#------------------------------------------------------------------------------

help:
	@echo "duo-talk-evaluation Makefile"
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run all tests"
	@echo "  make test-core         - Run duo-talk-core tests"
	@echo "  make test-director     - Run duo-talk-director tests"
	@echo "  make test-evaluation   - Run duo-talk-evaluation tests"
	@echo "  make coverage          - Run tests with coverage"
	@echo ""
	@echo "Experiments:"
	@echo "  make experiment-quick      - Run quick smoke test"
	@echo "  make experiment-director   - Run Director A/B test"
	@echo "  make experiment-generation - Run generation mode comparison"
	@echo "  make benchmark             - Run regression mini-benchmark (Phase 2.3)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              - Run linters"
	@echo "  make format            - Format code"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean             - Clean temporary files"

#------------------------------------------------------------------------------
# Testing
#------------------------------------------------------------------------------

test:
	$(PYTHON) scripts/ci/run_tests.py --component all

test-all: test

test-core:
	$(PYTHON) scripts/ci/run_tests.py --component core

test-director:
	$(PYTHON) scripts/ci/run_tests.py --component director

test-evaluation:
	$(PYTHON) scripts/ci/run_tests.py --component evaluation

coverage:
	$(PYTHON) scripts/ci/run_tests.py --component all --coverage

#------------------------------------------------------------------------------
# Experiments
#------------------------------------------------------------------------------

experiment-quick:
	$(PYTHON) scripts/ci/run_experiments.py quick

experiment-director:
	$(PYTHON) scripts/ci/run_experiments.py director-ab

experiment-generation:
	$(PYTHON) scripts/ci/run_experiments.py generation-mode

benchmark:
	$(PYTHON) scripts/ci/run_benchmark.py --scenarios all

benchmark-verbose:
	$(PYTHON) scripts/ci/run_benchmark.py --scenarios all --verbose

#------------------------------------------------------------------------------
# Code Quality
#------------------------------------------------------------------------------

lint:
	$(PYTHON) -m ruff check src/ tests/ experiments/

format:
	$(PYTHON) -m ruff format src/ tests/ experiments/

#------------------------------------------------------------------------------
# Utilities
#------------------------------------------------------------------------------

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage htmlcov/ 2>/dev/null || true

#------------------------------------------------------------------------------
# CI Pipeline (for GitHub Actions)
#------------------------------------------------------------------------------

ci-test: test coverage

ci-experiment: experiment-quick

ci-benchmark: benchmark

ci-full: ci-test ci-experiment ci-benchmark
