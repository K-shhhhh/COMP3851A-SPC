"""Report errors without HTTP-specific behaviour."""


class ReportNotFoundError(Exception):
    """The report or reportable target does not exist."""


class ReportPermissionDeniedError(Exception):
    """The reporter cannot access the selected target."""


class DuplicateReportError(Exception):
    """The same user already has an active report for this target."""


class InvalidEvidenceError(Exception):
    """An uploaded proof image violates the evidence contract."""
