from src.application.dtos.action_dtos import JailActionInputDTO, JailActionOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    InsufficientFundsError,
    InvalidGameActionError,
)


class JailActionUseCase:
    """
    Caso de Uso: Gestión de Cárcel.
    Permite:
    - GO_TO_JAIL: Enviar al jugador a prisión.
    - PAY_FINE: Pagar fianza de $50 y salir libre.
    - USE_CARD: Usar carta de 'Salga libre de la cárcel'.
    - STAY: Cumplir turno en prisión (incrementa jail_turns, máximo 3).
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

    def execute(self, dto: JailActionInputDTO) -> JailActionOutputDTO:
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")

        player = self._player_repo.get_by_id(dto.player_id)
        if not player or player.game_id != dto.game_id:
            raise PlayerNotFoundError(f"Jugador {dto.player_id} no válido.")

        amount_paid = 0
        desc = ""

        if dto.action == "GO_TO_JAIL":
            player.in_jail = True
            player.jail_turns = 1
            player.position = 10  # Casilla de Cárcel
            desc = f"{player.name} fue enviado a la Cárcel (¡Directo a prisión!)"

        elif dto.action == "PAY_FINE":
            if not player.in_jail:
                raise InvalidGameActionError(f"{player.name} no está en prisión.")
            if not player.can_afford(50):
                raise InsufficientFundsError(f"Saldo insuficiente para pagar fianza de $50 (Saldo: ${player.money}).")

            player.deduct_money(50)
            player.in_jail = False
            player.jail_turns = 0
            amount_paid = 50
            desc = f"{player.name} pagó fianza de $50 y salió libre de la Cárcel"

        elif dto.action == "USE_CARD":
            if not player.in_jail:
                raise InvalidGameActionError(f"{player.name} no está en prisión.")
            player.in_jail = False
            player.jail_turns = 0
            desc = f"{player.name} usó una Carta de 'Salga libre de la Cárcel'"

        elif dto.action == "STAY":
            if not player.in_jail:
                raise InvalidGameActionError(f"{player.name} no está en prisión.")
            if player.jail_turns >= 3:
                raise InvalidGameActionError("Has cumplido 3 turnos en la Cárcel. Las reglas oficiales exigen pagar la fianza de $50 o usar una carta para salir.")
            player.jail_turns += 1
            desc = f"{player.name} cumplió su turno #{player.jail_turns} en la Cárcel"
        else:
            raise InvalidGameActionError(f"Acción de cárcel desconocida: '{dto.action}'.")

        self._player_repo.save(player)

        tx = self._transaction_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=TransactionType.BANK_TRANSFER,
                amount=amount_paid,
                description=desc,
                source_player_id=player.id if amount_paid > 0 else None,
                target_player_id=None,
                tile_id="JAIL",
            )
        )

        all_players = self._player_repo.list_by_game(game.id)
        if dto.auto_advance_turn and all_players:
            game.advance_turn(len(all_players))
            self._game_repo.save(game)

        return JailActionOutputDTO(
            game_id=game.id,
            player_id=player.id,
            player_name=player.name,
            in_jail=player.in_jail,
            jail_turns=player.jail_turns,
            amount_paid=amount_paid,
            remaining_balance=player.money,
            transaction_id=tx.id if tx.id else 0,
            current_turn=game.current_turn,
            current_player_index=game.current_player_index,
        )
