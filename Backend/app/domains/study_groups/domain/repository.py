from abc import ABC, abstractmethod

from app.domains.study_groups.domain.models import StudyGroup


class StudyGroupRepository(ABC):

    @abstractmethod
    async def get_all_study_groups(self) -> list[StudyGroup]:
        raise NotImplementedError

    @abstractmethod
    async def get_study_group_by_id(
        self,
        study_group_id: int,
    ) -> StudyGroup:
        raise NotImplementedError

    @abstractmethod
    async def create_study_group(
        self,
        name: str,
        description: str,
        owner_id: int,
    ) -> StudyGroup:
        raise NotImplementedError

    @abstractmethod
    async def update_study_group(
        self,
        study_group: StudyGroup,
    ) -> StudyGroup:
        raise NotImplementedError

    @abstractmethod
    async def delete_study_group(
        self,
        study_group_id: int,
    ) -> None:
        raise NotImplementedError