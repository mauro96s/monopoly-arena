from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from src.domain.models.enums import TransactionType


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Transaction:
    id: Optional[int]
    game_id: int
    turn_number: int
    transaction_type: TransactionType
    amount: int
    description: str
    source_player_id: Optional[int] = None   # None si proviene de la Banca
    target_player_id: Optional[int] = None   # None si va hacia la Banca
    tile_id: Optional[str] = None
    created_at: datetime = field(default_factory=get_utc_now)
