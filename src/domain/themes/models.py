from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class GroupThemeMetadata:
    """Metadatos visuales y de presentación para un grupo de propiedades."""
    key: str
    name: str
    color_hex: str
    text_color: str = "#FFFFFF"
    icon: str = "home"


@dataclass
class TileThemeMetadata:
    """Metadatos visuales y de presentación para una casilla individual."""
    tile_id: str
    position: int
    name: str
    short_name: str
    icon: Optional[str] = None
    banner_color: Optional[str] = None


@dataclass
class ThemeDefinition:
    """
    Definición desacoplada y autocontenida de un tema visual para el tablero.
    Permite tematizar completamente nombres, abreviaturas, colores y monedas (OCP).
    """
    theme_id: str
    name: str
    description: str = ""
    currency_symbol: str = "$"
    currency_code: str = "USD"
    groups: List[GroupThemeMetadata] = field(default_factory=list)
    tiles: Dict[str, TileThemeMetadata] = field(default_factory=dict)

    def get_tile(self, tile_id: str) -> Optional[TileThemeMetadata]:
        return self.tiles.get(tile_id)

    def get_group(self, group_key: str) -> Optional[GroupThemeMetadata]:
        for g in self.groups:
            if g.key == group_key:
                return g
        return None
