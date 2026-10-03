"""Run a visible hybrid-search query against the ingested corpus."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from openai import AsyncOpenAI

from app.config import settings
from app.database.supabase import create_service_role_client
from app.retrieval.models import RetrievalFilters, SourcePassage
from app.retrieval.retriever import DocumentRetriever


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Question or search phrase")
    parser.add_argument(
        "--ticker",
        action="append",
        default=[],
        help="Restrict to a ticker; repeat for multiple companies",
    )
    parser.add_argument(
        "--filing-type",
        action="append",
        default=[],
        help="Restrict to a filing type; repeat for multiple types",
    )
    parser.add_argument("--year-from", type=int)
    parser.add_argument("--year-to", type=int)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--neighbor-window", type=int, default=1)
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.neighbor_window < 0:
        parser.error("--neighbor-window must not be negative")
    return args


def format_passage(position: int, passage: SourcePassage) -> str:
    """Format one result for terminal inspection."""
    role = "seed" if passage.is_seed else "neighbor"
    location = f"page {passage.page_number}" if passage.page_number else "page unknown"
    section = passage.section or "section unknown"
    excerpt = passage.content.replace("\n", " ").strip()
    if len(excerpt) > 700:
        excerpt = f"{excerpt[:697]}..."
    return (
        f"\n[{position}] {role} | RRF {passage.rrf_score:.6f}\n"
        f"{passage.ticker} {passage.filing_type} FY{passage.fiscal_year} | "
        f"{location} | {section}\n"
        f"chunk={passage.chunk_id} index={passage.chunk_index}\n"
        f"source={passage.source_url}\n"
        f"{excerpt}"
    )


async def run(args: argparse.Namespace) -> None:
    database = await create_service_role_client()
    openai = AsyncOpenAI(api_key=settings.openai_api_key)
    retriever = DocumentRetriever(database, openai)
    passages = await retriever.search(
        args.query,
        RetrievalFilters(
            tickers=tuple(args.ticker),
            filing_types=tuple(args.filing_type),
            fiscal_year_from=args.year_from,
            fiscal_year_to=args.year_to,
        ),
        limit=args.limit,
        neighbor_window=args.neighbor_window,
    )

    seed_count = sum(passage.is_seed for passage in passages)
    print(f"Retrieved {len(passages)} passages from {seed_count} fused seeds.")
    for position, passage in enumerate(passages, start=1):
        print(format_passage(position, passage))


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
