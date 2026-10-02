"""Tests for idempotent chunk ingestion decisions."""

from ingest.chunking import PreparedChunk
from ingest.pipeline import chunk_is_current, stored_embedding_dimensions


def test_chunk_is_current_when_hashes_and_embedding_config_match() -> None:
    chunk = PreparedChunk(
        chunk_index=0,
        content="Item 1. Business\n\nExample",
        token_count=8,
        page_number=None,
        section="Item 1. Business",
        metadata={
            "content_hash": "content-hash",
            "chunking_config_hash": "config-hash",
        },
    )
    existing = {
        "metadata": {
            "content_hash": "content-hash",
            "chunking_config_hash": "config-hash",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimensions": 1536,
        }
    }

    assert chunk_is_current(chunk, existing) is True


def test_chunk_is_not_current_when_content_changed() -> None:
    chunk = PreparedChunk(
        chunk_index=0,
        content="Changed",
        token_count=1,
        page_number=None,
        section=None,
        metadata={
            "content_hash": "new-hash",
            "chunking_config_hash": "config-hash",
        },
    )
    existing = {
        "metadata": {
            "content_hash": "old-hash",
            "chunking_config_hash": "config-hash",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimensions": 1536,
        }
    }

    assert chunk_is_current(chunk, existing) is False


def test_stored_embedding_dimensions_accepts_postgrest_vector_string() -> None:
    assert stored_embedding_dimensions("[0.1,0.2,0.3]") == 3


def test_stored_embedding_dimensions_accepts_list() -> None:
    assert stored_embedding_dimensions([0.1, 0.2, 0.3]) == 3
