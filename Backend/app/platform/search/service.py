# Search placeholder: wire an authorized search implementation before returning real results.
class SearchService:
    """Shared search service."""

    async def search(
        self,
        query: str,
    ):
        return []
