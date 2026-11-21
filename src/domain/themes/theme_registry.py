from typing import Dict, List, Optional
from src.domain.themes.models import ThemeDefinition, GroupThemeMetadata, TileThemeMetadata
from src.domain.themes.classic import CLASSIC_THEME


class ThemeRegistry:
    """
    Registro desacoplado y extensible de temas visuales para Monopoly.
    Cumple el principio Open/Closed (OCP): nuevos temas (Pokémon, Harry Potter, etc.)
    se registran dinámicamente sin modificar código preexistente.
    """
    _themes: Dict[str, ThemeDefinition] = {
        CLASSIC_THEME.theme_id: CLASSIC_THEME,
    }

    @classmethod
    def register_theme(cls, theme: ThemeDefinition) -> None:
        """Registra un nuevo tema en el catálogo global."""
        cls._themes[theme.theme_id] = theme

    @classmethod
    def get_theme(cls, theme_id: str = "classic") -> ThemeDefinition:
        """Obtiene un tema por su identificador único; si no existe, recurre al clásico."""
        return cls._themes.get(theme_id) or cls._themes["classic"]

    @classmethod
    def list_themes(cls) -> List[ThemeDefinition]:
        """Lista todos los temas disponibles en el catálogo."""
        return list(cls._themes.values())

    @classmethod
    def has_theme(cls, theme_id: str) -> bool:
        """Verifica si un tema está registrado."""
        return theme_id in cls._themes
