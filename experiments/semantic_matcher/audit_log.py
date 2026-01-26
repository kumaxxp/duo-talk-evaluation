"""Audit logging for Semantic Matcher.

All matching operations MUST be logged for traceability.
Logs are written in JSONL format for easy analysis.
"""

import json
from pathlib import Path
from typing import TextIO

from experiments.semantic_matcher.types import AuditLogEntry, MatchResult


class AuditLogger:
    """Logger for semantic matching operations.

    Writes audit entries to a JSONL file for traceability.
    """

    def __init__(self, log_path: Path | str):
        """Initialize audit logger.

        Args:
            log_path: Path to the JSONL log file
        """
        self.log_path = Path(log_path)
        self._ensure_parent_dir()

    def _ensure_parent_dir(self) -> None:
        """Ensure parent directory exists."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, entry: AuditLogEntry) -> None:
        """Write an audit log entry.

        Args:
            entry: The audit log entry to write
        """
        with open(self.log_path, "a", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, ensure_ascii=False)
            f.write("\n")

    def log_match_result(
        self, result: MatchResult, world_objects: set[str]
    ) -> AuditLogEntry:
        """Log a match result.

        Args:
            result: The match result
            world_objects: The world objects used

        Returns:
            The created audit log entry
        """
        entry = AuditLogEntry.from_match_result(result, world_objects)
        self.log(entry)
        return entry


class InMemoryAuditLogger:
    """In-memory audit logger for testing.

    Stores entries in a list instead of writing to file.
    """

    def __init__(self):
        """Initialize in-memory logger."""
        self.entries: list[AuditLogEntry] = []

    def log(self, entry: AuditLogEntry) -> None:
        """Store an audit log entry.

        Args:
            entry: The audit log entry to store
        """
        self.entries.append(entry)

    def log_match_result(
        self, result: MatchResult, world_objects: set[str]
    ) -> AuditLogEntry:
        """Log a match result.

        Args:
            result: The match result
            world_objects: The world objects used

        Returns:
            The created audit log entry
        """
        entry = AuditLogEntry.from_match_result(result, world_objects)
        self.log(entry)
        return entry

    def clear(self) -> None:
        """Clear all stored entries."""
        self.entries.clear()

    def to_jsonl(self) -> str:
        """Convert all entries to JSONL string.

        Returns:
            JSONL formatted string
        """
        lines = [json.dumps(e.to_dict(), ensure_ascii=False) for e in self.entries]
        return "\n".join(lines)


def load_audit_log(log_path: Path | str) -> list[AuditLogEntry]:
    """Load audit log entries from a JSONL file.

    Args:
        log_path: Path to the JSONL log file

    Returns:
        List of AuditLogEntry
    """
    from datetime import datetime

    path = Path(log_path)
    if not path.exists():
        return []

    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            entries.append(
                AuditLogEntry(
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    input_query=data["input_query"],
                    world_objects=data["world_objects"],
                    candidates=data["candidates"],
                    adopted=data["adopted"],
                    status=data["status"],
                    rejection_reason=data.get("rejection_reason"),
                )
            )
    return entries
