"""Tests for Reciprocal Rank Fusion."""

from uuid import UUID

import pytest

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import RankedChunk

CHUNK_A = UUID("00000000-0000-0000-0000-000000000001")
CHUNK_B = UUID("00000000-0000-0000-0000-000000000002")
CHUNK_C = UUID("00000000-0000-0000-0000-000000000003")
DOCUMENT = UUID("10000000-0000-0000-0000-000000000001")


def result(chunk_id: UUID, score: float = 1.0) -> RankedChunk:
    return RankedChunk(chunk_id, DOCUMENT, 0, score)


def test_result_in_both_rankings_wins() -> None:
    fused = reciprocal_rank_fusion(
        [[result(CHUNK_A), result(CHUNK_B)], [result(CHUNK_C), result(CHUNK_B)]]
    )

    assert [item.chunk_id for item in fused] == [CHUNK_B, CHUNK_A, CHUNK_C]
    assert fused[0].score == pytest.approx(2 / 62)


def test_duplicate_in_one_ranking_counts_once() -> None:
    fused = reciprocal_rank_fusion(
        [[result(CHUNK_A), result(CHUNK_A)], [result(CHUNK_B)]]
    )

    assert fused[0].score == pytest.approx(1 / 61)
    assert fused[1].score == pytest.approx(1 / 61)


def test_ties_use_first_seen_order_without_mutating_inputs() -> None:
    ranking = [result(CHUNK_B), result(CHUNK_A)]
    original = list(ranking)

    fused = reciprocal_rank_fusion([ranking, [result(CHUNK_A), result(CHUNK_B)]])

    assert [item.chunk_id for item in fused] == [CHUNK_B, CHUNK_A]
    assert ranking == original


def test_empty_rankings_return_empty_result() -> None:
    assert reciprocal_rank_fusion([[], []]) == []


def test_non_positive_k_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        reciprocal_rank_fusion([], k=0)
