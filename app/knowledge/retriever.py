"""Retrieve relevant info from PageIndex tree using LLM reasoning.

Uses the PageIndex self-hosted retrieval tools:
1. get_document_structure() — tree TOC (titles + summaries, no full text)
2. get_page_content(pages) — fetch specific sections by line number

The LLM reads the tree structure and decides which sections to fetch.
This is much cheaper than sending all content — the tree TOC is small.
"""
import json
import logging
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

# Add PageIndex lib to path
PAGEINDEX_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "lib", "pageindex")
if PAGEINDEX_DIR not in sys.path:
    sys.path.insert(0, PAGEINDEX_DIR)


async def retrieve_relevant_info(
    db: AsyncSession,
    tenant_id,
    query: str,
    max_results: int = 3,
) -> str:
    """Use PageIndex tree to find and retrieve relevant content.

    Two-step process:
    1. Get tree structure (titles + summaries) — small, cheap
    2. Ask LLM which sections are relevant — one focused call
    3. Fetch those sections' text
    """
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)
    )
    kb = result.scalar_one_or_none()

    if not kb or not kb.tree_json:
        return ""

    storage = kb.tree_json

    # Get the PageIndex tree
    if storage.get("type") == "pageindex":
        tree_data = storage.get("tree", {})
        structure = tree_data.get("structure", [])
    else:
        # Legacy format
        structure = storage.get("children", storage.get("structure", []))

    if not structure:
        return ""

    # Build a compact TOC from the tree (titles + summaries only — no text)
    toc = _build_toc_from_tree(structure)

    if not toc:
        return ""

    # Use LLM to pick relevant sections from the TOC
    try:
        from app.ai.llm_client import chat_completion
        import re

        prompt = f"""Given a customer question about a business, pick the most relevant sections from the knowledge base table of contents below.

Customer question: "{query}"

Knowledge base sections:
{toc}

Return ONLY a JSON array of the line numbers of the {max_results} most relevant sections, e.g. [5, 12, 28].
If no sections are relevant, return [].
Return ONLY the JSON array."""

        response = await chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=50,  # Very small — just a JSON array
        )

        # Parse line numbers
        match = re.search(r'\[[\d,\s]*\]', response)
        if not match:
            return _fallback_text(structure)

        line_nums = json.loads(match.group())
        if not line_nums:
            return ""

        # Fetch content for those line numbers from the tree
        return _get_content_by_line_nums(structure, line_nums)

    except Exception as e:
        logger.warning(f"PageIndex retrieval failed: {e}")
        return _fallback_text(structure)


def _build_toc_from_tree(nodes: list, indent: int = 0) -> str:
    """Build a compact table of contents from PageIndex tree.

    Shows title, line_num, and summary — NOT full text.
    This is very compact (few hundred tokens for 30 pages).
    """
    lines = []
    for node in nodes:
        if not isinstance(node, dict):
            continue

        title = node.get("title", "")
        line_num = node.get("line_num", "")
        summary = node.get("summary", node.get("prefix_summary", ""))

        prefix = "  " * indent
        entry = f"{prefix}- [{line_num}] {title}"
        if summary:
            entry += f" — {summary[:120]}"
        lines.append(entry)

        # Recurse into children
        children = node.get("nodes", [])
        if children:
            lines.append(_build_toc_from_tree(children, indent + 1))

    return "\n".join(lines)


def _get_content_by_line_nums(nodes: list, line_nums: list[int]) -> str:
    """Traverse tree and extract text for nodes matching the line numbers."""
    parts = []
    target_set = set(line_nums)

    def _traverse(node_list):
        for node in node_list:
            if not isinstance(node, dict):
                continue
            ln = node.get("line_num")
            if ln and ln in target_set:
                title = node.get("title", "")
                text = node.get("text", node.get("content", node.get("raw_content", "")))
                if title:
                    parts.append(f"## {title}")
                if text:
                    parts.append(text[:800])
            children = node.get("nodes", [])
            if children:
                _traverse(children)

    _traverse(nodes)
    return "\n\n".join(parts).strip()


def _fallback_text(nodes: list) -> str:
    """Return first few sections as fallback."""
    parts = []
    flat = _flatten(nodes)
    for node in flat[:3]:
        text = node.get("text", node.get("content", ""))
        if text:
            parts.append(text[:500])
    return "\n\n".join(parts)


def _flatten(nodes: list) -> list[dict]:
    """Flatten tree into list."""
    flat = []
    for node in nodes:
        if isinstance(node, dict):
            flat.append({k: v for k, v in node.items() if k != "nodes"})
            if node.get("nodes"):
                flat.extend(_flatten(node["nodes"]))
    return flat
