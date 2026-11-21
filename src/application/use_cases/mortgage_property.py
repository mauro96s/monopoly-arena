from src.application.dtos.action_dtos import MortgageInputDTO, MortgageOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    InsufficientFundsError,
    InvalidGameActionError,
)


class MortgagePropertyUseCase:
    """
    Caso de Uso: Hipotecar y Deshipotecar Propiedades.
    - Hipotecar: El jugador recibe el 50% del valor de compra.
    - Deshipotecar: El jugador paga el 50% + 10% de interés al banco (55% del valor de compra).
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

    def execute(self, dto: MortgageInputDTO) -> MortgageOutputDTO:
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
        if not tile_strategy:
            raise InvalidGameActionError("Propiedad no encontrada en el tablero.")

        price = tile_strategy.definition.price
        mortgage_value = price // 2

        if not prop_state.is_mortgaged:
            # Hipotecar: regla oficial, ninguna propiedad del grupo de color puede tener casas ni hoteles construidos
            group_tiles = BoardRuleRegistry.get_group_tile_ids(game.variant, tile_strategy.definition.group)
            group_props = [self._property_repo.get_by_tile(game.id, tid) for tid in group_tiles]
            for gp in group_props:
                if gp and (gp.houses_count > 0 or gp.hotels_count > 0):
                    gp_strat = BoardRuleRegistry.get_strategy(game.variant, gp.tile_id)
                    gp_name = gp_strat.definition.name if gp_strat else gp.tile_id
                    raise InvalidGameActionError(
                        f"No se puede hipotecar '{tile_strategy.definition.name}': "
                        f"el grupo {tile_strategy.definition.group.value} tiene edificios construidos (en '{gp_name}'). "
                        "Debes vender todas las casas y hoteles de todas las calles del grupo antes de hipotecar."
                    )

            prop_state.is_mortgaged = True
            prop_state.transfer_interest_paid = False
            player.add_money(mortgage_value)
            desc = f"{player.name} hipotecó {tile_strategy.definition.name} y recibió ${mortgage_value} del Banco"
            tx_type = TransactionType.MORTGAGE
            amount = mortgage_value
            src_id = None
            tgt_id = player.id
        else:
            # Deshipotecar: si el acreedor ya pagó el 10% de interés al transferir, solo abona el valor base
            if prop_state.transfer_interest_paid:
                unmortgage_cost = mortgage_value
                interest_note = " (sin recargo de interés por haberse abonado al transferir en bancarrota)"
            else:
                unmortgage_cost = int(mortgage_value * 1.1)
                interest_note = ""

            if not player.can_afford(unmortgage_cost):
                raise InsufficientFundsError(
                    f"Saldo insuficiente para deshipotecar (${unmortgage_cost} requeridos, saldo: ${player.money})."
                )

            prop_state.is_mortgaged = False
            prop_state.transfer_interest_paid = False
            player.deduct_money(unmortgage_cost)
            desc = f"{player.name} deshipotecó {tile_strategy.definition.name} pagando ${unmortgage_cost} al Banco{interest_note}"
            tx_type = TransactionType.UNMORTGAGE
            amount = unmortgage_cost
            src_id = player.id
            tgt_id = None

        self._player_repo.save(player)
        self._property_repo.save(prop_state)

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
                tile_id=dto.tile_id,
            )
        )

        return MortgageOutputDTO(
            game_id=game.id,
            player_id=player.id,
            tile_id=dto.tile_id,
            tile_name=tile_strategy.definition.name,
            amount=amount,
            is_mortgaged=prop_state.is_mortgaged,
            remaining_balance=player.money,
            transaction_id=tx.id if tx.id else 0,
        )
