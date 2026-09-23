"""Redis-backed attachment repository, shared across the backend and worker processes.

Interim replacement for InMemoryAttachmentRepository: the Celery worker runs
in a separate process/container, so it cannot see the backend's in-process
Python dict. Redis is a real network service both processes can reach, which
is the only reason this exists. This implements the exact same
AttachmentRepository interface, so nothing elsewhere in the app needs to
change: only the construction line in dependencies.py swaps.

Throwaway once Kaung/Paing's real PostgreSQL repository lands: this class
should be deleted at that point, not maintained alongside it.
"""

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone

from redis.asyncio import Redis

from app.domains.notes.domain.models import (
    NoteAttachment,
    NoteProcessingStatus,
)
from app.domains.notes.domain.repository import AttachmentRepository


class RedisAttachmentRepository(AttachmentRepository):
    """Store attachment records in Redis instead of local process memory."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        key_prefix: str = "spc:notes:attachment:",
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix

    # ---- key naming -------------------------------------------------

    def _attachment_key(self, attachment_id: int) -> str:
        return f"{self._key_prefix}{attachment_id}"

    def _next_id_key(self) -> str:
        return f"{self._key_prefix}next_id"

    def _user_index_key(self, user_id: str) -> str:
        return f"{self._key_prefix}by_user:{user_id}"

    # ---- serialization -----------------------------------------------
    # NoteAttachment is a frozen dataclass, not JSON-serializable on its
    # own (datetimes and the enum need converting to plain strings first).

    def _serialize(self, attachment: NoteAttachment) -> str:
        data = asdict(attachment)
        data["processing_status"] = attachment.processing_status.value
        data["uploaded_at"] = attachment.uploaded_at.isoformat()
        data["updated_at"] = attachment.updated_at.isoformat()
        if attachment.deleted_at is not None:
            data["deleted_at"] = attachment.deleted_at.isoformat()
        else:
            data["deleted_at"] = None
        return json.dumps(data)

    def _deserialize(self, raw: str) -> NoteAttachment:
        data = json.loads(raw)
        data["processing_status"] = NoteProcessingStatus(data["processing_status"])
        data["uploaded_at"] = datetime.fromisoformat(data["uploaded_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data["deleted_at"] is not None:
            data["deleted_at"] = datetime.fromisoformat(data["deleted_at"])
        return NoteAttachment(**data)

    # ---- interface methods --------------------------------------------

    async def create_attachment(
        self,
        *,
        uploaded_by: str,
        title: str,
        file_name: str,
        file_type: str,
        file_size_bytes: int,
        object_path: str,
        channel_id: str | None = None,
        message_id: int | None = None,
    ) -> NoteAttachment:
        """Create a queued attachment with a Redis-assigned identifier."""

        # INCR is atomic in Redis, so this is safe even if two uploads
        # happen at the exact same moment.
        new_id = await self._redis.incr(self._next_id_key())
        current_time = datetime.now(timezone.utc)

        attachment = NoteAttachment(
            attachment_id=new_id,
            uploaded_by=uploaded_by,
            title=title,
            file_name=file_name,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            object_path=object_path,
            processing_status=NoteProcessingStatus.QUEUED,
            processing_progress=0,
            uploaded_at=current_time,
            updated_at=current_time,
            channel_id=channel_id,
            message_id=message_id,
            processing_error=None,
            deleted_at=None,
        )

        await self._redis.set(self._attachment_key(new_id), self._serialize(attachment))

        # Only Notes Library uploads (no channel_id) need to appear in
        # list_note_library_attachments, so only those get indexed here.
        if channel_id is None:
            await self._redis.sadd(self._user_index_key(uploaded_by), new_id)

        return attachment

    async def get_attachment_by_id(
        self,
        attachment_id: int,
    ) -> NoteAttachment | None:
        """Return a non-deleted attachment for trusted internal processing."""

        raw = await self._redis.get(self._attachment_key(attachment_id))

        if raw is None:
            return None

        attachment = self._deserialize(raw)

        if attachment.deleted_at is not None:
            return None

        return attachment

    async def get_owned_attachment(
        self,
        *,
        attachment_id: int,
        user_id: str,
    ) -> NoteAttachment | None:
        """Return an attachment only when it belongs to the requesting user."""

        attachment = await self.get_attachment_by_id(attachment_id)

        if attachment is None:
            return None

        # Conservative rule, matching the in-memory adapter: only the
        # uploader receives access. Group-membership access comes later
        # with the real PostgreSQL repository.
        if attachment.uploaded_by != user_id:
            return None

        return attachment

    async def list_note_library_attachments(
        self,
        *,
        user_id: str,
        offset: int,
        limit: int,
        processing_status: NoteProcessingStatus | None = None,
    ) -> tuple[list[NoteAttachment], int]:
        """List non-deleted My Notes attachments for one student."""

        if offset < 0:
            raise ValueError("offset must not be negative")

        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        member_ids = await self._redis.smembers(self._user_index_key(user_id))

        matching_attachments = []
        for member_id in member_ids:
            attachment_id = int(member_id)
            attachment = await self.get_attachment_by_id(attachment_id)

            if attachment is None:
                # Deleted, or the index is stale -- skip rather than fail.
                continue

            if attachment.channel_id is not None:
                continue

            if processing_status is not None and attachment.processing_status != processing_status:
                continue

            matching_attachments.append(attachment)

        # Display the newest uploads first in My Notes.
        matching_attachments.sort(
            key=lambda attachment: attachment.uploaded_at,
            reverse=True,
        )

        total = len(matching_attachments)
        page = matching_attachments[offset : offset + limit]

        return page, total

    async def update_processing_status(
        self,
        *,
        attachment_id: int,
        processing_status: NoteProcessingStatus,
        processing_progress: int,
        processing_error: str | None = None,
    ) -> NoteAttachment | None:
        """Update processing state for a trusted background worker."""

        attachment = await self.get_attachment_by_id(attachment_id)

        if attachment is None:
            return None

        # NoteAttachment is frozen, so a changed copy is built with
        # dataclasses.replace() rather than mutating the original.
        updated_attachment = replace(
            attachment,
            processing_status=processing_status,
            processing_progress=processing_progress,
            processing_error=processing_error,
            updated_at=datetime.now(timezone.utc),
        )

        await self._redis.set(
            self._attachment_key(attachment_id),
            self._serialize(updated_attachment),
        )

        return updated_attachment

    async def soft_delete_owned_attachment(
        self,
        *,
        attachment_id: int,
        user_id: str,
        deleted_at: datetime,
    ) -> bool:
        """Soft-delete an attachment owned by the requesting user."""

        attachment = await self.get_attachment_by_id(attachment_id)

        if attachment is None:
            return False

        if attachment.uploaded_by != user_id:
            return False

        deleted_attachment = replace(
            attachment,
            deleted_at=deleted_at,
            updated_at=deleted_at,
        )

        await self._redis.set(
            self._attachment_key(attachment_id),
            self._serialize(deleted_attachment),
        )

        # Remove from the listing index too, so it stops appearing in My Notes.
        if attachment.channel_id is None:
            await self._redis.srem(self._user_index_key(user_id), attachment_id)

        return True
