from typing import Dict, List, Optional
from src.domain.models.enums import GameVariant, TileType, PropertyGroup
from src.domain.models.property import PropertyState
from src.domain.rules.base_strategy import TileActionStrategy, TileDefinition
from src.domain.rules.classic_rules import (
    StreetTileStrategy,
    RailroadTileStrategy,
    UtilityTileStrategy,
    NonPurchasableTileStrategy,
)


def build_classic_board() -> Dict[str, TileActionStrategy]:
    """
    Construye las 40 casillas oficiales del Monopoly Clásico.
    """
    tiles = [
        # Posición 0 - 9
        TileDefinition("GO", "Salida (Cobras $200)", 0, TileType.GO, PropertyGroup.SPECIAL),
        TileDefinition("MEDITERRANEAN_AVE", "Av. Mediterráneo", 1, TileType.STREET, PropertyGroup.BROWN, price=60, base_rent=2, house_cost=50, rent_matrix=(2, 10, 30, 90, 160, 250)),
        TileDefinition("COMMUNITY_CHEST_1", "Caja de Comunidad", 2, TileType.COMMUNITY_CHEST, PropertyGroup.SPECIAL),
        TileDefinition("BALTIC_AVE", "Av. Báltica", 3, TileType.STREET, PropertyGroup.BROWN, price=60, base_rent=4, house_cost=50, rent_matrix=(4, 20, 60, 180, 320, 450)),
        TileDefinition("INCOME_TAX", "Impuesto sobre Ingresos", 4, TileType.TAX, PropertyGroup.SPECIAL, price=200),
        TileDefinition("RAILROAD_READING", "Ferrocarril Reading", 5, TileType.RAILROAD, PropertyGroup.RAILROAD, price=200, base_rent=25),
        TileDefinition("ORIENTAL_AVE", "Av. Oriental", 6, TileType.STREET, PropertyGroup.LIGHT_BLUE, price=100, base_rent=6, house_cost=50, rent_matrix=(6, 30, 90, 270, 400, 550)),
        TileDefinition("CHANCE_1", "Suerte", 7, TileType.CHANCE, PropertyGroup.SPECIAL),
        TileDefinition("VERMONT_AVE", "Av. Vermont", 8, TileType.STREET, PropertyGroup.LIGHT_BLUE, price=100, base_rent=6, house_cost=50, rent_matrix=(6, 30, 90, 270, 400, 550)),
        TileDefinition("CONNECTICUT_AVE", "Av. Connecticut", 9, TileType.STREET, PropertyGroup.LIGHT_BLUE, price=120, base_rent=8, house_cost=50, rent_matrix=(8, 40, 100, 300, 450, 600)),

        # Posición 10 - 19
        TileDefinition("JAIL", "Cárcel / Visitas", 10, TileType.JAIL, PropertyGroup.SPECIAL),
        TileDefinition("ST_CHARLES_PLACE", "Plaza San Carlos", 11, TileType.STREET, PropertyGroup.PINK, price=140, base_rent=10, house_cost=100, rent_matrix=(10, 50, 150, 450, 625, 750)),
        TileDefinition("ELECTRIC_COMPANY", "Compañía de Electricidad", 12, TileType.UTILITY, PropertyGroup.UTILITY, price=150),
        TileDefinition("STATES_AVE", "Av. de los Estados", 13, TileType.STREET, PropertyGroup.PINK, price=140, base_rent=10, house_cost=100, rent_matrix=(10, 50, 150, 450, 625, 750)),
        TileDefinition("VIRGINIA_AVE", "Av. Virginia", 14, TileType.STREET, PropertyGroup.PINK, price=160, base_rent=12, house_cost=100, rent_matrix=(12, 60, 180, 500, 700, 900)),
        TileDefinition("RAILROAD_PENNSYLVANIA", "Ferrocarril de Pensilvania", 15, TileType.RAILROAD, PropertyGroup.RAILROAD, price=200, base_rent=25),
        TileDefinition("ST_JAMES_PLACE", "Plaza San Jaime", 16, TileType.STREET, PropertyGroup.ORANGE, price=180, base_rent=14, house_cost=100, rent_matrix=(14, 70, 200, 550, 750, 950)),
        TileDefinition("COMMUNITY_CHEST_2", "Caja de Comunidad", 17, TileType.COMMUNITY_CHEST, PropertyGroup.SPECIAL),
        TileDefinition("TENNESSEE_AVE", "Av. Tennessee", 18, TileType.STREET, PropertyGroup.ORANGE, price=180, base_rent=14, house_cost=100, rent_matrix=(14, 70, 200, 550, 750, 950)),
        TileDefinition("NEW_YORK_AVE", "Av. Nueva York", 19, TileType.STREET, PropertyGroup.ORANGE, price=200, base_rent=16, house_cost=100, rent_matrix=(16, 80, 220, 600, 800, 1000)),

        # Posición 20 - 29
        TileDefinition("FREE_PARKING", "Parking Gratuito", 20, TileType.FREE_PARKING, PropertyGroup.SPECIAL),
        TileDefinition("KENTUCKY_AVE", "Av. Kentucky", 21, TileType.STREET, PropertyGroup.RED, price=220, base_rent=18, house_cost=150, rent_matrix=(18, 90, 250, 700, 875, 1050)),
        TileDefinition("CHANCE_2", "Suerte", 22, TileType.CHANCE, PropertyGroup.SPECIAL),
        TileDefinition("INDIANA_AVE", "Av. Indiana", 23, TileType.STREET, PropertyGroup.RED, price=220, base_rent=18, house_cost=150, rent_matrix=(18, 90, 250, 700, 875, 1050)),
        TileDefinition("ILLINOIS_AVE", "Av. Illinois", 24, TileType.STREET, PropertyGroup.RED, price=240, base_rent=20, house_cost=150, rent_matrix=(20, 100, 300, 750, 925, 1100)),
        TileDefinition("RAILROAD_BO", "Ferrocarril B. & O.", 25, TileType.RAILROAD, PropertyGroup.RAILROAD, price=200, base_rent=25),
        TileDefinition("ATLANTIC_AVE", "Av. Atlántico", 26, TileType.STREET, PropertyGroup.YELLOW, price=260, base_rent=22, house_cost=150, rent_matrix=(22, 110, 330, 800, 975, 1150)),
        TileDefinition("VENTNOR_AVE", "Av. Ventnor", 27, TileType.STREET, PropertyGroup.YELLOW, price=260, base_rent=22, house_cost=150, rent_matrix=(22, 110, 330, 800, 975, 1150)),
        TileDefinition("WATER_WORKS", "Servicio de Agua Potable", 28, TileType.UTILITY, PropertyGroup.UTILITY, price=150),
        TileDefinition("MARVIN_GARDENS", "Jardines Marvin", 29, TileType.STREET, PropertyGroup.YELLOW, price=280, base_rent=24, house_cost=150, rent_matrix=(24, 120, 360, 850, 1025, 1200)),

        # Posición 30 - 39
        TileDefinition("GO_TO_JAIL", "¡Vaya a la Cárcel!", 30, TileType.GO_TO_JAIL, PropertyGroup.SPECIAL),
        TileDefinition("PACIFIC_AVE", "Av. Pacífico", 31, TileType.STREET, PropertyGroup.GREEN, price=300, base_rent=26, house_cost=200, rent_matrix=(26, 130, 390, 900, 1100, 1275)),
        TileDefinition("NORTH_CAROLINA_AVE", "Av. Carolina del Norte", 32, TileType.STREET, PropertyGroup.GREEN, price=300, base_rent=26, house_cost=200, rent_matrix=(26, 130, 390, 900, 1100, 1275)),
        TileDefinition("COMMUNITY_CHEST_3", "Caja de Comunidad", 33, TileType.COMMUNITY_CHEST, PropertyGroup.SPECIAL),
        TileDefinition("PENNSYLVANIA_AVE", "Av. Pensilvania", 34, TileType.STREET, PropertyGroup.GREEN, price=320, base_rent=28, house_cost=200, rent_matrix=(28, 150, 450, 1000, 1200, 1400)),
        TileDefinition("RAILROAD_SHORT_LINE", "Ferrocarril Vía Rápida (Short Line)", 35, TileType.RAILROAD, PropertyGroup.RAILROAD, price=200, base_rent=25),
        TileDefinition("CHANCE_3", "Suerte", 36, TileType.CHANCE, PropertyGroup.SPECIAL),
        TileDefinition("PARK_PLACE", "Plaza del Parque", 37, TileType.STREET, PropertyGroup.DARK_BLUE, price=350, base_rent=35, house_cost=200, rent_matrix=(35, 175, 500, 1100, 1300, 1500)),
        TileDefinition("LUXURY_TAX", "Impuesto de Lujo", 38, TileType.TAX, PropertyGroup.SPECIAL, price=100),
        TileDefinition("BOARDWALK", "Paseo Tablado (Boardwalk)", 39, TileType.STREET, PropertyGroup.DARK_BLUE, price=400, base_rent=50, house_cost=200, rent_matrix=(50, 200, 600, 1400, 1700, 2000)),
    ]

    registry: Dict[str, TileActionStrategy] = {}
    for t in tiles:
        if t.tile_type == TileType.STREET:
            registry[t.tile_id] = StreetTileStrategy(t)
        elif t.tile_type == TileType.RAILROAD:
            registry[t.tile_id] = RailroadTileStrategy(t)
        elif t.tile_type == TileType.UTILITY:
            registry[t.tile_id] = UtilityTileStrategy(t)
        else:
            registry[t.tile_id] = NonPurchasableTileStrategy(t)
    return registry


class BoardRuleRegistry:
    """
    Registro y Fábrica extensible de reglas de tablero.
    Permite registrar nuevas variantes del juego en tiempo de inicialización
    cumpliendo Open/Closed.
    """
    _variants: Dict[GameVariant, Dict[str, TileActionStrategy]] = {
        GameVariant.CLASSIC: build_classic_board()
    }

    @classmethod
    def register_variant(cls, variant_name: GameVariant, board_strategies: Dict[str, TileActionStrategy]) -> None:
        """Permite a expansiones futuras registrar sus propias reglas sin tocar el código clásico."""
        cls._variants[variant_name] = board_strategies

    @classmethod
    def get_board(cls, variant: GameVariant = GameVariant.CLASSIC) -> Dict[str, TileActionStrategy]:
        """Retorna el mapa completo de casillas para la variante indicada."""
        return cls._variants.get(variant) or cls._variants[GameVariant.CLASSIC]

    @classmethod
    def get_strategy(cls, variant: GameVariant, tile_id: str) -> Optional[TileActionStrategy]:
        variant_rules = cls._variants.get(variant)
        if not variant_rules:
            variant_rules = cls._variants[GameVariant.CLASSIC]
        return variant_rules.get(tile_id)

    @classmethod
    def get_purchasable_tiles(cls, variant: GameVariant = GameVariant.CLASSIC) -> List[TileDefinition]:
        """Obtiene la lista de casillas que pueden ser compradas."""
        variant_rules = cls._variants.get(variant) or cls._variants[GameVariant.CLASSIC]
        return [
            strategy.definition
            for strategy in variant_rules.values()
            if strategy.can_be_purchased()
        ]

    @classmethod
    def get_tile_definition(cls, tile_id: str, variant: GameVariant = GameVariant.CLASSIC) -> Optional[TileDefinition]:
        strategy = cls.get_strategy(variant, tile_id)
        return strategy.definition if strategy else None

    @classmethod
    def is_monopoly_owned(cls, owner_properties: List[PropertyState], group: PropertyGroup, variant: GameVariant = GameVariant.CLASSIC) -> bool:
        """Determina si el jugador posee todas las propiedades del grupo especificado."""
        from src.domain.rules.classic_rules import CLASSIC_GROUP_TILES
        required_tiles = CLASSIC_GROUP_TILES.get(group, set())
        if not required_tiles:
            return False
        owned_ids = {p.tile_id for p in owner_properties}
        return required_tiles.issubset(owned_ids)

    @classmethod
    def calculate_rent(
        cls,
        tile_id: str,
        property_state: PropertyState,
        owner_properties: List[PropertyState],
        dice_roll: int = 7,
        variant: GameVariant = GameVariant.CLASSIC
    ) -> int:
        strategy = cls.get_strategy(variant, tile_id)
        if not strategy:
            return 0
        return strategy.calculate_rent(property_state, owner_properties, dice_roll)
