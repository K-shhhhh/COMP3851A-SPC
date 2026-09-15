"""PostgreSQL integration point for attachment metadata.

The database developer implements every ``AttachmentRepository`` operation in
this adapter. The local Notes endpoints deliberately use
``InMemoryAttachmentRepository`` until that integration is ready.
"""

from app.domains.notes.domain.repository import AttachmentRepository


class PostgreSQLAttachmentRepository(AttachmentRepository):
    """Declare the pending PostgreSQL attachment repository adapter."""
