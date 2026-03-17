from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile

import trafilatura

logger = logging.getLogger(__name__)


async def crawl_website(url: str, depth: int = 3) -> list[dict]:
    """Crawl a website using Katana and extract text content.

    Returns list of {url, title, content} dicts.
    Falls back to trafilatura if Katana is not installed.
    """
    # Check if katana is available
    katana_path = shutil.which("katana")

    if katana_path:
        return await _crawl_with_katana(url, depth)
    else:
        logger.warning("Katana not found, falling back to trafilatura")
        return await _crawl_with_trafilatura(url, depth)


async def _crawl_with_katana(url: str, depth: int) -> list[dict]:
    """Crawl using Katana CLI tool."""
    output_dir = tempfile.mkdtemp(prefix="mama_crawl_")
    output_file = os.path.join(output_dir, "urls.json")

    try:
        cmd = [
            "katana",
            "-u", url,
            "-d", str(depth),
            "-j",  # JSON output
            "-o", output_file,
            "-fs", "fqdn",  # Scope to same domain
            "-silent",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=300
        )

        if process.returncode != 0:
            logger.error(f"Katana failed: {stderr.decode()}")
            return []

        # Parse Katana output and extract content
        urls = []
        if os.path.exists(output_file):
            with open(output_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            page_url = data.get("request", {}).get("endpoint", line)
                            urls.append(page_url)
                        except json.JSONDecodeError:
                            urls.append(line)

        # Extract content from discovered URLs
        results = []
        for page_url in urls[:50]:  # Limit to 50 pages
            content = await _extract_page_content(page_url)
            if content:
                results.append(content)

        return results

    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


async def _crawl_with_trafilatura(url: str, depth: int) -> list[dict]:
    """Fallback crawler using trafilatura's built-in discovery."""
    results = []

    # Use trafilatura to find and extract pages
    try:
        from trafilatura import spider
        known_urls = set()

        # Discover URLs
        to_visit, known_urls = spider.focused_crawler(
            url, max_seen_urls=50, max_known_urls=200
        )

        all_urls = list(known_urls)[:50]
        if url not in all_urls:
            all_urls.insert(0, url)

        for page_url in all_urls:
            content = await _extract_page_content(page_url)
            if content:
                results.append(content)

    except Exception as e:
        logger.error(f"Trafilatura crawl failed: {e}")
        # At minimum, extract the provided URL
        content = await _extract_page_content(url)
        if content:
            results.append(content)

    return results


async def _extract_page_content(url: str) -> dict | None:
    """Extract clean text content from a URL."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        if not text or len(text) < 50:
            return None

        metadata = trafilatura.extract(
            downloaded,
            output_format="json",
            include_comments=False,
        )
        title = ""
        if metadata:
            try:
                meta_dict = json.loads(metadata)
                title = meta_dict.get("title", "")
            except json.JSONDecodeError:
                pass

        return {
            "url": url,
            "title": title,
            "content": text,
        }

    except Exception as e:
        logger.error(f"Failed to extract {url}: {e}")
        return None
