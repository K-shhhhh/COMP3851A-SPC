from dataclasses import dataclass


@dataclass(slots=True)
class StudyGroup:
    """Domain entity representing a study group."""

    id: int
    name: str
    description: str
    owner_id: int