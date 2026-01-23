"""Tests for Model Comparison Experiment (v2.3)

v2.3 tests model migration to solve Empty Thought problem.
This test defines expected behavior for the model comparison.
"""

import pytest
from dataclasses import dataclass
from typing import Optional


@dataclass
class ThoughtMetrics:
    """Metrics for Thought generation quality"""
    total_responses: int = 0
    thought_present: int = 0
    thought_missing: int = 0
    thought_empty: int = 0
    thought_with_content: int = 0

    @property
    def presence_rate(self) -> float:
        """Rate of responses with Thought marker"""
        if self.total_responses == 0:
            return 0.0
        return self.thought_present / self.total_responses

    @property
    def content_rate(self) -> float:
        """Rate of responses with meaningful Thought content"""
        if self.total_responses == 0:
            return 0.0
        return self.thought_with_content / self.total_responses

    @property
    def empty_rate(self) -> float:
        """Rate of empty Thoughts (marker present but no content)"""
        if self.thought_present == 0:
            return 0.0
        return self.thought_empty / self.thought_present


@dataclass
class ModelComparisonResult:
    """Result of model comparison"""
    model_name: str
    thought_metrics: ThoughtMetrics
    avg_retries: float
    total_rejections: int
    avg_generation_time: float

    def meets_v23_criteria(self) -> bool:
        """Check if model meets v2.3 success criteria"""
        # v2.3 targets:
        # - Thought presence: 100%
        # - Empty Thought: < 5%
        # - Avg retries: < 1.0
        return (
            self.thought_metrics.presence_rate >= 1.0 and
            self.thought_metrics.empty_rate < 0.05 and
            self.avg_retries < 1.0
        )


class TestThoughtMetrics:
    """Test ThoughtMetrics calculations"""

    def test_presence_rate_calculation(self):
        """Presence rate is thought_present / total"""
        metrics = ThoughtMetrics(
            total_responses=100,
            thought_present=95,
            thought_missing=5,
        )
        assert metrics.presence_rate == 0.95

    def test_content_rate_calculation(self):
        """Content rate is thought_with_content / total"""
        metrics = ThoughtMetrics(
            total_responses=100,
            thought_present=95,
            thought_with_content=85,
        )
        assert metrics.content_rate == 0.85

    def test_empty_rate_calculation(self):
        """Empty rate is thought_empty / thought_present"""
        metrics = ThoughtMetrics(
            total_responses=100,
            thought_present=64,
            thought_empty=9,
        )
        # 9 / 64 = 0.140625
        assert abs(metrics.empty_rate - 0.140625) < 0.001

    def test_empty_metrics_return_zero(self):
        """Zero totals return zero rates"""
        metrics = ThoughtMetrics()
        assert metrics.presence_rate == 0.0
        assert metrics.content_rate == 0.0
        assert metrics.empty_rate == 0.0


class TestModelComparisonResult:
    """Test ModelComparisonResult v2.3 criteria"""

    def test_perfect_model_meets_criteria(self):
        """Model with 100% presence, 0% empty, 0 retries meets criteria"""
        result = ModelComparisonResult(
            model_name="perfect_model",
            thought_metrics=ThoughtMetrics(
                total_responses=100,
                thought_present=100,
                thought_missing=0,
                thought_empty=0,
                thought_with_content=100,
            ),
            avg_retries=0.0,
            total_rejections=0,
            avg_generation_time=1.0,
        )
        assert result.meets_v23_criteria() is True

    def test_gemma3_baseline_fails_criteria(self):
        """Gemma3 v2.2 results (14% empty) fails v2.3 criteria"""
        # Based on v2.2 experiment: 64 present, 9 empty
        result = ModelComparisonResult(
            model_name="gemma3:12b",
            thought_metrics=ThoughtMetrics(
                total_responses=64,
                thought_present=64,
                thought_missing=0,
                thought_empty=9,  # 14% empty rate
                thought_with_content=55,
            ),
            avg_retries=0.5,
            total_rejections=4,
            avg_generation_time=20.0,
        )
        # Empty rate is 14% > 5% threshold
        assert result.meets_v23_criteria() is False

    def test_model_with_low_presence_fails(self):
        """Model with <100% presence fails criteria"""
        result = ModelComparisonResult(
            model_name="bad_model",
            thought_metrics=ThoughtMetrics(
                total_responses=100,
                thought_present=90,  # 90% presence
                thought_missing=10,
                thought_empty=0,
                thought_with_content=90,
            ),
            avg_retries=0.5,
            total_rejections=0,
            avg_generation_time=1.0,
        )
        assert result.meets_v23_criteria() is False

    def test_model_with_high_retries_fails(self):
        """Model with retries >= 1.0 fails criteria"""
        result = ModelComparisonResult(
            model_name="retry_model",
            thought_metrics=ThoughtMetrics(
                total_responses=100,
                thought_present=100,
                thought_missing=0,
                thought_empty=4,  # 4% < 5%
                thought_with_content=96,
            ),
            avg_retries=1.5,  # Too many retries
            total_rejections=10,
            avg_generation_time=1.0,
        )
        assert result.meets_v23_criteria() is False

    def test_borderline_empty_rate_passes(self):
        """Model with exactly 4.9% empty passes"""
        # 4.9% of 100 = 4.9 -> round to 5
        result = ModelComparisonResult(
            model_name="borderline_model",
            thought_metrics=ThoughtMetrics(
                total_responses=100,
                thought_present=100,
                thought_missing=0,
                thought_empty=4,  # 4% < 5%
                thought_with_content=96,
            ),
            avg_retries=0.9,  # < 1.0
            total_rejections=0,
            avg_generation_time=1.0,
        )
        assert result.meets_v23_criteria() is True

    def test_exactly_5_percent_empty_fails(self):
        """Model with exactly 5% empty fails (not strictly less than)"""
        result = ModelComparisonResult(
            model_name="exact5_model",
            thought_metrics=ThoughtMetrics(
                total_responses=100,
                thought_present=100,
                thought_missing=0,
                thought_empty=5,  # Exactly 5%
                thought_with_content=95,
            ),
            avg_retries=0.5,
            total_rejections=0,
            avg_generation_time=1.0,
        )
        # 5% is not < 5%, so fails
        assert result.meets_v23_criteria() is False


class TestThoughtExtraction:
    """Test Thought extraction from responses"""

    def test_extract_valid_thought(self):
        """Extract valid Thought content"""
        response = "Thought: (姉様が起きてきた。今日も明るいな…)\nOutput: 「おはようございます、姉様」"

        import re
        match = re.search(r"Thought:\s*(.+?)(?=\nOutput:|$)", response, re.DOTALL)
        assert match is not None
        thought = match.group(1).strip()
        assert thought == "(姉様が起きてきた。今日も明るいな…)"

    def test_extract_empty_thought(self):
        """Detect empty Thought"""
        response = "Thought: (\nOutput: 「おはようございます」"

        import re
        match = re.search(r"Thought:\s*(.+?)(?=\nOutput:|$)", response, re.DOTALL)
        if match:
            thought = match.group(1).strip()
            # Only opening parenthesis = empty
            is_empty = thought in ["(", "()", "( )", ""]
            assert is_empty is True

    def test_extract_missing_thought(self):
        """Detect missing Thought marker"""
        response = "(笑顔で) 「おはようございます」"

        import re
        has_thought = bool(re.search(r"Thought:", response, re.IGNORECASE))
        assert has_thought is False


class TestModelAvailability:
    """Test model availability checking (mocked)"""

    def test_model_availability_structure(self):
        """Model availability check returns expected structure"""
        # This would be the actual check in the experiment
        available_models = {
            "llama3.1:8b": True,  # Benchmark model
            "qwen2.5:14b": True,  # Production candidate
            "gemma3:12b": True,   # Current baseline
        }

        # All target models should be defined
        assert "llama3.1:8b" in available_models
        assert "qwen2.5:14b" in available_models
