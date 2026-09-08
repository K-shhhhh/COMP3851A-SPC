# Cache placeholder: no Redis reads or writes occur in these methods yet.
# Owner: Krish implements the Redis-backed cache behavior.
class CacheService:
    """Shared cache service."""

    async def get(
        self,
        key: str,
    ):
        return None

    async def set(
        self,
        key: str,
        value,
    ):
        return True

    async def delete(
        self,
        key: str,
    ):
        return True
