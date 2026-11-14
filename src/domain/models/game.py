from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List
from src.domain.models.enums import GameStatus, GameVariant


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Game:
    id: Optional[int]
    code: str
    variant: GameVariant = GameVariant.CLASSIC
    status: GameStatus = GameStatus.WAITING
    current_turn: int = 1
    current_player_index: int = 0
    created_at: datetime = field(default_factory=get_utc_now)

    def advance_turn(self, total_players: int) -> None:
        if total_players <= 0:
            return
        self.current_player_index = (self.current_player_index + 1) % total_players
        if self.current_player_index == 0:
            self.current_turn += 1
