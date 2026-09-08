# Search placeholder: wire an authorized search implementation before returning real results.
# Owner: Krish implements search logic; Henrick enforces caller permissions at the API boundary.
class SearchService:
    """Shared search service."""

    async def search(
        self,
        query: str,
    ):
        return []
