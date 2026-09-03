# Administration repository contract used by the application service.
# The database developer implements these operations; abstract methods provide no storage.
from abc import ABC, abstractmethod

from app.domains.administration.domain.models import (
    SystemStatus,
)


class AdministrationRepository(ABC):

    @abstractmethod
    async def get_system_status(
        self,
    ) -> SystemStatus:
        raise NotImplementedError
