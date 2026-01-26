# P0 Freeze Policy

**Effective Date**: 2026-01-26
**Status**: ACTIVE

## Overview

This document defines the P0 (Phase 0) freeze policy for the GM Service judgment logic.
The purpose is to stabilize the core behavior and enable UI/scenario development without breaking existing functionality.

## Frozen Components

The following components in `duo-talk-gm` are **FROZEN** and must not be modified except for bug fixes:

### 1. Preflight Checker (`core/preflight.py`)
- `PreflightChecker.check()` - Pre-judgment validation
- `PreflightChecker._check_intent()` - Intent validation
- `PreflightChecker._check_move()` - MOVE intent validation
- `PreflightChecker._check_object_intent()` - Object intent validation
- Retry budget logic (max 2 retries)
- GIVE_UP behavior (PASS + log after budget exhausted)

### 2. Action Judge (`core/action_judge.py`)
- `ActionJudge.judge()` - Main judgment entry point
- `ActionJudge._judge_intent()` - Intent routing
- `ActionJudge._judge_get()` - GET validation
- `ActionJudge._judge_put()` - PUT validation
- `ActionJudge._judge_use()` - USE validation
- `ActionJudge._judge_move()` - MOVE validation
- `ActionJudge._judge_eat_drink()` - EAT_DRINK validation
- GM-013 soft prop resolution (aliases, derived props)

### 3. Stall Detector (`core/stall_detector.py`)
- `StallDetector.calculate()` - Stall score calculation
- Weight configuration (speech_repeat: 0.70, no_delta: 0.20, short: 0.10)
- Threshold values (WARNING: 0.3, STALLED: 0.8, CRITICAL: 0.9)
- Cooldown logic (5 turns)

### 4. Output Parser (`core/output_parser.py`)
- `OutputParser.parse()` - Response parsing
- Format detection and repair logic
- Intent extraction patterns
- Marker extraction (`extract_marker_targets()`, `extract_marker_texts()`)

## Allowed Modifications

### Bug Fixes Only
The following types of changes are allowed:
- **Crash fixes**: Preventing exceptions/errors
- **Data loss prevention**: Ensuring data integrity
- **Reference fixes**: Fixing incorrect variable/function references
- **Logging fixes**: Correcting missing or incorrect log output

### Examples of Allowed Changes
```python
# ALLOWED: Fix crash when prop is None
if prop is None:
    return JudgmentResult.allowed()

# ALLOWED: Fix missing log field
logger.info("preflight", extra={"turn": turn_number})  # was missing turn_number
```

### Examples of Prohibited Changes
```python
# PROHIBITED: Changing threshold value
max_retry_budget = 3  # was 2

# PROHIBITED: Adding new validation logic
if intent.intent == IntentType.INSPECT:
    return cls._check_inspect(intent, world_state, speaker)

# PROHIBITED: Modifying weight configuration
WEIGHTS = {
    "speech_repeat": 0.50,  # was 0.70
    ...
}
```

## Verification

### Snapshot Tests
Run `make test-freeze` to verify P0 logic has not changed:
```bash
make test-freeze
```

The test suite (`tests/test_p0_freeze.py`) contains golden outputs for:
- Preflight results for known inputs
- ActionJudge results for known inputs
- StallDetector scores for known inputs

### PR Checklist
Every PR must include:
- [ ] No changes to P0 frozen files (or bug fix justification)
- [ ] `make test-freeze` passes
- [ ] No new logic in frozen components

## Exceptions Process

If a bug fix requires modifying frozen logic:
1. Document the bug clearly
2. Provide minimal reproduction steps
3. Show the fix is the minimum necessary change
4. Ensure all tests pass after the fix
5. Update snapshot tests if output changes (with justification)

## Related Files

| File | Status | Location |
|------|--------|----------|
| preflight.py | FROZEN | duo-talk-gm/src/duo_talk_gm/core/ |
| action_judge.py | FROZEN | duo-talk-gm/src/duo_talk_gm/core/ |
| stall_detector.py | FROZEN | duo-talk-gm/src/duo_talk_gm/core/ |
| output_parser.py | FROZEN | duo-talk-gm/src/duo_talk_gm/core/ |

## Not Frozen (Modifiable)

The following are NOT frozen and can be modified:
- `prompts.py` - Guidance card text (wording only, not structure)
- `world_state.py` - World state model
- `gm_response.py` - Response models
- `fact_generator.py` - Fact card generation
- `world_updater.py` - World state updates
- All evaluation/experiment code in `duo-talk-evaluation`

---

*Last Updated: 2026-01-26*
