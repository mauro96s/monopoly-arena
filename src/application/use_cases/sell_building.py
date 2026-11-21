from src.application.dtos.action_dtos import SellBuildingInputDTO, SellBuildingOutputDTO
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
    InvalidGameActionError,
)


class SellBuildingUseCase:
    """
    Caso de Uso: Venta y Degradación de Casas y Hoteles.
    Reglas oficiales del Monopoly clásico:
    1. Venta Uniforme: Solo se puede vender de las propiedades que tengan el nivel máximo de edificios del grupo.
    2. Reembolso: El jugador recibe el 50% del costo original por cada nivel de edificio vendido (house_cost // 2).
    3. Inventario del Banco:
       - Vender 1 casa devuelve 1 casa al Banco (+1 available_houses).
       - Degradar 1 hotel a 4 casas devuelve 1 hotel (+1 available_hotels) y toma 4 casas (-4 available_houses).
    4. Escasez de Casas al vender Hoteles:
       - Si el Banco dispone de menos de 4 casas, no se puede degradar un hotel a 4 casas individualmente.
       - En tal caso, se requiere liquidación uniforme de todos los hoteles del grupo a 0 (recibiendo el 50% de los 5 niveles por cada hotel).
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

    def execute(self, dto: SellBuildingInputDTO) -> SellBuildingOutputDTO:
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
            raise InvalidGameActionError("Solo se pueden vender edificios en calles.")

        def get_prop_level(p) -> int:
            if not p:
                return 0
            return 5 if p.hotels_count >= 1 else p.houses_count

        current_level = get_prop_level(prop_state)
        if current_level == 0:
            raise InvalidGameActionError(f"'{tile_strategy.definition.name}' no tiene casas ni hoteles para vender.")

        # Obtener todas las propiedades del grupo de color
        group_tiles = BoardRuleRegistry.get_group_tile_ids(game.variant, tile_strategy.definition.group)
        group_props = [self._property_repo.get_by_tile(game.id, tid) for tid in group_tiles]
        group_levels = [get_prop_level(p) for p in group_props if p]
        max_level_in_group = max(group_levels) if group_levels else 0

        # Regla oficial: Venta uniforme
        if current_level < max_level_in_group:
            raise InvalidGameActionError(
                f"Venta no uniforme: '{tile_strategy.definition.name}' tiene nivel {current_level}, "
                f"pero otra propiedad del grupo tiene nivel {max_level_in_group}. "
                f"Las reglas oficiales exigen vender primero de las propiedades con más edificios."
            )

        refund_per_level = tile_strategy.definition.house_cost // 2
        total_refund = 0
        message = ""

        # Caso A: La propiedad tiene casas (niveles 1 a 4)
        if current_level in (1, 2, 3, 4):
            prop_state.houses_count -= 1
            game.available_houses += 1
            total_refund = refund_per_level
            player.add_money(total_refund)
            desc = f"{player.name} vendió 1 casa en {tile_strategy.definition.name} recibiendo ${total_refund} del Banco"
            message = f"Se vendió 1 casa en {tile_strategy.definition.name}. Quedan {prop_state.houses_count} casas."

        # Caso B: La propiedad tiene Hotel (nivel 5)
        else:
            if game.available_houses >= 4:
                # Degradación individual normal a 4 casas
                prop_state.hotels_count = 0
                prop_state.houses_count = 4
                game.available_hotels += 1
                game.available_houses -= 4
                total_refund = refund_per_level
                player.add_money(total_refund)
                desc = f"{player.name} degradó un Hotel a 4 casas en {tile_strategy.definition.name} recibiendo ${total_refund} del Banco"
                message = f"Hotel en {tile_strategy.definition.name} degradado a 4 casas exitosamente."
            else:
                # Escasez de casas en el Banco (< 4 disponibles)
                if not dto.sell_entire_group:
                    raise InvalidGameActionError(
                        f"Escasez de casas en el Banco: se necesitan 4 casas físicas para degradar el hotel a 4 casas, "
                        f"pero el Banco solo dispone de {game.available_houses}. "
                        f"Según el reglamento oficial del Monopoly, para obtener liquidez debes vender todos los hoteles "
                        f"del grupo {tile_strategy.definition.group.value} a 0 de forma uniforme (activa 'sell_entire_group=True')."
                    )

                # Liquidación uniforme de todos los hoteles del grupo a 0
                hotels_sold_count = 0
                for gp in group_props:
                    if gp and gp.hotels_count > 0:
                        gp.hotels_count = 0
                        gp.houses_count = 0
                        game.available_hotels += 1
                        hotels_sold_count += 1
                        self._property_repo.save(gp)
                        if gp.tile_id == prop_state.tile_id:
                            prop_state.hotels_count = 0
                            prop_state.houses_count = 0

                # Cada hotel liquidado a 0 equivale a 5 niveles (4 casas + 1 hotel)
                total_refund = hotels_sold_count * (5 * refund_per_level)
                player.add_money(total_refund)
                desc = (
                    f"{player.name} liquidó uniformemente {hotels_sold_count} hotel(es) del grupo "
                    f"{tile_strategy.definition.group.value} a 0 por escasez de casas en el Banco, recibiendo ${total_refund}"
                )
                message = (
                    f"Por escasez de casas en el Banco ({game.available_houses} disp.), se liquidaron {hotels_sold_count} "
                    f"hotel(es) del grupo {tile_strategy.definition.group.value} a 0, recibiendo ${total_refund}."
                )

        self._player_repo.save(player)
        self._property_repo.save(prop_state)
        self._game_repo.save(game)

        # Registrar en Ledger
        tx = self._transaction_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=TransactionType.SELL_BUILDING,
                amount=total_refund,
                description=desc,
                source_player_id=None,  # Banco paga al jugador
                target_player_id=player.id,
                tile_id=dto.tile_id,
            )
        )

        return SellBuildingOutputDTO(
            game_id=game.id,
            player_id=player.id,
            player_name=player.name,
            tile_id=dto.tile_id,
            tile_name=tile_strategy.definition.name,
            refund_amount=total_refund,
            new_houses_count=prop_state.houses_count,
            new_hotels_count=prop_state.hotels_count,
            remaining_balance=player.money,
            transaction_id=tx.id if tx.id else 0,
            available_houses=game.available_houses,
            available_hotels=game.available_hotels,
            message=message,
        )
