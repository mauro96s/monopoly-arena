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
    is_official: bool = False
    is_readonly: bool = False
    parent_theme_id: Optional[str] = None
    owner_user_id: Optional[str] = None
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

    def to_dict(self) -> dict:
        return {
            "theme_id": self.theme_id,
            "name": self.name,
            "description": self.description,
            "currency_symbol": self.currency_symbol,
            "currency_code": self.currency_code,
            "chance_deck_name": self.chance_deck_name,
            "community_chest_deck_name": self.community_chest_deck_name,
            "is_official": self.is_official,
            "is_readonly": self.is_readonly,
            "parent_theme_id": self.parent_theme_id,
            "owner_user_id": self.owner_user_id,
            "groups": [
                {
                    "key": g.key,
                    "name": g.name,
                    "color_hex": g.color_hex,
                    "text_color": g.text_color,
                    "icon": g.icon,
                }
                for g in self.groups
            ],
            "tiles": {
                tid: {
                    "tile_id": t.tile_id,
                    "position": t.position,
                    "name": t.name,
                    "short_name": t.short_name,
                    "icon": t.icon,
                    "banner_color": t.banner_color,
                }
                for tid, t in self.tiles.items()
            },
            "chance_cards": [
                {
                    "card_id": c.card_id,
                    "deck": c.deck.value if hasattr(c.deck, "value") else str(c.deck),
                    "title": c.title,
                    "description": c.description,
                    "effect_type": c.effect_type.value if hasattr(c.effect_type, "value") else str(c.effect_type),
                    "params": c.params,
                    "icon": c.icon,
                }
                for c in self.chance_cards
            ],
            "community_chest_cards": [
                {
                    "card_id": c.card_id,
                    "deck": c.deck.value if hasattr(c.deck, "value") else str(c.deck),
                    "title": c.title,
                    "description": c.description,
                    "effect_type": c.effect_type.value if hasattr(c.effect_type, "value") else str(c.effect_type),
                    "params": c.params,
                    "icon": c.icon,
                }
                for c in self.community_chest_cards
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ThemeDefinition":
        from src.domain.themes.card_models import CardEffectType, DeckType

        groups = [
            GroupThemeMetadata(
                key=g["key"],
                name=g["name"],
                color_hex=g["color_hex"],
                text_color=g.get("text_color", "#FFFFFF"),
                icon=g.get("icon", "home"),
            )
            for g in data.get("groups", [])
        ]

        tiles = {}
        for tid, t in data.get("tiles", {}).items():
            tiles[tid] = TileThemeMetadata(
                tile_id=t["tile_id"],
                position=t["position"],
                name=t["name"],
                short_name=t.get("short_name", t["name"]),
                icon=t.get("icon"),
                banner_color=t.get("banner_color"),
            )

        chance_cards = []
        for c in data.get("chance_cards", []):
            try:
                eff = CardEffectType(c["effect_type"])
            except Exception:
                eff = CardEffectType.COLLECT_FROM_BANK
            chance_cards.append(
                ThemeCardDefinition(
                    card_id=c["card_id"],
                    deck=DeckType.CHANCE,
                    title=c["title"],
                    description=c["description"],
                    effect_type=eff,
                    params=c.get("params", {}),
                    icon=c.get("icon"),
                )
            )

        chest_cards = []
        for c in data.get("community_chest_cards", []):
            try:
                eff = CardEffectType(c["effect_type"])
            except Exception:
                eff = CardEffectType.COLLECT_FROM_BANK
            chest_cards.append(
                ThemeCardDefinition(
                    card_id=c["card_id"],
                    deck=DeckType.COMMUNITY_CHEST,
                    title=c["title"],
                    description=c["description"],
                    effect_type=eff,
                    params=c.get("params", {}),
                    icon=c.get("icon"),
                )
            )

        return cls(
            theme_id=data["theme_id"],
            name=data["name"],
            description=data.get("description", ""),
            currency_symbol=data.get("currency_symbol", "$"),
            currency_code=data.get("currency_code", "USD"),
            chance_deck_name=data.get("chance_deck_name", "Fortuna"),
            community_chest_deck_name=data.get("community_chest_deck_name", "Arca Comunal"),
            is_official=data.get("is_official", False),
            is_readonly=data.get("is_readonly", False),
            parent_theme_id=data.get("parent_theme_id"),
            owner_user_id=data.get("owner_user_id"),
            groups=groups,
            tiles=tiles,
            chance_cards=chance_cards,
            community_chest_cards=chest_cards,
        )
