from dataclasses import dataclass
from typing import Protocol, Optional, List
from src.domain.models.enums import TileType, PropertyGroup
from src.domain.models.property import PropertyState
from src.domain.models.player import Player


@dataclass(frozen=True)
class TileDefinition:
    """Definición inmutable de una casilla en el tablero."""
    tile_id: str
    name: str
    position: int
    tile_type: TileType
    group: PropertyGroup
    price: int = 0
    base_rent: int = 0
    house_cost: int = 0
    rent_matrix: tuple[int, ...] = ()  # [base, 1 casa, 2 casas, 3 casas, 4 casas, hotel]


class TileActionStrategy(Protocol):
    """
    Patrón Strategy para desacoplar el comportamiento de cada tipo de casilla.
    Permite el Principio Open/Closed: cualquier expansión futura implementa esta
    interfaz sin modificar el motor central.
    """
    definition: TileDefinition

    def can_be_purchased(self) -> bool:
        """Determina si un jugador puede comprar esta casilla."""
        ...

    def calculate_rent(
        self,
        property_state: PropertyState,
        owner_properties: List[PropertyState],
        dice_roll: int = 0
    ) -> int:
        """Calcula el monto de renta a pagar al caer en esta casilla."""
        ...
