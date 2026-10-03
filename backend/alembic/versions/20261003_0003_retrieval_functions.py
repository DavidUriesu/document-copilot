"""Add RPC functions for hybrid document retrieval.

Revision ID: 20261003_0003
Revises: 20261001_0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261003_0003"
down_revision: str | Sequence[str] | None = "20261001_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create caller-scoped retrieval functions exposed through PostgREST."""
    op.execute(
        """
        CREATE FUNCTION public.match_document_chunks_semantic(
            query_embedding vector(1536),
            candidate_limit integer,
            filter_tickers text[] DEFAULT NULL,
            filter_filing_types text[] DEFAULT NULL,
            filter_year_from integer DEFAULT NULL,
            filter_year_to integer DEFAULT NULL
        )
        RETURNS TABLE (
            chunk_id uuid,
            document_id uuid,
            chunk_index integer,
            score double precision
        )
        LANGUAGE sql
        STABLE
        SECURITY INVOKER
        SET search_path = ''
        AS $$
            SELECT
                dc.id,
                dc.document_id,
                dc.chunk_index,
                1 - (
                    dc.embedding OPERATOR(public.<=>) query_embedding
                ) AS score
            FROM public.document_chunks AS dc
            JOIN public.source_documents AS sd ON sd.id = dc.document_id
            WHERE (filter_tickers IS NULL OR sd.ticker = ANY(filter_tickers))
              AND (
                  filter_filing_types IS NULL
                  OR sd.filing_type = ANY(filter_filing_types)
              )
              AND (filter_year_from IS NULL OR sd.fiscal_year >= filter_year_from)
              AND (filter_year_to IS NULL OR sd.fiscal_year <= filter_year_to)
            ORDER BY dc.embedding OPERATOR(public.<=>) query_embedding, dc.id
            LIMIT candidate_limit
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.match_document_chunks_full_text(
            query_text text,
            candidate_limit integer,
            filter_tickers text[] DEFAULT NULL,
            filter_filing_types text[] DEFAULT NULL,
            filter_year_from integer DEFAULT NULL,
            filter_year_to integer DEFAULT NULL
        )
        RETURNS TABLE (
            chunk_id uuid,
            document_id uuid,
            chunk_index integer,
            score real
        )
        LANGUAGE sql
        STABLE
        SECURITY INVOKER
        SET search_path = ''
        AS $$
            WITH parsed AS (
                SELECT websearch_to_tsquery('english', query_text) AS value
            )
            SELECT
                dc.id,
                dc.document_id,
                dc.chunk_index,
                ts_rank_cd(dc.search_vector, parsed.value) AS score
            FROM public.document_chunks AS dc
            JOIN public.source_documents AS sd ON sd.id = dc.document_id
            CROSS JOIN parsed
            WHERE dc.search_vector @@ parsed.value
              AND (filter_tickers IS NULL OR sd.ticker = ANY(filter_tickers))
              AND (
                  filter_filing_types IS NULL
                  OR sd.filing_type = ANY(filter_filing_types)
              )
              AND (filter_year_from IS NULL OR sd.fiscal_year >= filter_year_from)
              AND (filter_year_to IS NULL OR sd.fiscal_year <= filter_year_to)
            ORDER BY score DESC, dc.id
            LIMIT candidate_limit
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.get_document_chunk_window(
            seed_chunk_ids uuid[],
            window_size integer
        )
        RETURNS TABLE (
            seed_chunk_id uuid,
            chunk_id uuid,
            document_id uuid,
            chunk_index integer,
            content text,
            page_number integer,
            section varchar,
            ticker varchar,
            company_name varchar,
            filing_type varchar,
            filing_date date,
            report_date date,
            fiscal_year integer,
            accession_number varchar,
            source_url text
        )
        LANGUAGE sql
        STABLE
        SECURITY INVOKER
        SET search_path = ''
        AS $$
            SELECT
                seed.id,
                neighbor.id,
                neighbor.document_id,
                neighbor.chunk_index,
                neighbor.content,
                neighbor.page_number,
                neighbor.section,
                sd.ticker,
                sd.company_name,
                sd.filing_type,
                sd.filing_date,
                sd.report_date,
                sd.fiscal_year,
                sd.accession_number,
                sd.source_url
            FROM unnest(seed_chunk_ids) WITH ORDINALITY AS requested(id, position)
            JOIN public.document_chunks AS seed ON seed.id = requested.id
            JOIN public.document_chunks AS neighbor
              ON neighbor.document_id = seed.document_id
             AND neighbor.chunk_index BETWEEN
                 seed.chunk_index - window_size AND seed.chunk_index + window_size
            JOIN public.source_documents AS sd ON sd.id = neighbor.document_id
            ORDER BY requested.position, neighbor.chunk_index
        $$
        """
    )

    op.execute(
        """
        REVOKE ALL ON FUNCTION public.match_document_chunks_semantic(
            vector, integer, text[], text[], integer, integer
        ) FROM PUBLIC;
        REVOKE ALL ON FUNCTION public.match_document_chunks_full_text(
            text, integer, text[], text[], integer, integer
        ) FROM PUBLIC;
        REVOKE ALL ON FUNCTION public.get_document_chunk_window(
            uuid[], integer
        ) FROM PUBLIC;

        GRANT EXECUTE ON FUNCTION public.match_document_chunks_semantic(
            vector, integer, text[], text[], integer, integer
        ) TO authenticated, service_role;
        GRANT EXECUTE ON FUNCTION public.match_document_chunks_full_text(
            text, integer, text[], text[], integer, integer
        ) TO authenticated, service_role;
        GRANT EXECUTE ON FUNCTION public.get_document_chunk_window(
            uuid[], integer
        ) TO authenticated, service_role;
        """
    )


def downgrade() -> None:
    """Drop hybrid retrieval functions."""
    op.execute(
        "DROP FUNCTION public.get_document_chunk_window(uuid[], integer)"
    )
    op.execute(
        "DROP FUNCTION public.match_document_chunks_full_text("
        "text, integer, text[], text[], integer, integer)"
    )
    op.execute(
        "DROP FUNCTION public.match_document_chunks_semantic("
        "vector, integer, text[], text[], integer, integer)"
    )
