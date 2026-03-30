"""Build PageIndex tree structure from crawled website content.

Uses the self-hosted PageIndex library (lib/pageindex) to convert
crawled HTML/text into a hierarchical tree with summaries.
The tree enables zero-cost retrieval during chat.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

# Add PageIndex lib to path
PAGEINDEX_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "lib", "pageindex")
if PAGEINDEX_DIR not in sys.path:
    sys.path.insert(0, PAGEINDEX_DIR)

# Configure LiteLLM to use OpenRouter
os.environ.setdefault("OPENROUTER_API_KEY", "")


def _get_pageindex_model() -> str:
    """Get the model string for PageIndex/LiteLLM using OpenRouter."""
    from app.config import get_settings
    settings = get_settings()
    api_key = settings.OPENROUTER_API_KEY
    model = settings.OPENROUTER_MODEL

    # LiteLLM uses openrouter/ prefix to route to OpenRouter
    os.environ["OPENROUTER_API_KEY"] = api_key
    return f"openrouter/{model}"


def _pages_to_markdown(pages: list[dict]) -> str:
    """Convert crawled pages to markdown format for PageIndex processing."""
    md_parts = []
    for page in pages:
        title = page.get("title", "").strip()
        content = page.get("content", "").strip()
        url = page.get("url", "")

        if not content:
            continue

        # Create markdown heading from title
        if title:
            md_parts.append(f"# {title}")
        elif url:
            md_parts.append(f"# {url}")
        else:
            md_parts.append("# Page")

        if url:
            md_parts.append(f"Source: {url}")
        md_parts.append("")
        md_parts.append(content)
        md_parts.append("")

    return "\n\n".join(md_parts)


async def build_knowledge_index(
    db: AsyncSession,
    tenant_id,
    pages: list[dict],
) -> KnowledgeBase:
    """Build a PageIndex tree from crawled pages and store it.

    Flow:
    1. Convert crawled pages to markdown
    2. Use PageIndex md_to_tree() to build hierarchical tree with summaries
    3. Store tree JSON in knowledge_bases table
    """
    if not pages:
        logger.warning("No pages to index")
        return None

    model = _get_pageindex_model()
    markdown = _pages_to_markdown(pages)

    if not markdown.strip():
        logger.warning("No content to index after conversion")
        return None

    logger.info(f"Building PageIndex tree from {len(pages)} pages ({len(markdown)} chars)")

    # Write markdown to temp file for PageIndex
    tree_data = None
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(markdown)
        md_path = f.name

    try:
        from pageindex.page_index_md import md_to_tree

        tree_data = await md_to_tree(
            md_path=md_path,
            if_thinning=False,
            if_add_node_summary="yes",
            summary_token_threshold=200,
            model=model,
            if_add_doc_description="no",
            if_add_node_text="yes",
            if_add_node_id="yes",
        )
        logger.info(f"PageIndex tree built: {len(tree_data.get('structure', []))} top-level nodes")

    except Exception as e:
        logger.error(f"PageIndex md_to_tree failed: {e}", exc_info=True)
        # Fallback: build a simple tree without LLM summaries
        tree_data = _build_simple_tree(pages)
    finally:
        os.unlink(md_path)

    # Upsert knowledge base
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)
    )
    kb = result.scalar_one_or_none()

    storage = {
        "type": "pageindex",
        "tree": tree_data,
        "metadata": {
            "indexed_at": datetime.utcnow().isoformat(),
            "total_pages": len(pages),
            "model": model,
        },
    }

    if kb:
        kb.tree_json = storage
        kb.source_documents = [{"url": p["url"], "title": p.get("title", "")} for p in pages]
        kb.last_indexed_at = datetime.utcnow()
    else:
        kb = KnowledgeBase(
            tenant_id=tenant_id,
            tree_json=storage,
            source_documents=[{"url": p["url"], "title": p.get("title", "")} for p in pages],
            last_indexed_at=datetime.utcnow(),
        )
        db.add(kb)

    await db.flush()
    return kb


def _build_simple_tree(pages: list[dict]) -> dict:
    """Fallback: build a simple tree without LLM summaries."""
    structure = []
    for i, page in enumerate(pages):
        content = page.get("content", "")
        if content:
            structure.append({
                "title": page.get("title", f"Page {i+1}"),
                "node_id": str(i + 1).zfill(4),
                "text": content[:2000],
                "line_num": 1,
            })
    return {
        "doc_name": "website",
        "line_count": sum(len(p.get("content", "").split("\n")) for p in pages),
        "structure": structure,
    }
