"""OpenAI embedding generation for prepared document chunks."""

from __future__ import annotations

from openai import AsyncOpenAI


async def create_embeddings(
    client: AsyncOpenAI,
    texts: list[str],
    model: str,
    dimensions: int,
) -> list[list[float]]:
    """Embed a batch and validate its ordering and dimensions."""
    response = await client.embeddings.create(
        input=texts,
        model=model,
        dimensions=dimensions,
        encoding_format="float",
    )
    ordered = sorted(response.data, key=lambda item: item.index)
    embeddings = [item.embedding for item in ordered]

    if len(embeddings) != len(texts):
        raise RuntimeError("OpenAI returned a different number of embeddings")
    if any(len(embedding) != dimensions for embedding in embeddings):
        raise RuntimeError(
            f"OpenAI returned an embedding other than {dimensions} dimensions"
        )

    return embeddings
