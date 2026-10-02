"""Chunk, embed, and persist the local SEC filing corpus."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from openai import AsyncOpenAI
from postgrest.types import ReturnMethod
from supabase import AsyncClient

from app.config import settings
from app.database.supabase import create_service_role_client
from ingest.chunking import FilingMetadata, PreparedChunk, build_chunks
from ingest.embeddings import create_embeddings

DOCLING_DIR = Path(__file__).resolve().parents[2] / "data" / "docling"
EMBEDDING_BATCH_SIZE = 8
DATABASE_WRITE_ATTEMPTS = 3


@dataclass(frozen=True)
class FilingArtifact:
    path: Path
    metadata: FilingMetadata


def load_filing_artifacts(
    accession_number: str | None = None,
    ticker: str | None = None,
) -> list[FilingArtifact]:
    manifest = json.loads(
        (DOCLING_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    artifacts = []

    for filing in manifest["filings"]:
        if accession_number and filing["accession_number"] != accession_number:
            continue
        if ticker and filing["ticker"] != ticker.upper():
            continue
        metadata = FilingMetadata(
            accession_number=filing["accession_number"],
            ticker=filing["ticker"],
            filing_type=filing["form"],
            fiscal_year=int(filing["report_date"][:4]),
            local_path=filing["local_path"],
        )
        artifacts.append(
            FilingArtifact(path=DOCLING_DIR / filing["local_path"], metadata=metadata)
        )

    if accession_number and not artifacts:
        raise ValueError(f"No filing found for accession {accession_number}")
    return artifacts


def chunk_is_current(
    chunk: PreparedChunk,
    existing: dict[str, Any] | None,
) -> bool:
    if not existing:
        return False
    metadata = existing.get("metadata") or {}
    return (
        metadata.get("content_hash") == chunk.metadata["content_hash"]
        and metadata.get("chunking_config_hash")
        == chunk.metadata["chunking_config_hash"]
        and metadata.get("embedding_model") == settings.openai_embedding_model
        and metadata.get("embedding_dimensions")
        == settings.openai_embedding_dimensions
    )


def stored_embedding_dimensions(value: object) -> int:
    """Count a pgvector returned as either a JSON string or a list."""
    embedding = json.loads(value) if isinstance(value, str) else value
    if not isinstance(embedding, list):
        raise TypeError("Supabase returned an invalid embedding value")
    return len(embedding)


async def source_document_id(
    client: AsyncClient,
    accession_number: str,
) -> str:
    response = await (
        client.table("source_documents")
        .select("id")
        .eq("accession_number", accession_number)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise RuntimeError(
            f"Source document {accession_number} is not in Supabase"
        )
    return response.data[0]["id"]


async def existing_chunks(
    client: AsyncClient,
    document_id: str,
) -> dict[int, dict[str, Any]]:
    response = await (
        client.table("document_chunks")
        .select("chunk_index,metadata")
        .eq("document_id", document_id)
        .execute()
    )
    return {row["chunk_index"]: row for row in response.data}


async def upload_chunks(
    client: AsyncClient,
    openai_client: AsyncOpenAI,
    document_id: str,
    chunks: list[PreparedChunk],
    complete_document: bool,
) -> tuple[int, int]:
    existing = await existing_chunks(client, document_id)
    pending = [
        chunk
        for chunk in chunks
        if not chunk_is_current(chunk, existing.get(chunk.chunk_index))
    ]

    for offset in range(0, len(pending), EMBEDDING_BATCH_SIZE):
        batch = pending[offset : offset + EMBEDDING_BATCH_SIZE]
        embeddings = await create_embeddings(
            openai_client,
            [chunk.content for chunk in batch],
            settings.openai_embedding_model,
            settings.openai_embedding_dimensions,
        )
        rows = []
        for chunk, embedding in zip(batch, embeddings, strict=True):
            metadata = {
                **chunk.metadata,
                "embedding_dimensions": settings.openai_embedding_dimensions,
                "embedding_model": settings.openai_embedding_model,
            }
            rows.append(
                {
                    "document_id": document_id,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "section": chunk.section,
                    "content": chunk.content,
                    "embedding": embedding,
                    "token_count": chunk.token_count,
                    "metadata": metadata,
                }
            )
        for attempt in range(DATABASE_WRITE_ATTEMPTS):
            try:
                await (
                    client.table("document_chunks")
                    .upsert(
                        rows,
                        on_conflict="document_id,chunk_index",
                        returning=ReturnMethod.minimal,
                    )
                    .execute()
                )
                break
            except httpx.HTTPError:
                if attempt == DATABASE_WRITE_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(2**attempt)
        print(
            f"Stored chunks {batch[0].chunk_index}-"
            f"{batch[-1].chunk_index}",
            flush=True,
        )

    if complete_document:
        await (
            client.table("document_chunks")
            .delete(returning=ReturnMethod.minimal)
            .eq("document_id", document_id)
            .gte("chunk_index", len(chunks))
            .execute()
        )

    return len(pending), len(chunks) - len(pending)


async def verify_single_chunk(
    client: AsyncClient,
    document_id: str,
    chunk_index: int,
) -> None:
    response = await (
        client.table("document_chunks")
        .select("id,embedding,search_vector,token_count,metadata")
        .eq("document_id", document_id)
        .eq("chunk_index", chunk_index)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise RuntimeError("The single test chunk was not stored")
    row = response.data[0]
    if (
        stored_embedding_dimensions(row["embedding"])
        != settings.openai_embedding_dimensions
    ):
        raise RuntimeError("Stored embedding has the wrong dimensions")
    if not row["search_vector"]:
        raise RuntimeError("Postgres did not generate the search vector")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accession", help="Process only one SEC accession")
    parser.add_argument("--ticker", help="Process only one ticker")
    parser.add_argument(
        "--max-chunks",
        type=int,
        help="Process at most this many chunks across the selected filings",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Generate embeddings and write chunks; otherwise only run locally",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Confirm an unrestricted paid full-corpus upload",
    )
    args = parser.parse_args()
    if args.max_chunks is not None and args.max_chunks < 1:
        parser.error("--max-chunks must be positive")
    if args.upload and args.max_chunks is None and not args.full:
        parser.error("unrestricted upload requires --full")
    if args.full and not args.upload:
        parser.error("--full requires --upload")
    return args


async def run(args: argparse.Namespace) -> None:
    artifacts = load_filing_artifacts(args.accession, args.ticker)
    prepared: list[tuple[FilingArtifact, list[PreparedChunk], bool]] = []
    remaining = args.max_chunks
    total_tokens = 0

    for artifact in artifacts:
        chunks = build_chunks(artifact.path, artifact.metadata)
        complete_document = remaining is None or remaining >= len(chunks)
        if remaining is not None:
            chunks = chunks[:remaining]
            remaining -= len(chunks)
        if not chunks:
            break
        prepared.append((artifact, chunks, complete_document))
        total_tokens += sum(chunk.token_count for chunk in chunks)
        print(
            f"{artifact.metadata.ticker} {artifact.metadata.fiscal_year}: "
            f"{len(chunks)} chunks"
        )

    all_chunks = [chunk for _, chunks, _ in prepared for chunk in chunks]
    counts = [chunk.token_count for chunk in all_chunks]
    print(f"Documents: {len(prepared)}")
    print(f"Chunks: {len(all_chunks)}")
    print(f"Tokens: {total_tokens}")
    if counts:
        print(
            f"Chunk tokens: min={min(counts)}, "
            f"average={sum(counts) / len(counts):.1f}, max={max(counts)}"
        )

    if not args.upload:
        print("Dry run complete; no embeddings or database writes were made.")
        return

    supabase = await create_service_role_client()
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    embedded = 0
    skipped = 0
    document_ids = []

    for artifact, chunks, complete_document in prepared:
        document_id = await source_document_id(
            supabase, artifact.metadata.accession_number
        )
        document_ids.append(document_id)
        new_count, skipped_count = await upload_chunks(
            supabase,
            openai_client,
            document_id,
            chunks,
            complete_document,
        )
        embedded += new_count
        skipped += skipped_count

    if len(all_chunks) == 1:
        await verify_single_chunk(
            supabase, document_ids[0], all_chunks[0].chunk_index
        )
        print("Single-chunk integration check passed.")
    print(f"Embedded/uploaded: {embedded}; already current: {skipped}")


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
