# GUI MVP - NiceGUI Evaluation Dashboard

**Status**: Phase B Implementation

## Overview

NiceGUI-based web UI for observing and debugging the duo-talk evaluation system.
Purpose: Enable visualization of experiment results to identify failure patterns.

## Features

### MVP (Phase B)

1. **Scenario Selection**
   - Load scenarios from `experiments/scenarios/*.json`
   - Display scenario summary (locations, characters, props)

2. **Execution Panel**
   - Profile selection (dev/gate/full)
   - Run experiment button
   - Real-time log output

3. **Results Viewer**
   - List recent runs (sorted by timestamp)
   - View turn details (thought, speech)
   - Show format repair diffs (raw vs repaired)
   - Display guidance card available lists

## Usage

```bash
# Start GUI
make gui

# Or directly
python -m gui_nicegui.main
```

Access at: http://localhost:8080

## Directory Structure

```
gui_nicegui/
├── __init__.py
├── main.py              # Main NiceGUI application
└── data/
    ├── __init__.py
    ├── scenarios.py     # Scenario loading
    ├── results.py       # Results loading
    ├── diff.py          # Text diff generation
    └── guidance.py      # Guidance card parsing
```

## Data Layer

The data layer is TDD-tested:

| Module | Purpose | Tests |
|--------|---------|-------|
| scenarios.py | Load scenario JSON files | 3 |
| results.py | Parse run results | 3 |
| diff.py | Generate repair diffs | 3 |
| guidance.py | Extract available lists | 2 |

Total: 11 tests

## Future Enhancements (Post-MVP)

- [ ] World state visualization (2D map)
- [ ] Stall score graph over time
- [ ] A/B comparison view
- [ ] Export to markdown report
- [ ] Real-time streaming during runs

---

*Last Updated: 2026-01-26*
