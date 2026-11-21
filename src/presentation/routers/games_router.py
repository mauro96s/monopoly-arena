from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
from src.presentation.schemas.action_schemas import CreateGameRequest, AddPlayerRequest
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.presentation.dependencies import (
    get_game_repository,
    get_player_repository,
    get_property_repository,
    get_transaction_repository,
    get_finish_game_use_case,
)
from src.application.use_cases.finish_game import FinishGameUseCase
from src.presentation.schemas.action_schemas import FinishGameResponse, PlayerRankingSchema
from src.domain.models.game import Game
from src.domain.models.player import Player
from src.domain.models.transaction import Transaction
from src.domain.models.enums import GameStatus, GameVariant, TransactionType
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.themes import ThemeRegistry, ThemeDefinition

router = APIRouter(prefix="/games", tags=["Games"])


class GameResponse(BaseModel):
    id: int
    code: str
    variant: str
    theme_id: str = "classic"
    status: str
    current_turn: int
    current_player_index: int
    has_rolled_dice: bool = False
    consecutive_doubles: int = 0
    available_houses: int = 32
    available_hotels: int = 12


class PlayerResponse(BaseModel):
    id: int
    game_id: int
    name: str
    token: str
    money: int
    position: int
    is_bankrupt: bool
    in_jail: bool
    jail_turns: int = 0
    out_of_jail_cards: int = 0


class PropertyStateResponse(BaseModel):
    tile_id: str
    tile_position: int
    owner_id: Optional[int]
    houses_count: int
    hotels_count: int
    is_mortgaged: bool


class TransactionResponse(BaseModel):
    id: int
    turn_number: int
    transaction_type: str
    amount: int
    description: str
    source_player_id: Optional[int]
    target_player_id: Optional[int]
    created_at: str


class BoardTileResponse(BaseModel):
    tile_id: str
    name: str
    short_name: Optional[str] = None
    position: int
    tile_type: str
    group: str
    price: int
    base_rent: int
    house_cost: int = 0
    rent_matrix: List[int] = []
    can_be_purchased: bool
    color_hex: Optional[str] = None
    icon: Optional[str] = None


class GroupThemeSchema(BaseModel):
    key: str
    name: str
    color_hex: str
    text_color: str = "#FFFFFF"
    icon: str = "home"


class TileThemeSchema(BaseModel):
    tile_id: str
    position: int
    name: str
    short_name: str
    icon: Optional[str] = None
    banner_color: Optional[str] = None


class ThemeResponse(BaseModel):
    theme_id: str
    name: str
    description: str
    currency_symbol: str
    currency_code: str
    groups: List[GroupThemeSchema]
    tiles: dict[str, TileThemeSchema]


class RentPreviewResponse(BaseModel):
    tile_id: str
    tile_name: str
    owner_id: int
    owner_name: str
    rent_amount: int
    is_monopoly_doubled: bool
    houses_count: int
    hotels_count: int
    is_mortgaged: bool


@router.get("", response_model=List[GameResponse])
def list_games(
    limit: int = 20,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
):
    games = game_repo.list_all(limit=limit)
    return [
        GameResponse(
            id=g.id,  # type: ignore
            code=g.code,
            variant=g.variant.value,
            status=g.status.value,
            current_turn=g.current_turn,
            current_player_index=g.current_player_index,
            has_rolled_dice=g.has_rolled_dice,
            consecutive_doubles=g.consecutive_doubles,
        )
        for g in games
    ]


@router.post("", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
def create_game(
    payload: CreateGameRequest,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
):
    existing = game_repo.get_by_code(payload.code)
    if existing:
        raise HTTPException(status_code=400, detail="El código de partida ya existe.")

    variant = GameVariant(payload.variant.upper()) if payload.variant else GameVariant.CLASSIC
    theme_id = payload.theme_id or "classic"
    new_game = Game(id=None, code=payload.code, variant=variant, theme_id=theme_id, status=GameStatus.WAITING)
    saved = game_repo.save(new_game)
    return GameResponse(
        id=saved.id,  # type: ignore
        code=saved.code,
        variant=saved.variant.value,
        theme_id=saved.theme_id,
        status=saved.status.value,
        current_turn=saved.current_turn,
        current_player_index=saved.current_player_index,
        has_rolled_dice=saved.has_rolled_dice,
        consecutive_doubles=saved.consecutive_doubles,
        available_houses=saved.available_houses,
        available_hotels=saved.available_hotels,
    )


@router.get("/{game_id}", response_model=GameResponse)
def get_game(
    game_id: int,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
):
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    return GameResponse(
        id=game.id,  # type: ignore
        code=game.code,
        variant=game.variant.value,
        theme_id=getattr(game, "theme_id", "classic") or "classic",
        status=game.status.value,
        current_turn=game.current_turn,
        current_player_index=game.current_player_index,
        has_rolled_dice=game.has_rolled_dice,
        consecutive_doubles=game.consecutive_doubles,
        available_houses=game.available_houses,
        available_hotels=game.available_hotels,
    )


@router.post("/{game_id}/advance-turn", response_model=GameResponse)
def advance_turn(
    game_id: int,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    tx_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
):
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    if game.status == GameStatus.FINISHED:
        raise HTTPException(status_code=400, detail="La partida ya ha finalizado.")

    players = player_repo.list_by_game(game_id)
    if not players:
        raise HTTPException(status_code=400, detail="No hay jugadores en la partida.")

    active_player = players[game.current_player_index % len(players)]

    # Regla oficial de Cárcel al pasar turno
    if active_player.in_jail:
        if active_player.jail_turns >= 3:
            raise HTTPException(
                status_code=400,
                detail=f"Acción bloqueada: {active_player.name} ha cumplido 3 turnos en la Cárcel. Las reglas oficiales exigen pagar la fianza de $50 o usar una carta para salir antes de continuar."
            )
        active_player.jail_turns += 1
        player_repo.save(active_player)
        tx_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=TransactionType.BANK_TRANSFER,
                amount=0,
                description=f"{active_player.name} cumplió su turno #{active_player.jail_turns} en la Cárcel",
                source_player_id=None,
                target_player_id=None,
                tile_id="JAIL",
            )
        )

    game.advance_turn(len(players))
    game.status = GameStatus.IN_PROGRESS
    saved = game_repo.save(game)
    return GameResponse(
        id=saved.id,  # type: ignore
        code=saved.code,
        variant=saved.variant.value,
        theme_id=getattr(saved, "theme_id", "classic") or "classic",
        status=saved.status.value,
        current_turn=saved.current_turn,
        current_player_index=saved.current_player_index,
        has_rolled_dice=saved.has_rolled_dice,
        consecutive_doubles=saved.consecutive_doubles,
        available_houses=saved.available_houses,
        available_hotels=saved.available_hotels,
    )


@router.post("/{game_id}/finish", response_model=FinishGameResponse)
def finish_game(
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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{game_id}/board-tiles", response_model=List[BoardTileResponse])
def get_game_board_tiles(
    game_id: int,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
):
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    purchasable = {t.tile_id for t in BoardRuleRegistry.get_purchasable_tiles(game.variant)}
    all_strategies = BoardRuleRegistry._variants.get(game.variant) or BoardRuleRegistry._variants[GameVariant.CLASSIC]

    # Cargar tema activo de la partida
    theme = ThemeRegistry.get_theme(getattr(game, "theme_id", "classic") or "classic")

    # Ordenar por posición 0 a 39
    sorted_tiles = sorted(all_strategies.values(), key=lambda s: s.definition.position)

    tiles_response: List[BoardTileResponse] = []
    for s in sorted_tiles:
        tile_meta = theme.get_tile(s.definition.tile_id)
        grp_meta = theme.get_group(s.definition.group.value)

        # Nombre enriquecido por el tema
        disp_name = tile_meta.name if tile_meta else s.definition.name
        short_name = tile_meta.short_name if tile_meta else disp_name

        # Color de franja / casillero
        color_hex = (tile_meta.banner_color if tile_meta and tile_meta.banner_color else None) or (grp_meta.color_hex if grp_meta else None)
        icon = (tile_meta.icon if tile_meta and tile_meta.icon else None) or (grp_meta.icon if grp_meta else None)

        tiles_response.append(
            BoardTileResponse(
                tile_id=s.definition.tile_id,
                name=disp_name,
                short_name=short_name,
                position=s.definition.position,
                tile_type=s.definition.tile_type.value,
                group=s.definition.group.value,
                price=s.definition.price,
                base_rent=s.definition.base_rent,
                house_cost=s.definition.house_cost,
                rent_matrix=list(s.definition.rent_matrix),
                can_be_purchased=s.definition.tile_id in purchasable,
                color_hex=color_hex,
                icon=icon,
            )
        )
    return tiles_response


@router.get("/{game_id}/calculate-rent/{tile_id}", response_model=RentPreviewResponse)
def calculate_rent_preview(
    game_id: int,
    tile_id: str,
    dice_roll: int = 7,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    prop_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
):
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    prop_state = prop_repo.get_by_tile(game_id, tile_id)
    if not prop_state or not prop_state.is_owned:
        raise HTTPException(status_code=400, detail="Esta casilla no tiene dueño.")

    owner = player_repo.get_by_id(prop_state.owner_id)  # type: ignore
    if not owner:
        raise HTTPException(status_code=404, detail="Dueño no encontrado.")

    tile_strategy = BoardRuleRegistry.get_strategy(game.variant, tile_id)
    if not tile_strategy:
        raise HTTPException(status_code=404, detail="Casilla no encontrada.")

    owner_properties = prop_repo.list_by_owner(game_id, owner.id)  # type: ignore
    rent_amount = tile_strategy.calculate_rent(prop_state, owner_properties, dice_roll)

    group_tiles = BoardRuleRegistry.get_group_tile_ids(game.variant, tile_strategy.definition.group)
    owned_ids = {p.tile_id for p in owner_properties}
    is_monopoly_doubled = bool(
        prop_state.houses_count == 0
        and prop_state.hotels_count == 0
        and group_tiles
        and group_tiles.issubset(owned_ids)
        and len(group_tiles) > 1
    )

    return RentPreviewResponse(
        tile_id=tile_id,
        tile_name=tile_strategy.definition.name,
        owner_id=owner.id,  # type: ignore
        owner_name=owner.name,
        rent_amount=rent_amount,
        is_monopoly_doubled=is_monopoly_doubled,
        houses_count=prop_state.houses_count,
        hotels_count=prop_state.hotels_count,
        is_mortgaged=prop_state.is_mortgaged,
    )


@router.get("/{game_id}/theme", response_model=ThemeResponse)
def get_game_theme(
    game_id: int,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
):
    """Retorna la configuración completa del tema visual activo de la partida."""
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    theme = ThemeRegistry.get_theme(getattr(game, "theme_id", "classic") or "classic")
    return ThemeResponse(
        theme_id=theme.theme_id,
        name=theme.name,
        description=theme.description,
        currency_symbol=theme.currency_symbol,
        currency_code=theme.currency_code,
        groups=[
            GroupThemeSchema(
                key=g.key,
                name=g.name,
                color_hex=g.color_hex,
                text_color=g.text_color,
                icon=g.icon,
            )
            for g in theme.groups
        ],
        tiles={
            tid: TileThemeSchema(
                tile_id=t.tile_id,
                position=t.position,
                name=t.name,
                short_name=t.short_name,
                icon=t.icon,
                banner_color=t.banner_color,
            )
            for tid, t in theme.tiles.items()
        },
    )


@router.get("/themes/available")
def list_available_themes():
    """Lista todos los temas registrados disponibles para nuevas partidas."""
    return [
        {
            "theme_id": t.theme_id,
            "name": t.name,
            "description": t.description,
            "currency_symbol": t.currency_symbol,
            "currency_code": t.currency_code,
        }
        for t in ThemeRegistry.list_themes()
    ]


@router.post("/{game_id}/players", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
def add_player(
    game_id: int,
    payload: AddPlayerRequest,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    new_player = Player(id=None, game_id=game_id, name=payload.name, token=payload.token)
    saved = player_repo.save(new_player)
    return PlayerResponse(
        id=saved.id,  # type: ignore
        game_id=saved.game_id,
        name=saved.name,
        token=saved.token,
        money=saved.money,
        position=saved.position,
        is_bankrupt=saved.is_bankrupt,
        in_jail=saved.in_jail,
        jail_turns=saved.jail_turns,
        out_of_jail_cards=saved.out_of_jail_cards,
    )


@router.get("/{game_id}/players", response_model=List[PlayerResponse])
def list_players(
    game_id: int,
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    players = player_repo.list_by_game(game_id)
    return [
        PlayerResponse(
            id=p.id,  # type: ignore
            game_id=p.game_id,
            name=p.name,
            token=p.token,
            money=p.money,
            position=p.position,
            is_bankrupt=p.is_bankrupt,
            in_jail=p.in_jail,
            jail_turns=p.jail_turns,
            out_of_jail_cards=p.out_of_jail_cards,
        )
        for p in players
    ]


@router.get("/{game_id}/properties", response_model=List[PropertyStateResponse])
def list_properties(
    game_id: int,
    prop_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
):
    properties = prop_repo.list_by_game(game_id)
    return [
        PropertyStateResponse(
            tile_id=p.tile_id,
            tile_position=p.tile_position,
            owner_id=p.owner_id,
            houses_count=p.houses_count,
            hotels_count=p.hotels_count,
            is_mortgaged=p.is_mortgaged,
        )
        for p in properties
    ]


@router.get("/{game_id}/transactions", response_model=List[TransactionResponse])
def list_transactions(
    game_id: int,
    tx_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
):
    txs = tx_repo.list_by_game(game_id)
    return [
        TransactionResponse(
            id=t.id,  # type: ignore
            turn_number=t.turn_number,
            transaction_type=t.transaction_type.value,
            amount=t.amount,
            description=t.description,
            source_player_id=t.source_player_id,
            target_player_id=t.target_player_id,
            created_at=t.created_at.isoformat(),
        )
        for t in txs
    ]


class BulkDeleteGamesRequest(BaseModel):
    game_ids: List[int]


@router.delete("/{game_id}")
def delete_game(
    game_id: int,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
):
    """Elimina una partida individual por ID."""
    success = game_repo.delete(game_id)
    if not success:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    return {"success": True, "deleted_id": game_id}


@router.post("/bulk-delete")
def bulk_delete_games(
    payload: BulkDeleteGamesRequest,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
):
    """Elimina múltiples partidas seleccionadas por ID."""
    deleted_count = game_repo.delete_bulk(payload.game_ids)
    return {"success": True, "deleted_count": deleted_count}


@router.delete("")
def delete_all_games(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
):
    """Elimina todas las partidas existentes en el sistema."""
    deleted_count = game_repo.delete_all()
    return {"success": True, "deleted_count": deleted_count}
