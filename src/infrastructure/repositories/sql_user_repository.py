from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.domain.interfaces.user_repository import UserRepositoryProtocol
from src.domain.models.user import User
from src.infrastructure.orm.models import UserModel


class SqlUserRepository(UserRepositoryProtocol):
    """Implementación de repositorio SQLite/SQLAlchemy para la entidad User."""

    def __init__(self, session: Session):
        self._session = session
        self._ensure_table()

    def _ensure_table(self) -> None:
        try:
            self._session.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(64) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    email VARCHAR(128) UNIQUE,
                    display_name VARCHAR(64),
                    role VARCHAR(16) NOT NULL DEFAULT 'USER',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            self._session.commit()
        except Exception:
            self._session.rollback()

    def _to_domain(self, model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            password_hash=model.password_hash,
            email=model.email,
            display_name=model.display_name or model.username,
            role=model.role or "USER",
            created_at=model.created_at,
        )

    def get_by_id(self, user_id: int) -> Optional[User]:
        model = self._session.query(UserModel).filter(UserModel.id == user_id).first()
        return self._to_domain(model) if model else None

    def get_by_username(self, username: str) -> Optional[User]:
        model = self._session.query(UserModel).filter(UserModel.username == username.strip().lower()).first()
        return self._to_domain(model) if model else None

    def list_all(self) -> List[User]:
        models = self._session.query(UserModel).order_by(UserModel.created_at.desc()).all()
        return [self._to_domain(m) for m in models]

    def save(self, user: User) -> User:
        clean_username = user.username.strip().lower()
        if user.id is None:
            model = UserModel(
                username=clean_username,
                password_hash=user.password_hash,
                email=user.email.strip().lower() if user.email else None,
                display_name=user.display_name or user.username,
                role=user.role or "USER",
                created_at=user.created_at,
            )
            self._session.add(model)
            self._session.commit()
            self._session.refresh(model)
            user.id = model.id
            return user
        else:
            model = self._session.query(UserModel).filter(UserModel.id == user.id).first()
            if model:
                model.username = clean_username
                model.password_hash = user.password_hash
                model.email = user.email.strip().lower() if user.email else None
                model.display_name = user.display_name or user.username
                model.role = user.role
                self._session.commit()
            return user

    def delete(self, user_id: int) -> bool:
        model = self._session.query(UserModel).filter(UserModel.id == user_id).first()
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True
