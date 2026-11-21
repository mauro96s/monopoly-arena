from typing import Optional
from src.application.dtos.action_dtos import BankActionInputDTO, BankActionOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType
from src.domain.rules.rule_hooks import RulesetEngine
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    InsufficientFundsError,
    InvalidGameActionError,
)


class BankActionUseCase:
    """
    Caso de Uso: Movimiento Bancario Manual entre la Banca y un Jugador.
    Soporta:
    - BANK_PAYS_PLAYER / CREDIT (+): El Banco acredita fondos al jugador.
    - PLAYER_PAYS_BANK / DEBIT (-): El jugador paga fondos al Banco.
    - PASS_GO (+): Cobro de $200 por pasar por la Salida.
    """

    def __init__(
        self,
        game_repo: GameRepositoryProtocol,
        player_repo: PlayerRepositoryProtocol,
        property_repo: Optional[PropertyRepositoryProtocol] = None,
        transaction_repo: Optional[TransactionRepositoryProtocol] = None,
    ):
        self._game_repo = game_repo
        self._player_repo = player_repo
        self._property_repo = property_repo
        self._transaction_repo = transaction_repo

    def execute(self, dto: BankActionInputDTO) -> BankActionOutputDTO:
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")

        player = self._player_repo.get_by_id(dto.player_id)
        if not player or player.game_id != dto.game_id:
            raise PlayerNotFoundError(f"Jugador {dto.player_id} no válido.")

        all_players = self._player_repo.list_by_game(game.id)

        # Determinar dirección de la transacción bancaria
        if dto.action_type in ("BANK_PAYS_PLAYER", "CREDIT", "PASS_GO"):
            is_credit = True
            amount = dto.custom_amount if (dto.custom_amount and dto.custom_amount > 0) else (200 if dto.action_type == "PASS_GO" else 0)
            default_desc = f"{player.name} cobró $200 por pasar por la Salida" if dto.action_type == "PASS_GO" else f"El Banco pagó ${amount} a {player.name}"
            desc = dto.description.strip() if dto.description and dto.description.strip() else default_desc
        elif dto.action_type in ("PLAYER_PAYS_BANK", "DEBIT", "INCOME_TAX", "LUXURY_TAX"):
            is_credit = False
            amount = dto.custom_amount if (dto.custom_amount and dto.custom_amount > 0) else (200 if dto.action_type == "INCOME_TAX" else (100 if dto.action_type == "LUXURY_TAX" else 0))
            default_desc = f"{player.name} pagó ${amount} de impuestos" if "TAX" in dto.action_type else f"{player.name} pagó ${amount} al Banco"
            desc = dto.description.strip() if dto.description and dto.description.strip() else default_desc
        else:
            raise InvalidGameActionError(f"Tipo de movimiento bancario no válido: '{dto.action_type}'.")

        if amount <= 0:
            raise InvalidGameActionError("El monto bancario debe ser mayor a $0.")

        # Aplicar débito o crédito
        if is_credit:
            player.add_money(amount)
            src_id = None
            tgt_id = player.id
            tx_type = TransactionType.PASS_GO if dto.action_type == "PASS_GO" else TransactionType.BANK_TRANSFER
        else:
            if not player.can_afford(amount):
                raise InsufficientFundsError(f"Fondos insuficientes (${amount} requeridos, saldo actual: ${player.money}).")
            player.deduct_money(amount)
            RulesetEngine.process_tax_or_fine(game, player, amount)
            self._game_repo.save(game)
            src_id = player.id
            tgt_id = None
            tx_type = TransactionType.TAX_PAYMENT if "TAX" in dto.action_type else TransactionType.BANK_TRANSFER

        self._player_repo.save(player)

        tx_id = 0
        if self._transaction_repo:
            tx = self._transaction_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=tx_type,
                    amount=amount,
                    description=desc,
                    source_player_id=src_id,
                    target_player_id=tgt_id,
                )
            )
            tx_id = tx.id if tx.id else 0

        if dto.auto_advance_turn and all_players:
            game.advance_turn(len(all_players))
            self._game_repo.save(game)

        return BankActionOutputDTO(
            game_id=game.id,
            player_id=player.id,
            player_name=player.name,
            amount=amount,
            is_credit=is_credit,
            remaining_balance=player.money,
            transaction_id=tx_id,
            current_turn=game.current_turn,
            current_player_index=game.current_player_index,
        )
