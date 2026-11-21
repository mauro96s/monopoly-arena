from src.application.dtos.action_dtos import BuildHouseInputDTO, BuildHouseOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType, TileType
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    PropertyNotFoundError,
    InsufficientFundsError,
    InvalidGameActionError,
)


class BuildHouseUseCase:
    """
    Caso de Uso: Construcción de Casas y Hoteles.
    Valida la posesión del monopolio del grupo de color y la solvencia del jugador
    según la tabla de costos oficial de la escritura.
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

    def execute(self, dto: BuildHouseInputDTO) -> BuildHouseOutputDTO:
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")

        player = self._player_repo.get_by_id(dto.player_id)
        if not player or player.game_id != dto.game_id:
            raise PlayerNotFoundError(f"Jugador {dto.player_id} no válido.")

        prop_state = self._property_repo.get_by_tile(game.id, dto.tile_id)
        if not prop_state or prop_state.owner_id != player.id:
            raise InvalidGameActionError(f"El jugador no es dueño de la propiedad '{dto.tile_id}'.")

        tile_strategy = BoardRuleRegistry.get_strategy(game.variant, dto.tile_id)
        if not tile_strategy or tile_strategy.definition.tile_type != TileType.STREET:
            raise InvalidGameActionError("Solo se puede construir en calles con monopolio.")

        # Verificar Monopolio completo
        owner_properties = self._property_repo.list_by_owner(game.id, player.id)
        group_tiles = BoardRuleRegistry.get_group_tile_ids(game.variant, tile_strategy.definition.group)
        owned_ids = {p.tile_id for p in owner_properties}
        if not group_tiles.issubset(owned_ids):
            raise InvalidGameActionError(
                f"No puedes construir en '{tile_strategy.definition.name}' sin poseer todas las calles del grupo {tile_strategy.definition.group.value}."
            )

        if prop_state.is_mortgaged:
            raise InvalidGameActionError("No se puede construir en una propiedad hipotecada.")

        if prop_state.hotels_count >= 1:
            raise InvalidGameActionError(f"'{tile_strategy.definition.name}' ya tiene el máximo permitido (1 Hotel).")

        cost = tile_strategy.definition.house_cost
        if not player.can_afford(cost):
            raise InsufficientFundsError(
                f"Fondos insuficientes para construir (${cost} requeridos, saldo: ${player.money})."
            )

        # Aplicar mejora
        is_hotel = False
        if prop_state.houses_count < 4:
            prop_state.houses_count += 1
            item_name = f"casa #{prop_state.houses_count}"
        else:
            prop_state.houses_count = 0
            prop_state.hotels_count = 1
            is_hotel = True
            item_name = "Hotel"

        player.deduct_money(cost)
        self._player_repo.save(player)
        self._property_repo.save(prop_state)

        # Registrar en Ledger
        desc = f"{player.name} construyó {item_name} en {tile_strategy.definition.name} por ${cost}"
        tx = self._transaction_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=TransactionType.BUILD_HOUSE,
                amount=cost,
                description=desc,
                source_player_id=player.id,
                target_player_id=None,  # Pago al Banco
                tile_id=dto.tile_id,
            )
        )

        return BuildHouseOutputDTO(
            game_id=game.id,
            player_id=player.id,
            player_name=player.name,
            tile_id=dto.tile_id,
            tile_name=tile_strategy.definition.name,
            cost_paid=cost,
            new_houses_count=prop_state.houses_count,
            new_hotels_count=prop_state.hotels_count,
            remaining_balance=player.money,
            transaction_id=tx.id if tx.id else 0,
        )
