from app.domains.study_groups.domain.models import StudyGroup
from app.domains.study_groups.domain.repository import StudyGroupRepository


class PostgreSQLStudyGroupRepository(StudyGroupRepository):

    async def get_all_study_groups(self) -> list[StudyGroup]:

        return [
            StudyGroup(
                id=1,
                name="COMP3851 Study Group",
                description="Weekly study sessions.",
                owner_id=1,
            )
        ]

    async def get_study_group_by_id(
        self,
        study_group_id: int,
    ) -> StudyGroup:

        return StudyGroup(
            id=study_group_id,
            name="COMP3851 Study Group",
            description="Weekly study sessions.",
            owner_id=1,
        )

    async def create_study_group(
        self,
        name: str,
        description: str,
        owner_id: int,
    ) -> StudyGroup:

        return StudyGroup(
            id=2,
            name=name,
            description=description,
            owner_id=owner_id,
        )

    async def update_study_group(
        self,
        study_group: StudyGroup,
    ) -> StudyGroup:

        return study_group

    async def delete_study_group(
        self,
        study_group_id: int,
    ) -> None:

        return None