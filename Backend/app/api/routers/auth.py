"""Expose the authentication domain router through the central API package.

This compatibility module keeps the public import path stable. Authentication
endpoint behaviour belongs in ``domains.auth.presentation.router``.
"""

from app.domains.auth.presentation.router import router
