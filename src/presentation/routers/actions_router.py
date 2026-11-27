from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from src.presentation.schemas.action_schemas import (
    BuyPropertyRequest,
    BuyPropertyResponse,
    AuctionPropertyRequest,
    AuctionPropertyResponse,
    PayRentRequest,
    PayRentResponse,
    BuildHouseRequest,
    BuildHouseResponse,
    SellBuildingRequest,
    SellBuildingResponse,
    DeclareBankruptcyRequest,
    DeclareBankruptcyResponse,
    MortgageRequest,
    MortgageResponse,
    JailActionRequest,
    JailActionResponse,
    BankActionRequest,
    BankActionResponse,
    TransferMoneyRequest,
    TransferMoneyResponse,
    FinishGameResponse,
    PlayerRankingSchema,
    RollDiceRequest,
    RollDiceResponse,
    DrawCardRequest,
    DrawCardResponse,
)
from src.application.dtos.action_dtos import (
    BuyPropertyInputDTO,
    AuctionPropertyInputDTO,
    PayRentInputDTO,
    BuildHouseInputDTO,
    SellBuildingInputDTO,
    DeclareBankruptcyInputDTO,
    MortgageInputDTO,
    JailActionInputDTO,
    BankActionInputDTO,
    TransferMoneyInputDTO,
    RollDiceInputDTO,
    DrawCardInputDTO,
)
from src.application.use_cases import (
    BuyPropertyUseCase,
    AuctionPropertyUseCase,
    PayRentUseCase,
    BuildHouseUseCase,
    SellBuildingUseCase,
    DeclareBankruptcyUseCase,
    MortgagePropertyUseCase,
    JailActionUseCase,
    BankActionUseCase,
    TransferMoneyUseCase,
    FinishGameUseCase,
    RollDiceUseCase,
    MovePlayerByDiceUseCase,
    DrawCardUseCase,
)
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.models.enums import GameStatus
from src.domain.models.game import Game
from src.domain.models.player import Player
from src.domain.models.user import User
from src.presentation.dependencies import (
    get_game_repository,
    get_player_repository,
    get_buy_property_use_case,
    get_auction_property_use_case,
    get_pay_rent_use_case,
    get_build_house_use_case,
    get_sell_building_use_case,
    get_declare_bankruptcy_use_case,
    get_mortgage_property_use_case,
    get_jail_action_use_case,
    get_bank_action_use_case,
    get_transfer_money_use_case,
    get_finish_game_use_case,
    get_roll_dice_use_case,
    get_move_player_by_dice_use_case,
    get_draw_card_use_case,
    get_current_user_optional,
    assert_can_act_for_player,
)
from src.presentation.websocket_manager import broadcast_game_event_sync
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    PropertyNotFoundError,
    PropertyAlreadyOwnedError,
    InsufficientFundsError,
    InvalidGameActionError,
)

router = APIRouter(prefix="/games/{game_id}/actions", tags=["Game Actions"])


def assert_active_turn(
    game_id: int,
    player_id: int,
    game_repo: GameRepositoryProtocol,
    player_repo: PlayerRepositoryProtocol,
    current_user: Optional[User] = None,
):
    """Garantiza la regla estricta: solo el jugador en turno puede ejecutar acciones y valida autoría en multijugador."""
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    if game.status == GameStatus.FINISHED:
        raise HTTPException(status_code=400, detail="La partida ya ha finalizado.")

    players = player_repo.list_by_game(game_id)
    if not players:
        return

    active_player = players[game.current_player_index % len(players)]
    if player_id != active_player.id:
        player_name = next((p.name for p in players if p.id == player_id), "Este jugador")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Acción bloqueada: No es el turno de {player_name}. Es el turno de {active_player.name}."
        )

    # Validar autoría multijugador
    assert_can_act_for_player(game, active_player, current_user)


@router.post("/roll-dice", response_model=RollDiceResponse, status_code=status.HTTP_200_OK)
@router.post("/roll-dice/", response_model=RollDiceResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
@router.post("/move-player", response_model=RollDiceResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
@router.post("/move-player/", response_model=RollDiceResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def roll_dice(
    game_id: int,
    payload: Optional[RollDiceRequest] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
    use_case: RollDiceUseCase = Depends(get_roll_dice_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    if payload is None:
        payload = RollDiceRequest()

    # Resolver jugador activo si no se especifica player_id
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    if game.status == GameStatus.FINISHED:
        raise HTTPException(status_code=400, detail="La partida ya ha finalizado.")

    players = player_repo.list_by_game(game_id)
    if not players:
        raise HTTPException(status_code=400, detail="No hay jugadores en la partida.")

    active_player = players[game.current_player_index % len(players)]
    target_player_id = payload.player_id if payload.player_id is not None else active_player.id

    assert_active_turn(game_id, target_player_id, game_repo, player_repo, current_user)

    total_roll = payload.dice_sum if payload.dice_sum is not None else payload.total_roll
    d1 = payload.dice1 if payload.dice1 is not None else payload.dice_1
    d2 = payload.dice2 if payload.dice2 is not None else payload.dice_2

    dto = RollDiceInputDTO(
        game_id=game_id,
        player_id=target_player_id,
        dice_1=d1,
        dice_2=d2,
        total_roll=total_roll,
        dice_sum=total_roll,
        auto_advance_turn=bool(payload.auto_advance_turn),
    )
    try:
        res = use_case.execute(dto)
        response = RollDiceResponse(
            success=True,
            game_id=res.game_id,
            player_id=res.player_id,
            player_name=res.player_name,
            dice_1=res.dice_1,
            dice_2=res.dice_2,
            total_roll=res.total_roll,
            dice_sum=res.total_roll,
            is_doubles=res.is_doubles,
            old_position=res.old_position,
            current_position=res.new_position,
            new_position=res.new_position,
            passed_go=res.passed_go,
            landed_tile_id=res.landed_tile_id,
            landed_tile_name=res.landed_tile_name,
            landed_tile_type=res.landed_tile_type,
            action_required=res.action_required,
            action_details=res.action_details,
            player_money=res.player_money,
            money=res.player_money,
            updated_money=res.player_money,
            player_status=res.player_status,
            player_state=res.player_status,
            in_jail=res.in_jail,
            extra_turn=res.extra_turn,
            has_rolled_dice=res.has_rolled_dice,
            consecutive_doubles=res.consecutive_doubles,
            current_turn=res.current_turn,
            current_player_index=res.current_player_index,
            transaction_id=res.transaction_id,
        )
        broadcast_game_event_sync(game_id, "DICE_ROLLED", {
            "player_id": res.player_id,
            "total_roll": res.total_roll,
            "new_position": res.new_position,
            "action_required": res.action_required,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/buy-property", response_model=BuyPropertyResponse, status_code=status.HTTP_200_OK)
def buy_property(
    game_id: int,
    payload: BuyPropertyRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    use_case: BuyPropertyUseCase = Depends(get_buy_property_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.player_id, game_repo, player_repo, current_user)
    dto = BuyPropertyInputDTO(
        game_id=game_id,
        player_id=payload.player_id,
        tile_id=payload.tile_id,
        auto_advance_turn=payload.auto_advance_turn,
    )
    try:
        result = use_case.execute(dto)
        response = BuyPropertyResponse(
            success=True,
            game_id=result.game_id,
            player_id=result.player_id,
            player_name=result.player_name,
            tile_id=result.tile_id,
            tile_name=result.tile_name,
            price_paid=result.price_paid,
            remaining_balance=result.remaining_balance,
            transaction_id=result.transaction_id,
            current_turn=result.current_turn,
            current_player_index=result.current_player_index,
            is_game_finished=result.is_game_finished,
            winner_player_id=result.winner_player_id,
            winner_player_name=result.winner_player_name,
            quick_end_details=result.quick_end_details,
        )
        broadcast_game_event_sync(game_id, "PROPERTY_BOUGHT", {
            "player_id": result.player_id,
            "tile_id": result.tile_id,
            "price_paid": result.price_paid,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (PropertyAlreadyOwnedError, InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/auction", response_model=AuctionPropertyResponse, status_code=status.HTTP_200_OK)
@router.post("/auction-property", response_model=AuctionPropertyResponse, status_code=status.HTTP_200_OK)
def auction_property(
    game_id: int,
    payload: AuctionPropertyRequest,
    use_case: AuctionPropertyUseCase = Depends(get_auction_property_use_case),
):
    """Adjudica una propiedad no adquirida tras una subasta oficial entre jugadores."""
    winner_id = payload.winner_player_id if payload.winner_player_id is not None else payload.buyer_player_id
    if winner_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Se requiere el identificador del ganador (winner_player_id o buyer_player_id)."
        )
    bid = payload.winning_bid if payload.winning_bid is not None else payload.bid_amount
    if bid is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Se requiere el monto de la puja (winning_bid o bid_amount)."
        )

    dto = AuctionPropertyInputDTO(
        game_id=game_id,
        winner_player_id=winner_id,
        tile_id=payload.tile_id,
        winning_bid=bid,
        auto_advance_turn=bool(payload.auto_advance_turn),
    )
    try:
        result = use_case.execute(dto)
        response = AuctionPropertyResponse(
            success=True,
            game_id=result.game_id,
            winner_player_id=result.winner_player_id,
            winner_name=result.winner_name,
            tile_id=result.tile_id,
            tile_name=result.tile_name,
            winning_bid=result.winning_bid,
            remaining_balance=result.remaining_balance,
            transaction_id=result.transaction_id,
            current_turn=result.current_turn,
            current_player_index=result.current_player_index,
            is_game_finished=result.is_game_finished,
            winner_player_id_game=result.winner_player_id_game,
            winner_player_name_game=result.winner_player_name_game,
            quick_end_details=result.quick_end_details,
        )
        broadcast_game_event_sync(game_id, "PROPERTY_AUCTIONED", {
            "winner_player_id": result.winner_player_id,
            "tile_id": result.tile_id,
            "winning_bid": result.winning_bid,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (PropertyAlreadyOwnedError, InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/pay-rent", response_model=PayRentResponse, status_code=status.HTTP_200_OK)
def pay_rent(
    game_id: int,
    payload: PayRentRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    use_case: PayRentUseCase = Depends(get_pay_rent_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.payer_player_id, game_repo, player_repo, current_user)
    dto = PayRentInputDTO(
        game_id=game_id,
        payer_player_id=payload.payer_player_id,
        tile_id=payload.tile_id,
        dice_roll=payload.dice_roll,
        auto_advance_turn=payload.auto_advance_turn,
    )
    try:
        result = use_case.execute(dto)
        response = PayRentResponse(
            success=True,
            game_id=result.game_id,
            payer_id=result.payer_id,
            payer_name=result.payer_name,
            owner_id=result.owner_id,
            owner_name=result.owner_name,
            tile_id=result.tile_id,
            tile_name=result.tile_name,
            rent_amount=result.rent_amount,
            is_monopoly_doubled=result.is_monopoly_doubled,
            houses_count=result.houses_count,
            hotels_count=result.hotels_count,
            payer_balance=result.payer_balance,
            owner_balance=result.owner_balance,
            transaction_id=result.transaction_id,
            current_turn=result.current_turn,
            current_player_index=result.current_player_index,
        )
        broadcast_game_event_sync(game_id, "RENT_PAID", {
            "payer_id": result.payer_id,
            "owner_id": result.owner_id,
            "rent_amount": result.rent_amount,
            "tile_id": result.tile_id,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/build-house", response_model=BuildHouseResponse, status_code=status.HTTP_200_OK)
def build_house(
    game_id: int,
    payload: BuildHouseRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    use_case: BuildHouseUseCase = Depends(get_build_house_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.player_id, game_repo, player_repo, current_user)
    dto = BuildHouseInputDTO(
        game_id=game_id,
        player_id=payload.player_id,
        tile_id=payload.tile_id,
    )
    try:
        result = use_case.execute(dto)
        response = BuildHouseResponse(
            success=True,
            game_id=result.game_id,
            player_id=result.player_id,
            player_name=result.player_name,
            tile_id=result.tile_id,
            tile_name=result.tile_name,
            cost_paid=result.cost_paid,
            new_houses_count=result.new_houses_count,
            new_hotels_count=result.new_hotels_count,
            remaining_balance=result.remaining_balance,
            available_houses=result.available_houses,
            available_hotels=result.available_hotels,
            transaction_id=result.transaction_id,
        )
        broadcast_game_event_sync(game_id, "HOUSE_BUILT", {
            "player_id": result.player_id,
            "tile_id": result.tile_id,
            "new_houses_count": result.new_houses_count,
            "new_hotels_count": result.new_hotels_count,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sell-building", response_model=SellBuildingResponse, status_code=status.HTTP_200_OK)
@router.post("/sell-house", response_model=SellBuildingResponse, status_code=status.HTTP_200_OK)
def sell_building(
    game_id: int,
    payload: SellBuildingRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    use_case: SellBuildingUseCase = Depends(get_sell_building_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.player_id, game_repo, player_repo, current_user)
    dto = SellBuildingInputDTO(
        game_id=game_id,
        player_id=payload.player_id,
        tile_id=payload.tile_id,
        sell_entire_group=payload.sell_entire_group,
    )
    try:
        result = use_case.execute(dto)
        response = SellBuildingResponse(
            success=True,
            game_id=result.game_id,
            player_id=result.player_id,
            player_name=result.player_name,
            tile_id=result.tile_id,
            tile_name=result.tile_name,
            refund_amount=result.refund_amount,
            new_houses_count=result.new_houses_count,
            new_hotels_count=result.new_hotels_count,
            remaining_balance=result.remaining_balance,
            available_houses=result.available_houses,
            available_hotels=result.available_hotels,
            transaction_id=result.transaction_id,
            message=result.message,
        )
        broadcast_game_event_sync(game_id, "BUILDING_SOLD", {
            "player_id": result.player_id,
            "tile_id": result.tile_id,
            "refund_amount": result.refund_amount,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/declare-bankruptcy", response_model=DeclareBankruptcyResponse, status_code=status.HTTP_200_OK)
def declare_bankruptcy(
    game_id: int,
    payload: DeclareBankruptcyRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    use_case: DeclareBankruptcyUseCase = Depends(get_declare_bankruptcy_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    bankrupt_player = player_repo.get_by_id(payload.bankrupt_player_id)
    if not bankrupt_player:
        raise HTTPException(status_code=404, detail="Jugador quebrado no encontrado.")
    assert_can_act_for_player(game, bankrupt_player, current_user)

    dto = DeclareBankruptcyInputDTO(
        game_id=game_id,
        bankrupt_player_id=payload.bankrupt_player_id,
        creditor_player_id=payload.creditor_player_id,
        unmortgage_transferred_properties=payload.unmortgage_transferred_properties,
    )
    try:
        result = use_case.execute(dto)
        response = DeclareBankruptcyResponse(
            success=True,
            game_id=result.game_id,
            bankrupt_player_id=result.bankrupt_player_id,
            bankrupt_player_name=result.bankrupt_player_name,
            creditor_player_id=result.creditor_player_id,
            creditor_player_name=result.creditor_player_name,
            cash_transferred=result.cash_transferred,
            properties_transferred=result.properties_transferred,
            mortgage_interest_paid_to_bank=result.mortgage_interest_paid_to_bank,
            unmortgage_principal_paid_to_bank=result.unmortgage_principal_paid_to_bank,
            released_to_auction_tiles=result.released_to_auction_tiles,
            remaining_active_players_count=result.remaining_active_players_count,
            is_game_finished=result.is_game_finished,
            winner_player_id=result.winner_player_id,
            winner_player_name=result.winner_player_name,
            transaction_id=result.transaction_id,
            message=result.message,
        )
        broadcast_game_event_sync(game_id, "BANKRUPTCY_DECLARED", {
            "bankrupt_player_id": result.bankrupt_player_id,
            "creditor_player_id": result.creditor_player_id,
            "is_game_finished": result.is_game_finished,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/mortgage", response_model=MortgageResponse, status_code=status.HTTP_200_OK)
@router.post("/mortgage-property", response_model=MortgageResponse, status_code=status.HTTP_200_OK)
def mortgage_property(
    game_id: int,
    payload: MortgageRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    use_case: MortgagePropertyUseCase = Depends(get_mortgage_property_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.player_id, game_repo, player_repo, current_user)
    dto = MortgageInputDTO(
        game_id=game_id,
        player_id=payload.player_id,
        tile_id=payload.tile_id,
    )
    try:
        result = use_case.execute(dto)
        response = MortgageResponse(
            success=True,
            game_id=result.game_id,
            player_id=result.player_id,
            tile_id=result.tile_id,
            tile_name=result.tile_name,
            amount=result.amount,
            is_mortgaged=result.is_mortgaged,
            remaining_balance=result.remaining_balance,
            transaction_id=result.transaction_id,
        )
        broadcast_game_event_sync(game_id, "PROPERTY_MORTGAGED", {
            "player_id": result.player_id,
            "tile_id": result.tile_id,
            "is_mortgaged": result.is_mortgaged,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/jail", response_model=JailActionResponse, status_code=status.HTTP_200_OK)
@router.post("/jail-action", response_model=JailActionResponse, status_code=status.HTTP_200_OK)
def jail_action(
    game_id: int,
    payload: JailActionRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    use_case: JailActionUseCase = Depends(get_jail_action_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    players = player_repo.list_by_game(game_id)
    if not players:
        raise HTTPException(status_code=400, detail="No hay jugadores en la partida.")

    active_player = players[game.current_player_index % len(players)]
    target_player_id = payload.player_id if payload.player_id is not None else active_player.id

    assert_active_turn(game_id, target_player_id, game_repo, player_repo, current_user)
    auto_advance = payload.auto_advance_turn if payload.auto_advance_turn is not None else (True if payload.action == "GO_TO_JAIL" else False)
    dto = JailActionInputDTO(
        game_id=game_id,
        player_id=target_player_id,
        action=payload.action,
        dice_1=payload.dice_1,
        dice_2=payload.dice_2,
        auto_advance_turn=auto_advance,
    )
    try:
        result = use_case.execute(dto)
        response = JailActionResponse(
            success=True,
            game_id=result.game_id,
            player_id=result.player_id,
            player_name=result.player_name,
            in_jail=result.in_jail,
            jail_turns=result.jail_turns,
            amount_paid=result.amount_paid,
            remaining_balance=result.remaining_balance,
            transaction_id=result.transaction_id,
            dice_1=result.dice_1,
            dice_2=result.dice_2,
            is_doubles=result.is_doubles,
            new_position=result.new_position,
            action_required=result.action_required,
            action_details=result.action_details,
            current_turn=result.current_turn,
            current_player_index=result.current_player_index,
        )
        broadcast_game_event_sync(game_id, "JAIL_ACTION", {
            "player_id": result.player_id,
            "in_jail": result.in_jail,
            "amount_paid": result.amount_paid,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/bank", response_model=BankActionResponse, status_code=status.HTTP_200_OK)
@router.post("/bank-action", response_model=BankActionResponse, status_code=status.HTTP_200_OK)
def bank_action(
    game_id: int,
    payload: BankActionRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    use_case: BankActionUseCase = Depends(get_bank_action_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.player_id, game_repo, player_repo, current_user)
    dto = BankActionInputDTO(
        game_id=game_id,
        player_id=payload.player_id,
        action_type=payload.action_type,
        custom_amount=payload.custom_amount,
        description=payload.description,
        auto_advance_turn=payload.auto_advance_turn,
    )
    try:
        result = use_case.execute(dto)
        response = BankActionResponse(
            success=True,
            game_id=result.game_id,
            player_id=result.player_id,
            player_name=result.player_name,
            amount=result.amount,
            is_credit=result.is_credit,
            remaining_balance=result.remaining_balance,
            transaction_id=result.transaction_id,
            current_turn=result.current_turn,
            current_player_index=result.current_player_index,
            is_game_finished=result.is_game_finished,
            winner_player_id=result.winner_player_id,
            winner_player_name=result.winner_player_name,
            quick_end_details=result.quick_end_details,
        )
        broadcast_game_event_sync(game_id, "BANK_ACTION", {
            "player_id": result.player_id,
            "amount": result.amount,
            "is_credit": result.is_credit,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/transfer-money", response_model=TransferMoneyResponse, status_code=status.HTTP_200_OK)
def transfer_money(
    game_id: int,
    payload: TransferMoneyRequest,
    use_case: TransferMoneyUseCase = Depends(get_transfer_money_use_case),
):
    dto = TransferMoneyInputDTO(
        game_id=game_id,
        amount=payload.amount,
        description=payload.description,
        source_player_id=payload.source_player_id,
        target_player_id=payload.target_player_id,
    )
    try:
        result = use_case.execute(dto)
        response = TransferMoneyResponse(
            success=True,
            game_id=result.game_id,
            transaction_id=result.transaction_id,
            amount=result.amount,
            description=result.description,
            source_balance=result.source_balance,
            target_balance=result.target_balance,
            current_turn=result.current_turn,
            current_player_index=result.current_player_index,
        )
        broadcast_game_event_sync(game_id, "MONEY_TRANSFERRED", {
            "source_player_id": result.source_player_id,
            "target_player_id": result.target_player_id,
            "amount": result.amount,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InsufficientFundsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/finish", response_model=FinishGameResponse, status_code=status.HTTP_200_OK)
def finish_game_action(
    game_id: int,
    use_case: FinishGameUseCase = Depends(get_finish_game_use_case),
):
    """Finaliza la partida y calcula el podio oficial por patrimonio neto."""
    try:
        result = use_case.execute(game_id)
        response = FinishGameResponse(
            success=True,
            game_id=result.game_id,
            winner_name=result.winner_name,
            winner_token=result.winner_token,
            winner_net_worth=result.winner_net_worth,
            rankings=[
                PlayerRankingSchema(
                    rank=r.rank,
                    player_id=r.player_id,
                    name=r.name,
                    token=r.token,
                    cash=r.cash,
                    properties_value=r.properties_value,
                    buildings_value=r.buildings_value,
                    mortgage_debt=r.mortgage_debt,
                    net_worth=r.net_worth,
                )
                for r in result.rankings
            ],
            transaction_id=result.transaction_id,
        )
        broadcast_game_event_sync(game_id, "GAME_FINISHED", {
            "winner_name": result.winner_name,
            "winner_token": result.winner_token,
            "winner_net_worth": result.winner_net_worth,
        })
        return response
    except (GameNotFoundError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/draw-card", response_model=DrawCardResponse, status_code=status.HTTP_200_OK)
def draw_card_action(
    game_id: int,
    payload: DrawCardRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    use_case: DrawCardUseCase = Depends(get_draw_card_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    """Roba y ejecuta una carta de Fortuna o Arca Comunal (Manual / Auditoría)."""
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    player = player_repo.get_by_id(payload.player_id)
    if not player or player.game_id != game.id:
        raise HTTPException(status_code=404, detail="Jugador no encontrado.")
    assert_can_act_for_player(game, player, current_user)

    dto = DrawCardInputDTO(
        game_id=game_id,
        player_id=payload.player_id,
        deck_type=payload.deck_type,
        card_id=payload.card_id,
    )
    try:
        result = use_case.execute(dto)
        response = DrawCardResponse(
            success=True,
            game_id=result.game_id,
            player_id=result.player_id,
            player_name=result.player_name,
            deck_type=result.deck_type,
            deck_name=result.deck_name,
            card_id=result.card_id,
            title=result.title,
            description=result.description,
            effect_type=result.effect_type,
            amount_delta=result.amount_delta,
            old_position=result.old_position,
            new_position=result.new_position,
            passed_go=result.passed_go,
            in_jail=result.in_jail,
            out_of_jail_cards_count=result.out_of_jail_cards_count,
            transaction_id=result.transaction_id,
            landed_tile_action=result.landed_tile_action,
            landed_tile_details=result.landed_tile_details,
            message=result.message,
        )
        broadcast_game_event_sync(game_id, "CARD_DRAWN", {
            "player_id": result.player_id,
            "deck_type": result.deck_type,
            "card_id": result.card_id,
            "effect_type": result.effect_type,
        })
        return response
    except (GameNotFoundError, PlayerNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
