"""Structure-aware chunk preparation for SEC filings."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tiktoken
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from docling_core.types.doc import DoclingDocument

FINAL_MAX_TOKENS = 800
DOCLING_MAX_TOKENS = 760
TOKENIZER_NAME = "cl100k_base"
PIPELINE_VERSION = 1

SEC_SECTIONS = {
    "1": "Item 1. Business",
    "1A": "Item 1A. Risk Factors",
    "1B": "Item 1B. Unresolved Staff Comments",
    "1C": "Item 1C. Cybersecurity",
    "2": "Item 2. Properties",
    "3": "Item 3. Legal Proceedings",
    "4": "Item 4. Mine Safety Disclosures",
    "5": "Item 5. Market for Registrant's Common Equity",
    "6": "Item 6. Reserved",
    "7": "Item 7. Management's Discussion and Analysis",
    "7A": "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Item 8. Financial Statements and Supplementary Data",
    "9": "Item 9. Changes in and Disagreements With Accountants",
    "9A": "Item 9A. Controls and Procedures",
    "9B": "Item 9B. Other Information",
    "9C": "Item 9C. Disclosure Regarding Foreign Jurisdictions",
    "10": "Item 10. Directors, Executive Officers and Corporate Governance",
    "11": "Item 11. Executive Compensation",
    "12": "Item 12. Security Ownership of Certain Beneficial Owners and Management",
    "13": "Item 13. Certain Relationships and Related Transactions",
    "14": "Item 14. Principal Accountant Fees and Services",
    "15": "Item 15. Exhibits and Financial Statement Schedules",
    "16": "Item 16. Form 10-K Summary",
}

SECTION_KEYWORDS = {
    "1": "business",
    "1A": "riskfactors",
    "1B": "unresolvedstaffcomments",
    "1C": "cybersecurity",
    "2": "properties",
    "3": "legalproceedings",
    "4": "minesafetydisclosures",
    "5": "marketfor",
    "6": "reserved",
    "7": "managementsdiscussion",
    "7A": "quantitativeandqualitative",
    "8": "financialstatements",
    "9": "changesinanddisagreements",
    "9A": "controlsandprocedures",
    "9B": "otherinformation",
    "9C": "foreignjurisdictions",
    "10": "directors",
    "11": "executivecompensation",
    "12": "securityownership",
    "13": "certainrelationships",
    "14": "principalaccountant",
    "15": "exhibits",
    "16": "form10ksummary",
}

SECTION_PATTERN = re.compile(
    r"^[|#* \t]*item\s+(1a|1b|1c|[1-9]|7a|9a|9b|9c|1[0-6])\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class FilingMetadata:
    accession_number: str
    ticker: str
    filing_type: str
    fiscal_year: int
    local_path: str


@dataclass(frozen=True)
class PreparedChunk:
    chunk_index: int
    content: str
    token_count: int
    page_number: int | None
    section: str | None
    metadata: dict[str, Any]


def chunking_config_hash() -> str:
    config = {
        "docling_max_tokens": DOCLING_MAX_TOKENS,
        "final_max_tokens": FINAL_MAX_TOKENS,
        "merge_peers": True,
        "pipeline_version": PIPELINE_VERSION,
        "repeat_table_header": True,
        "tokenizer": TOKENIZER_NAME,
    }
    serialized = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def detect_sec_section(text: str) -> str | None:
    """Recognize titled SEC item headings at line or table boundaries."""
    section = None
    for match in SECTION_PATTERN.finditer(text):
        item = match.group(1).upper()
        heading_context = text[match.start() : match.end() + 200]
        normalized_heading = re.sub(r"[^a-z0-9]", "", heading_context.lower())
        if SECTION_KEYWORDS[item] in normalized_heading:
            section = SEC_SECTIONS[item]
    stripped = text.lstrip("|#* \t\r\n").lower()
    is_serialized_table = ", 1 =" in text[:1200]
    if section is None and (stripped.startswith("item") or is_serialized_table):
        normalized = re.sub(r"[^a-z0-9]", "", text[:1200].lower())
        for item, keyword in SECTION_KEYWORDS.items():
            marker = f"item{item.lower()}"
            position = normalized.find(marker)
            if position >= 0 and keyword in normalized[position : position + 350]:
                section = SEC_SECTIONS[item]
    return section


def build_chunks(
    document_path: Path,
    filing: FilingMetadata,
) -> list[PreparedChunk]:
    """Create token-bounded, metadata-enriched chunks from Docling JSON."""
    document = DoclingDocument.load_from_json(document_path)
    encoding = tiktoken.get_encoding(TOKENIZER_NAME)
    tokenizer = OpenAITokenizer(
        tokenizer=encoding,
        max_tokens=DOCLING_MAX_TOKENS,
    )
    chunker = HybridChunker(
        tokenizer=tokenizer,
        merge_peers=True,
        repeat_table_header=True,
    )
    config_hash = chunking_config_hash()
    section = None
    prepared = []

    for chunk_index, chunk in enumerate(chunker.chunk(dl_doc=document)):
        section = detect_sec_section(chunk.text) or section
        content = chunker.contextualize(chunk).strip()
        if section and not content.startswith(section):
            content = f"{section}\n\n{content}"

        token_count = tokenizer.count_tokens(content)
        if token_count > FINAL_MAX_TOKENS:
            raise ValueError(
                f"Chunk {chunk_index} in {document_path.name} has "
                f"{token_count} tokens; maximum is {FINAL_MAX_TOKENS}"
            )

        page_numbers = sorted(
            {
                provenance.page_no
                for item in chunk.meta.doc_items
                for provenance in item.prov
            }
        )
        headings = list(chunk.meta.headings or [])
        captions = list(chunk.meta.model_dump().get("captions") or [])
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        prepared.append(
            PreparedChunk(
                chunk_index=chunk_index,
                content=content,
                token_count=token_count,
                page_number=page_numbers[0] if page_numbers else None,
                section=section or (headings[-1] if headings else None),
                metadata={
                    "accession_number": filing.accession_number,
                    "captions": captions,
                    "chunking_config_hash": config_hash,
                    "content_hash": content_hash,
                    "doc_item_refs": [
                        item.self_ref for item in chunk.meta.doc_items
                    ],
                    "filing_type": filing.filing_type,
                    "fiscal_year": filing.fiscal_year,
                    "headings": headings,
                    "local_path": filing.local_path,
                    "overlap_tokens": 0,
                    "page_numbers": page_numbers,
                    "ticker": filing.ticker,
                    "tokenizer": TOKENIZER_NAME,
                },
            )
        )

    return prepared
