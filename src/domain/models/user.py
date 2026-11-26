from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    """
    Entidad de Dominio que representa la identidad de un jugador o anfitrión en la plataforma.
    """
    id: Optional[int]
    username: str
    password_hash: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str = "USER"  # "USER" o "ADMIN"
    created_at: datetime = field(default_factory=get_utc_now)
