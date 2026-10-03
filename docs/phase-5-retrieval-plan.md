# Phase 5 retrieval implementation plan

## Outcome

Phase 5 is complete when a plain Python call can take a user query and optional
filing filters, run semantic and lexical retrieval against Supabase Postgres,
fuse the two rankings, expand the winning chunks with local context, and return
typed source passages ready for the Phase 6 PydanticAI tools.

This phase does **not** generate an answer. Retrieval must remain usable and
testable without invoking an LLM agent.

## Pattern to carry over from the reference implementation

The [hybrid retrieval example](https://github.com/daveebbelaar/ai-cookbook/tree/main/knowledge/hybrid-retrieval)
separates four concerns: sparse retrieval, dense retrieval, rank fusion, and
evaluation. The useful ideas for this codebase are:

- Give lexical and semantic retrieval the same small interface: ranked stable
  IDs plus channel-specific scores.
- Retrieve a wider candidate set from each channel and fuse ranks rather than
  incomparable raw scores.
- Use Reciprocal Rank Fusion (RRF) with the conventional smoothing constant of
  60 as the first baseline.
- Keep orchestration in a thin `search` facade so storage and ranking can be
  changed independently.
- Measure retrieval quality on known questions instead of judging a few
  outputs by eye.

The storage-specific parts should not be copied. PostgreSQL full-text search
replaces BM25, pgvector replaces the in-memory embedding matrix, and the
existing OpenAI embedding settings remain the single source of truth. The
reference's cross-encoder reranker is intentionally deferred: it is not in the
Phase 5 contract, it would add another provider and runtime dependency, and we
need a measured hybrid baseline before deciding whether it earns its cost.

## Proposed request flow

```text
query + filters
      |
      +--> OpenAI query embedding --> pgvector RPC -------+
      |                                                   |
      +-------------------------> full-text RPC ----------+--> RRF
                                                               |
                                                        top seed chunks
                                                               |
                                                   neighbor chunk lookup
                                                               |
                                                    SourcePassage[]
```

Embed the query once. After that call returns, run the semantic and full-text
RPCs concurrently with `asyncio.gather`. Each channel should request more
candidates than the final result count; start with 30 candidates per channel,
RRF them with `k=60`, keep 8 seed chunks, and fetch one chunk on either side of
each seed. These are named constants, not environment variables, until an
evaluation shows a deployment-specific setting is useful.

## Public contracts

Add `app/retrieval/models.py` for the types shared by queries, fusion, the
retriever, and later the agent:

```python
@dataclass(frozen=True)
class RetrievalFilters:
    tickers: tuple[str, ...] = ()
    filing_types: tuple[str, ...] = ()
    fiscal_year_from: int | None = None
    fiscal_year_to: int | None = None


@dataclass(frozen=True)
class RankedChunk:
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    score: float


@dataclass(frozen=True)
class SourcePassage:
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    page_number: int | None
    section: str | None
    ticker: str
    company_name: str
    filing_type: str
    filing_date: date
    report_date: date
    fiscal_year: int
    accession_number: str
    source_url: str
    rrf_score: float | None
    is_seed: bool
```

`DocumentRetriever.search(query, filters=None, limit=8,
neighbor_window=1) -> list[SourcePassage]` is the Phase 5 entry point. It owns
embedding, the two searches, fusion, neighbor expansion, deduplication, and
stable output ordering. It receives the async Supabase client and async OpenAI
client through its constructor; it must not create clients or read global
credentials itself.

Keep `RankedChunk` deliberately small. Search channels only need identity,
rank, and their diagnostic score. Hydrate content and filing metadata once,
after fusion, so duplicate candidates do not move large text payloads through
both searches.

## Database work

Add one reviewed Alembic migration with three Postgres functions exposed via
Supabase RPC. SQL functions are preferable to client-side query-builder tricks
because vector distance, `ts_rank_cd`, joins, filters, and deterministic order
need to execute in Postgres.

### `match_document_chunks_semantic`

- Parameters: query vector, candidate limit, optional ticker array, optional
  filing-type array, and optional fiscal-year bounds.
- Join `document_chunks` to `source_documents` for filters.
- Rank by `document_chunks.embedding <=> query_embedding` ascending.
- Return chunk/document identity, chunk index, and cosine similarity
  (`1 - distance`) for diagnostics.
- Add `id` as the final ordering key so ties are deterministic.

### `match_document_chunks_full_text`

- Accept the same filters and candidate limit plus the raw query string.
- Build the query with `websearch_to_tsquery('english', query_text)` so normal
  analyst questions, quoted phrases, and exclusions are accepted safely.
- Filter with `search_vector @@ tsquery` and rank with
  `ts_rank_cd(search_vector, tsquery)` descending.
- Add `id` as the final ordering key.
- Return an empty result for a blank/stop-word-only query rather than allowing
  it to fail the whole hybrid search.

### `get_document_chunk_window`

- Parameters: seed chunk IDs and a bounded window size.
- Resolve each seed to `(document_id, chunk_index)`, then fetch chunks from the
  same document within `seed_index +/- window`.
- Join source-document citation metadata in the same round trip.
- Return the seed's RRF association separately from chunk identity so
  overlapping windows can be deduplicated in Python.

Functions should use the caller's permissions (`SECURITY INVOKER`, the
default), receive only typed parameters, set a fixed `search_path`, and grant
execution only to the roles that already have corpus read access. No dynamic
SQL is needed. The user-scoped Supabase client should call them so current RLS
policy remains effective.

Before finalizing the migration, run `EXPLAIN (ANALYZE, BUFFERS)` against an
ingested corpus and confirm the semantic query uses the HNSW index and lexical
query uses the GIN index. Do not add indexes speculatively; the current schema
already has the two primary retrieval indexes and source-document indexes for
ticker and fiscal year.

## Python modules

### `app/retrieval/queries.py`

- Define the three async, typed database boundary functions.
- Convert `RetrievalFilters` into exact RPC parameter dictionaries in one
  helper; normalize tickers to uppercase at the boundary.
- Validate RPC rows into the internal dataclasses and fail visibly on malformed
  external data.
- Do not perform ranking policy or create database clients here.

### `app/retrieval/fusion.py`

- Implement a pure `reciprocal_rank_fusion(rankings, k=60)` function.
- Accept ranked sequences of chunk IDs and return IDs with fused scores.
- Count a chunk at most once per input ranking.
- Sort by descending RRF score, then by a deterministic first-seen order. This
  makes tests and result ordering stable when scores tie.
- Retain raw semantic and lexical scores only as diagnostics; never average
  them because their scales are unrelated.

### `app/retrieval/retriever.py`

- Reject blank queries and non-positive limits/window sizes at this public
  boundary.
- Generate the query embedding with the existing model and dimension settings.
  Reuse the validation behavior in ingestion, but expose a single-query helper
  rather than importing a batch-oriented ingestion module into app runtime
  code.
- Run both search channels concurrently after embedding.
- Fuse candidate IDs, take the requested seeds, fetch windows in one RPC,
  deduplicate overlapping neighbors, and return deterministic document order:
  seed RRF order first, then neighbors by document and chunk index.
- Preserve individual chunk IDs. Do not concatenate neighbors into a synthetic
  chunk, because Phase 6 citations must map to persisted `document_chunks.id`
  values.
- If one search channel fails, fail the retrieval call. A silent dense-only or
  lexical-only fallback would hide an operational problem and change ranking
  behavior without the user knowing.

## Filters and multi-filing questions

Filters are part of the retrieval API even though Phase 5 does not infer them.
This is necessary for questions covering a company or year range: unrestricted
top-k search can otherwise fill all slots with one filing. Phase 6's
`search_filings` tool will pass explicit tickers and years supplied by the
agent. For broad comparison questions, the tool can issue multiple bounded
searches (for example, one per ticker or year) instead of making Phase 5 hide
query decomposition inside retrieval.

No score threshold should be introduced in the baseline. RRF scores depend on
candidate-list sizes and overlap, so an arbitrary cutoff is not evidence of
relevance. Return a bounded ranking and let Phase 6 judge evidence sufficiency;
later evaluation can justify a threshold or reranker.

## PydanticAI handoff in Phase 6

PydanticAI brings the components together above, not inside, the retrieval
pipeline:

```python
@dataclass
class DocumentAgentDeps:
    user_id: UUID
    thread_id: UUID
    retriever: DocumentRetriever


@agent.tool
async def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    tickers: list[str] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[SourcePassage]:
    return await ctx.deps.retriever.search(
        query,
        RetrievalFilters(
            tickers=tuple(tickers or ()),
            fiscal_year_from=start_year,
            fiscal_year_to=end_year,
        ),
    )
```

Register three bounded tools in Phase 6:

- `search_filings`: the hybrid search entry point, with structured filters.
- `read_chunk`: exact lookup by chunk ID for a stable citation target.
- `read_surrounding_chunks`: explicit context expansion when the agent needs
  more than the default window.

The retriever is supplied through typed `RunContext` dependencies, tool inputs
are schema-validated, and the final answer uses the typed `GroundedAnswer`
output. The agent never receives credentials, a raw Supabase client, or a SQL
tool. This preserves the reference implementation's thin retrieval facade and
the architecture's requirement that grounding validation remain deterministic.

## Test plan

### Unit tests

`tests/retrieval/test_fusion.py`:

- a result present in both lists outranks single-channel results;
- rank positions use one-based RRF calculation and `k=60`;
- duplicates within one channel count once;
- empty rankings and deterministic ties behave correctly;
- input rankings are not mutated.

`tests/retrieval/test_queries.py`:

- each function calls the expected RPC with exact parameter names;
- optional filters become SQL nulls and populated filters retain their values;
- tickers normalize to uppercase;
- returned rows are parsed into typed results;
- malformed RPC data fails at the database boundary.

`tests/retrieval/test_retriever.py`:

- the query is embedded once with configured model/dimensions;
- both channels receive the same filters and candidate limit;
- fused seed order is honored;
- overlapping neighbor windows are deduplicated without losing seed identity;
- blank input and invalid limits fail before network work;
- embedding, database, and single-channel failures propagate.

Use small fakes or `AsyncMock` at the OpenAI/query-function boundaries. Unit
tests must not need environment credentials, network access, or Postgres.

### Integration test

Add an opt-in `@pytest.mark.integration` test that creates real clients, runs a
known query against the ingested corpus, and asserts structural facts rather
than brittle exact rank positions: results exist, IDs are unique, citation
metadata is populated, requested filters are respected, and at least one
expected company/section appears. Register the marker in `pyproject.toml` so it
is never selected accidentally by the fast suite.

### Retrieval smoke evaluation

Add a small script or integration-test parameter set based on the ten questions
in `client-brief.md`. Record, per query, the expected tickers, year coverage,
and a few relevant phrases/sections. Print top seeds with rank provenance and
metadata for human review. At minimum include:

- an exact-term query (`AWS operating income`, `1099`-style lexical behavior);
- a paraphrase query to prove dense retrieval adds recall;
- a multi-year company query;
- a multi-company comparison query;
- an unsupported inference query to confirm retrieval exposes evidence without
  manufacturing a conclusion.

This becomes the baseline for deciding later whether query decomposition,
per-document result diversification, contextual embeddings, or a cross-encoder
reranker is warranted.

## Implementation order

1. Add retrieval dataclasses and the Alembic RPC migration.
2. Exercise both RPCs manually on the ingested corpus and inspect query plans.
3. Implement and unit-test the query boundary.
4. Implement pure RRF and its full edge-case test matrix.
5. Implement `DocumentRetriever`, neighbor expansion, and mocked orchestration
   tests.
6. Add and run the opt-in integration test.
7. Run the client-brief smoke evaluation, save the observed baseline, and tune
   candidate/seed/window constants only if the evidence supports it.
8. Check off Phase 5 in `todos.md` only after the fast suite passes and manual
   verification shows both lexical-only and semantic-only wins represented in
   the fused results.

## Definition of done

- Semantic and lexical queries execute separately in Postgres and use their
  intended indexes.
- RRF is pure, deterministic, and covered by unit tests.
- One async retriever call returns typed, citation-ready passages and neighbors.
- Ticker, filing type, and fiscal-year filters work end to end.
- Fast tests perform no external I/O; the real-corpus test is opt-in.
- The ten client-brief questions have a recorded retrieval baseline.
- Phase 6 can expose the retriever through typed PydanticAI dependencies and
  bounded tools without changing Phase 5's public contract.
