"""Logging utilities for HAKONIWA Console.

Provides timestamped logging with trace IDs for debugging and monitoring.
"""

import time
import uuid
from datetime import datetime
from typing import Callable


class TraceContext:
    """Context for tracing a single One-Step execution."""

    def __init__(self, speaker: str, turn_number: int):
        self.trace_id = uuid.uuid4().hex[:8]
        self.speaker = speaker
        self.turn_number = turn_number
        self.start_time = time.perf_counter()
        self.events: list[dict] = []

    def log_event(self, phase: str, message: str, latency_ms: int | None = None) -> str:
        """Log an event and return formatted log string."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        elapsed_ms = int((time.perf_counter() - self.start_time) * 1000)

        event = {
            "timestamp": timestamp,
            "elapsed_ms": elapsed_ms,
            "phase": phase,
            "message": message,
            "latency_ms": latency_ms,
        }
        self.events.append(event)

        # Format: [HH:MM:SS.mmm] [trace_id] [phase] message (latency/elapsed)
        latency_str = f" ({latency_ms}ms)" if latency_ms else ""
        return f"[{timestamp}] [{self.trace_id}] [{phase}] {message}{latency_str}"

    def get_summary(self) -> dict:
        """Get trace summary for reporting."""
        total_elapsed = int((time.perf_counter() - self.start_time) * 1000)
        return {
            "trace_id": self.trace_id,
            "speaker": self.speaker,
            "turn_number": self.turn_number,
            "total_elapsed_ms": total_elapsed,
            "event_count": len(self.events),
            "events": self.events,
        }


class LogBuffer:
    """Buffer for accumulating log lines with optional callback."""

    def __init__(self, max_lines: int = 100, callback: Callable[[str], None] | None = None):
        self.lines: list[str] = []
        self.max_lines = max_lines
        self.callback = callback

    def append(self, line: str) -> None:
        """Append a log line."""
        self.lines.append(line)
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines:]
        if self.callback:
            self.callback(line)

    def get_all(self) -> str:
        """Get all log lines as a single string."""
        return "\n".join(self.lines)

    def get_last(self, n: int = 1) -> str:
        """Get last N log lines."""
        return "\n".join(self.lines[-n:])

    def clear(self) -> None:
        """Clear all log lines."""
        self.lines.clear()


def format_timestamp() -> str:
    """Get current timestamp in HH:MM:SS.mmm format."""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def format_log_line(phase: str, message: str, trace_id: str | None = None) -> str:
    """Format a log line with timestamp and optional trace ID."""
    timestamp = format_timestamp()
    if trace_id:
        return f"[{timestamp}] [{trace_id}] [{phase}] {message}"
    return f"[{timestamp}] [{phase}] {message}"
