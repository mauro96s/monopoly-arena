from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BuyPropertyInputDTO:
    game_id: int
    player_id: int
    tile_id: str
    auto_advance_turn: bool = True


@dataclass(frozen=True)
class BuyPropertyOutputDTO:
    game_id: int
    player_id: int
    player_name: str
    tile_id: str
    tile_name: str
    price_paid: int
    remaining_balance: int
    transaction_id: int
    current_turn: int
    current_player_index: int


@dataclass(frozen=True)
class PayRentInputDTO:
    game_id: int
    payer_player_id: int
    tile_id: str
    dice_roll: int = 7
    auto_advance_turn: bool = True


@dataclass(frozen=True)
class PayRentOutputDTO:
    game_id: int
    payer_id: int
    payer_name: str
    owner_id: int
    owner_name: str
    tile_id: str
    tile_name: str
    rent_amount: int
    is_monopoly_doubled: bool
    houses_count: int
    hotels_count: int
    payer_balance: int
    owner_balance: int
    transaction_id: int
    current_turn: int
    current_player_index: int


@dataclass(frozen=True)
class BuildHouseInputDTO:
    game_id: int
    player_id: int
    tile_id: str


@dataclass(frozen=True)
class BuildHouseOutputDTO:
    game_id: int
    player_id: int
    player_name: str
    tile_id: str
    tile_name: str
    cost_paid: int
    new_houses_count: int
    new_hotels_count: int
    remaining_balance: int
    transaction_id: int
    available_houses: int = 32
    available_hotels: int = 12


@dataclass(frozen=True)
class SellBuildingInputDTO:
    game_id: int
    player_id: int
    tile_id: str
    sell_entire_group: bool = False


@dataclass(frozen=True)
class SellBuildingOutputDTO:
    game_id: int
    player_id: int
    player_name: str
    tile_id: str
    tile_name: str
    refund_amount: int
    new_houses_count: int
    new_hotels_count: int
    remaining_balance: int
    transaction_id: int
    available_houses: int
    available_hotels: int
    message: str = ""


@dataclass(frozen=True)
class MortgageInputDTO:
    game_id: int
    player_id: int
    tile_id: str


@dataclass(frozen=True)
class MortgageOutputDTO:
    game_id: int
    player_id: int
    tile_id: str
    tile_name: str
    amount: int
    is_mortgaged: bool
    remaining_balance: int
    transaction_id: int


@dataclass(frozen=True)
class JailActionInputDTO:
    game_id: int
    player_id: int
    action: str  # "PAY_FINE", "USE_CARD", "TRY_DOUBLES", "GO_TO_JAIL"
    dice_1: Optional[int] = None
    dice_2: Optional[int] = None
    auto_advance_turn: bool = False


@dataclass(frozen=True)
class JailActionOutputDTO:
    game_id: int
    player_id: int
    player_name: str
    in_jail: bool
    jail_turns: int
    amount_paid: int
    remaining_balance: int
    transaction_id: int
    dice_1: Optional[int] = None
    dice_2: Optional[int] = None
    is_doubles: Optional[bool] = None
    new_position: Optional[int] = None
    action_required: Optional[str] = None
    action_details: Optional[dict] = None
    current_turn: int = 1
    current_player_index: int = 0


@dataclass(frozen=True)
class BankActionInputDTO:
    game_id: int
    player_id: int
    action_type: str  # "PASS_GO", "INCOME_TAX", "LUXURY_TAX", "CHANCE_REWARD", "CHEST_REWARD"
    custom_amount: Optional[int] = None
    description: Optional[str] = None
    auto_advance_turn: bool = True


@dataclass(frozen=True)
class BankActionOutputDTO:
    game_id: int
    player_id: int
    player_name: str
    amount: int
    is_credit: bool
    remaining_balance: int
    transaction_id: int
    current_turn: int
    current_player_index: int


@dataclass(frozen=True)
class TransferMoneyInputDTO:
    game_id: int
    amount: int
    description: str
    source_player_id: Optional[int] = None   # None si es la banca
    target_player_id: Optional[int] = None   # None si es la banca
    auto_advance_turn: bool = True


@dataclass(frozen=True)
class TransferMoneyOutputDTO:
    game_id: int
    transaction_id: int
    amount: int
    description: str
    source_balance: Optional[int] = None
    target_balance: Optional[int] = None
    current_turn: int = 1
    current_player_index: int = 0


@dataclass(frozen=True)
class RollDiceInputDTO:
    game_id: int
    player_id: Optional[int] = None
    dice_1: Optional[int] = None
    dice_2: Optional[int] = None
    total_roll: Optional[int] = None
    dice_sum: Optional[int] = None
    auto_advance_turn: bool = False
    is_jail_attempt: bool = False


@dataclass(frozen=True)
class RollDiceOutputDTO:
    game_id: int
    player_id: int
    player_name: str
    dice_1: int
    dice_2: int
    total_roll: int
    is_doubles: bool
    old_position: int
    new_position: int
    passed_go: bool
    landed_tile_id: str
    landed_tile_name: str
    landed_tile_type: str
    action_required: str
    action_details: dict
    player_money: int
    player_status: str = "ACTIVE"
    in_jail: bool = False
    extra_turn: bool = False
    has_rolled_dice: bool = True
    consecutive_doubles: int = 0
    current_turn: int = 1
    current_player_index: int = 0
    transaction_id: Optional[int] = None


@dataclass(frozen=True)
class AuctionPropertyInputDTO:
    game_id: int
    winner_player_id: int
    tile_id: str
    winning_bid: int
    auto_advance_turn: bool = True


@dataclass(frozen=True)
class AuctionPropertyOutputDTO:
    success: bool
    game_id: int
    winner_player_id: int
    winner_name: str
    tile_id: str
    tile_name: str
    winning_bid: int
    remaining_balance: int
    transaction_id: int
    current_turn: int
    current_player_index: int
