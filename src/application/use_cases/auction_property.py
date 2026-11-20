from src.application.dtos.action_dtos import AuctionPropertyInputDTO, AuctionPropertyOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.models.property import PropertyState
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType, GameStatus
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    PropertyNotFoundError,
    PropertyAlreadyOwnedError,
    InsufficientFundsError,
    InvalidGameActionError,
)


class AuctionPropertyUseCase:
    """
    Caso de Uso: Adjudicación de Propiedad por Subasta (Auction).
    Permite a cualquier jugador activo adjudicarse una propiedad no comprada
    tras una puja, descontando la oferta ganadora y registrando el título.
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

    def execute(self, dto: AuctionPropertyInputDTO) -> AuctionPropertyOutputDTO:
        # 1. Validar partida
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")
        if game.status == GameStatus.FINISHED:
            raise InvalidGameActionError("La partida ya ha finalizado.")

        # 2. Validar ganador de la subasta
        winner = self._player_repo.get_by_id(dto.winner_player_id)
        if not winner or winner.game_id != dto.game_id:
            raise PlayerNotFoundError(f"Jugador {dto.winner_player_id} no pertenece a esta partida.")

        if winner.in_jail:
            raise InvalidGameActionError(f"{winner.name} está en la Cárcel y no puede participar en subastas.")

        # 3. Validar casilla
        tile_strategy = BoardRuleRegistry.get_strategy(game.variant, dto.tile_id)
        if not tile_strategy:
            raise PropertyNotFoundError(f"La casilla '{dto.tile_id}' no existe en el tablero.")

        if not tile_strategy.can_be_purchased():
            raise InvalidGameActionError(f"La casilla '{tile_strategy.definition.name}' no puede subastarse.")

        prop_state = self._property_repo.get_by_tile(game.id, dto.tile_id)
        if prop_state and prop_state.is_owned:
            raise PropertyAlreadyOwnedError(
                f"La propiedad '{tile_strategy.definition.name}' ya tiene dueño."
            )

        # 4. Validar monto de la puja
        if dto.winning_bid < 1:
            raise InvalidGameActionError("La oferta ganadora de la subasta debe ser al menos $1.")

        if not winner.can_afford(dto.winning_bid):
            raise InsufficientFundsError(
                f"{winner.name} no tiene fondos suficientes (${winner.money}) para cubrir la puja de ${dto.winning_bid}."
            )

        # 5. Ejecutar débito y adjudicación de título
        winner.deduct_money(dto.winning_bid)
        self._player_repo.save(winner)

        if not prop_state:
            prop_state = PropertyState(
                id=None,
                game_id=game.id,
                tile_id=dto.tile_id,
                tile_position=tile_strategy.definition.position,
                owner_id=winner.id,
            )
        else:
            prop_state.assign_owner(winner.id)
        self._property_repo.save(prop_state)

        # 6. Registrar en el libro contable
        tx = self._transaction_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=TransactionType.BUY_PROPERTY,
                amount=dto.winning_bid,
                description=f"🔨 {winner.name} ganó la subasta de {tile_strategy.definition.name} por ${dto.winning_bid}",
                source_player_id=winner.id,
                target_player_id=None,
                tile_id=dto.tile_id,
            )
        )

        # 7. Avanzar turno si corresponde
        all_players = self._player_repo.list_by_game(game.id)
        if dto.auto_advance_turn and all_players:
            game.advance_turn(len(all_players))
            game.has_rolled_dice = False
            game.consecutive_doubles = 0
            self._game_repo.save(game)

        return AuctionPropertyOutputDTO(
            success=True,
            game_id=game.id,
            winner_player_id=winner.id,
            winner_name=winner.name,
            tile_id=dto.tile_id,
            tile_name=tile_strategy.definition.name,
            winning_bid=dto.winning_bid,
            remaining_balance=winner.money,
            transaction_id=tx.id,
            current_turn=game.current_turn,
            current_player_index=game.current_player_index,
        )
