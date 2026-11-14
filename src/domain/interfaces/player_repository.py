from typing import Protocol, Optional, List
from src.domain.models.player import Player


class PlayerRepositoryProtocol(Protocol):
    def get_by_id(self, player_id: int) -> Optional[Player]:
        """Obtiene un jugador por su ID."""
        ...

    def list_by_game(self, game_id: int) -> List[Player]:
        """Obtiene la lista ordenada de jugadores de una partida."""
        ...

    def save(self, player: Player) -> Player:
        """Crea o actualiza la información de un jugador (dinero, posición, etc.)."""
        ...
