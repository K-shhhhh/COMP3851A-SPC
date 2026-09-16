"""Celery task integration point for the attachment-processing pipeline.

Owner: Krish/background-processing integration.

Krish will move or expose the tested pipeline as importable Python code and
register its ``process_attachment(attachment_id, object_path)`` entry point as
a Celery task here. No task is registered yet, so the current local in-memory
dispatcher remains active.
"""
