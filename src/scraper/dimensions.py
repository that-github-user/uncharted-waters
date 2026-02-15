"""DTIC Dimensions web scraper using the results.json endpoint."""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from src.config import (
    BRANCH_PATTERNS,
    DETAIL_FETCH_TOP_N,
    DTIC_BASE_URL,
    DTIC_DETAIL_URL,
    DTIC_SEARCH_URL,
    MAX_PAGES,
    REQUEST_DELAY_SECONDS,
    SEARCH_FIELD,
    SEARCH_MODE,
    SEARCH_TYPE,
    USER_AGENT,
)
from src.models import MilitaryBranch, Publication, SearchQuery
from src.scraper.base import PublicationSource

logger = logging.getLogger(__name__)


def detect_branches(text: str) -> list[MilitaryBranch]:
    """Detect military branches from acknowledgements or other text."""
    if not text:
        return []
    text_lower = text.lower()
    branches = []
    for branch_key, patterns in BRANCH_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in text_lower:
                branches.append(MilitaryBranch(branch_key))
                break
    return branches


def _parse_publication(doc: dict) -> Publication:
    """Parse a single document from the results.json response."""
    authors = []
    raw_authors = doc.get("author_list", [])
    if isinstance(raw_authors, str):
        # Live API returns a semicolon- or comma-separated string
        for name in re.split(r"[;,]", raw_authors):
            name = name.strip()
            if name:
                authors.append(name)
    elif isinstance(raw_authors, list):
        for author in raw_authors:
            if isinstance(author, dict):
                name = author.get("full_name", "")
            else:
                name = str(author).strip()
            if name:
                authors.append(name)

    pub_year = None
    if doc.get("pub_year"):
        try:
            pub_year = int(doc["pub_year"])
        except (ValueError, TypeError):
            pass

    ack = doc.get("acknowledgements", "") or ""
    funding = doc.get("funding_section", "") or ""
    # Combine acknowledgements and funding_section for branch detection
    branch_text = f"{ack} {funding}".strip()
    pub_id = str(doc.get("id", ""))

    pub = Publication(
        id=pub_id,
        title=doc.get("title", ""),
        short_abstract=doc.get("short_abstract", "") or "",
        authors=authors,
        pub_year=pub_year,
        journal_title=doc.get("journal_title", "") or "",
        doi=doc.get("doi", "") or "",
        acknowledgements=ack,
        times_cited=doc.get("times_cited", 0) or 0,
        score=doc.get("score", 0.0) or 0.0,
        detected_branches=detect_branches(branch_text),
        url=f"{DTIC_DETAIL_URL}/{pub_id}" if pub_id else "",
    )
    return pub


class DimensionsScraper(PublicationSource):
    """Scraper for DTIC Dimensions results.json endpoint."""

    def __init__(self, delay: float = REQUEST_DELAY_SECONDS):
        self.delay = delay
        self.client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
            follow_redirects=True,
        )

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    def _build_search_url(self, query_text: str, cursor: str | None = None) -> str:
        params = {
            "search_mode": SEARCH_MODE,
            "search_text": query_text,
            "search_type": SEARCH_TYPE,
            "search_field": SEARCH_FIELD,
        }
        if cursor:
            params["np"] = cursor
        return f"{DTIC_SEARCH_URL}?{urlencode(params)}"

    async def _fetch_page(self, url: str) -> dict | None:
        """Fetch a single results.json page."""
        await asyncio.sleep(self.delay)
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            return None

    async def search(self, query: SearchQuery) -> list[Publication]:
        """Search DTIC with a single query, paginating through results."""
        publications: list[Publication] = []
        url = self._build_search_url(query.text)

        for page_num in range(MAX_PAGES):
            logger.info("Fetching page %d for query '%s'", page_num + 1, query.strategy)
            data = await self._fetch_page(url)
            if not data:
                break

            docs = data.get("docs", [])
            if not docs:
                break

            for doc in docs:
                pub = _parse_publication(doc)
                publications.append(pub)

            # Check for next page
            nav = data.get("navigation", {})
            next_url = nav.get("results_json")
            if not next_url:
                break
            # next_url is relative — build absolute
            if next_url.startswith("/"):
                url = f"{DTIC_BASE_URL}{next_url}"
            else:
                url = next_url

        logger.info(
            "Query '%s' returned %d publications", query.strategy, len(publications)
        )
        return publications

    async def fetch_full_abstracts_batch(
        self, publications: list[Publication], max_count: int = DETAIL_FETCH_TOP_N
    ) -> list[Publication]:
        """No-op: detail pages are JS-rendered and cannot be scraped with httpx.

        Short abstracts from the search results are used instead.
        This method is kept for interface compatibility and future API support.
        """
        logger.info(
            "Skipping detail page fetch (JS-rendered). Using short abstracts for %d publications.",
            len(publications),
        )
        return publications

    async def search_all(self, queries: list[SearchQuery]) -> list[Publication]:
        """Run multiple search queries and deduplicate by publication ID."""
        seen_ids: set[str] = set()
        all_pubs: list[Publication] = []

        for query in queries:
            pubs = await self.search(query)
            for pub in pubs:
                if pub.id and pub.id not in seen_ids:
                    seen_ids.add(pub.id)
                    all_pubs.append(pub)

        logger.info(
            "Total unique publications across %d queries: %d",
            len(queries),
            len(all_pubs),
        )
        return all_pubs
