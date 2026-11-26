from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class DeckType(str, Enum):
    CHANCE = "CHANCE"
    COMMUNITY_CHEST = "COMMUNITY_CHEST"


class CardEffectType(str, Enum):
    COLLECT_FROM_BANK = "COLLECT_FROM_BANK"
    PAY_TO_BANK = "PAY_TO_BANK"
    COLLECT_FROM_ALL = "COLLECT_FROM_ALL"
    PAY_TO_ALL = "PAY_TO_ALL"
    MOVE_TO_POSITION = "MOVE_TO_POSITION"
    MOVE_RELATIVE = "MOVE_RELATIVE"
    MOVE_NEAREST_TYPE = "MOVE_NEAREST_TYPE"
    GO_TO_JAIL = "GO_TO_JAIL"
    GET_OUT_OF_JAIL_CARD = "GET_OUT_OF_JAIL_CARD"
    REPAIRS_PER_BUILDING = "REPAIRS_PER_BUILDING"


@dataclass
class ThemeCardDefinition:
    """
    Definición desacoplada de una carta de Fortuna (Suerte) o Arca Comunal.
    Permite tematizar títulos, descripciones y vincular efectos mecánicos estándar (OCP).
    """
    card_id: str
    deck: DeckType
    title: str
    description: str
    effect_type: CardEffectType
    params: Dict[str, Any] = field(default_factory=dict)
    icon: Optional[str] = None
