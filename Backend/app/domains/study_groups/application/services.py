# Study Groups use cases depend on repository interfaces, not HTTP or SQL.
# Current methods delegate to repositories; authorization and business rules still need implementation.
from app.domains.study_groups.domain.models import StudyGroup
from app.domains.study_groups.domain.repository import StudyGroupRepository


class StudyGroupService:

    def __init__(
        self,
        repository: StudyGroupRepository,
    ):
        self.repository = repository

    async def get_all_study_groups(self):

        return await self.repository.get_all_study_groups()

    async def get_study_group_by_id(
        self,
        study_group_id: int,
    ):

        return await self.repository.get_study_group_by_id(
            study_group_id
        )

    async def create_study_group(
        self,
        name: str,
        description: str,
        owner_id: int,
    ):

        return await self.repository.create_study_group(
            name,
            description,
            owner_id,
        )

    async def update_study_group(
        self,
        study_group: StudyGroup,
    ):

        return await self.repository.update_study_group(
            study_group
        )

    async def delete_study_group(
        self,
        study_group_id: int,
    ):

        await self.repository.delete_study_group(
            study_group_id
        )
