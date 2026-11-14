from src.application.dtos.action_dtos import TransferMoneyInputDTO, TransferMoneyOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    InsufficientFundsError,
)


class TransferMoneyUseCase:
    """
    Caso de Uso: Transferencias entre Jugadores o con la Banca (Rentas, Premios, Multas).
    """

    def __init__(
        self,
        game_repo: GameRepositoryProtocol,
        player_repo: PlayerRepositoryProtocol,
        transaction_repo: TransactionRepositoryProtocol,
    ):
        self._game_repo = game_repo
        self._player_repo = player_repo
        self._transaction_repo = transaction_repo

    def execute(self, dto: TransferMoneyInputDTO) -> TransferMoneyOutputDTO:
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no encontrada.")

        source_player = None
        target_player = None

        if dto.source_player_id:
            source_player = self._player_repo.get_by_id(dto.source_player_id)
            if not source_player or source_player.game_id != dto.game_id:
                raise PlayerNotFoundError(f"Jugador emisor {dto.source_player_id} no válido.")
            if not source_player.can_afford(dto.amount):
                raise InsufficientFundsError(f"Fondos insuficientes para la transferencia de ${dto.amount}.")
            source_player.deduct_money(dto.amount)
            self._player_repo.save(source_player)

        if dto.target_player_id:
            target_player = self._player_repo.get_by_id(dto.target_player_id)
            if not target_player or target_player.game_id != dto.game_id:
                raise PlayerNotFoundError(f"Jugador receptor {dto.target_player_id} no válido.")
            target_player.add_money(dto.amount)
            self._player_repo.save(target_player)

        tx_type = TransactionType.PLAYER_TRADE if (source_player and target_player) else TransactionType.BANK_TRANSFER

        tx = self._transaction_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=tx_type,
                amount=dto.amount,
                description=dto.description,
                source_player_id=dto.source_player_id,
                target_player_id=dto.target_player_id,
            )
        )

        return TransferMoneyOutputDTO(
            game_id=game.id,
            transaction_id=tx.id if tx.id else 0,
            amount=dto.amount,
            description=dto.description,
            source_balance=source_player.money if source_player else None,
            target_balance=target_player.money if target_player else None,
        )
