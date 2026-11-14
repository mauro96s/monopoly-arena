from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.presentation.dependencies import (
    get_game_repository,
    get_player_repository,
    get_property_repository,
    get_transaction_repository,
)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
def view_lobby(
    request: Request,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
):
    """Vista de Lobby: Listado de partidas activas y formulario de creación."""
    recent_games = game_repo.list_all(limit=12)
    return templates.TemplateResponse(
        request=request,
        name="lobby.html",
        context={"recent_games": recent_games},
    )


@router.get("/game/{game_id}", response_class=HTMLResponse)
def view_game(
    game_id: int,
    request: Request,
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    prop_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    tx_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
):
    """Vista del Tablero de Control de la partida."""
    game = game_repo.get_by_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada")

    players = player_repo.list_by_game(game_id)
    properties = prop_repo.list_by_game(game_id)
    transactions = tx_repo.list_by_game(game_id, limit=30)

    return templates.TemplateResponse(
        request=request,
        name="game.html",
        context={
            "game": game,
            "players": players,
            "properties": properties,
            "transactions": transactions,
        },
    )
