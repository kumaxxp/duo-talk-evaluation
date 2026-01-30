#!/bin/bash
# Integration test runner for HAKONIWA Console
# Usage: ./scripts/ci/run_integration.sh [--with-services]
#
# Options:
#   --with-services  Start GM service before running tests (requires duo-talk-gm)
#   --real-core      Use real Core service (requires Ollama)
#   --real-director  Use real Director service
#   --real-gm        Use real GM service (starts automatically with --with-services)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GM_PID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cleanup() {
    if [ -n "$GM_PID" ]; then
        log_info "Stopping GM service (PID: $GM_PID)..."
        kill $GM_PID 2>/dev/null || true
        wait $GM_PID 2>/dev/null || true
    fi
}

trap cleanup EXIT

start_gm_service() {
    local GM_ROOT="$PROJECT_ROOT/../duo-talk-gm"

    if [ ! -d "$GM_ROOT" ]; then
        log_warn "duo-talk-gm not found at $GM_ROOT, skipping GM service startup"
        return 1
    fi

    log_info "Starting GM service..."
    cd "$GM_ROOT"

    # Start uvicorn in background
    uvicorn duo_talk_gm.main:app --port 8001 --host 127.0.0.1 &
    GM_PID=$!

    # Wait for service to be ready
    log_info "Waiting for GM service to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8001/health > /dev/null 2>&1; then
            log_info "GM service is ready!"
            return 0
        fi
        sleep 1
    done

    log_error "GM service failed to start within 30 seconds"
    return 1
}

run_integration_tests() {
    cd "$PROJECT_ROOT"

    log_info "Running integration tests..."

    # Set environment variables based on flags
    local ENV_VARS=""

    if [ "$USE_REAL_CORE" = "1" ]; then
        ENV_VARS="USE_REAL_CORE=1 $ENV_VARS"
        log_info "Using real Core service"
    fi

    if [ "$USE_REAL_DIRECTOR" = "1" ]; then
        ENV_VARS="USE_REAL_DIRECTOR=1 $ENV_VARS"
        log_info "Using real Director service"
    fi

    if [ "$USE_REAL_GM" = "1" ]; then
        ENV_VARS="USE_REAL_GM=1 $ENV_VARS"
        log_info "Using real GM service"
    fi

    # Run pytest
    if [ -n "$ENV_VARS" ]; then
        env $ENV_VARS python -m pytest tests/integration/ -v --tb=short
    else
        python -m pytest tests/integration/ -v --tb=short
    fi
}

# Parse arguments
WITH_SERVICES=0
USE_REAL_CORE=0
USE_REAL_DIRECTOR=0
USE_REAL_GM=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --with-services)
            WITH_SERVICES=1
            USE_REAL_GM=1
            shift
            ;;
        --real-core)
            USE_REAL_CORE=1
            shift
            ;;
        --real-director)
            USE_REAL_DIRECTOR=1
            shift
            ;;
        --real-gm)
            USE_REAL_GM=1
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Usage: $0 [--with-services] [--real-core] [--real-director] [--real-gm]"
            exit 1
            ;;
    esac
done

# Export for subprocess
export USE_REAL_CORE
export USE_REAL_DIRECTOR
export USE_REAL_GM

# Main execution
log_info "=== HAKONIWA Console Integration Tests ==="
log_info "Project root: $PROJECT_ROOT"

if [ "$WITH_SERVICES" = "1" ]; then
    start_gm_service || log_warn "Continuing without GM service"
fi

run_integration_tests
RESULT=$?

if [ $RESULT -eq 0 ]; then
    log_info "=== Integration tests PASSED ==="
else
    log_error "=== Integration tests FAILED ==="
fi

exit $RESULT
