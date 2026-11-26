from typing import Any, Dict, List, Optional
from src.domain.themes.models import ThemeDefinition, GroupThemeMetadata, TileThemeMetadata
from src.domain.themes.classic import CLASSIC_THEME
from src.domain.themes.harry_potter import HARRY_POTTER_THEME


class ThemeRegistry:
    """
    Registro desacoplado y extensible de temas visuales para Monopoly.
    Cumple el principio Open/Closed (OCP): nuevos temas (Mundo Mágico, personalizados, etc.)
    se registran dinámicamente sin modificar código preexistente y se consultan tanto
    en memoria como desde persistencia en base de datos.
    """
    _themes: Dict[str, ThemeDefinition] = {
        CLASSIC_THEME.theme_id: CLASSIC_THEME,
        HARRY_POTTER_THEME.theme_id: HARRY_POTTER_THEME,
    }
    _repository: Optional[Any] = None

    @classmethod
    def set_repository(cls, repository: Any) -> None:
        """Configura el repositorio para la resolución dinámica de temas persistidos."""
        cls._repository = repository

    @classmethod
    def register_theme(cls, theme: ThemeDefinition) -> None:
        """Registra un nuevo tema en el catálogo global en memoria."""
        cls._themes[theme.theme_id] = theme

    @classmethod
    def unregister_theme(cls, theme_id: str) -> None:
        """Elimina un tema del catálogo en memoria (si no es oficial)."""
        if theme_id in cls._themes and not cls._themes[theme_id].is_readonly:
            del cls._themes[theme_id]

    @classmethod
    def get_theme(cls, theme_id: str = "classic") -> ThemeDefinition:
        """
        Obtiene un tema por su identificador único.
        1. Consulta la memoria local.
        2. Si no existe, consulta el repositorio de base de datos.
        3. Recurre con seguridad al tema clásico oficial si no se encuentra.
        """
        if theme_id in cls._themes:
            return cls._themes[theme_id]

        if cls._repository:
            try:
                db_theme = cls._repository.get_by_theme_id(theme_id)
                if db_theme:
                    cls._themes[theme_id] = db_theme
                    return db_theme
            except Exception:
                pass

        return cls._themes.get("classic", CLASSIC_THEME)

    @classmethod
    def list_themes(cls) -> List[ThemeDefinition]:
        """
        Lista todos los temas disponibles (oficiales en memoria y personalizados en BD).
        """
        merged: Dict[str, ThemeDefinition] = dict(cls._themes)

        if cls._repository:
            try:
                persisted = cls._repository.list_all()
                for t in persisted:
                    if t.theme_id not in merged:
                        merged[t.theme_id] = t
            except Exception:
                pass

        return list(merged.values())

    @classmethod
    def has_theme(cls, theme_id: str) -> bool:
        """Verifica si un tema existe en memoria o en el repositorio."""
        if theme_id in cls._themes:
            return True
        if cls._repository:
            try:
                return cls._repository.get_by_theme_id(theme_id) is not None
            except Exception:
                pass
        return False
