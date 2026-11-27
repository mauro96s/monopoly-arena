from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
import random
import uuid
from pydantic import BaseModel
from src.presentation.schemas.action_schemas import (
    CreateGameRequest,
    AddPlayerRequest,
    CreateRulePresetRequest,
    RulePresetResponse,
)
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.interfaces.rule_preset_repository import RulePresetRepositoryProtocol
from src.domain.interfaces.theme_repository import ThemeRepositoryProtocol
from src.domain.models.rule_preset import RulePreset
from src.domain.models.user import User
from src.presentation.dependencies import (
    get_game_repository,
    get_player_repository,
    get_property_repository,
    get_transaction_repository,
    get_finish_game_use_case,
    get_rule_preset_repository,
    get_theme_repository,
    get_current_user_optional,
    assert_can_act_for_player,
)
from src.presentation.websocket_manager import broadcast_game_event_sync
from src.application.use_cases.finish_game import FinishGameUseCase
from src.presentation.schemas.action_schemas import FinishGameResponse, PlayerRankingSchema
from src.domain.models.game import Game
from src.domain.models.player import Player
from src.domain.models.transaction import Transaction
from src.domain.models.enums import GameStatus, GameVariant, TransactionType
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.rules.ruleset_config import RulesetConfig
from src.domain.themes import ThemeRegistry, ThemeDefinition, GroupThemeMetadata, TileThemeMetadata
from src.domain.themes.card_models import ThemeCardDefinition, DeckType, CardEffectType
from src.domain.exceptions import InvalidGameActionError

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
    ruleset_config: dict = {}
    free_parking_pool: int = 0
    pending_auction_tiles: List[str] = []
    owner_user_id: Optional[int] = None


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
    user_id: Optional[int] = None


class JoinGameRequest(BaseModel):
    name: str
    token: str


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


class CardThemeSchema(BaseModel):
    card_id: str
    deck: str
    title: str
    description: str
    effect_type: str
    params: dict = {}
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
    chance_deck_name: str = "Fortuna"
    community_chest_deck_name: str = "Arca Comunal"
    is_official: bool = False
    is_readonly: bool = False
    parent_theme_id: Optional[str] = None
    owner_user_id: Optional[str] = None
    groups: List[GroupThemeSchema] = []
    tiles: dict[str, TileThemeSchema] = {}
    chance_cards: List[CardThemeSchema] = []
    community_chest_cards: List[CardThemeSchema] = []


class CloneThemeRequest(BaseModel):
    target_theme_id: Optional[str] = None
    target_name: Optional[str] = None
    target_description: Optional[str] = None


class SaveThemeRequest(BaseModel):
    theme_id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    currency_symbol: Optional[str] = "$"
    currency_code: Optional[str] = "USD"
    chance_deck_name: Optional[str] = "Fortuna"
    community_chest_deck_name: Optional[str] = "Arca Comunal"
    groups: List[GroupThemeSchema] = []
    tiles: dict[str, TileThemeSchema] = {}
    chance_cards: List[CardThemeSchema] = []
    community_chest_cards: List[CardThemeSchema] = []


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


# ========================================================
# PRESETS DE REGLAS
# ========================================================
@router.get("/rule-presets", response_model=List[RulePresetResponse], status_code=status.HTTP_200_OK)
def list_rule_presets(
    preset_repo: RulePresetRepositoryProtocol = Depends(get_rule_preset_repository),
):
    """Lista todos los perfiles o presets de reglas disponibles (sistema y personalizados)."""
    presets = preset_repo.list_all()
    return [
        RulePresetResponse(
            id=p.id,  # type: ignore
            name=p.name,
            description=p.description,
            ruleset_config=p.ruleset_config.to_dict(),
            is_system_default=p.is_system_default,
            owner_user_id=p.owner_user_id,
            created_at=p.created_at.isoformat() if p.created_at else None,
        )
        for p in presets
    ]


@router.post("/rule-presets", response_model=RulePresetResponse, status_code=status.HTTP_201_CREATED)
def create_rule_preset(
    payload: CreateRulePresetRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    preset_repo: RulePresetRepositoryProtocol = Depends(get_rule_preset_repository),
):
    """Crea y guarda un nuevo preset de reglas personalizado."""
    existing = preset_repo.get_by_name(payload.name.strip())
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un preset con el nombre '{payload.name}'.")

    owner_user_id = current_user.id if isinstance(current_user, User) else None
    cfg = RulesetConfig.from_dict(payload.ruleset_config)
    new_preset = RulePreset(
        id=None,
        name=payload.name.strip(),
        description=payload.description or "",
        ruleset_config=cfg,
        is_system_default=False,
        owner_user_id=owner_user_id,
    )
    saved = preset_repo.save(new_preset)
    return RulePresetResponse(
        id=saved.id,  # type: ignore
        name=saved.name,
        description=saved.description,
        ruleset_config=saved.ruleset_config.to_dict(),
        is_system_default=saved.is_system_default,
        owner_user_id=saved.owner_user_id,
        created_at=saved.created_at.isoformat() if saved.created_at else None,
    )


@router.delete("/rule-presets/{preset_id}", status_code=status.HTTP_200_OK)
def delete_rule_preset(
    preset_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    preset_repo: RulePresetRepositoryProtocol = Depends(get_rule_preset_repository),
):
    """Elimina un preset personalizado. No permite eliminar presets del sistema ni de otros usuarios."""
    preset = preset_repo.get_by_id(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset no encontrado.")
    if preset.is_system_default:
        raise HTTPException(status_code=400, detail="No se pueden eliminar los presets predeterminados del sistema.")

    if preset.owner_user_id is not None:
        if not (isinstance(current_user, User) and current_user.id == preset.owner_user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes autorización para eliminar este preset de reglas creado por otro usuario."
            )

    preset_repo.delete(preset_id)
    return {"success": True, "message": f"Preset '{preset.name}' eliminado con éxito."}


@router.post("", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
def create_game(
    payload: CreateGameRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    preset_repo: RulePresetRepositoryProtocol = Depends(get_rule_preset_repository),
):
    existing = game_repo.get_by_code(payload.code)
    if existing:
        raise HTTPException(status_code=400, detail="El código de partida ya existe.")

    variant = GameVariant(payload.variant.upper()) if payload.variant else GameVariant.CLASSIC
    theme_id = payload.theme_id or "classic"

    # Resolver ruleset: preset_id tiene prioridad o fallback a ruleset_config directo
    if getattr(payload, "rule_preset_id", None):
        preset = preset_repo.get_by_id(payload.rule_preset_id)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Preset {payload.rule_preset_id} no encontrado.")
        ruleset = preset.ruleset_config
    elif getattr(payload, "ruleset_config", None):
        ruleset = RulesetConfig.from_dict(payload.ruleset_config)
    else:
        ruleset = RulesetConfig()

    owner_user_id = current_user.id if isinstance(current_user, User) else None

    new_game = Game(
        id=None,
        code=payload.code,
        variant=variant,
        theme_id=theme_id,
        ruleset_config=ruleset,
        status=GameStatus.WAITING,
        owner_user_id=owner_user_id,
    )
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
        ruleset_config=saved.get_ruleset().to_dict(),
        free_parking_pool=saved.free_parking_pool,
        pending_auction_tiles=list(saved.pending_auction_tiles),
        owner_user_id=saved.owner_user_id,
    )


@router.get("/by-code/{code}", response_model=GameResponse)
def get_game_by_code(
    code: str,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
):
    """Permite a los jugadores buscar una sala por su código alfanumérico para unirse."""
    game = game_repo.get_by_code(code.strip())
    if not game:
        raise HTTPException(status_code=404, detail=f"Partida con código '{code}' no encontrada.")
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
        ruleset_config=game.get_ruleset().to_dict(),
        free_parking_pool=game.free_parking_pool,
        pending_auction_tiles=list(game.pending_auction_tiles),
        owner_user_id=game.owner_user_id,
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
        ruleset_config=game.get_ruleset().to_dict(),
        free_parking_pool=game.free_parking_pool,
        pending_auction_tiles=list(game.pending_auction_tiles),
        owner_user_id=game.owner_user_id,
    )


@router.post("/{game_id}/join", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
def join_game_room(
    game_id: int,
    payload: JoinGameRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    """Permite unirse a una sala de espera validando estado, ficha y nombre."""
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    if game.status != GameStatus.WAITING:
        raise HTTPException(
            status_code=400,
            detail="No es posible unirse: la partida ya ha comenzado o finalizado."
        )

    existing_players = player_repo.list_by_game(game_id)
    norm_name = payload.name.strip().lower()
    if any(p.name.strip().lower() == norm_name for p in existing_players):
        raise HTTPException(status_code=400, detail=f"Ya existe un jugador con el nombre '{payload.name}'.")
    if any(p.token == payload.token for p in existing_players):
        raise HTTPException(status_code=400, detail=f"La ficha '{payload.token}' ya fue seleccionada por otro jugador.")

    user_id = current_user.id if isinstance(current_user, User) else None
    new_player = Player(
        id=None,
        game_id=game_id,
        name=payload.name.strip(),
        token=payload.token,
        user_id=user_id,
    )
    saved = player_repo.save(new_player)

    # Notificar a los clientes conectados a la sala
    broadcast_game_event_sync(game_id, "PLAYER_JOINED", {
        "player_id": saved.id,
        "name": saved.name,
        "token": saved.token,
        "user_id": saved.user_id,
    })

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
        user_id=saved.user_id,
    )


@router.post("/{game_id}/start", response_model=GameResponse)
def start_game_room(
    game_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    theme_repo: ThemeRepositoryProtocol = Depends(get_theme_repository),
):
    """Inicia formalmente la partida desde el Lobby, barajando mazos de cartas."""
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")
    if game.status != GameStatus.WAITING:
        raise HTTPException(status_code=400, detail="La partida no se encuentra en estado de espera.")

    players = player_repo.list_by_game(game_id)
    if len(players) < 2:
        raise HTTPException(status_code=400, detail="Se requieren al menos 2 jugadores para iniciar la partida.")

    # Barajar mazos del tema asignado
    theme_id = getattr(game, "theme_id", "classic") or "classic"
    theme = theme_repo.get_by_theme_id(theme_id) or ThemeRegistry.get_theme(theme_id)

    chance_card_ids = [c.card_id for c in theme.chance_cards]
    chest_card_ids = [c.card_id for c in theme.community_chest_cards]
    random.shuffle(chance_card_ids)
    random.shuffle(chest_card_ids)

    game.chance_deck_order = chance_card_ids
    game.community_chest_deck_order = chest_card_ids
    game.status = GameStatus.IN_PROGRESS
    game.current_turn = 1
    game.current_player_index = 0
    saved = game_repo.save(game)

    # Notificar a los clientes conectados que la partida inició
    broadcast_game_event_sync(game_id, "GAME_STARTED", {
        "game_id": saved.id,
        "status": saved.status.value,
        "current_player_index": saved.current_player_index,
    })

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
        ruleset_config=saved.get_ruleset().to_dict(),
        free_parking_pool=saved.free_parking_pool,
        pending_auction_tiles=list(saved.pending_auction_tiles),
        owner_user_id=saved.owner_user_id,
    )


@router.post("/{game_id}/advance-turn", response_model=GameResponse)
def advance_turn(
    game_id: int,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    tx_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
    current_user: Optional[User] = Depends(get_current_user_optional),
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
    assert_can_act_for_player(game, active_player, current_user)

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

    broadcast_game_event_sync(game_id, "TURN_ADVANCED", {
        "game_id": saved.id,
        "current_turn": saved.current_turn,
        "current_player_index": saved.current_player_index,
    })

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
        ruleset_config=saved.get_ruleset().to_dict(),
        free_parking_pool=saved.free_parking_pool,
        pending_auction_tiles=list(saved.pending_auction_tiles),
        owner_user_id=saved.owner_user_id,
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


def _build_theme_response(theme: ThemeDefinition) -> ThemeResponse:
    """Función de mapeo pura para convertir ThemeDefinition en ThemeResponse."""
    return ThemeResponse(
        theme_id=theme.theme_id,
        name=theme.name,
        description=theme.description,
        currency_symbol=theme.currency_symbol,
        currency_code=theme.currency_code,
        chance_deck_name=theme.chance_deck_name,
        community_chest_deck_name=theme.community_chest_deck_name,
        is_official=theme.is_official,
        is_readonly=theme.is_readonly,
        parent_theme_id=theme.parent_theme_id,
        owner_user_id=theme.owner_user_id,
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
        chance_cards=[
            CardThemeSchema(
                card_id=c.card_id,
                deck=c.deck.value if hasattr(c.deck, "value") else str(c.deck),
                title=c.title,
                description=c.description,
                effect_type=c.effect_type.value if hasattr(c.effect_type, "value") else str(c.effect_type),
                params=c.params,
                icon=c.icon,
            )
            for c in theme.chance_cards
        ],
        community_chest_cards=[
            CardThemeSchema(
                card_id=c.card_id,
                deck=c.deck.value if hasattr(c.deck, "value") else str(c.deck),
                title=c.title,
                description=c.description,
                effect_type=c.effect_type.value if hasattr(c.effect_type, "value") else str(c.effect_type),
                params=c.params,
                icon=c.icon,
            )
            for c in theme.community_chest_cards
        ],
    )


@router.get("/{game_id}/theme", response_model=ThemeResponse)
def get_game_theme(
    game_id: int,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    theme_repo: ThemeRepositoryProtocol = Depends(get_theme_repository),
):
    """Retorna la configuración completa del tema visual activo de la partida."""
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    theme_id = getattr(game, "theme_id", "classic") or "classic"
    theme = theme_repo.get_by_theme_id(theme_id) or ThemeRegistry.get_theme(theme_id)
    return _build_theme_response(theme)


@router.get("/themes/available")
def list_available_themes(
    theme_repo: ThemeRepositoryProtocol = Depends(get_theme_repository),
):
    """Lista todos los temas registrados disponibles (oficiales y personalizados)."""
    return [
        {
            "theme_id": t.theme_id,
            "name": t.name,
            "description": t.description,
            "currency_symbol": t.currency_symbol,
            "currency_code": t.currency_code,
            "chance_deck_name": t.chance_deck_name,
            "community_chest_deck_name": t.community_chest_deck_name,
            "is_official": t.is_official,
            "is_readonly": t.is_readonly,
            "parent_theme_id": t.parent_theme_id,
            "chance_cards_count": len(t.chance_cards),
            "community_chest_cards_count": len(t.community_chest_cards),
        }
        for t in ThemeRegistry.list_themes()
    ]


@router.get("/themes/{theme_id}", response_model=ThemeResponse)
def get_theme_by_id(
    theme_id: str,
    theme_repo: ThemeRepositoryProtocol = Depends(get_theme_repository),
):
    """Retorna la definición completa de un tema por su identificador."""
    theme = theme_repo.get_by_theme_id(theme_id) or ThemeRegistry.get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail=f"Tema '{theme_id}' no encontrado.")
    return _build_theme_response(theme)


@router.post("/themes/{theme_id}/clone", response_model=ThemeResponse, status_code=status.HTTP_201_CREATED)
def clone_theme(
    theme_id: str,
    payload: Optional[CloneThemeRequest] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
    theme_repo: ThemeRepositoryProtocol = Depends(get_theme_repository),
):
    """Clona un tema existente (oficial o personalizado) a un nuevo tema editable."""
    base_theme = theme_repo.get_by_theme_id(theme_id) or ThemeRegistry.get_theme(theme_id)
    if not base_theme:
        raise HTTPException(status_code=404, detail=f"Tema base '{theme_id}' no encontrado.")

    target_id = payload.target_theme_id.strip() if (payload and payload.target_theme_id) else f"{theme_id}_copy_{uuid.uuid4().hex[:6]}"
    target_name = payload.target_name.strip() if (payload and payload.target_name) else f"{base_theme.name} (Copia)"
    target_desc = payload.target_description.strip() if (payload and payload.target_description) else f"Copia personalizada de {base_theme.name}"

    cloned_groups = [
        GroupThemeMetadata(key=g.key, name=g.name, color_hex=g.color_hex, text_color=g.text_color, icon=g.icon)
        for g in base_theme.groups
    ]
    cloned_tiles = {
        tid: TileThemeMetadata(tile_id=t.tile_id, position=t.position, name=t.name, short_name=t.short_name, icon=t.icon, banner_color=t.banner_color)
        for tid, t in base_theme.tiles.items()
    }
    cloned_chance = [
        ThemeCardDefinition(card_id=f"{target_id}_{c.card_id}", deck=c.deck, title=c.title, description=c.description, effect_type=c.effect_type, params=dict(c.params), icon=c.icon)
        for c in base_theme.chance_cards
    ]
    cloned_chest = [
        ThemeCardDefinition(card_id=f"{target_id}_{c.card_id}", deck=c.deck, title=c.title, description=c.description, effect_type=c.effect_type, params=dict(c.params), icon=c.icon)
        for c in base_theme.community_chest_cards
    ]

    owner_user_id = str(current_user.id) if isinstance(current_user, User) else None

    new_theme = ThemeDefinition(
        theme_id=target_id,
        name=target_name,
        description=target_desc,
        currency_symbol=base_theme.currency_symbol,
        currency_code=base_theme.currency_code,
        chance_deck_name=base_theme.chance_deck_name,
        community_chest_deck_name=base_theme.community_chest_deck_name,
        is_official=False,
        is_readonly=False,
        parent_theme_id=base_theme.theme_id,
        owner_user_id=owner_user_id,
        groups=cloned_groups,
        tiles=cloned_tiles,
        chance_cards=cloned_chance,
        community_chest_cards=cloned_chest,
    )

    saved = theme_repo.save(new_theme)
    return _build_theme_response(saved)


@router.post("/themes", response_model=ThemeResponse, status_code=status.HTTP_201_CREATED)
def create_custom_theme(
    payload: SaveThemeRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    theme_repo: ThemeRepositoryProtocol = Depends(get_theme_repository),
):
    """Crea y persiste un nuevo tema personalizado."""
    target_id = payload.theme_id.strip() if payload.theme_id else f"custom_{uuid.uuid4().hex[:6]}"
    if ThemeRegistry.has_theme(target_id):
        raise HTTPException(status_code=400, detail=f"El tema '{target_id}' ya existe.")

    groups = [
        GroupThemeMetadata(key=g.key, name=g.name, color_hex=g.color_hex, text_color=g.text_color, icon=g.icon)
        for g in payload.groups
    ]
    tiles = {
        tid: TileThemeMetadata(tile_id=t.tile_id, position=t.position, name=t.name, short_name=t.short_name, icon=t.icon, banner_color=t.banner_color)
        for tid, t in payload.tiles.items()
    }
    chance_cards = [
        ThemeCardDefinition(card_id=c.card_id, deck=DeckType.CHANCE, title=c.title, description=c.description, effect_type=CardEffectType(c.effect_type), params=c.params, icon=c.icon)
        for c in payload.chance_cards
    ]
    community_chest_cards = [
        ThemeCardDefinition(card_id=c.card_id, deck=DeckType.COMMUNITY_CHEST, title=c.title, description=c.description, effect_type=CardEffectType(c.effect_type), params=c.params, icon=c.icon)
        for c in payload.community_chest_cards
    ]

    owner_user_id = str(current_user.id) if isinstance(current_user, User) else None

    theme = ThemeDefinition(
        theme_id=target_id,
        name=payload.name.strip(),
        description=payload.description or "",
        currency_symbol=payload.currency_symbol or "$",
        currency_code=payload.currency_code or "USD",
        chance_deck_name=payload.chance_deck_name or "Fortuna",
        community_chest_deck_name=payload.community_chest_deck_name or "Arca Comunal",
        is_official=False,
        is_readonly=False,
        owner_user_id=owner_user_id,
        groups=groups,
        tiles=tiles,
        chance_cards=chance_cards,
        community_chest_cards=community_chest_cards,
    )

    saved = theme_repo.save(theme)
    return _build_theme_response(saved)


@router.put("/themes/{theme_id}", response_model=ThemeResponse)
def update_custom_theme(
    theme_id: str,
    payload: SaveThemeRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    theme_repo: ThemeRepositoryProtocol = Depends(get_theme_repository),
):
    """Actualiza un tema personalizado existente."""
    existing = theme_repo.get_by_theme_id(theme_id) or ThemeRegistry.get_theme(theme_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Tema '{theme_id}' no encontrado.")
    if existing.is_readonly or existing.is_official:
        raise HTTPException(status_code=400, detail=f"El tema '{theme_id}' es protegido y no puede modificarse.")

    if existing.owner_user_id is not None:
        if not (isinstance(current_user, User) and str(current_user.id) == str(existing.owner_user_id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes autorización para modificar este tema creado por otro usuario."
            )

    groups = [
        GroupThemeMetadata(key=g.key, name=g.name, color_hex=g.color_hex, text_color=g.text_color, icon=g.icon)
        for g in payload.groups
    ]
    tiles = {
        tid: TileThemeMetadata(tile_id=t.tile_id, position=t.position, name=t.name, short_name=t.short_name, icon=t.icon, banner_color=t.banner_color)
        for tid, t in payload.tiles.items()
    }
    chance_cards = [
        ThemeCardDefinition(card_id=c.card_id, deck=DeckType.CHANCE, title=c.title, description=c.description, effect_type=CardEffectType(c.effect_type), params=c.params, icon=c.icon)
        for c in payload.chance_cards
    ]
    community_chest_cards = [
        ThemeCardDefinition(card_id=c.card_id, deck=DeckType.COMMUNITY_CHEST, title=c.title, description=c.description, effect_type=CardEffectType(c.effect_type), params=c.params, icon=c.icon)
        for c in payload.community_chest_cards
    ]

    updated = ThemeDefinition(
        theme_id=theme_id,
        name=payload.name.strip(),
        description=payload.description or "",
        currency_symbol=payload.currency_symbol or "$",
        currency_code=payload.currency_code or "USD",
        chance_deck_name=payload.chance_deck_name or "Fortuna",
        community_chest_deck_name=payload.community_chest_deck_name or "Arca Comunal",
        is_official=False,
        is_readonly=False,
        parent_theme_id=existing.parent_theme_id,
        owner_user_id=existing.owner_user_id,
        groups=groups,
        tiles=tiles,
        chance_cards=chance_cards,
        community_chest_cards=community_chest_cards,
    )

    saved = theme_repo.save(updated)
    return _build_theme_response(saved)


@router.delete("/themes/{theme_id}", status_code=status.HTTP_200_OK)
def delete_custom_theme(
    theme_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    theme_repo: ThemeRepositoryProtocol = Depends(get_theme_repository),
):
    """Elimina un tema personalizado."""
    existing = theme_repo.get_by_theme_id(theme_id)
    if existing and existing.owner_user_id is not None:
        if not (isinstance(current_user, User) and str(current_user.id) == str(existing.owner_user_id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes autorización para eliminar este tema creado por otro usuario."
            )
    try:
        success = theme_repo.delete(theme_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Tema '{theme_id}' no encontrado.")
        return {"success": True, "message": f"Tema '{theme_id}' eliminado correctamente."}
    except InvalidGameActionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{game_id}/players", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
def add_player(
    game_id: int,
    payload: AddPlayerRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
):
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada.")

    user_id = current_user.id if isinstance(current_user, User) else None
    new_player = Player(id=None, game_id=game_id, name=payload.name, token=payload.token, user_id=user_id)
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
        user_id=saved.user_id,
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
            user_id=p.user_id,
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
