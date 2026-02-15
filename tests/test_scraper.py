"""Tests for the DTIC Dimensions scraper."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from src.models import MilitaryBranch, SearchQuery
from src.scraper.dimensions import DimensionsScraper, _parse_publication, detect_branches

FIXTURES = Path(__file__).parent / "fixtures"


class TestBranchDetection:
    def test_detects_navy(self):
        text = "Supported by the Office of Naval Research (ONR) grant N00014-20-1-2345"
        branches = detect_branches(text)
        assert MilitaryBranch.NAVY in branches

    def test_detects_army(self):
        text = "Funded by ARO under grant W911NF-21-1-0001"
        branches = detect_branches(text)
        assert MilitaryBranch.ARMY in branches

    def test_detects_darpa(self):
        text = "Supported by DARPA contract HR0011-20-C-0050"
        branches = detect_branches(text)
        assert MilitaryBranch.DARPA in branches

    def test_detects_air_force(self):
        text = "Air Force Office of Scientific Research grant FA9550-20-1-0001"
        branches = detect_branches(text)
        assert MilitaryBranch.AIR_FORCE in branches

    def test_empty_text(self):
        assert detect_branches("") == []

    def test_no_match(self):
        assert detect_branches("Funded by the National Science Foundation") == []


class TestParsePublication:
    def test_parses_basic_fields(self):
        doc = {
            "id": "pub.123",
            "title": "Test Title",
            "short_abstract": "Test abstract",
            "author_list": [{"full_name": "John Doe"}],
            "pub_year": 2023,
            "journal_title": "Test Journal",
            "doi": "10.1234/test",
            "acknowledgements": "ONR grant N00014",
            "times_cited": 5,
            "score": 7.5,
        }
        pub = _parse_publication(doc)
        assert pub.id == "pub.123"
        assert pub.title == "Test Title"
        assert pub.short_abstract == "Test abstract"
        assert pub.authors == ["John Doe"]
        assert pub.pub_year == 2023
        assert pub.journal_title == "Test Journal"
        assert pub.times_cited == 5
        assert MilitaryBranch.NAVY in pub.detected_branches

    def test_parses_string_author_list(self):
        doc = {
            "id": "pub.789",
            "title": "String Authors",
            "author_list": "Alice Smith, Bob Jones, Carol Lee",
        }
        pub = _parse_publication(doc)
        assert pub.authors == ["Alice Smith", "Bob Jones", "Carol Lee"]

    def test_detects_branches_from_funding_section(self):
        doc = {
            "id": "pub.fund1",
            "title": "Funding Test",
            "acknowledgements": "Thanks to our lab members.",
            "funding_section": "Supported by the Office of Naval Research (ONR) grant N00014-24-1-2536",
        }
        pub = _parse_publication(doc)
        assert MilitaryBranch.NAVY in pub.detected_branches

    def test_handles_missing_fields(self):
        doc = {"id": "pub.456", "title": "Minimal"}
        pub = _parse_publication(doc)
        assert pub.id == "pub.456"
        assert pub.title == "Minimal"
        assert pub.authors == []
        assert pub.pub_year is None


class TestDimensionsScraper:
    @pytest.mark.asyncio
    async def test_search_parses_results(self):
        fixture_data = json.loads((FIXTURES / "search_results.json").read_text())

        with respx.mock:
            respx.get(url__startswith="https://dtic.dimensions.ai/discover/publication/results.json").mock(
                return_value=httpx.Response(200, json=fixture_data)
            )

            scraper = DimensionsScraper(delay=0)
            query = SearchQuery(text="underwater vehicle", strategy="title")
            results = await scraper.search(query)
            await scraper.close()

        assert len(results) == 3
        assert results[0].id == "pub.1140561283"
        assert results[0].title == "Autonomous Underwater Vehicle Navigation in GPS-Denied Environments"
        assert MilitaryBranch.NAVY in results[0].detected_branches
        assert MilitaryBranch.ARMY in results[1].detected_branches
        assert MilitaryBranch.DARPA in results[2].detected_branches

    @pytest.mark.asyncio
    async def test_fetch_full_abstracts_batch_is_noop(self):
        """Detail pages are JS-rendered, so batch fetch is a passthrough."""
        from src.models import Publication
        pubs = [Publication(id="pub.1", title="Test")]
        scraper = DimensionsScraper(delay=0)
        result = await scraper.fetch_full_abstracts_batch(pubs)
        await scraper.close()
        assert result == pubs

    @pytest.mark.asyncio
    async def test_search_all_deduplicates(self):
        fixture_data = json.loads((FIXTURES / "search_results.json").read_text())

        with respx.mock:
            respx.get(url__startswith="https://dtic.dimensions.ai/discover/publication/results.json").mock(
                return_value=httpx.Response(200, json=fixture_data)
            )

            scraper = DimensionsScraper(delay=0)
            queries = [
                SearchQuery(text="underwater vehicle", strategy="title"),
                SearchQuery(text="underwater vehicle nav", strategy="keywords"),
            ]
            results = await scraper.search_all(queries)
            await scraper.close()

        # Should deduplicate — same 3 IDs returned for both queries
        assert len(results) == 3
