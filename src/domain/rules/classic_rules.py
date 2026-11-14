from typing import List
from src.domain.rules.base_strategy import TileActionStrategy, TileDefinition
from src.domain.models.property import PropertyState
from src.domain.models.enums import TileType, PropertyGroup


CLASSIC_GROUP_TILES = {
    PropertyGroup.BROWN: {"MEDITERRANEAN_AVE", "BALTIC_AVE"},
    PropertyGroup.LIGHT_BLUE: {"ORIENTAL_AVE", "VERMONT_AVE", "CONNECTICUT_AVE"},
    PropertyGroup.PINK: {"ST_CHARLES_PLACE", "STATES_AVE", "VIRGINIA_AVE"},
    PropertyGroup.ORANGE: {"ST_JAMES_PLACE", "TENNESSEE_AVE", "NEW_YORK_AVE"},
    PropertyGroup.RED: {"KENTUCKY_AVE", "INDIANA_AVE", "ILLINOIS_AVE"},
    PropertyGroup.YELLOW: {"ATLANTIC_AVE", "VENTNOR_AVE", "MARVIN_GARDENS"},
    PropertyGroup.GREEN: {"PACIFIC_AVE", "NORTH_CAROLINA_AVE", "PENNSYLVANIA_AVE"},
    PropertyGroup.DARK_BLUE: {"PARK_PLACE", "BOARDWALK"},
    PropertyGroup.RAILROAD: {"RAILROAD_READING", "RAILROAD_PENNSYLVANIA", "RAILROAD_BO", "RAILROAD_SHORT_LINE"},
    PropertyGroup.UTILITY: {"ELECTRIC_COMPANY", "WATER_WORKS"},
}


class StreetTileStrategy:
    """Estrategia para calles tradicionales con casas y hoteles."""
    def __init__(self, definition: TileDefinition):
        self.definition = definition

    def can_be_purchased(self) -> bool:
        return True

    def calculate_rent(
        self,
        property_state: PropertyState,
        owner_properties: List[PropertyState],
        dice_roll: int = 0
    ) -> int:
        if property_state.is_mortgaged:
            return 0

        # Renta por hoteles (índice 5 en rent_matrix: base, 1c, 2c, 3c, 4c, hotel)
        if property_state.hotels_count > 0 and len(self.definition.rent_matrix) >= 6:
            return self.definition.rent_matrix[5]

        # Renta por casas (1 a 4 casas)
        if property_state.houses_count > 0 and len(self.definition.rent_matrix) > property_state.houses_count:
            return self.definition.rent_matrix[property_state.houses_count]

        # Regla de Monopolio: si el dueño tiene todas las calles de este color sin casas, la renta base se DUPLICA
        group_tiles = CLASSIC_GROUP_TILES.get(self.definition.group, set())
        owned_tile_ids = {p.tile_id for p in owner_properties}
        if group_tiles and group_tiles.issubset(owned_tile_ids):
            return self.definition.base_rent * 2

        # Renta base normal
        return self.definition.base_rent


class RailroadTileStrategy:
    """Estrategia para estaciones de tren (la renta se duplica según la cantidad poseída: 25, 50, 100, 200)."""
    def __init__(self, definition: TileDefinition):
        self.definition = definition

    def can_be_purchased(self) -> bool:
        return True

    def calculate_rent(
        self,
        property_state: PropertyState,
        owner_properties: List[PropertyState],
        dice_roll: int = 0
    ) -> int:
        if property_state.is_mortgaged:
            return 0

        railroads = CLASSIC_GROUP_TILES.get(PropertyGroup.RAILROAD, set())
        railroads_owned = sum(1 for p in owner_properties if p.tile_id in railroads)
        scale = max(1, min(railroads_owned, 4))
        return 25 * (2 ** (scale - 1))


class UtilityTileStrategy:
    """Estrategia para servicios públicos (Luz y Agua: 4x o 10x los dados)."""
    def __init__(self, definition: TileDefinition):
        self.definition = definition

    def can_be_purchased(self) -> bool:
        return True

    def calculate_rent(
        self,
        property_state: PropertyState,
        owner_properties: List[PropertyState],
        dice_roll: int = 0
    ) -> int:
        if property_state.is_mortgaged:
            return 0

        utilities_owned = sum(1 for p in owner_properties if p.tile_id in ("ELECTRIC_COMPANY", "WATER_WORKS"))
        multiplier = 10 if utilities_owned >= 2 else 4
        return (dice_roll or 7) * multiplier


class NonPurchasableTileStrategy:
    """Estrategia para casillas que no se pueden comprar (Salida, Impuestos, Suerte, Cárcel, Parking)."""
    def __init__(self, definition: TileDefinition):
        self.definition = definition

    def can_be_purchased(self) -> bool:
        return False

    def calculate_rent(
        self,
        property_state: PropertyState,
        owner_properties: List[PropertyState],
        dice_roll: int = 0
    ) -> int:
        return 0
