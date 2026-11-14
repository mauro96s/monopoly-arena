from typing import List
from dataclasses import dataclass
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.models.transaction import Transaction
from src.domain.models.enums import GameStatus, TransactionType
from src.domain.exceptions import GameNotFoundError, InvalidGameActionError


@dataclass(frozen=True)
class PlayerRankingDTO:
    rank: int
    player_id: int
    name: str
    token: str
    cash: int
    properties_value: int
    buildings_value: int
    mortgage_debt: int
    net_worth: int


@dataclass(frozen=True)
class FinishGameOutputDTO:
    game_id: int
    winner_name: str
    winner_token: str
    winner_net_worth: int
    rankings: List[PlayerRankingDTO]
    transaction_id: int


class FinishGameUseCase:
    """
    Caso de Uso: Finalizar Partida y Calcular Podio de Ganadores.
    Calcula el patrimonio neto total de cada jugador:
    Efectivo + Valor de Compra de Propiedades + Inversión en Edificios (Casas/Hoteles) - Deudas de Hipoteca.
    """

    def __init__(
        self,
        game_repo: GameRepositoryProtocol,
        player_repo: PlayerRepositoryProtocol,
        property_repo: PropertyRepositoryProtocol,
        transaction_repo: TransactionRepositoryProtocol,
    ):
        self._game_repo = game_repo
        self._player_repo = player_repo
        self._property_repo = property_repo
        self._transaction_repo = transaction_repo

    def execute(self, game_id: int) -> FinishGameOutputDTO:
        game = self._game_repo.get_by_id(game_id)
        if not game:
            raise GameNotFoundError(f"Partida {game_id} no encontrada.")

        players = self._player_repo.list_by_game(game_id)
        if not players:
            raise InvalidGameActionError("No hay jugadores registrados en la partida.")

        all_properties = self._property_repo.list_by_game(game_id)

        # Calcular patrimonio neto de cada jugador
        player_scores = []
        for p in players:
            cash = p.money
            props_owned = [prop for prop in all_properties if prop.owner_id == p.id]

            props_val = 0
            bldgs_val = 0
            mortg_debt = 0

            for prop in props_owned:
                strat = BoardRuleRegistry.get_strategy(game.variant, prop.tile_id)
                if not strat:
                    continue
                defn = strat.definition

                # Valor de la propiedad
                props_val += defn.price

                # Valor de casas ($cost) y hoteles ($cost * 5)
                if prop.houses_count > 0:
                    bldgs_val += prop.houses_count * defn.house_cost
                if prop.hotels_count > 0:
                    bldgs_val += defn.house_cost * 5

                # Deuda si está hipotecada (valor de rescate 50%)
                if prop.is_mortgaged:
                    mortg_debt += defn.price // 2

            net_worth = cash + props_val + bldgs_val - mortg_debt

            player_scores.append({
                "player_id": p.id,
                "name": p.name,
                "token": p.token,
                "cash": cash,
                "properties_value": props_val,
                "buildings_value": bldgs_val,
                "mortgage_debt": mortg_debt,
                "net_worth": net_worth,
            })

        # Ordenar de mayor a menor patrimonio neto
        player_scores.sort(key=lambda s: s["net_worth"], reverse=True)

        rankings: List[PlayerRankingDTO] = []
        for i, s in enumerate(player_scores, start=1):
            rankings.append(PlayerRankingDTO(
                rank=i,
                player_id=s["player_id"],
                name=s["name"],
                token=s["token"],
                cash=s["cash"],
                properties_value=s["properties_value"],
                buildings_value=s["buildings_value"],
                mortgage_debt=s["mortgage_debt"],
                net_worth=s["net_worth"],
            ))

        winner = rankings[0]

        # Actualizar estado de la partida a FINISHED
        game.status = GameStatus.FINISHED
        self._game_repo.save(game)

        # Registrar en el ledger
        tx = self._transaction_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=TransactionType.GAME_FINISHED,
                amount=winner.net_worth,
                description=f"🏆 ¡Partida Finalizada! Ganador: {winner.name} ({winner.token}) con patrimonio neto de ${winner.net_worth:,}",
                source_player_id=winner.player_id,
                target_player_id=None,
            )
        )

        return FinishGameOutputDTO(
            game_id=game.id,
            winner_name=winner.name,
            winner_token=winner.token,
            winner_net_worth=winner.net_worth,
            rankings=rankings,
            transaction_id=tx.id if tx.id else 0,
        )
