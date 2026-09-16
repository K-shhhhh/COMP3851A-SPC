"""Integration point for Krish's attachment-processing RAG pipeline.

Krish implements ``AttachmentProcessingDispatcher`` here after exposing the
tested ``process_attachment(attachment_id, object_path)`` function as
importable Python code. Extraction, chunking, embedding, status updates, and
chunk persistence belong to the RAG/background-processing responsibility.
"""
