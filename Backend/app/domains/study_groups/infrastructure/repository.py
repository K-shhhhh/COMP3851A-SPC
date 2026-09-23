# DEMO study groups repository: returns constructed objects instead of executing SQL.
# Do not interpret successful responses as persisted data or authenticated access.
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

# import uuid
# from datetime import datetime, timezone

# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.domains.study_groups.domain.models import StudyGroup
# from app.domains.study_groups.domain.repository import StudyGroupRepository

# from app.models.orm_models import (
#     Group as ORMGroup,
#     GroupType,
# )


# class PostgreSQLStudyGroupRepository(StudyGroupRepository):

#     def __init__(self, session: AsyncSession) -> None:
#         self.session = session

# @staticmethod
# def _to_domain(group: ORMGroup) -> StudyGroup:
#     return StudyGroup(
#         id=str(group.group_id),
#         name=group.group_name,
#         description=group.description,
#         creator_id=str(group.created_by),
#         admin_id=str(group.current_admin),
#         group_type=group.group_type.value,
#         max_members=group.max_members,
#     )

#     async def get_all_study_groups(self) -> list[StudyGroup]:
#         stmt = (
#             select(ORMGroup)
#             .where(ORMGroup.deleted_at.is_(None))
#             .order_by(ORMGroup.created_at)
#         )

#         result = await self.session.scalars(stmt)

#         return [
#             self._to_domain(group)
#             for group in result.all()
#         ]

#     async def get_study_group_by_id(
#         self,
#         study_group_id: uuid.UUID,
#     ) -> StudyGroup:

#         stmt = select(ORMGroup).where(
#             ORMGroup.group_id == study_group_id,
#             ORMGroup.deleted_at.is_(None),
#         )

#         orm_group = await self.session.scalar(stmt)

#         if orm_group is None:
#             raise LookupError(
#                 f"Study group {study_group_id} not found"
#             )

#         return self._to_domain(orm_group)

#     async def create_study_group(
#         self,
#         name: str,
#         description: str | None,
#         creator_id: uuid.UUID,
#         group_type: str,
#         max_members: int,
#     ) -> StudyGroup:

#         orm_group = ORMGroup(
#             group_name=name,
#             description=description,
#             created_by=creator_id,

#             # Your business rule:
#             current_admin=creator_id,

#             group_type=GroupType(group_type),
#             max_members=max_members,

#             created_at=datetime.now(timezone.utc),
#         )

#         self.session.add(orm_group)

#         try:
#             await self.session.commit()
#         except Exception:
#             await self.session.rollback()
#             raise

#         await self.session.refresh(orm_group)

#         return self._to_domain(orm_group)

#     async def update_study_group(
#         self,
#         study_group: StudyGroup,
#     ) -> StudyGroup:

#         stmt = select(ORMGroup).where(
#             ORMGroup.group_id == study_group.id,
#             ORMGroup.deleted_at.is_(None),
#         )

#         orm_group = await self.session.scalar(stmt)

#         if orm_group is None:
#             raise LookupError(
#                 f"Study group {study_group.id} not found"
#             )

#         orm_group.group_name = study_group.name
#         orm_group.description = study_group.description
#         orm_group.current_admin = study_group.admin_id
#         orm_group.group_type = GroupType(study_group.group_type)
#         orm_group.max_members = study_group.max_members

#         orm_group.last_updated_at = datetime.now(timezone.utc)

#         try:
#             await self.session.commit()
#         except Exception:
#             await self.session.rollback()
#             raise

#         await self.session.refresh(orm_group)

#         return self._to_domain(orm_group)

#     async def delete_study_group(
#         self,
#         study_group_id: uuid.UUID,
#     ) -> None:

#         stmt = select(ORMGroup).where(
#             ORMGroup.group_id == study_group_id,
#             ORMGroup.deleted_at.is_(None),
#         )

#         orm_group = await self.session.scalar(stmt)

#         if orm_group is None:
#             raise LookupError(
#                 f"Study group {study_group_id} not found"
#             )

#         orm_group.deleted_at = datetime.now(timezone.utc)

#         try:
#             await self.session.commit()
#         except Exception:
#             await self.session.rollback()
#             raise