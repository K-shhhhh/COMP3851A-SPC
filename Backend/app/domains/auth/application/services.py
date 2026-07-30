from app.domains.auth.domain.repository import AuthRepository


class AuthService:

    def __init__(
        self,
        repository: AuthRepository,
    ):
        self.repository = repository

    async def login(
        self,
        email: str,
        password: str,
    ):
        return await self.repository.login(
            email,
            password,
        )

    async def register(
        self,
        full_name: str,
        email: str,
        password: str,
    ):
        return await self.repository.register(
            full_name,
            email,
            password,
        )