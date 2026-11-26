from dataclasses import dataclass, field
from typing import Dict, List, Optional
from src.domain.themes.card_models import DeckType, ThemeCardDefinition


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
    chance_deck_name: str = "Fortuna"
    community_chest_deck_name: str = "Arca Comunal"
    groups: List[GroupThemeMetadata] = field(default_factory=list)
    tiles: Dict[str, TileThemeMetadata] = field(default_factory=dict)
    chance_cards: List[ThemeCardDefinition] = field(default_factory=list)
    community_chest_cards: List[ThemeCardDefinition] = field(default_factory=list)

    def get_tile(self, tile_id: str) -> Optional[TileThemeMetadata]:
        return self.tiles.get(tile_id)

    def get_group(self, group_key: str) -> Optional[GroupThemeMetadata]:
        for g in self.groups:
            if g.key == group_key:
                return g
        return None

    def get_deck_cards(self, deck: DeckType) -> List[ThemeCardDefinition]:
        if deck == DeckType.CHANCE:
            return self.chance_cards
        elif deck == DeckType.COMMUNITY_CHEST:
            return self.community_chest_cards
        return []

    def get_card(self, card_id: str) -> Optional[ThemeCardDefinition]:
        for card in self.chance_cards:
            if card.card_id == card_id:
                return card
        for card in self.community_chest_cards:
            if card.card_id == card_id:
                return card
        return None
