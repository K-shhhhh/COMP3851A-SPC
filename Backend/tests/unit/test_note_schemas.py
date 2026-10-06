"""Unit coverage for public Notes response timing fields."""

from datetime import datetime, timedelta, timezone

from app.domains.notes.domain.models import NoteAttachment, NoteProcessingStatus
from app.domains.notes.presentation.schemas import NoteStatusResponse


def test_ready_status_reports_final_upload_to_ready_duration() -> None:
    uploaded_at = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)
    started_at = uploaded_at + timedelta(seconds=2)
    completed_at = uploaded_at + timedelta(seconds=19)
    attachment = NoteAttachment(
        attachment_id=1,
        uploaded_by="user-1",
        title="Timed PDF",
        file_name="timed.pdf",
        file_type="application/pdf",
        file_size_bytes=100,
        object_path="/private/timed.pdf",
        processing_status=NoteProcessingStatus.READY,
        processing_progress=100,
        uploaded_at=uploaded_at,
        updated_at=completed_at,
        processing_started_at=started_at,
        processing_completed_at=completed_at,
    )

    response = NoteStatusResponse.from_attachment(attachment)

    assert response.elapsed_ms == 19_000
    assert response.total_duration_ms == 19_000
    assert response.processing_started_at == started_at
    assert response.processing_completed_at == completed_at
