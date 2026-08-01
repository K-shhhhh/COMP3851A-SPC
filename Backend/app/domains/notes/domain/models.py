from dataclasses import dataclass


@dataclass(slots=True)
class Note:
    """Domain entity representing a study note."""

    id: int
    title: str
    content: str
    owner_id: int