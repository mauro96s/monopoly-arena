from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from src.domain.models.enums import GameStatus, GameVariant
from src.domain.rules.ruleset_config import RulesetConfig

if TYPE_CHECKING:
    from src.domain.models.player import Player


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Game:
    id: Optional[int]
    code: str
    variant: GameVariant = GameVariant.CLASSIC
    theme_id: str = "classic"
    status: GameStatus = GameStatus.WAITING
    current_turn: int = 1
    current_player_index: int = 0
    created_at: datetime = field(default_factory=get_utc_now)
    has_rolled_dice: bool = False
    consecutive_doubles: int = 0
    available_houses: int = 32
    available_hotels: int = 12
    ruleset_config: RulesetConfig = field(default_factory=RulesetConfig)
    free_parking_pool: int = 0
    pending_auction_tiles: List[str] = field(default_factory=list)
    chance_deck_order: List[str] = field(default_factory=list)
    community_chest_deck_order: List[str] = field(default_factory=list)
    owner_user_id: Optional[int] = None

    def get_deck_order(self, deck_type_val: str) -> List[str]:
        if str(deck_type_val).upper() in ("CHANCE", "DECKTYPE.CHANCE"):
            return self.chance_deck_order
        return self.community_chest_deck_order

    def set_deck_order(self, deck_type_val: str, order: List[str]) -> None:
        if str(deck_type_val).upper() in ("CHANCE", "DECKTYPE.CHANCE"):
            self.chance_deck_order = order
        else:
            self.community_chest_deck_order = order

    def pop_next_card(self, deck_type_val: str) -> Optional[str]:
        order = self.get_deck_order(deck_type_val)
        if not order:
            return None
        return order.pop(0)

    def put_card_at_bottom(self, deck_type_val: str, card_id: str) -> None:
        order = self.get_deck_order(deck_type_val)
        if card_id not in order:
            order.append(card_id)

    def get_ruleset(self) -> RulesetConfig:
        if isinstance(self.ruleset_config, RulesetConfig):
            return self.ruleset_config
        if isinstance(self.ruleset_config, dict):
            return RulesetConfig.from_dict(self.ruleset_config)
        return RulesetConfig()

    def advance_turn(self, total_players: int) -> None:
        if total_players <= 0:
            return
        self.current_player_index = (self.current_player_index + 1) % total_players
        if self.current_player_index == 0:
            self.current_turn += 1
        self.has_rolled_dice = False
        self.consecutive_doubles = 0

    def advance_to_next_active_player(self, players: List["Player"]) -> None:
        """Avanza al siguiente jugador activo saltando a los jugadores en bancarrota."""
        if not players:
            return
        total = len(players)
        active_count = sum(1 for p in players if not p.is_bankrupt)
        if active_count <= 1:
            self.status = GameStatus.FINISHED
            return

        for _ in range(total):
            self.current_player_index = (self.current_player_index + 1) % total
            if self.current_player_index == 0:
                self.current_turn += 1
            if not players[self.current_player_index].is_bankrupt:
                break
        self.has_rolled_dice = False
        self.consecutive_doubles = 0
