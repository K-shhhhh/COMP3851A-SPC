"""Business errors raised by Study Group application use cases.

These exceptions do not contain HTTP status code. The presentation layer
will translate them into the shared API error response.
"""

class StudyGroupError(Exception):
    """Base exception for expected Study Group failures."""
    
class StudyGroupNotFoundError(StudyGroupError):
    """Raised when a group is missing or inaccessible to the student."""
    
class StudyGroupPermissionDeniedError(StudyGroupError):
    """Raised when the student cannot perform a group operation."""
    
class StudyGroupAlreadyMemberError(StudyGroupError):
    """Raised when a student attempts to join the same group twice."""
    
class StudyGroupMembershipNotFoundError(StudyGroupError):
    """Raised when an operation requires a membership that does not exist."""
    
class PrivateStudyGroupJoinError(StudyGroupError):
    """Raised when a student attempts to directly join a private group."""
    
class StudyGroupFullError(StudyGroupError):
    """Raised when the group has reached its configured member limit."""
    
class InvalidStudyGroupError(StudyGroupError):
    """Raised when group input violates application rules."""
