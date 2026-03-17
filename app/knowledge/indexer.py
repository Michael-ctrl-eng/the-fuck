from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_client import chat_completion
from app.models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


async def build_knowledge_index(
    db: AsyncSession,
    tenant_id,
    pages: list[dict],
) -> KnowledgeBase:
    """Build a PageIndex-style hierarchical knowledge tree from crawled pages.

    Each page is analyzed by the LLM to extract a structured TOC with content.
    The tree is stored as JSON in the knowledge_bases table.
    """
    tree = {
        "type": "root",
        "children": [],
        "metadata": {
            "indexed_at": datetime.utcnow().isoformat(),
            "total_pages": len(pages),
        },
    }

    for page in pages:
        try:
            page_node = await _index_page(page)
            if page_node:
                tree["children"].append(page_node)
        except Exception as e:
            logger.error(f"Failed to index page {page.get('url')}: {e}")

    # Upsert knowledge base
    from sqlalchemy import select

    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)
    )
    kb = result.scalar_one_or_none()

    if kb:
        kb.tree_json = tree
        kb.source_documents = [{"url": p["url"], "title": p.get("title", "")} for p in pages]
        kb.last_indexed_at = datetime.utcnow()
    else:
        kb = KnowledgeBase(
            tenant_id=tenant_id,
            tree_json=tree,
            source_documents=[{"url": p["url"], "title": p.get("title", "")} for p in pages],
            last_indexed_at=datetime.utcnow(),
        )
        db.add(kb)

    await db.flush()
    return kb


async def _index_page(page: dict) -> dict | None:
    """Create a hierarchical node for a single page."""
    content = page.get("content", "")
    if not content:
        return None

    # For short content, store directly
    if len(content) < 2000:
        return {
            "type": "page",
            "url": page.get("url", ""),
            "title": page.get("title", ""),
            "content": content,
            "sections": [],
        }

    # For longer content, use LLM to extract structure
    try:
        prompt = f"""Analyze this webpage content and extract a structured summary.
Return a JSON object with:
- "title": page title
- "summary": 2-3 sentence summary
- "sections": array of {{"heading": "...", "content": "...", "key_info": ["..."]}}

Focus on extracting:
- Product names and prices
- Product descriptions
- Contact information
- Delivery/shipping info
- Business policies

Content:
{content[:4000]}"""

        response = await chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
        )

        # Try to parse as JSON
        try:
            # Find JSON in response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                structured = json.loads(json_match.group())
                return {
                    "type": "page",
                    "url": page.get("url", ""),
                    "title": structured.get("title", page.get("title", "")),
                    "summary": structured.get("summary", ""),
                    "sections": structured.get("sections", []),
                    "raw_content": content[:2000],
                }
        except json.JSONDecodeError:
            pass

    except Exception as e:
        logger.warning(f"LLM indexing failed for {page.get('url')}: {e}")

    # Fallback: store raw content
    return {
        "type": "page",
        "url": page.get("url", ""),
        "title": page.get("title", ""),
        "content": content[:3000],
        "sections": [],
    }
