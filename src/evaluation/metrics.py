"""対話品質メトリクス定義"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DialogueQualityMetrics:
    """対話品質の多次元評価メトリクス"""
    
    # キャラクター一貫性 (0.0-1.0)
    character_consistency: float
    
    # 話題の新規性 (0.0-1.0)
    topic_novelty: float
    
    # 姉妹らしい関係性 (0.0-1.0)
    relationship_quality: float
    
    # 対話の自然さ (0.0-1.0)
    naturalness: float
    
    # 情報の具体性 (0.0-1.0)
    concreteness: float
    
    # 総合スコア (重み付け平均)
    overall_score: float = 0.0
    
    # 検出された問題点
    issues: List[str] = field(default_factory=list)
    
    # 良かった点
    strengths: Optional[List[str]] = None
    
    # 改善提案
    suggestions: Optional[List[str]] = None
    
    def __post_init__(self):
        """総合スコアを自動計算"""
        if self.overall_score == 0:  # 未設定の場合
            self.overall_score = (
                self.character_consistency * 0.25 +
                self.topic_novelty * 0.20 +
                self.relationship_quality * 0.25 +
                self.naturalness * 0.15 +
                self.concreteness * 0.15
            )
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "character_consistency": self.character_consistency,
            "topic_novelty": self.topic_novelty,
            "relationship_quality": self.relationship_quality,
            "naturalness": self.naturalness,
            "concreteness": self.concreteness,
            "overall_score": self.overall_score,
            "issues": self.issues,
            "strengths": self.strengths or [],
            "suggestions": self.suggestions or []
        }
