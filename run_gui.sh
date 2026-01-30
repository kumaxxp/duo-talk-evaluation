#!/bin/bash
# HAKONIWA Console 起動スクリプト
#
# Usage:
#   ./run_gui.sh              # 通常起動
#   ./run_gui.sh --port 8081  # ポート指定
#   ./run_gui.sh --with-gm    # GM サービスも起動
#
# Environment:
#   HAKONIWA_PORT    - GUI ポート (default: 8080)
#   HAKONIWA_GM_PORT - GM ポート (default: 8001)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default values
PORT="${HAKONIWA_PORT:-8080}"
GM_PORT="${HAKONIWA_GM_PORT:-8001}"
WITH_GM=0
GM_PID=""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --with-gm)
            WITH_GM=1
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--port PORT] [--with-gm]"
            echo ""
            echo "Options:"
            echo "  --port PORT    Set GUI port (default: 8080)"
            echo "  --with-gm      Also start GM service"
            echo ""
            echo "Environment:"
            echo "  HAKONIWA_PORT     GUI port"
            echo "  HAKONIWA_GM_PORT  GM port"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check conda environment
if [[ -z "$CONDA_DEFAULT_ENV" ]] || [[ "$CONDA_DEFAULT_ENV" != "duo-talk" ]]; then
    log_warn "Activating conda environment 'duo-talk'..."
    if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/miniconda3/etc/profile.d/conda.sh"
        conda activate duo-talk
    elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/anaconda3/etc/profile.d/conda.sh"
        conda activate duo-talk
    else
        log_error "Could not find conda. Please activate 'duo-talk' environment manually."
        exit 1
    fi
fi

# Start GM service if requested
if [ "$WITH_GM" = "1" ]; then
    GM_ROOT="$SCRIPT_DIR/../duo-talk-gm"
    if [ -d "$GM_ROOT" ]; then
        log_info "Starting GM service on port $GM_PORT..."
        cd "$GM_ROOT"
        uvicorn duo_talk_gm.main:app --port "$GM_PORT" --host 127.0.0.1 &
        GM_PID=$!
        cd "$SCRIPT_DIR"

        # Wait for GM to be ready
        for i in {1..10}; do
            if curl -s "http://localhost:$GM_PORT/health" > /dev/null 2>&1; then
                log_info "GM service is ready!"
                break
            fi
            sleep 1
        done
    else
        log_warn "duo-talk-gm not found, skipping GM service"
    fi
fi

# Display service status
log_info "=== HAKONIWA Console ==="
log_info "GUI: http://localhost:$PORT"

# Check service availability
python -c "
import sys
sys.path.insert(0, 'gui_nicegui')
from adapters.core_adapter import CORE_AVAILABLE
from adapters.director_adapter import DIRECTOR_AVAILABLE
print(f'Core: {\"✓\" if CORE_AVAILABLE else \"✗ (mock)\"}')
print(f'Director: {\"✓\" if DIRECTOR_AVAILABLE else \"✗ (mock)\"}')
" 2>/dev/null || log_warn "Could not check service status"

if [ "$WITH_GM" = "1" ] && [ -n "$GM_PID" ]; then
    log_info "GM: ✓ (port $GM_PORT)"
else
    log_info "GM: ✗ (mock)"
fi

log_info "========================"
log_info "Starting GUI..."

# Start GUI
export NICEGUI_PORT="$PORT"
python -m gui_nicegui.main
