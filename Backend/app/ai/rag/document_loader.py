# AI extension point: load approved uploaded learning material.
# Owner: Krish
#
# Worker entry point Henrick's upload flow calls after queuing a job:
#   enqueue("process_attachment", {"attachment_id": attachment_id})
#
# Per Henrick (13/09): object_path is temporary -- it comes from the backend's
# trusted storage service for now. Once Kaung's attachment repository lookup
# is ready, this becomes process_attachment(attachment_id) only, and
# object_path gets loaded from the ATTACHMENTS record instead of being passed in.
#
# Status updates (queued/processing/ready/failed) are print()-only for now,
# per agreement -- swap these for real repository calls once they exist.
# Do not modify uploaded_by, object_path, channel_id, message_id, or other
# file metadata from this function -- those belong to the backend/DB side.

from app.ai.rag.parser import extract_structured_pdf
from app.ai.rag.chunking import chunk_documents
from app.ai.rag.embedding import embed_chunks
from app.ai.rag.vector_store import save_chunks_local


def process_attachment(attachment_id: int, object_path: str = None) -> None:
    status = "processing"
    print(f"[attachment {attachment_id}] status: {status}")

    try:
        pages = extract_structured_pdf(object_path, image_mode="strict")
        chunks = chunk_documents(pages, chunk_size_words=350, overlap_words=60)
        embedded_chunks = embed_chunks(chunks, attachment_id)

        # TODO: replace with a real CHUNKS insert once Kaung's repository exists
        save_chunks_local(embedded_chunks)

        print(f"[attachment {attachment_id}] {len(pages)} page-entries -> "
              f"{len(chunks)} chunks -> {len(embedded_chunks)} embedded chunks")

        status = "ready"
        print(f"[attachment {attachment_id}] status: {status}")

    except Exception as e:
        status = "failed"
        print(f"[attachment {attachment_id}] status: {status}")
        print(f"[attachment {attachment_id}] error: {e}")
