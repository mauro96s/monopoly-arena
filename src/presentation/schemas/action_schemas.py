from pydantic import BaseModel, Field
from typing import Optional


class BuyPropertyRequest(BaseModel):
    player_id: int = Field(..., description="ID del jugador que realiza la compra")
    tile_id: str = Field(..., description="Identificador de la casilla (ej: BOARDWALK, MEDITERRANEAN_AVE)")
    auto_advance_turn: bool = True


class BuyPropertyResponse(BaseModel):
    success: bool = True
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


class PayRentRequest(BaseModel):
    payer_player_id: int = Field(..., description="ID del jugador que cayó en la casilla ajena")
    tile_id: str = Field(..., description="Identificador de la casilla en que cayó")
    dice_roll: int = Field(7, description="Suma de los dados (utilizado para calcular renta de servicios)")
    auto_advance_turn: bool = True


class PayRentResponse(BaseModel):
    success: bool = True
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


class BuildHouseRequest(BaseModel):
    player_id: int = Field(..., description="ID del dueño del monopolio")
    tile_id: str = Field(..., description="Casilla donde se construye")


class BuildHouseResponse(BaseModel):
    success: bool = True
    game_id: int
    player_id: int
    player_name: str
    tile_id: str
    tile_name: str
    cost_paid: int
    new_houses_count: int
    new_hotels_count: int
    remaining_balance: int
    available_houses: int = 32
    available_hotels: int = 12
    transaction_id: int


class SellBuildingRequest(BaseModel):
    player_id: int = Field(..., description="ID del dueño del monopolio")
    tile_id: str = Field(..., description="Casilla donde se vende/degrada la construcción")
    sell_entire_group: bool = Field(False, description="Activa la liquidación uniforme del grupo en caso de escasez de casas en el Banco")


class SellBuildingResponse(BaseModel):
    success: bool = True
    game_id: int
    player_id: int
    player_name: str
    tile_id: str
    tile_name: str
    refund_amount: int
    new_houses_count: int
    new_hotels_count: int
    remaining_balance: int
    available_houses: int
    available_hotels: int
    transaction_id: int
    message: str = ""


class MortgageRequest(BaseModel):
    player_id: int = Field(..., description="ID del dueño")
    tile_id: str = Field(..., description="Casilla a hipotecar/deshipotecar")


class MortgageResponse(BaseModel):
    success: bool = True
    game_id: int
    player_id: int
    tile_id: str
    tile_name: str
    amount: int
    is_mortgaged: bool
    remaining_balance: int
    transaction_id: int


class JailActionRequest(BaseModel):
    player_id: Optional[int] = Field(None, description="ID del jugador (opcional: asume el jugador activo)")
    action: str = Field(..., description="'PAY_FINE', 'USE_CARD', 'TRY_DOUBLES', 'GO_TO_JAIL'")
    dice_1: Optional[int] = Field(None, ge=1, le=6)
    dice_2: Optional[int] = Field(None, ge=1, le=6)
    auto_advance_turn: Optional[bool] = Field(None, description="Avanzar turno automáticamente tras encarcelar (True por defecto para GO_TO_JAIL)")


class JailActionResponse(BaseModel):
    success: bool = True
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
    current_turn: int
    current_player_index: int


class BankActionRequest(BaseModel):
    player_id: int
    action_type: str = Field(..., description="'BANK_PAYS_PLAYER', 'PLAYER_PAYS_BANK', 'PASS_GO'")
    custom_amount: Optional[int] = None
    description: Optional[str] = None
    auto_advance_turn: bool = True


class BankActionResponse(BaseModel):
    success: bool = True
    game_id: int
    player_id: int
    player_name: str
    amount: int
    is_credit: bool
    remaining_balance: int
    transaction_id: int
    current_turn: int
    current_player_index: int


class TransferMoneyRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Monto en dinero de Monopoly a transferir")
    description: str = Field(..., min_length=3, max_length=200, description="Motivo del movimiento")
    source_player_id: Optional[int] = Field(None, description="ID del jugador que paga (None para la Banca)")
    target_player_id: Optional[int] = Field(None, description="ID del jugador que cobra (None para la Banca)")
    auto_advance_turn: bool = False


class TransferMoneyResponse(BaseModel):
    success: bool = True
    game_id: int
    transaction_id: int
    amount: int
    description: str
    source_balance: Optional[int] = None
    target_balance: Optional[int] = None
    current_turn: int
    current_player_index: int


class PlayerRankingSchema(BaseModel):
    rank: int
    player_id: int
    name: str
    token: str
    cash: int
    properties_value: int
    buildings_value: int
    mortgage_debt: int
    net_worth: int


class FinishGameResponse(BaseModel):
    success: bool = True
    game_id: int
    winner_name: str
    winner_token: str
    winner_net_worth: int
    rankings: list[PlayerRankingSchema]
    transaction_id: int


class CreateGameRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=16, description="Código de sala (ej: 'SALA123')")
    variant: Optional[str] = "CLASSIC"
    theme_id: Optional[str] = Field("classic", description="ID del tema visual (ej: 'classic', 'pokemon', 'harry_potter')")


class AddPlayerRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    token: str = Field(..., description="Ficha del jugador (ej: 'Carro', 'Sombrero')")


class RollDiceRequest(BaseModel):
    player_id: Optional[int] = Field(None, description="ID del jugador (opcional: asume el jugador con el turno activo)")
    dice_sum: Optional[int] = Field(None, ge=2, le=12, description="Suma total de los dados (ej: 7)")
    total_roll: Optional[int] = Field(None, ge=2, le=12, description="Alias para suma de dados")
    dice_1: Optional[int] = Field(None, ge=1, le=6, description="Valor del dado 1")
    dice_2: Optional[int] = Field(None, ge=1, le=6, description="Valor del dado 2")
    dice1: Optional[int] = Field(None, ge=1, le=6, description="Alias dado 1")
    dice2: Optional[int] = Field(None, ge=1, le=6, description="Alias dado 2")
    auto_advance_turn: Optional[bool] = Field(False, description="Avanzar turno automáticamente tras mover")


class RollDiceResponse(BaseModel):
    success: bool = True
    game_id: int
    player_id: int
    player_name: str
    dice_1: int
    dice_2: int
    total_roll: int
    dice_sum: Optional[int] = None
    is_doubles: bool
    old_position: int
    current_position: Optional[int] = None
    new_position: int
    passed_go: bool
    landed_tile_id: str
    landed_tile_name: str
    landed_tile_type: str
    action_required: str
    action_details: dict
    player_money: int
    money: Optional[int] = None
    updated_money: Optional[int] = None
    player_status: Optional[str] = "ACTIVE"
    player_state: Optional[str] = "ACTIVE"
    in_jail: bool = False
    extra_turn: bool = False
    has_rolled_dice: bool = True
    consecutive_doubles: int = 0
    current_turn: int = 1
    current_player_index: int = 0
    transaction_id: Optional[int] = None


class AuctionPropertyRequest(BaseModel):
    winner_player_id: Optional[int] = None
    buyer_player_id: Optional[int] = None
    tile_id: str
    winning_bid: Optional[int] = None
    bid_amount: Optional[int] = None
    auto_advance_turn: Optional[bool] = True


class AuctionPropertyResponse(BaseModel):
    success: bool = True
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
