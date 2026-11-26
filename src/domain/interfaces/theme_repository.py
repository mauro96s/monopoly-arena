from typing import List, Optional, Protocol
from src.domain.themes.models import ThemeDefinition


class ThemeRepositoryProtocol(Protocol):
    """Contrato del repositorio para la persistencia y gestión de temas visuales."""

    def get_by_theme_id(self, theme_id: str) -> Optional[ThemeDefinition]:
        ...

    def list_all(self) -> List[ThemeDefinition]:
        ...

    def save(self, theme: ThemeDefinition) -> ThemeDefinition:
        ...

    def delete(self, theme_id: str) -> bool:
        ...
