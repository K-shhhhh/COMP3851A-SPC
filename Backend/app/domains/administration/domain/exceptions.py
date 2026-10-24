"""Administration application errors mapped safely at the HTTP boundary."""


class AdministrationResourceNotFoundError(Exception):
    pass


class AdministrationConflictError(Exception):
    pass


class AdministrationValidationError(Exception):
    pass
