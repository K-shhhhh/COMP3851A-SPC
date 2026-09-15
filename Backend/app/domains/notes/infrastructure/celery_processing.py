"""Celery dispatch integration point for Notes attachment processing.

Owner: Krish/background-processing integration.

The implementation will adapt ``AttachmentProcessingDispatcher`` to the
registered Celery task after Krish merges the processing pipeline. Local Notes
development continues to use ``memory_processing.py`` until that handoff is
ready and tested.
"""
