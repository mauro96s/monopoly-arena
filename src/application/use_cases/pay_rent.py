from src.application.dtos.action_dtos import PayRentInputDTO, PayRentOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.rules.classic_rules import CLASSIC_GROUP_TILES
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    PropertyNotFoundError,
    InsufficientFundsError,
    InvalidGameActionError,
)


class PayRentUseCase:
    """
    Caso de Uso: Cálculo y Pago Automático de Renta.
    Evalúa automáticamente si la propiedad tiene casas, hoteles o si el dueño posee
    el monopolio completo del grupo de color (duplicando renta base),
    descontando el saldo al pagador y abonando al dueño sin ingreso manual.
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

    def execute(self, dto: PayRentInputDTO) -> PayRentOutputDTO:
        # 1. Validar partida
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")

        # 2. Validar pagador
        payer = self._player_repo.get_by_id(dto.payer_player_id)
        if not payer or payer.game_id != dto.game_id:
            raise PlayerNotFoundError(f"Jugador pagador {dto.payer_player_id} no válido.")

        # 3. Validar estado de la casilla y su dueño
        prop_state = self._property_repo.get_by_tile(game.id, dto.tile_id)
        if not prop_state or not prop_state.is_owned:
            raise InvalidGameActionError(f"La casilla '{dto.tile_id}' no tiene dueño actualmente.")

        if prop_state.owner_id == payer.id:
            raise InvalidGameActionError("Un jugador no puede pagarse renta a sí mismo.")

        owner = self._player_repo.get_by_id(prop_state.owner_id)
        if not owner or owner.game_id != dto.game_id:
            raise PlayerNotFoundError(f"El dueño de la propiedad (ID {prop_state.owner_id}) no fue encontrado.")

        # 4. Obtener estrategia de casilla
        tile_strategy = BoardRuleRegistry.get_strategy(game.variant, dto.tile_id)
        if not tile_strategy:
            raise PropertyNotFoundError(f"Casilla '{dto.tile_id}' no encontrada en el tablero.")

        # 5. Obtener todas las propiedades del dueño para el cálculo automático
        owner_properties = self._property_repo.list_by_owner(game.id, owner.id)

        # 6. Calcular Renta Automática (Monopolio x2, Casas, Hoteles, Estaciones, Servicios)
        rent_amount = tile_strategy.calculate_rent(
            property_state=prop_state,
            owner_properties=owner_properties,
            dice_roll=dto.dice_roll,
        )

        is_monopoly_doubled = False
        group_tiles = CLASSIC_GROUP_TILES.get(tile_strategy.definition.group, set())
        owned_ids = {p.tile_id for p in owner_properties}
        if (
            prop_state.houses_count == 0
            and prop_state.hotels_count == 0
            and group_tiles
            and group_tiles.issubset(owned_ids)
            and len(group_tiles) > 1
        ):
            is_monopoly_doubled = True

        # 7. Validar fondos del pagador
        if not payer.can_afford(rent_amount):
            raise InsufficientFundsError(
                f"{payer.name} no cuenta con fondos suficientes para pagar la renta de ${rent_amount} (Saldo: ${payer.money})."
            )

        # 8. Transferencia monetaria
        payer.deduct_money(rent_amount)
        owner.add_money(rent_amount)
        self._player_repo.save(payer)
        self._player_repo.save(owner)

        # 9. Descripción detallada de auditoría
        details = []
        if prop_state.hotels_count > 0:
            details.append("1 Hotel")
        elif prop_state.houses_count > 0:
            details.append(f"{prop_state.houses_count} Casas")
        elif is_monopoly_doubled:
            details.append("Monopolio x2")

        details_str = f" ({', '.join(details)})" if details else ""
        desc = f"{payer.name} pagó ${rent_amount} de renta a {owner.name} por {tile_strategy.definition.name}{details_str}"

        # 10. Registrar en el Ledger
        tx = self._transaction_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=TransactionType.PAY_RENT,
                amount=rent_amount,
                description=desc,
                source_player_id=payer.id,
                target_player_id=owner.id,
                tile_id=dto.tile_id,
            )
        )

        # 11. Avance automático de turno
        all_players = self._player_repo.list_by_game(game.id)
        if dto.auto_advance_turn and all_players:
            game.advance_turn(len(all_players))
            self._game_repo.save(game)

        return PayRentOutputDTO(
            game_id=game.id,
            payer_id=payer.id,
            payer_name=payer.name,
            owner_id=owner.id,
            owner_name=owner.name,
            tile_id=dto.tile_id,
            tile_name=tile_strategy.definition.name,
            rent_amount=rent_amount,
            is_monopoly_doubled=is_monopoly_doubled,
            houses_count=prop_state.houses_count,
            hotels_count=prop_state.hotels_count,
            payer_balance=payer.money,
            owner_balance=owner.money,
            transaction_id=tx.id if tx.id else 0,
            current_turn=game.current_turn,
            current_player_index=game.current_player_index,
        )
