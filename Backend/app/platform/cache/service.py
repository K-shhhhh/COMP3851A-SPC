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