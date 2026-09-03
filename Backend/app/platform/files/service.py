# File-storage placeholder: no bytes are persisted or retrieved yet.
# Define upload limits, authorization and quarantine before accepting real material.
class FileStorageService:
    """Shared file storage service."""

    async def upload(
        self,
        filename: str,
        data: bytes,
    ):
        return filename

    async def download(
        self,
        filename: str,
    ):
        return None

    async def delete(
        self,
        filename: str,
    ):
        return True
