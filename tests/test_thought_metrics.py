"""Tests for thought metrics calculator (Phase 2.3+)"""

import pytest

from evaluation.thought_metrics import (
    ThoughtMetrics,
    ThoughtMetricsCalculator,
    CharacterProfile,
)


class TestCharacterProfile:
    """Tests for CharacterProfile dataclass"""

    def test_creates_profile(self):
        """Can create character profile"""
        profile = CharacterProfile(speaker="やな")
        assert profile.speaker == "やな"
        assert profile.total_thoughts == 0

    def test_missing_rate(self):
        """Calculates missing rate correctly"""
        profile = CharacterProfile(
            speaker="やな",
            total_thoughts=10,
            missing_count=2,
        )
        assert profile.missing_rate == 0.2

    def test_missing_rate_zero_thoughts(self):
        """Missing rate is 0 when no thoughts"""
        profile = CharacterProfile(speaker="やな")
        assert profile.missing_rate == 0.0

    def test_dominant_emotion(self):
        """Returns dominant emotion"""
        profile = CharacterProfile(
            speaker="やな",
            emotion_distribution={"JOY": 5, "WORRY": 2, "NEUTRAL": 3},
        )
        assert profile.dominant_emotion == "JOY"

    def test_dominant_emotion_empty(self):
        """Returns NEUTRAL when no emotions"""
        profile = CharacterProfile(speaker="やな")
        assert profile.dominant_emotion == "NEUTRAL"


class TestThoughtMetrics:
    """Tests for ThoughtMetrics dataclass"""

    def test_creates_metrics(self):
        """Can create metrics"""
        metrics = ThoughtMetrics()
        assert metrics.total_thoughts == 0
        assert metrics.quality_score == 0.0

    def test_to_dict(self):
        """Can convert to dictionary"""
        metrics = ThoughtMetrics(
            total_thoughts=10,
            missing_rate=0.1,
            avg_length=50.0,
            quality_score=0.8,
        )
        d = metrics.to_dict()

        assert d["total_thoughts"] == 10
        assert d["missing_rate"] == 0.1
        assert d["avg_length"] == 50.0
        assert d["quality_score"] == 0.8


class TestThoughtMetricsCalculator:
    """Tests for ThoughtMetricsCalculator"""

    @pytest.fixture
    def calculator(self):
        """Create calculator with default settings"""
        return ThoughtMetricsCalculator()

    @pytest.fixture
    def sample_entries(self):
        """Create sample log entries"""
        return [
            {
                "speaker": "やな",
                "thought": "今日も元気に頑張ろう！",
                "thought_length": 12,
                "thought_missing": False,
                "emotion": "JOY",
                "emotion_intensity": 0.8,
                "relationship_tone": "SUPPORTIVE",
            },
            {
                "speaker": "あゆ",
                "thought": "姉様は相変わらず騒がしい...",
                "thought_length": 15,
                "thought_missing": False,
                "emotion": "SKEPTICAL",
                "emotion_intensity": 0.5,
                "relationship_tone": "TEASING",
            },
            {
                "speaker": "やな",
                "thought": "あゆが心配だな...",
                "thought_length": 10,
                "thought_missing": False,
                "emotion": "WORRY",
                "emotion_intensity": 0.6,
                "relationship_tone": "SUPPORTIVE",
            },
            {
                "speaker": "あゆ",
                "thought": "まあ、姉様も悪くない",
                "thought_length": 11,
                "thought_missing": False,
                "emotion": "TRUST",
                "emotion_intensity": 0.4,
                "relationship_tone": "NEUTRAL",
            },
        ]

    def test_empty_entries(self, calculator):
        """Returns empty metrics for empty entries"""
        metrics = calculator.calculate([])
        assert metrics.total_thoughts == 0
        assert metrics.quality_score == 0.0

    def test_basic_metrics(self, calculator, sample_entries):
        """Calculates basic metrics correctly"""
        metrics = calculator.calculate(sample_entries)

        assert metrics.total_thoughts == 4
        assert metrics.missing_count == 0
        assert metrics.missing_rate == 0.0
        assert metrics.avg_length == 12.0  # (12+15+10+11)/4
        assert metrics.min_length == 10
        assert metrics.max_length == 15

    def test_missing_rate(self, calculator):
        """Calculates missing rate correctly"""
        entries = [
            {"speaker": "やな", "thought_length": 10, "thought_missing": False},
            {"speaker": "あゆ", "thought_length": 0, "thought_missing": True},
            {"speaker": "やな", "thought_length": 15, "thought_missing": False},
            {"speaker": "あゆ", "thought_length": 0, "thought_missing": True},
        ]
        metrics = calculator.calculate(entries)

        assert metrics.missing_count == 2
        assert metrics.missing_rate == 0.5

    def test_emotion_diversity(self, calculator, sample_entries):
        """Calculates emotion diversity correctly"""
        metrics = calculator.calculate(sample_entries)

        # 4 unique emotions in 4 entries
        assert metrics.emotion_diversity == 1.0

    def test_neutral_rate(self, calculator):
        """Calculates neutral rate correctly"""
        entries = [
            {"speaker": "やな", "emotion": "NEUTRAL"},
            {"speaker": "あゆ", "emotion": "NEUTRAL"},
            {"speaker": "やな", "emotion": "JOY"},
            {"speaker": "あゆ", "emotion": "NEUTRAL"},
        ]
        metrics = calculator.calculate(entries)

        assert metrics.neutral_rate == 0.75

    def test_high_intensity_rate(self, calculator):
        """Calculates high intensity rate correctly"""
        entries = [
            {"speaker": "やな", "emotion_intensity": 0.9},
            {"speaker": "あゆ", "emotion_intensity": 0.5},
            {"speaker": "やな", "emotion_intensity": 0.8},
            {"speaker": "あゆ", "emotion_intensity": 0.3},
        ]
        metrics = calculator.calculate(entries)

        # 2 entries with intensity > 0.7
        assert metrics.high_intensity_rate == 0.5

    def test_character_profiles(self, calculator, sample_entries):
        """Calculates per-character profiles"""
        metrics = calculator.calculate(sample_entries)

        assert "やな" in metrics.character_profiles
        assert "あゆ" in metrics.character_profiles

        yana = metrics.character_profiles["やな"]
        assert yana.total_thoughts == 2
        assert yana.speaker == "やな"

        ayu = metrics.character_profiles["あゆ"]
        assert ayu.total_thoughts == 2
        assert ayu.speaker == "あゆ"

    def test_character_emotion_distribution(self, calculator, sample_entries):
        """Tracks emotion distribution per character"""
        metrics = calculator.calculate(sample_entries)

        yana = metrics.character_profiles["やな"]
        assert "JOY" in yana.emotion_distribution
        assert "WORRY" in yana.emotion_distribution

        ayu = metrics.character_profiles["あゆ"]
        assert "SKEPTICAL" in ayu.emotion_distribution
        assert "TRUST" in ayu.emotion_distribution

    def test_quality_score_range(self, calculator, sample_entries):
        """Quality score is between 0 and 1"""
        metrics = calculator.calculate(sample_entries)

        assert 0.0 <= metrics.quality_score <= 1.0

    def test_quality_score_high_for_good_data(self, calculator):
        """High quality score for good data"""
        # Create good quality data
        entries = [
            {
                "speaker": "やな",
                "thought": "x" * 80,  # Good length
                "thought_length": 80,
                "thought_missing": False,
                "emotion": "JOY",
                "emotion_intensity": 0.7,
            },
            {
                "speaker": "あゆ",
                "thought": "y" * 80,
                "thought_length": 80,
                "thought_missing": False,
                "emotion": "SKEPTICAL",
                "emotion_intensity": 0.5,
            },
        ]
        metrics = calculator.calculate(entries)

        # Should have reasonably high score
        assert metrics.quality_score >= 0.5

    def test_quality_score_low_for_bad_data(self, calculator):
        """Low quality score for bad data"""
        # Create poor quality data
        entries = [
            {
                "speaker": "やな",
                "thought": "",
                "thought_length": 0,
                "thought_missing": True,
                "emotion": "NEUTRAL",
                "emotion_intensity": 0.0,
            },
            {
                "speaker": "あゆ",
                "thought": "",
                "thought_length": 0,
                "thought_missing": True,
                "emotion": "NEUTRAL",
                "emotion_intensity": 0.0,
            },
        ]
        metrics = calculator.calculate(entries)

        # Should have low score
        assert metrics.quality_score < 0.5

    def test_custom_targets(self):
        """Can use custom targets"""
        calculator = ThoughtMetricsCalculator(
            missing_rate_target=0.05,  # 5%
            avg_length_target=50.0,  # 50 chars
            neutral_rate_max=0.30,  # 30%
        )

        entries = [
            {"speaker": "やな", "thought_length": 50, "thought_missing": False},
        ]
        metrics = calculator.calculate(entries)

        # Should work with custom targets
        assert metrics.total_thoughts == 1


class TestProfileMatch:
    """Tests for character profile matching"""

    @pytest.fixture
    def calculator(self):
        return ThoughtMetricsCalculator()

    def test_yana_good_profile(self, calculator):
        """Yana with expected emotion profile scores well"""
        # Create entries matching やな's expected profile
        entries = []
        # JOY: 40% (expected 30-50%)
        for _ in range(4):
            entries.append({"speaker": "やな", "emotion": "JOY", "thought_length": 50})
        # WORRY: 15% (expected 10-20%)
        for _ in range(2):
            entries.append({"speaker": "やな", "emotion": "WORRY", "thought_length": 50})
        # CONFIDENCE: 15% (expected 10-20%)
        for _ in range(1):
            entries.append({"speaker": "やな", "emotion": "CONFIDENCE", "thought_length": 50})
        # NEUTRAL: 15% (expected ≤20%)
        for _ in range(2):
            entries.append({"speaker": "やな", "emotion": "NEUTRAL", "thought_length": 50})
        # Other: 15%
        for _ in range(1):
            entries.append({"speaker": "やな", "emotion": "SURPRISE", "thought_length": 50})

        metrics = calculator.calculate(entries)
        # Profile should match reasonably well
        assert metrics.quality_score > 0.3

    def test_ayu_good_profile(self, calculator):
        """Ayu with expected emotion profile scores well"""
        entries = []
        # SKEPTICAL: 30% (expected 20-40%)
        for _ in range(3):
            entries.append({"speaker": "あゆ", "emotion": "SKEPTICAL", "thought_length": 50})
        # NEUTRAL: 25% (expected 20-30%)
        for _ in range(2):
            entries.append({"speaker": "あゆ", "emotion": "NEUTRAL", "thought_length": 50})
        # TRUST: 15% (expected 10-20%)
        for _ in range(2):
            entries.append({"speaker": "あゆ", "emotion": "TRUST", "thought_length": 50})
        # ANNOYANCE: 15% (expected 10-20%)
        for _ in range(1):
            entries.append({"speaker": "あゆ", "emotion": "ANNOYANCE", "thought_length": 50})
        # Other: 15%
        for _ in range(2):
            entries.append({"speaker": "あゆ", "emotion": "SURPRISE", "thought_length": 50})

        metrics = calculator.calculate(entries)
        assert metrics.quality_score > 0.3
