from typing import Protocol, Optional, List
from src.domain.models.game import Game


class GameRepositoryProtocol(Protocol):
    def get_by_id(self, game_id: int) -> Optional[Game]:
        """Obtiene una partida por su ID numérico."""
        ...

    def get_by_code(self, code: str) -> Optional[Game]:
        """Obtiene una partida por su código único de sala."""
        ...

    def list_all(self, limit: int = 20) -> List[Game]:
        """Obtiene la lista de partidas recientes."""
        ...

    def save(self, game: Game) -> Game:
        """Crea o actualiza una partida."""
        ...

    def delete(self, game_id: int) -> bool:
        """Elimina una partida por su ID numérico."""
        ...

    def delete_bulk(self, game_ids: List[int]) -> int:
        """Elimina varias partidas por sus IDs."""
        ...

    def delete_all(self) -> int:
        """Elimina todas las partidas existentes."""
        ...
