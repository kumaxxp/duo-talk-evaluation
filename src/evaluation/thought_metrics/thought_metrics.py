"""Thought log metrics calculator (Phase 2.3+)

Calculates quality metrics from ThoughtLogger data.

Metrics:
- Basic: missing_rate, avg_length, min_length
- Character: per-character stats, balance
- Emotion: diversity, distribution, intensity
- Quality score: Overall 0.0-1.0 score
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CharacterProfile:
    """Per-character thought statistics

    Attributes:
        speaker: Character name
        total_thoughts: Total thought count
        missing_count: Missing thought count
        avg_length: Average thought length
        min_length: Minimum thought length
        max_length: Maximum thought length
        emotion_distribution: Emotion frequency dict
        avg_intensity: Average emotion intensity
        tone_distribution: Relationship tone frequency dict
    """

    speaker: str
    total_thoughts: int = 0
    missing_count: int = 0
    avg_length: float = 0.0
    min_length: int = 0
    max_length: int = 0
    emotion_distribution: dict = field(default_factory=dict)
    avg_intensity: float = 0.0
    tone_distribution: dict = field(default_factory=dict)

    @property
    def missing_rate(self) -> float:
        if self.total_thoughts == 0:
            return 0.0
        return self.missing_count / self.total_thoughts

    @property
    def dominant_emotion(self) -> str:
        if not self.emotion_distribution:
            return "NEUTRAL"
        return max(self.emotion_distribution.items(), key=lambda x: x[1])[0]


@dataclass
class ThoughtMetrics:
    """Aggregated thought metrics

    Attributes:
        total_thoughts: Total thought count
        missing_count: Missing thought count
        missing_rate: Missing rate (0.0-1.0)
        avg_length: Average thought length
        min_length: Minimum thought length
        max_length: Maximum thought length
        emotion_diversity: Unique emotions / total thoughts
        neutral_rate: NEUTRAL emotion rate
        high_intensity_rate: High intensity (>0.7) rate
        character_profiles: Per-character profiles
        quality_score: Overall quality score (0.0-1.0)
    """

    total_thoughts: int = 0
    missing_count: int = 0
    missing_rate: float = 0.0
    avg_length: float = 0.0
    min_length: int = 0
    max_length: int = 0
    emotion_diversity: float = 0.0
    neutral_rate: float = 0.0
    high_intensity_rate: float = 0.0
    character_profiles: dict = field(default_factory=dict)
    quality_score: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "total_thoughts": self.total_thoughts,
            "missing_count": self.missing_count,
            "missing_rate": self.missing_rate,
            "avg_length": self.avg_length,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "emotion_diversity": self.emotion_diversity,
            "neutral_rate": self.neutral_rate,
            "high_intensity_rate": self.high_intensity_rate,
            "quality_score": self.quality_score,
            "character_profiles": {
                k: {
                    "speaker": v.speaker,
                    "total_thoughts": v.total_thoughts,
                    "missing_count": v.missing_count,
                    "avg_length": v.avg_length,
                    "dominant_emotion": v.dominant_emotion,
                }
                for k, v in self.character_profiles.items()
            },
        }


# Expected emotion profiles per character
YANA_EXPECTED_EMOTIONS = {
    "JOY": (0.30, 0.50),  # (min, max) expected rate
    "WORRY": (0.10, 0.20),
    "CONFIDENCE": (0.10, 0.20),
    "NEUTRAL": (0.00, 0.20),
}

AYU_EXPECTED_EMOTIONS = {
    "SKEPTICAL": (0.20, 0.40),
    "NEUTRAL": (0.20, 0.30),
    "TRUST": (0.10, 0.20),
    "ANNOYANCE": (0.10, 0.20),
}


class ThoughtMetricsCalculator:
    """Calculator for thought log metrics

    Usage:
        calculator = ThoughtMetricsCalculator()
        metrics = calculator.calculate(entries)
        print(f"Quality Score: {metrics.quality_score:.2f}")
    """

    def __init__(
        self,
        missing_rate_target: float = 0.01,
        avg_length_target: float = 80.0,
        neutral_rate_max: float = 0.50,
    ):
        """Initialize calculator with targets

        Args:
            missing_rate_target: Target missing rate (default: 1%)
            avg_length_target: Target average length (default: 80 chars)
            neutral_rate_max: Maximum acceptable NEUTRAL rate (default: 50%)
        """
        self.missing_rate_target = missing_rate_target
        self.avg_length_target = avg_length_target
        self.neutral_rate_max = neutral_rate_max

    def calculate(self, entries: list[dict]) -> ThoughtMetrics:
        """Calculate metrics from log entries

        Args:
            entries: List of thought log entries (as dicts)

        Returns:
            ThoughtMetrics with all calculated values
        """
        if not entries:
            return ThoughtMetrics()

        metrics = ThoughtMetrics()
        metrics.total_thoughts = len(entries)

        # Basic metrics
        lengths = []
        emotions = []
        intensities = []
        character_data: dict[str, list] = {}

        for entry in entries:
            # Missing check
            if entry.get("thought_missing", False):
                metrics.missing_count += 1

            # Length
            length = entry.get("thought_length", 0)
            lengths.append(length)

            # Emotion
            emotion = entry.get("emotion", "NEUTRAL")
            emotions.append(emotion)

            intensity = entry.get("emotion_intensity", 0.0)
            intensities.append(intensity)

            # Character grouping
            speaker = entry.get("speaker", "unknown")
            if speaker not in character_data:
                character_data[speaker] = []
            character_data[speaker].append(entry)

        # Calculate aggregates
        metrics.missing_rate = metrics.missing_count / metrics.total_thoughts
        metrics.avg_length = sum(lengths) / len(lengths) if lengths else 0.0
        metrics.min_length = min(lengths) if lengths else 0
        metrics.max_length = max(lengths) if lengths else 0

        # Emotion metrics
        unique_emotions = set(emotions)
        metrics.emotion_diversity = len(unique_emotions) / metrics.total_thoughts

        neutral_count = sum(1 for e in emotions if e == "NEUTRAL")
        metrics.neutral_rate = neutral_count / metrics.total_thoughts

        high_intensity_count = sum(1 for i in intensities if i > 0.7)
        metrics.high_intensity_rate = high_intensity_count / metrics.total_thoughts

        # Character profiles
        for speaker, char_entries in character_data.items():
            profile = self._calculate_character_profile(speaker, char_entries)
            metrics.character_profiles[speaker] = profile

        # Quality score
        metrics.quality_score = self._calculate_quality_score(metrics)

        return metrics

    def _calculate_character_profile(
        self,
        speaker: str,
        entries: list[dict],
    ) -> CharacterProfile:
        """Calculate profile for a single character"""
        profile = CharacterProfile(speaker=speaker)
        profile.total_thoughts = len(entries)

        if not entries:
            return profile

        # Missing
        profile.missing_count = sum(
            1 for e in entries if e.get("thought_missing", False)
        )

        # Lengths
        lengths = [e.get("thought_length", 0) for e in entries]
        profile.avg_length = sum(lengths) / len(lengths)
        profile.min_length = min(lengths)
        profile.max_length = max(lengths)

        # Emotions
        for entry in entries:
            emotion = entry.get("emotion", "NEUTRAL")
            profile.emotion_distribution[emotion] = (
                profile.emotion_distribution.get(emotion, 0) + 1
            )

        # Intensities
        intensities = [e.get("emotion_intensity", 0.0) for e in entries]
        profile.avg_intensity = sum(intensities) / len(intensities)

        # Tones
        for entry in entries:
            tone = entry.get("relationship_tone", "NEUTRAL")
            profile.tone_distribution[tone] = (
                profile.tone_distribution.get(tone, 0) + 1
            )

        return profile

    def _calculate_quality_score(self, metrics: ThoughtMetrics) -> float:
        """Calculate overall quality score (0.0-1.0)

        Components:
        - Basic quality (40%): missing rate + length
        - Emotion quality (30%): diversity + neutral rate
        - Character consistency (30%): profile match

        Returns:
            Quality score between 0.0 and 1.0
        """
        # Basic quality (40%)
        missing_score = max(0, 1.0 - metrics.missing_rate / self.missing_rate_target)
        missing_score = min(1.0, missing_score)

        length_score = min(1.0, metrics.avg_length / self.avg_length_target)

        basic_score = (missing_score * 0.6 + length_score * 0.4) * 0.4

        # Emotion quality (30%)
        diversity_score = min(1.0, metrics.emotion_diversity / 0.5)

        neutral_penalty = max(0, metrics.neutral_rate - self.neutral_rate_max) * 2
        neutral_penalty = min(1.0, neutral_penalty)

        emotion_score = (diversity_score * 0.7 + (1.0 - neutral_penalty) * 0.3) * 0.3

        # Character consistency (30%)
        profile_score = self._calculate_profile_match(metrics.character_profiles)
        character_score = profile_score * 0.3

        return basic_score + emotion_score + character_score

    def _calculate_profile_match(self, profiles: dict) -> float:
        """Calculate how well character profiles match expectations

        Args:
            profiles: Dict of speaker -> CharacterProfile

        Returns:
            Match score between 0.0 and 1.0
        """
        if not profiles:
            return 0.5  # Neutral score if no data

        scores = []

        # Check やな profile
        if "やな" in profiles:
            yana = profiles["やな"]
            yana_score = self._match_emotion_profile(
                yana.emotion_distribution,
                yana.total_thoughts,
                YANA_EXPECTED_EMOTIONS,
            )
            scores.append(yana_score)

        # Check あゆ profile
        if "あゆ" in profiles:
            ayu = profiles["あゆ"]
            ayu_score = self._match_emotion_profile(
                ayu.emotion_distribution,
                ayu.total_thoughts,
                AYU_EXPECTED_EMOTIONS,
            )
            scores.append(ayu_score)

        if not scores:
            return 0.5

        return sum(scores) / len(scores)

    def _match_emotion_profile(
        self,
        distribution: dict,
        total: int,
        expected: dict,
    ) -> float:
        """Calculate match score for emotion distribution vs expected

        Args:
            distribution: Actual emotion counts
            total: Total count
            expected: Expected ranges {emotion: (min_rate, max_rate)}

        Returns:
            Match score between 0.0 and 1.0
        """
        if total == 0:
            return 0.5

        matches = 0
        checks = 0

        for emotion, (min_rate, max_rate) in expected.items():
            checks += 1
            actual_count = distribution.get(emotion, 0)
            actual_rate = actual_count / total

            if min_rate <= actual_rate <= max_rate:
                matches += 1
            elif actual_rate < min_rate:
                # Partial credit for being close
                matches += actual_rate / min_rate * 0.5
            else:
                # Partial credit for being close
                matches += max(0, 1 - (actual_rate - max_rate) / max_rate) * 0.5

        return matches / checks if checks > 0 else 0.5
