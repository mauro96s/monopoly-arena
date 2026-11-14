from typing import Protocol, Optional, List
from src.domain.models.property import PropertyState


class PropertyRepositoryProtocol(Protocol):
    def get_by_tile(self, game_id: int, tile_id: str) -> Optional[PropertyState]:
        """Obtiene el estado de una casilla/propiedad dentro de una partida."""
        ...

    def list_by_game(self, game_id: int) -> List[PropertyState]:
        """Lista el estado de todas las propiedades activas de la partida."""
        ...

    def list_by_owner(self, game_id: int, owner_id: int) -> List[PropertyState]:
        """Lista las propiedades que pertenecen a un jugador específico."""
        ...

    def save(self, property_state: PropertyState) -> PropertyState:
        """Crea o actualiza el estado de la propiedad (dueño, casas, hipoteca)."""
        ...
