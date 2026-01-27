"""Tests for Semantic Matcher Preprocessor.

TDD tests for query expansion and normalization.
"""

import pytest

from experiments.semantic_matcher.preprocess import (
    expand_queries,
    normalize_query,
    extract_x_no_y_pattern,
)


class TestExtractXNoYPattern:
    """Tests for 「XのY」pattern extraction."""

    def test_basic_x_no_y(self):
        """Test basic 'XのY' pattern."""
        result = extract_x_no_y_pattern("冷蔵庫の牛乳")
        assert result == ("冷蔵庫", "牛乳")

    def test_television_remote(self):
        """Test 'テレビのリモコン' pattern."""
        result = extract_x_no_y_pattern("テレビのリモコン")
        assert result == ("テレビ", "リモコン")

    def test_bookshelf_book(self):
        """Test 'XのY' with longer Y."""
        result = extract_x_no_y_pattern("本棚の植物図鑑")
        assert result == ("本棚", "植物図鑑")

    def test_no_pattern(self):
        """Test string without 'の' pattern."""
        result = extract_x_no_y_pattern("冷蔵庫")
        assert result is None

    def test_multiple_no(self):
        """Test string with multiple 'の'."""
        # Should extract first X and remaining Y
        result = extract_x_no_y_pattern("冷蔵庫の牛乳のパック")
        assert result == ("冷蔵庫", "牛乳のパック")

    def test_empty_x_or_y(self):
        """Test edge case with empty X or Y."""
        result = extract_x_no_y_pattern("の牛乳")
        assert result is None

        result = extract_x_no_y_pattern("冷蔵庫の")
        assert result is None


class TestNormalizeQuery:
    """Tests for query normalization."""

    def test_strip_whitespace(self):
        """Test whitespace stripping."""
        assert normalize_query("  冷蔵庫  ") == "冷蔵庫"

    def test_normalize_quotes(self):
        """Test quote removal."""
        assert normalize_query("「冷蔵庫」") == "冷蔵庫"
        assert normalize_query("『本棚』") == "本棚"

    def test_normalize_punctuation(self):
        """Test punctuation removal."""
        assert normalize_query("冷蔵庫。") == "冷蔵庫"
        assert normalize_query("テレビ、") == "テレビ"

    def test_preserve_core(self):
        """Test that core object name is preserved."""
        assert normalize_query("マグカップ") == "マグカップ"


class TestExpandQueries:
    """Tests for query expansion."""

    def test_simple_query_no_expansion(self):
        """Test simple query returns itself."""
        result = expand_queries("冷蔵庫")
        assert "冷蔵庫" in result
        assert len(result) == 1

    def test_x_no_y_expansion(self):
        """Test 'XのY' expands to X and Y."""
        result = expand_queries("冷蔵庫の牛乳")
        assert "冷蔵庫" in result
        assert "牛乳" in result

    def test_television_remote_expansion(self):
        """Test 'テレビのリモコン' expansion."""
        result = expand_queries("テレビのリモコン")
        assert "テレビ" in result
        assert "リモコン" in result

    def test_long_query_truncation(self):
        """Test long queries are handled."""
        long_query = "ソファーに深く腰掛け、少し間をおいてから"
        result = expand_queries(long_query)
        # Should still produce some candidates
        assert len(result) >= 1
        # Original might be excluded if too long
        # But we should have at least a normalized version

    def test_complex_query(self):
        """Test complex query with multiple patterns."""
        result = expand_queries("本棚の植物図鑑らしき本")
        assert "本棚" in result

    def test_expansion_order(self):
        """Test that X comes before Y in expansion."""
        result = expand_queries("冷蔵庫の牛乳")
        # X should be prioritized (likely to be the container)
        assert result.index("冷蔵庫") < result.index("牛乳")

    def test_deduplication(self):
        """Test duplicate queries are removed."""
        result = expand_queries("冷蔵庫の冷蔵庫")
        assert result.count("冷蔵庫") == 1

    def test_empty_query(self):
        """Test empty query handling."""
        result = expand_queries("")
        assert result == []

    def test_whitespace_only(self):
        """Test whitespace-only query."""
        result = expand_queries("   ")
        assert result == []


class TestExpandQueriesWithWorldObjects:
    """Tests for expansion with world_objects filtering."""

    def test_filter_by_world_objects(self):
        """Test that non-world objects can be filtered."""
        world_objects = {"冷蔵庫", "テレビ", "ソファ"}
        result = expand_queries("冷蔵庫の牛乳", world_objects=world_objects)

        # 冷蔵庫 is in world, should be included
        assert "冷蔵庫" in result
        # 牛乳 is NOT in world, should be excluded
        assert "牛乳" not in result

    def test_sister_bag_guard(self):
        """Test '姉のカバン' doesn't suggest '姉' if not in world."""
        world_objects = {"カバン", "バッグ"}
        result = expand_queries("姉のカバン", world_objects=world_objects)

        # 姉 is not an object, should not be suggested
        assert "姉" not in result
        # カバン is in world
        assert "カバン" in result

    def test_no_world_filter_returns_all(self):
        """Test that without world_objects, all expansions are returned."""
        result = expand_queries("冷蔵庫の牛乳", world_objects=None)
        assert "冷蔵庫" in result
        assert "牛乳" in result


class TestEdgeCases:
    """Edge case tests."""

    def test_action_description_filtered(self):
        """Test action descriptions are handled."""
        # This is an action description, not an object name
        result = expand_queries("ソファーに深く腰掛け")
        # Should extract potential object names
        # ソファー should be a candidate
        candidates = [q for q in result if "ソファ" in q]
        assert len(candidates) >= 1

    def test_partial_match_variant(self):
        """Test ソファー vs ソファ handling."""
        result = expand_queries("ソファーに座る")
        # Should normalize ソファー to ソファ if needed
        # Or include both variants
        assert any("ソファ" in q for q in result)

    def test_movement_description(self):
        """Test movement descriptions."""
        result = expand_queries("冷蔵庫へ向かい、レタス")
        # Should extract 冷蔵庫 as potential object
        assert "冷蔵庫" in result

    def test_cardboard_box_example(self):
        """Test long example from real data."""
        query = "段ボール箱の中から、少し色褪せた古いオルゴール"
        result = expand_queries(query)
        # Should extract 段ボール箱
        assert "段ボール箱" in result
