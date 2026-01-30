# duo-talk-evaluation Makefile
# CI/CD and development commands

.PHONY: help test test-all test-core test-director test-evaluation test-gm \
        test-freeze test-integration coverage experiment-quick experiment-director experiment-generation \
        benchmark lint format clean dev-run run-dev run-gate run-full gui gui-with-gm \
        new-scenario lint-scenarios scenario-summary play load-test release-gui release-clean

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
	@echo "  make test              - Run all tests (core/director/evaluation/gm)"
	@echo "  make test-core         - Run duo-talk-core tests"
	@echo "  make test-director     - Run duo-talk-director tests"
	@echo "  make test-evaluation   - Run duo-talk-evaluation tests"
	@echo "  make test-gm           - Run duo-talk-gm tests"
	@echo "  make test-freeze       - Run P0 Freeze verification tests"
	@echo "  make test-integration  - Run integration tests (One-Step E2E)"
	@echo "  make coverage          - Run tests with coverage"
	@echo "  make ci-gate           - Quick CI gate (gm+eval tests, lint, gui-smoke)"
	@echo "  make load-test         - Run load test (N=5 concurrent One-Step)"
	@echo ""
	@echo "Runner (GM 2x2):"
	@echo "  make dev-run           - Run dev profile (quick, seeds=1, turns=3)"
	@echo "  make run-dev           - Alias for dev-run"
	@echo "  make run-gate          - Run gate profile (seeds=3, turns=5)"
	@echo "  make run-full          - Run full profile (seeds=5, turns=10)"
	@echo "  make demo-pack-gate    - Run demo scenarios with gate profile"
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
	@echo "GUI:"
	@echo "  make gui               - Start NiceGUI evaluation dashboard (port 8080)"
	@echo "  make gui-with-gm       - Start GUI with GM service"
	@echo ""
	@echo "Release:"
	@echo "  make release-gui       - Create release package (tar.gz)"
	@echo "  make release-clean     - Clean release artifacts"
	@echo ""
	@echo "Scenario Tools:"
	@echo "  make new-scenario id=scn_xxx  - Generate new scenario template"
	@echo "  make lint-scenarios           - Lint all scenarios"
	@echo "  make scenario-summary s=name  - Show scenario world summary"
	@echo "  make play s=scenario_id       - Interactive play mode"
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

test-gm:
	$(PYTHON) scripts/ci/run_tests.py --component gm

test-freeze:
	$(PYTHON) -m pytest tests/test_p0_freeze.py -v

coverage:
	$(PYTHON) scripts/ci/run_tests.py --component all --coverage

test-integration:
	$(PYTHON) -m pytest tests/integration/ -v --tb=short

test-integration-real:
	./scripts/ci/run_integration.sh --with-services

load-test:
	$(PYTHON) scripts/load_test_one_step.py --concurrent 5 --iterations 3

#------------------------------------------------------------------------------
# Runner (GM 2x2)
#------------------------------------------------------------------------------

# Default scenario and experiment ID
SCENARIO ?= coffee_trap
EXP_ID ?= $(shell date +%Y%m%d_%H%M%S)

dev-run:
	PYTHONPATH=. $(PYTHON) experiments/gm_2x2_runner.py --experiment_id dev_$(EXP_ID) --profile dev --scenarios $(SCENARIO)

run-dev: dev-run

run-gate:
	PYTHONPATH=. $(PYTHON) experiments/gm_2x2_runner.py --experiment_id gate_$(EXP_ID) --profile gate --scenarios $(SCENARIO)

run-full:
	PYTHONPATH=. $(PYTHON) experiments/gm_2x2_runner.py --experiment_id full_$(EXP_ID) --profile full --scenarios $(SCENARIO)

# Demo Pack: Run all demo-tagged scenarios with gate profile
demo-pack-gate:
	@echo "=== Demo Pack (Gate Profile) ==="
	@echo "Running: coffee_trap, wrong_location, locked_door"
	PYTHONPATH=. $(PYTHON) experiments/gm_2x2_runner.py --experiment_id demo_pack_$(EXP_ID) --profile gate --scenarios coffee_trap,wrong_location,locked_door
	@echo ""
	@echo "Results: results/demo_pack_$(EXP_ID)_*"

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

# CI Gate: Quick verification for PR checks
# Runs: test (gm + evaluation), lint-scenarios, gui-smoke
ci-gate:
	@echo "=== CI Gate: Running tests ==="
	$(PYTHON) scripts/ci/run_tests.py --component gm
	$(PYTHON) scripts/ci/run_tests.py --component evaluation
	@echo ""
	@echo "=== CI Gate: Linting scenarios ==="
	$(PYTHON) scripts/scenario_tools.py lint experiments/scenarios/*.json
	@echo ""
	@echo "=== CI Gate: GUI smoke test (import only) ==="
	$(PYTHON) -c "from gui_nicegui.main import create_app; print('GUI import OK')"
	@echo ""
	@echo "=== CI Gate: PASSED ==="

#------------------------------------------------------------------------------
# GUI
#------------------------------------------------------------------------------

gui:
	$(PYTHON) -m gui_nicegui.main

gui-with-gm:
	./run_gui.sh --with-gm

#------------------------------------------------------------------------------
# Release
#------------------------------------------------------------------------------

RELEASE_NAME ?= hakoniwa-console
RELEASE_VERSION ?= 0.1.0

release-gui:
	@echo "=== Creating release package ==="
	@mkdir -p dist
	@echo "Exporting requirements..."
	pip freeze > dist/requirements-freeze.txt
	@echo "Creating archive..."
	tar --exclude='*.pyc' --exclude='__pycache__' --exclude='.pytest_cache' \
		--exclude='results/*' --exclude='reports/*.csv' --exclude='dist' \
		-czvf dist/$(RELEASE_NAME)-$(RELEASE_VERSION).tar.gz \
		gui_nicegui/ run_gui.sh Makefile requirements.txt \
		docs/specs/PHASE4_RELEASE_NOTES.md docs/specs/DEMO_SCRIPT.md \
		docs/specs/PHASE4_GUI_IMPL_NOTES.md
	@echo ""
	@echo "Release package created: dist/$(RELEASE_NAME)-$(RELEASE_VERSION).tar.gz"
	@ls -lh dist/$(RELEASE_NAME)-$(RELEASE_VERSION).tar.gz

release-clean:
	rm -rf dist/

#------------------------------------------------------------------------------
# Scenario Tools (Phase C)
#------------------------------------------------------------------------------

# Generate new scenario template
# Usage: make new-scenario id=scn_xxx
new-scenario:
	@if [ -z "$(id)" ]; then echo "Error: id required (make new-scenario id=scn_xxx)"; exit 1; fi
	$(PYTHON) scripts/scenario_tools.py new $(id)

# Lint all scenarios
lint-scenarios:
	$(PYTHON) scripts/scenario_tools.py lint experiments/scenarios/*.json

# Show scenario world summary
# Usage: make scenario-summary s=coffee_trap
scenario-summary:
	@if [ -z "$(s)" ]; then echo "Error: s required (make scenario-summary s=name)"; exit 1; fi
	$(PYTHON) scripts/scenario_tools.py summary experiments/scenarios/$(s).json

# Interactive play mode
# Usage: make play s=coffee_trap
play:
	@if [ -z "$(s)" ]; then echo "Error: s required (make play s=scenario_id)"; exit 1; fi
	PYTHONPATH=. $(PYTHON) scripts/play_mode.py $(s)
