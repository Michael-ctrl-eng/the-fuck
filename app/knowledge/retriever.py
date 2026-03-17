import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import chat_completion
from app.models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


async def retrieve_relevant_info(
    db: AsyncSession,
    tenant_id,
    query: str,
    max_results: int = 3,
) -> str:
    """Retrieve relevant information from the knowledge base using LLM reasoning.

    PageIndex-style: instead of vector similarity, we use the LLM to reason
    over the document tree and select relevant sections.
    """
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)
    )
    kb = result.scalar_one_or_none()

    if not kb or not kb.tree_json:
        return ""

    tree = kb.tree_json
    children = tree.get("children", [])

    if not children:
        return ""

    # Build a TOC for LLM to reason over
    toc = _build_toc(children)

    if not toc:
        # If tree is small, return all content
        return _extract_all_content(children)

    # Ask LLM which sections are relevant
    try:
        prompt = f"""Given a customer's question about a business, select the most relevant sections from the knowledge base.

Customer question: "{query}"

Available sections:
{toc}

Return the numbers of the {max_results} most relevant sections as a JSON array, e.g. [1, 3, 5].
Only return the JSON array, nothing else."""

        response = await chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=100,
        )

        # Parse section numbers
        import re
        match = re.search(r'\[[\d,\s]+\]', response)
        if match:
            section_nums = json.loads(match.group())
            return _get_sections_by_index(children, section_nums)

    except Exception as e:
        logger.warning(f"LLM retrieval failed: {e}")

    # Fallback: return all content
    return _extract_all_content(children)


def _build_toc(children: list[dict]) -> str:
    """Build a numbered table of contents from the tree."""
    toc_lines = []
    idx = 1
    for child in children:
        title = child.get("title", child.get("url", f"Section {idx}"))
        summary = child.get("summary", "")
        sections = child.get("sections", [])

        toc_lines.append(f"{idx}. {title}")
        if summary:
            toc_lines.append(f"   Summary: {summary}")
        for section in sections:
            heading = section.get("heading", "")
            if heading:
                toc_lines.append(f"   - {heading}")
        idx += 1

    return "\n".join(toc_lines)


def _get_sections_by_index(children: list[dict], indices: list[int]) -> str:
    """Extract content from specific sections."""
    parts = []
    for idx in indices:
        if 1 <= idx <= len(children):
            child = children[idx - 1]
            content = child.get("content", child.get("raw_content", ""))
            sections = child.get("sections", [])

            if sections:
                for s in sections:
                    parts.append(f"### {s.get('heading', '')}")
                    parts.append(s.get("content", ""))
                    key_info = s.get("key_info", [])
                    if key_info:
                        parts.append("Key info: " + ", ".join(key_info))
            elif content:
                parts.append(content)

    return "\n\n".join(parts)


def _extract_all_content(children: list[dict]) -> str:
    """Extract all content from tree (for small knowledge bases)."""
    parts = []
    for child in children[:10]:
        content = child.get("content", child.get("raw_content", ""))
        if content:
            title = child.get("title", "")
            if title:
                parts.append(f"## {title}")
            parts.append(content[:1000])

    return "\n\n".join(parts)
