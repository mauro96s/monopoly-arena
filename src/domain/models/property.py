from dataclasses import dataclass
from typing import Optional


@dataclass
class PropertyState:
    id: Optional[int]
    game_id: int
    tile_id: str             # Identificador único de casilla (ej: "MEDITERRANEAN_AVE", "BOARDWALK")
    tile_position: int       # 0 a 39 en tablero clásico
    owner_id: Optional[int] = None
    houses_count: int = 0
    hotels_count: int = 0
    is_mortgaged: bool = False
    transfer_interest_paid: bool = False

    @property
    def is_owned(self) -> bool:
        return self.owner_id is not None

    def assign_owner(self, player_id: int) -> None:
        self.owner_id = player_id
