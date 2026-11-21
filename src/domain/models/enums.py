from enum import Enum


class GameStatus(str, Enum):
    WAITING = "WAITING"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"


class GameVariant(str, Enum):
    CLASSIC = "CLASSIC"
    # Diseñado para futuras expansiones (Open/Closed)
    CUSTOM_EXPANSION = "CUSTOM_EXPANSION"


class TileType(str, Enum):
    STREET = "STREET"
    RAILROAD = "RAILROAD"
    UTILITY = "UTILITY"
    TAX = "TAX"
    CHANCE = "CHANCE"
    COMMUNITY_CHEST = "COMMUNITY_CHEST"
    GO = "GO"
    JAIL = "JAIL"
    FREE_PARKING = "FREE_PARKING"
    GO_TO_JAIL = "GO_TO_JAIL"


class PropertyGroup(str, Enum):
    BROWN = "BROWN"
    LIGHT_BLUE = "LIGHT_BLUE"
    PINK = "PINK"
    ORANGE = "ORANGE"
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    DARK_BLUE = "DARK_BLUE"
    RAILROAD = "RAILROAD"
    UTILITY = "UTILITY"
    SPECIAL = "SPECIAL"


class TransactionType(str, Enum):
    BUY_PROPERTY = "BUY_PROPERTY"
    PAY_RENT = "PAY_RENT"
    PASS_GO = "PASS_GO"
    TAX_PAYMENT = "TAX_PAYMENT"
    BANK_TRANSFER = "BANK_TRANSFER"
    PLAYER_TRADE = "PLAYER_TRADE"
    BUILD_HOUSE = "BUILD_HOUSE"
    SELL_BUILDING = "SELL_BUILDING"
    MORTGAGE = "MORTGAGE"
    UNMORTGAGE = "UNMORTGAGE"
    GAME_FINISHED = "GAME_FINISHED"
