from src.application.dtos.action_dtos import BuyPropertyInputDTO, BuyPropertyOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.rules.quick_end_evaluator import QuickEndEvaluator
from src.domain.models.property import PropertyState
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    PropertyNotFoundError,
    PropertyAlreadyOwnedError,
    InsufficientFundsError,
    InvalidGameActionError,
)


class BuyPropertyUseCase:
    """
    Caso de Uso: Compra de Propiedad (Monopoly Clásico y Expansiones).
    Cumple rigurosamente con SOLID:
    - S: Única responsabilidad de orquestar la compra y registrar la transacción.
    - O: Abierto a extensión gracias al patrón Strategy provisto por BoardRuleRegistry.
    - L & I: Depende de protocolos mínimos y sustituibles.
    - D: Inversión de dependencias (recibe abstracciones por inyección en el constructor).
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

    def execute(self, dto: BuyPropertyInputDTO) -> BuyPropertyOutputDTO:
        # 1. Validar partida
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")

        # 2. Validar jugador
        player = self._player_repo.get_by_id(dto.player_id)
        if not player or player.game_id != dto.game_id:
            raise PlayerNotFoundError(f"Jugador {dto.player_id} no pertenece a esta partida.")

        if player.in_jail:
            raise InvalidGameActionError(f"{player.name} está en la Cárcel y no puede comprar propiedades hasta obtener su libertad.")

        # 3. Obtener la regla / estrategia de la casilla según la variante del juego (Open/Closed)
        tile_strategy = BoardRuleRegistry.get_strategy(game.variant, dto.tile_id)
        if not tile_strategy:
            raise PropertyNotFoundError(f"La casilla '{dto.tile_id}' no existe en el tablero de la variante {game.variant}.")

        # 4. Validar si la casilla es comprable
        if not tile_strategy.can_be_purchased():
            raise InvalidGameActionError(f"La casilla '{tile_strategy.definition.name}' no puede comprarse.")

        # 5. Validar disponibilidad de la propiedad en el estado actual de la partida
        prop_state = self._property_repo.get_by_tile(game.id, dto.tile_id)
        if prop_state and prop_state.is_owned:
            raise PropertyAlreadyOwnedError(
                f"La propiedad '{tile_strategy.definition.name}' ya tiene dueño (Jugador ID {prop_state.owner_id})."
            )

        price = tile_strategy.definition.price

        # 6. Validar solvencia del jugador
        if not player.can_afford(price):
            raise InsufficientFundsError(
                f"El jugador '{player.name}' no tiene fondos suficientes. Requiere ${price}, saldo actual: ${player.money}."
            )

        # 7. Ejecutar cambios en el Dominio
        player.deduct_money(price)
        self._player_repo.save(player)

        if not prop_state:
            prop_state = PropertyState(
                id=None,
                game_id=game.id,
                tile_id=dto.tile_id,
                tile_position=tile_strategy.definition.position,
                owner_id=player.id,
            )
        else:
            prop_state.assign_owner(player.id)
        self._property_repo.save(prop_state)

        # 8. Registrar movimiento contable en el Ledger
        tx = self._transaction_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=TransactionType.BUY_PROPERTY,
                amount=price,
                description=f"{player.name} compró {tile_strategy.definition.name} por ${price}",
                source_player_id=player.id,
                target_player_id=None,  # Pago a la Banca
                tile_id=dto.tile_id,
            )
        )

        # 9. Evaluar condición de fin rápido (ALL_PROPERTIES_SOLD)
        quick_end = QuickEndEvaluator.evaluate_after_property_acquired(
            game=game,
            property_repo=self._property_repo,
            player_repo=self._player_repo,
            game_repo=self._game_repo,
            transaction_repo=self._transaction_repo,
        )

        # 10. Avance automático de turno circular (J1 -> J2 -> J3 -> J1) si no finalizó
        all_players = self._player_repo.list_by_game(game.id)
        if not quick_end.triggered and dto.auto_advance_turn and all_players:
            game.advance_turn(len(all_players))
            self._game_repo.save(game)

        # 11. Retornar DTO de resultado agnóstico
        return BuyPropertyOutputDTO(
            game_id=game.id,
            player_id=player.id,
            player_name=player.name,
            tile_id=dto.tile_id,
            tile_name=tile_strategy.definition.name,
            price_paid=price,
            remaining_balance=player.money,
            transaction_id=tx.id if tx.id else 0,
            current_turn=game.current_turn,
            current_player_index=game.current_player_index,
            is_game_finished=quick_end.triggered,
            winner_player_id=quick_end.winner_id,
            winner_player_name=quick_end.winner_name,
            quick_end_details={
                "triggered": quick_end.triggered,
                "victory_mode": game.get_ruleset().victory_mode,
                "winner_id": quick_end.winner_id,
                "winner_name": quick_end.winner_name,
                "winner_net_worth": quick_end.winner_net_worth,
                "rankings": quick_end.rankings,
                "disqualified_player_ids": quick_end.disqualified_player_ids,
                "reason": quick_end.reason,
            } if quick_end.triggered else None,
        )
