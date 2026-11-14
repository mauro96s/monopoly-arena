from fastapi import APIRouter, Depends, HTTPException, status
from src.presentation.schemas.action_schemas import (
    BuyPropertyRequest,
    BuyPropertyResponse,
    PayRentRequest,
    PayRentResponse,
    BuildHouseRequest,
    BuildHouseResponse,
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
)
from src.application.dtos.action_dtos import (
    BuyPropertyInputDTO,
    PayRentInputDTO,
    BuildHouseInputDTO,
    MortgageInputDTO,
    JailActionInputDTO,
    BankActionInputDTO,
    TransferMoneyInputDTO,
)
from src.application.use_cases import (
    BuyPropertyUseCase,
    PayRentUseCase,
    BuildHouseUseCase,
    MortgagePropertyUseCase,
    JailActionUseCase,
    BankActionUseCase,
    TransferMoneyUseCase,
    FinishGameUseCase,
)
from src.presentation.dependencies import (
    get_game_repository,
    get_player_repository,
    get_buy_property_use_case,
    get_pay_rent_use_case,
    get_build_house_use_case,
    get_mortgage_property_use_case,
    get_jail_action_use_case,
    get_bank_action_use_case,
    get_transfer_money_use_case,
    get_finish_game_use_case,
)
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.models.enums import GameStatus
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    PropertyNotFoundError,
    PropertyAlreadyOwnedError,
    InsufficientFundsError,
    InvalidGameActionError,
)

router = APIRouter(prefix="/games/{game_id}/actions", tags=["Game Actions"])


def assert_active_turn(game_id: int, player_id: int, game_repo: GameRepositoryProtocol, player_repo: PlayerRepositoryProtocol):
    """Garantiza la regla estricta: solo el jugador en turno puede ejecutar acciones."""
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


@router.post("/buy-property", response_model=BuyPropertyResponse, status_code=status.HTTP_200_OK)
def buy_property(
    game_id: int,
    payload: BuyPropertyRequest,
    use_case: BuyPropertyUseCase = Depends(get_buy_property_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.player_id, game_repo, player_repo)
    dto = BuyPropertyInputDTO(
        game_id=game_id,
        player_id=payload.player_id,
        tile_id=payload.tile_id,
        auto_advance_turn=payload.auto_advance_turn,
    )
    try:
        result = use_case.execute(dto)
        return BuyPropertyResponse(
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
        )
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (PropertyAlreadyOwnedError, InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/pay-rent", response_model=PayRentResponse, status_code=status.HTTP_200_OK)
def pay_rent(
    game_id: int,
    payload: PayRentRequest,
    use_case: PayRentUseCase = Depends(get_pay_rent_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.payer_player_id, game_repo, player_repo)
    dto = PayRentInputDTO(
        game_id=game_id,
        payer_player_id=payload.payer_player_id,
        tile_id=payload.tile_id,
        dice_roll=payload.dice_roll,
        auto_advance_turn=payload.auto_advance_turn,
    )
    try:
        result = use_case.execute(dto)
        return PayRentResponse(
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
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/build-house", response_model=BuildHouseResponse, status_code=status.HTTP_200_OK)
def build_house(
    game_id: int,
    payload: BuildHouseRequest,
    use_case: BuildHouseUseCase = Depends(get_build_house_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.player_id, game_repo, player_repo)
    dto = BuildHouseInputDTO(
        game_id=game_id,
        player_id=payload.player_id,
        tile_id=payload.tile_id,
    )
    try:
        result = use_case.execute(dto)
        return BuildHouseResponse(
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
            transaction_id=result.transaction_id,
        )
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/mortgage", response_model=MortgageResponse, status_code=status.HTTP_200_OK)
@router.post("/mortgage-property", response_model=MortgageResponse, status_code=status.HTTP_200_OK)
def mortgage_property(
    game_id: int,
    payload: MortgageRequest,
    use_case: MortgagePropertyUseCase = Depends(get_mortgage_property_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.player_id, game_repo, player_repo)
    dto = MortgageInputDTO(
        game_id=game_id,
        player_id=payload.player_id,
        tile_id=payload.tile_id,
    )
    try:
        result = use_case.execute(dto)
        return MortgageResponse(
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
    except (GameNotFoundError, PlayerNotFoundError, PropertyNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/jail", response_model=JailActionResponse, status_code=status.HTTP_200_OK)
@router.post("/jail-action", response_model=JailActionResponse, status_code=status.HTTP_200_OK)
def jail_action(
    game_id: int,
    payload: JailActionRequest,
    use_case: JailActionUseCase = Depends(get_jail_action_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.player_id, game_repo, player_repo)
    dto = JailActionInputDTO(
        game_id=game_id,
        player_id=payload.player_id,
        action=payload.action,
        auto_advance_turn=payload.auto_advance_turn,
    )
    try:
        result = use_case.execute(dto)
        return JailActionResponse(
            success=True,
            game_id=result.game_id,
            player_id=result.player_id,
            player_name=result.player_name,
            in_jail=result.in_jail,
            jail_turns=result.jail_turns,
            amount_paid=result.amount_paid,
            remaining_balance=result.remaining_balance,
            transaction_id=result.transaction_id,
            current_turn=result.current_turn,
            current_player_index=result.current_player_index,
        )
    except (GameNotFoundError, PlayerNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InsufficientFundsError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/bank", response_model=BankActionResponse, status_code=status.HTTP_200_OK)
@router.post("/bank-action", response_model=BankActionResponse, status_code=status.HTTP_200_OK)
def bank_action(
    game_id: int,
    payload: BankActionRequest,
    use_case: BankActionUseCase = Depends(get_bank_action_use_case),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    assert_active_turn(game_id, payload.player_id, game_repo, player_repo)
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
        return BankActionResponse(
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
        )
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
        return TransferMoneyResponse(
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
        return FinishGameResponse(
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
    except (GameNotFoundError, InvalidGameActionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
