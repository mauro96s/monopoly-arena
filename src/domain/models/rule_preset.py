from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from src.domain.rules.ruleset_config import RulesetConfig


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RulePreset:
    """
    Entidad de dominio que representa un perfil o preset de reglas guardado y reutilizable.
    """
    id: Optional[int]
    name: str
    description: str
    ruleset_config: RulesetConfig = field(default_factory=RulesetConfig)
    is_system_default: bool = False
    created_at: datetime = field(default_factory=get_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "ruleset_config": self.ruleset_config.to_dict(),
            "is_system_default": self.is_system_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
