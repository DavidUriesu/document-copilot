"""Rank-only fusion for independently scored retrieval channels."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.retrieval.models import FusedChunk, RankedChunk

RRF_K = 60


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[RankedChunk]],
    k: int = RRF_K,
) -> list[FusedChunk]:
    """Fuse rankings without comparing their incompatible raw scores."""
    if k < 1:
        raise ValueError("RRF k must be positive")

    scores: dict[UUID, float] = {}
    first_seen: dict[UUID, int] = {}

    for ranking in rankings:
        seen_in_ranking: set[UUID] = set()
        for rank, result in enumerate(ranking, start=1):
            if result.chunk_id in seen_in_ranking:
                continue
            seen_in_ranking.add(result.chunk_id)
            first_seen.setdefault(result.chunk_id, len(first_seen))
            scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + (
                1.0 / (k + rank)
            )

    ordered_ids = sorted(
        scores,
        key=lambda chunk_id: (-scores[chunk_id], first_seen[chunk_id]),
    )
    return [FusedChunk(chunk_id, scores[chunk_id]) for chunk_id in ordered_ids]
