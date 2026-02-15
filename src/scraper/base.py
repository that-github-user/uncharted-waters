"""Abstract base class for publication sources."""

from abc import ABC, abstractmethod

from src.models import Publication, SearchQuery


class PublicationSource(ABC):
    """Interface for retrieving publications from DTIC or similar sources."""

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[Publication]:
        """Search for publications matching the query."""
        ...

    @abstractmethod
    async def fetch_full_abstracts_batch(
        self, publications: list[Publication], max_count: int = 50
    ) -> list[Publication]:
        """Fetch full abstracts for publications (if supported by source)."""
        ...

    @abstractmethod
    async def search_all(self, queries: list[SearchQuery]) -> list[Publication]:
        """Run multiple queries and deduplicate results."""
        ...
