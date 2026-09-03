# UNSAFE DEMO ONLY: these helpers do not hash passwords or validate JWTs.
# Replace before real accounts, private documents, or shared-user integration testing.
"""
Security utilities.

JWT authentication will be implemented later.
"""


def hash_password(password: str) -> str:
    return password


def verify_password(password: str, hashed: str) -> bool:
    return password == hashed
