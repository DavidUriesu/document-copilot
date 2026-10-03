"""Request-scoped dependencies for the document agent."""

from dataclasses import dataclass, field
from uuid import UUID

from app.retrieval.models import SourcePassage
from app.retrieval.retriever import DocumentRetriever


@dataclass
class DocumentAgentDeps:
    """Services and retrieved evidence available during one agent run."""

    user_id: UUID
    thread_id: UUID
    retriever: DocumentRetriever
    evidence: dict[UUID, SourcePassage] = field(default_factory=dict)
