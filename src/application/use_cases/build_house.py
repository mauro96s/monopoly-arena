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

        # 1. Regla oficial: NINGUNA propiedad del grupo puede estar hipotecada
        group_props = [self._property_repo.get_by_tile(game.id, tid) for tid in group_tiles]
        for gp in group_props:
            if gp and gp.is_mortgaged:
                gp_strat = BoardRuleRegistry.get_strategy(game.variant, gp.tile_id)
                gp_name = gp_strat.definition.name if gp_strat else gp.tile_id
                raise InvalidGameActionError(
                    f"No se puede construir en el grupo {tile_strategy.definition.group.value}: "
                    f"la propiedad '{gp_name}' está hipotecada. Todas las calles del grupo deben estar libres de hipoteca."
                )

        if prop_state.hotels_count >= 1:
            raise InvalidGameActionError(f"'{tile_strategy.definition.name}' ya tiene el máximo permitido (1 Hotel).")

        # 2. Regla oficial: Construcción uniforme (Even building rule)
        # Nivel de edificio: 0 a 4 para casas, 5 para hotel
        def get_prop_level(p) -> int:
            if not p:
                return 0
            return 5 if p.hotels_count >= 1 else p.houses_count

        current_level = get_prop_level(prop_state)
        group_levels = [get_prop_level(p) for p in group_props if p]
        min_level_in_group = min(group_levels) if group_levels else 0

        if current_level > min_level_in_group:
            raise InvalidGameActionError(
                f"Construcción no uniforme: '{tile_strategy.definition.name}' ya tiene nivel {current_level}, "
                f"mientras que otra propiedad del grupo tiene nivel {min_level_in_group}. "
                f"Las reglas del Monopoly exigen construir uniformemente en todas las calles del grupo."
            )

        # 3. Regla oficial: Reserva física de 32 casas y 12 hoteles en el Banco
        is_upgrading_to_hotel = (prop_state.houses_count == 4)
        if not is_upgrading_to_hotel:
            # Desea construir una casa (0->1, 1->2, 2->3, 3->4)
            if game.available_houses < 1:
                raise InvalidGameActionError(
                    "El Banco no dispone de casas físicas (0 disponibles). "
                    "Debes esperar a que otro jugador venda casas para construir."
                )
        else:
            # Desea construir un hotel (4->5)
            if game.available_hotels < 1:
                raise InvalidGameActionError(
                    "El Banco no dispone de hoteles físicos (0 disponibles). "
                    "Debes esperar a que se libere un hotel en el Banco para construir."
                )

        cost = tile_strategy.definition.house_cost
        if not player.can_afford(cost):
            raise InsufficientFundsError(
                f"Fondos insuficientes para construir (${cost} requeridos, saldo: ${player.money})."
            )

        # Aplicar mejora y actualizar reserva del Banco
        if not is_upgrading_to_hotel:
            prop_state.houses_count += 1
            game.available_houses -= 1
            item_name = f"casa #{prop_state.houses_count}"
        else:
            # Hotel: se entregan las 4 casas de vuelta al Banco y se toma 1 hotel
            prop_state.houses_count = 0
            prop_state.hotels_count = 1
            game.available_hotels -= 1
            game.available_houses += 4
            item_name = "Hotel"

        player.deduct_money(cost)
        self._player_repo.save(player)
        self._property_repo.save(prop_state)
        self._game_repo.save(game)

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
            available_houses=game.available_houses,
            available_hotels=game.available_hotels,
        )
