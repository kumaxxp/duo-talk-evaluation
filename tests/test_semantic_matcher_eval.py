"""Tests for Semantic Matcher Evaluation Harness.

Tests the evaluation pipeline including:
- Sample extraction from logs
- Metric computation
- Threshold grid evaluation
"""

import json
import tempfile
from pathlib import Path

import pytest

from experiments.semantic_matcher.eval_types import (
    MissingObjectSample,
    EvalResult,
    EvalMetrics,
    EvalSummary,
)
from experiments.semantic_matcher.extractor import (
    extract_world_objects,
    extract_samples_from_run,
    deduplicate_samples,
    filter_samples_with_gt,
    _infer_ground_truth,
)
from experiments.semantic_matcher.evaluator import (
    evaluate_sample,
    evaluate_samples_at_threshold,
    run_evaluation,
    evaluate_single_query,
)
from experiments.semantic_matcher.fuzzy import FuzzyMatcher


class TestMissingObjectSample:
    """Tests for MissingObjectSample dataclass."""

    def test_create_sample(self):
        """Test creating a sample."""
        sample = MissingObjectSample(
            sample_id="test_001",
            run_path=Path("/tmp/test"),
            session_id="session_001",
            turn_number=5,
            query="コップ",
            world_objects={"マグカップ", "コーヒーメーカー"},
            scenario="coffee_trap",
            speaker="あゆ",
            denied_reason="invented_object",
            ground_truth="マグカップ",
        )

        assert sample.sample_id == "test_001"
        assert sample.query == "コップ"
        assert "マグカップ" in sample.world_objects
        assert sample.ground_truth == "マグカップ"

    def test_sample_without_gt(self):
        """Test sample without ground truth."""
        sample = MissingObjectSample(
            sample_id="test_002",
            run_path=Path("/tmp/test"),
            session_id="session_001",
            turn_number=3,
            query="不明なオブジェクト",
            world_objects={"本棚", "ソファ"},
            scenario="living_room",
            speaker="やな",
        )

        assert sample.ground_truth is None
        assert sample.denied_reason is None


class TestEvalMetrics:
    """Tests for EvalMetrics computation."""

    def test_compute_metrics_basic(self):
        """Test basic metrics computation."""
        # Create mock results
        sample = MissingObjectSample(
            sample_id="s1",
            run_path=Path("/tmp"),
            session_id="sess",
            turn_number=1,
            query="カップ",
            world_objects={"マグカップ"},
            scenario="test",
            speaker="あゆ",
            ground_truth="マグカップ",
        )

        results = [
            EvalResult(
                sample=sample,
                candidates=[("マグカップ", 0.85)],
                top_candidate="マグカップ",
                top_score=0.85,
                is_true_positive=True,
                is_false_positive=False,
                is_no_match=False,
                gt_in_candidates=True,
                threshold_used=0.7,
            )
        ]

        metrics = EvalMetrics.compute(results, excluded_count=0, threshold=0.7)

        assert metrics.total_samples == 1
        assert metrics.true_positives == 1
        assert metrics.false_positives == 0
        assert metrics.recall == 1.0
        assert metrics.precision == 1.0

    def test_compute_metrics_with_fp(self):
        """Test metrics with false positives."""
        sample1 = MissingObjectSample(
            sample_id="s1",
            run_path=Path("/tmp"),
            session_id="sess",
            turn_number=1,
            query="カップ",
            world_objects={"マグカップ", "ティーカップ"},
            scenario="test",
            speaker="あゆ",
            ground_truth="マグカップ",
        )

        sample2 = MissingObjectSample(
            sample_id="s2",
            run_path=Path("/tmp"),
            session_id="sess",
            turn_number=2,
            query="グラス",
            world_objects={"ワイングラス", "コップ"},
            scenario="test",
            speaker="やな",
            ground_truth="コップ",
        )

        results = [
            EvalResult(
                sample=sample1,
                candidates=[("ティーカップ", 0.75)],
                top_candidate="ティーカップ",
                top_score=0.75,
                is_true_positive=False,
                is_false_positive=True,  # Wrong suggestion
                is_no_match=False,
                gt_in_candidates=False,
                threshold_used=0.7,
            ),
            EvalResult(
                sample=sample2,
                candidates=[("コップ", 0.80)],
                top_candidate="コップ",
                top_score=0.80,
                is_true_positive=True,
                is_false_positive=False,
                is_no_match=False,
                gt_in_candidates=True,
                threshold_used=0.7,
            ),
        ]

        metrics = EvalMetrics.compute(results, excluded_count=0, threshold=0.7)

        assert metrics.total_samples == 2
        assert metrics.true_positives == 1
        assert metrics.false_positives == 1
        assert metrics.recall == 0.5
        assert metrics.precision == 0.5

    def test_compute_metrics_empty(self):
        """Test metrics with no results."""
        metrics = EvalMetrics.compute([], excluded_count=5, threshold=0.7)

        assert metrics.total_samples == 0
        assert metrics.excluded_samples == 5
        assert metrics.exclusion_rate == 1.0
        assert metrics.recall == 0.0

    def test_to_dict(self):
        """Test serialization to dict."""
        metrics = EvalMetrics(
            total_samples=10,
            excluded_samples=2,
            exclusion_rate=0.1667,
            true_positives=7,
            false_positives=1,
            no_matches=2,
            recall=0.7,
            precision=0.875,
            fp_rate=0.1,
            threshold=0.8,
        )

        d = metrics.to_dict()

        assert d["total_samples"] == 10
        assert d["recall"] == 0.7
        assert d["threshold"] == 0.8


class TestEvalSummary:
    """Tests for EvalSummary."""

    def test_find_best_by_f1(self):
        """Test finding best threshold by F1 score."""
        metrics_by_threshold = {
            0.7: EvalMetrics(
                total_samples=10,
                excluded_samples=0,
                exclusion_rate=0.0,
                true_positives=8,
                false_positives=4,
                no_matches=2,
                recall=0.8,
                precision=0.667,
                fp_rate=0.4,
                threshold=0.7,
            ),
            0.8: EvalMetrics(
                total_samples=10,
                excluded_samples=0,
                exclusion_rate=0.0,
                true_positives=6,
                false_positives=1,
                no_matches=3,
                recall=0.6,
                precision=0.857,
                fp_rate=0.1,
                threshold=0.8,
            ),
            0.9: EvalMetrics(
                total_samples=10,
                excluded_samples=0,
                exclusion_rate=0.0,
                true_positives=4,
                false_positives=0,
                no_matches=6,
                recall=0.4,
                precision=1.0,
                fp_rate=0.0,
                threshold=0.9,
            ),
        }

        summary = EvalSummary.find_best(metrics_by_threshold, "test_input")

        # F1 scores:
        # 0.7: 2 * 0.8 * 0.667 / (0.8 + 0.667) = 0.727
        # 0.8: 2 * 0.6 * 0.857 / (0.6 + 0.857) = 0.705
        # 0.9: 2 * 0.4 * 1.0 / (0.4 + 1.0) = 0.571
        assert summary.best_threshold == 0.7
        assert summary.best_metrics.recall == 0.8

    def test_to_markdown(self):
        """Test markdown generation."""
        metrics_by_threshold = {
            0.8: EvalMetrics(
                total_samples=10,
                excluded_samples=0,
                exclusion_rate=0.0,
                true_positives=7,
                false_positives=1,
                no_matches=2,
                recall=0.7,
                precision=0.875,
                fp_rate=0.1,
                threshold=0.8,
            ),
        }

        summary = EvalSummary.find_best(metrics_by_threshold, "test")
        md = summary.to_markdown()

        assert "# Semantic Matcher Evaluation Report" in md
        assert "Best Threshold" in md
        assert "0.8" in md


class TestExtractor:
    """Tests for sample extraction."""

    def test_extract_world_objects(self, tmp_path):
        """Test extracting world objects from canonical."""
        world_data = {
            "props": {
                "マグカップ": {"location": "キッチン"},
                "コーヒーメーカー": {"location": "キッチン"},
                "ソファ": {"location": "リビング"},
            }
        }

        world_path = tmp_path / "world_canonical.json"
        with open(world_path, "w", encoding="utf-8") as f:
            json.dump(world_data, f)

        objects = extract_world_objects(world_path)

        assert "マグカップ" in objects
        assert "コーヒーメーカー" in objects
        assert "ソファ" in objects
        assert len(objects) == 3

    def test_infer_ground_truth_substring(self):
        """Test GT inference from substring matching."""
        world_objects = {"マグカップ", "コーヒーメーカー", "テレビ"}
        turn = {}

        # Query is substring of world object
        gt = _infer_ground_truth("カップ", turn, world_objects)
        assert gt == "マグカップ"

        # World object is substring of query
        gt = _infer_ground_truth("大きなテレビ", turn, world_objects)
        assert gt == "テレビ"

    def test_infer_ground_truth_from_resolved_target(self):
        """Test GT inference from resolved_target field."""
        world_objects = {"本棚", "ソファ"}
        turn = {"resolved_target": "本棚"}

        gt = _infer_ground_truth("棚", turn, world_objects)
        assert gt == "本棚"

    def test_deduplicate_samples(self):
        """Test sample deduplication."""
        sample1 = MissingObjectSample(
            sample_id="s1",
            run_path=Path("/tmp"),
            session_id="sess",
            turn_number=1,
            query="カップ",
            world_objects=set(),
            scenario="test",
            speaker="あゆ",
        )

        sample2 = MissingObjectSample(
            sample_id="s1",  # Same ID
            run_path=Path("/tmp"),
            session_id="sess",
            turn_number=1,
            query="カップ",
            world_objects=set(),
            scenario="test",
            speaker="あゆ",
        )

        sample3 = MissingObjectSample(
            sample_id="s2",  # Different ID
            run_path=Path("/tmp"),
            session_id="sess",
            turn_number=2,
            query="グラス",
            world_objects=set(),
            scenario="test",
            speaker="やな",
        )

        unique = deduplicate_samples([sample1, sample2, sample3])

        assert len(unique) == 2
        assert {s.sample_id for s in unique} == {"s1", "s2"}

    def test_filter_samples_with_gt(self):
        """Test filtering by GT availability."""
        with_gt = MissingObjectSample(
            sample_id="s1",
            run_path=Path("/tmp"),
            session_id="sess",
            turn_number=1,
            query="カップ",
            world_objects=set(),
            scenario="test",
            speaker="あゆ",
            ground_truth="マグカップ",
        )

        without_gt = MissingObjectSample(
            sample_id="s2",
            run_path=Path("/tmp"),
            session_id="sess",
            turn_number=2,
            query="不明",
            world_objects=set(),
            scenario="test",
            speaker="やな",
            ground_truth=None,
        )

        gt_samples, no_gt_samples = filter_samples_with_gt([with_gt, without_gt])

        assert len(gt_samples) == 1
        assert len(no_gt_samples) == 1
        assert gt_samples[0].sample_id == "s1"
        assert no_gt_samples[0].sample_id == "s2"


class TestEvaluator:
    """Tests for evaluation engine."""

    def test_evaluate_single_query(self):
        """Test single query evaluation."""
        world_objects = {"マグカップ", "ティーカップ", "コーヒーメーカー"}

        match, score, candidates = evaluate_single_query(
            "カップ", world_objects, threshold=0.7
        )

        # Should match something with "カップ" in it
        assert match is not None
        assert score >= 0.7
        assert len(candidates) > 0

    def test_evaluate_single_query_no_match(self):
        """Test query with no match."""
        world_objects = {"本棚", "ソファ", "テレビ"}

        match, score, candidates = evaluate_single_query(
            "コーヒー", world_objects, threshold=0.7
        )

        # No good match expected
        if match is None:
            assert score == 0.0
        else:
            # If there was a match, verify it's above threshold
            assert score >= 0.7

    def test_evaluate_sample_true_positive(self):
        """Test evaluation resulting in true positive."""
        sample = MissingObjectSample(
            sample_id="test",
            run_path=Path("/tmp"),
            session_id="sess",
            turn_number=1,
            query="カップ",
            world_objects={"マグカップ", "テレビ"},
            scenario="test",
            speaker="あゆ",
            ground_truth="マグカップ",
        )

        matcher = FuzzyMatcher(suggest_threshold=0.5, allow_auto_adopt=False)
        result = evaluate_sample(sample, matcher, threshold=0.5)

        # "カップ" should match "マグカップ"
        assert result.top_candidate == "マグカップ"
        assert result.is_true_positive is True
        assert result.is_false_positive is False
        assert result.gt_in_candidates is True

    def test_evaluate_samples_at_threshold(self):
        """Test batch evaluation at threshold."""
        samples = [
            MissingObjectSample(
                sample_id="s1",
                run_path=Path("/tmp"),
                session_id="sess",
                turn_number=1,
                query="カップ",
                world_objects={"マグカップ", "テレビ"},
                scenario="test",
                speaker="あゆ",
                ground_truth="マグカップ",
            ),
            MissingObjectSample(
                sample_id="s2",
                run_path=Path("/tmp"),
                session_id="sess",
                turn_number=2,
                query="テレビ画面",
                world_objects={"マグカップ", "テレビ"},
                scenario="test",
                speaker="やな",
                ground_truth="テレビ",
            ),
        ]

        results, excluded = evaluate_samples_at_threshold(samples, threshold=0.5)

        assert len(results) == 2
        assert excluded == 0

    def test_run_evaluation_threshold_grid(self, tmp_path):
        """Test full evaluation with threshold grid."""
        samples = [
            MissingObjectSample(
                sample_id="s1",
                run_path=Path("/tmp"),
                session_id="sess",
                turn_number=1,
                query="カップ",
                world_objects={"マグカップ", "コーヒーメーカー"},
                scenario="test",
                speaker="あゆ",
                ground_truth="マグカップ",
            ),
        ]

        summary = run_evaluation(
            samples=samples,
            threshold_grid=[0.5, 0.7, 0.9],
            output_dir=tmp_path,
            input_source="test",
        )

        assert len(summary.threshold_grid) == 3
        assert 0.5 in summary.metrics_by_threshold
        assert 0.7 in summary.metrics_by_threshold
        assert 0.9 in summary.metrics_by_threshold

        # Audit log should exist
        audit_path = tmp_path / "audit.jsonl"
        assert audit_path.exists()


class TestIntegration:
    """Integration tests for the full pipeline."""

    def test_full_pipeline_with_mock_data(self, tmp_path):
        """Test full extraction and evaluation pipeline."""
        # Create mock run directory structure
        run_dir = tmp_path / "gm_test_run"
        run_dir.mkdir()

        # Create artifacts directory
        artifacts_dir = run_dir / "artifacts" / "session_001"
        artifacts_dir.mkdir(parents=True)

        # Create world_canonical.json
        world_data = {
            "props": {
                "マグカップ": {"location": "キッチン"},
                "コーヒーメーカー": {"location": "キッチン"},
                "ソファ": {"location": "リビング"},
            }
        }
        with open(artifacts_dir / "world_canonical.json", "w", encoding="utf-8") as f:
            json.dump(world_data, f)

        # Create turns_log.json with invented objects
        turns = [
            {
                "session_id": "session_001",
                "scenario": "coffee_trap",
                "turn_number": 1,
                "speaker": "あゆ",
                "denied_reason": None,
                "invented_objects": ["コップ"],  # Should match マグカップ
                "invented_reasons": {"コップ": "not_in_world"},
                "blocked_target_before": None,
                "blocked_target_after": None,
                "marker_targets_before": ["コップ"],
                "marker_targets_after": ["マグカップ"],
                "resolved_target": "マグカップ",
            }
        ]
        with open(run_dir / "turns_log.json", "w", encoding="utf-8") as f:
            json.dump(turns, f)

        # Extract samples
        samples = extract_samples_from_run(run_dir)

        assert len(samples) == 1
        assert samples[0].query == "コップ"
        assert samples[0].ground_truth == "マグカップ"  # Inferred from resolved_target
        assert "マグカップ" in samples[0].world_objects

        # Run evaluation
        output_dir = tmp_path / "eval_output"
        summary = run_evaluation(
            samples=samples,
            threshold_grid=[0.5, 0.7],
            output_dir=output_dir,
            input_source="test_run",
        )

        assert summary.best_metrics.total_samples == 1
        # Should be true positive since コップ matches マグカップ
        assert summary.best_metrics.true_positives == 1
        assert (output_dir / "audit.jsonl").exists()
