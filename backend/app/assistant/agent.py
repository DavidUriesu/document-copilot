"""PydanticAI agent configured for grounded filing analysis."""

from pathlib import Path

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.assistant.tools import read_chunk, read_surrounding_chunks, search_filings
from app.config import settings
from app.grounding.validator import GroundingError, validate_grounded_answer

INSTRUCTIONS = (Path(__file__).with_name("instructions.md")).read_text(encoding="utf-8")
MAX_AGENT_REQUESTS = 12
MAX_AGENT_TOOL_CALLS = 20
MAX_TOOL_RETRIES = 2
MAX_OUTPUT_RETRIES = 3

model = OpenAIResponsesModel(
    settings.openai_chat_model,
    provider=OpenAIProvider(api_key=settings.openai_api_key),
)
document_agent = Agent(
    model,
    deps_type=DocumentAgentDeps,
    output_type=GroundedAnswer,
    instructions=INSTRUCTIONS,
    tools=[search_filings, read_chunk, read_surrounding_chunks],
    retries={"tools": MAX_TOOL_RETRIES, "output": MAX_OUTPUT_RETRIES},
)


@document_agent.output_validator
async def validate_output(
    ctx: RunContext[DocumentAgentDeps], output: GroundedAnswer
) -> GroundedAnswer:
    """Give the model a bounded chance to correct invalid grounding."""
    try:
        validate_grounded_answer(output, ctx.deps.evidence)
    except GroundingError as exc:
        raise ModelRetry(str(exc)) from exc
    return output
