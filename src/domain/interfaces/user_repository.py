from typing import List, Optional, Protocol
from src.domain.models.user import User


class UserRepositoryProtocol(Protocol):
    """Contrato del repositorio para la persistencia y gestión de usuarios."""

    def get_by_id(self, user_id: int) -> Optional[User]:
        ...

    def get_by_username(self, username: str) -> Optional[User]:
        ...

    def list_all(self) -> List[User]:
        ...

    def save(self, user: User) -> User:
        ...

    def delete(self, user_id: int) -> bool:
        ...
