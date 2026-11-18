import random
from typing import Optional
from src.application.dtos.action_dtos import RollDiceInputDTO, RollDiceOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType, TileType
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    InvalidGameActionError,
)


class RollDiceUseCase:
    """
    Caso de Uso: Tirar Dados y Mover Jugador por el Tablero en Vivo.
    - Soporta tiro aleatorio 2d6 o valor ingresado manualmente.
    - Actualiza posición: (position + roll) % 40.
    - Detecta paso por la SALIDA (casilla 0) y abona $200 automáticamente.
    - Detecta casilla de destino (Propiedad libre, Renta a rival, Impuestos, Cárcel, Neutral).
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
        self._tx_repo = transaction_repo

    def execute(self, dto: RollDiceInputDTO) -> RollDiceOutputDTO:
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")

        player = self._player_repo.get_by_id(dto.player_id)
        if not player or player.game_id != dto.game_id:
            raise PlayerNotFoundError(f"Jugador {dto.player_id} no válido.")

        # Calcular o simular dados
        if dto.total_roll and dto.total_roll > 0:
            total_roll = dto.total_roll
            dice_1 = total_roll // 2
            dice_2 = total_roll - dice_1
        elif dto.dice_1 and dto.dice_2:
            dice_1 = dto.dice_1
            dice_2 = dto.dice_2
            total_roll = dice_1 + dice_2
        else:
            dice_1 = random.randint(1, 6)
            dice_2 = random.randint(1, 6)
            total_roll = dice_1 + dice_2

        is_doubles = (dice_1 == dice_2)
        old_position = player.position

        # Manejo de Cárcel
        if player.in_jail:
            if is_doubles:
                # Saca dobles: ¡Queda libre de inmediato y avanza los dados!
                player.in_jail = False
                player.jail_turns = 0
                self._tx_repo.record(
                    Transaction(
                        id=None,
                        game_id=game.id,
                        turn_number=game.current_turn,
                        transaction_type=TransactionType.BANK_TRANSFER,
                        amount=0,
                        description=f"{player.name} sacó dobles ({dice_1}+{dice_2}) y salió libre de la Cárcel",
                        source_player_id=None,
                        target_player_id=player.id,
                        tile_id="JAIL",
                    )
                )
                new_position = (old_position + total_roll) % 40
            else:
                # No sacó dobles: Permanece en prisión
                player.jail_turns += 1
                self._player_repo.save(player)
                self._tx_repo.record(
                    Transaction(
                        id=None,
                        game_id=game.id,
                        turn_number=game.current_turn,
                        transaction_type=TransactionType.BANK_TRANSFER,
                        amount=0,
                        description=f"{player.name} tiró {dice_1}+{dice_2} ({total_roll}) sin dobles y sigue en prisión (Turno #{player.jail_turns})",
                        source_player_id=None,
                        target_player_id=None,
                        tile_id="JAIL",
                    )
                )
                return RollDiceOutputDTO(
                    game_id=game.id,
                    player_id=player.id,
                    player_name=player.name,
                    dice_1=dice_1,
                    dice_2=dice_2,
                    total_roll=total_roll,
                    is_doubles=is_doubles,
                    old_position=old_position,
                    new_position=old_position,
                    passed_go=False,
                    landed_tile_id="JAIL",
                    landed_tile_name="Cárcel / Visitas",
                    landed_tile_type="JAIL",
                    action_required="IN_JAIL",
                    action_details={"jail_turns": player.jail_turns, "must_pay_fine": player.jail_turns >= 3},
                    player_money=player.money,
                    transaction_id=None,
                )
        else:
            new_position = (old_position + total_roll) % 40

        # Detectar paso por la SALIDA (casilla 0) y abonar $200
        passed_go = (new_position < old_position)
        tx_id = None
        if passed_go:
            player.add_money(200)
            tx = self._tx_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=TransactionType.PASS_GO,
                    amount=200,
                    description=f"{player.name} pasó por la SALIDA y cobró $200 de la Banca",
                    source_player_id=None,
                    target_player_id=player.id,
                    tile_id="GO",
                )
            )
            tx_id = tx.id

        # Localizar definición de casilla
        board = BoardRuleRegistry.get_board(game.variant)
        tile_strategy = next((s for s in board.values() if s.definition.position == new_position), None)
        if not tile_strategy:
            raise InvalidGameActionError(f"Casilla no encontrada en posición {new_position}.")

        tile_def = tile_strategy.definition

        # Casilla Especial: ¡Vaya a la Cárcel! (Posición 30)
        if new_position == 30:
            player.in_jail = True
            player.jail_turns = 1
            player.position = 10  # Trasladar a prisión
            self._player_repo.save(player)
            self._tx_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=TransactionType.BANK_TRANSFER,
                    amount=0,
                    description=f"{player.name} cayó en ¡Vaya a la Cárcel! y fue enviado directo a prisión",
                    source_player_id=None,
                    target_player_id=None,
                    tile_id="GO_TO_JAIL",
                )
            )
            return RollDiceOutputDTO(
                game_id=game.id,
                player_id=player.id,
                player_name=player.name,
                dice_1=dice_1,
                dice_2=dice_2,
                total_roll=total_roll,
                is_doubles=is_doubles,
                old_position=old_position,
                new_position=10,
                passed_go=passed_go,
                landed_tile_id="GO_TO_JAIL",
                landed_tile_name="¡Vaya a la Cárcel!",
                landed_tile_type="GO_TO_JAIL",
                action_required="WENT_TO_JAIL",
                action_details={"jail_position": 10},
                player_money=player.money,
                transaction_id=tx_id,
            )

        # Actualizar posición definitiva del jugador
        player.position = new_position
        self._player_repo.save(player)

        # Evaluar acciones contextuales por casilla
        action_required = "NEUTRAL"
        action_details = {}

        if tile_strategy.can_be_purchased():
            prop = self._property_repo.get_by_tile_id(game.id, tile_def.tile_id)
            if not prop or prop.owner_id is None:
                action_required = "CAN_BUY"
                action_details = {
                    "price": tile_def.price,
                    "base_rent": tile_def.base_rent,
                    "group": tile_def.group.value,
                    "can_afford": player.can_afford(tile_def.price),
                }
            elif prop.owner_id == player.id:
                action_required = "OWNED_BY_SELF"
                action_details = {
                    "houses_count": prop.houses_count,
                    "hotels_count": prop.hotels_count,
                }
            else:
                if prop.is_mortgaged:
                    action_required = "MORTGAGED"
                    action_details = {"owner_id": prop.owner_id}
                else:
                    owner = self._player_repo.get_by_id(prop.owner_id)
                    all_props = self._property_repo.list_by_owner(game.id, prop.owner_id)
                    rent_amount = tile_strategy.calculate_rent(prop, all_props, total_roll)
                    action_required = "MUST_PAY_RENT"
                    action_details = {
                        "owner_id": prop.owner_id,
                        "owner_name": owner.name if owner else "Rival",
                        "rent_amount": rent_amount,
                    }
        elif tile_def.tile_type == TileType.TAX:
            action_required = "PAY_TAX"
            action_details = {"tax_amount": tile_def.price or 100}

        return RollDiceOutputDTO(
            game_id=game.id,
            player_id=player.id,
            player_name=player.name,
            dice_1=dice_1,
            dice_2=dice_2,
            total_roll=total_roll,
            is_doubles=is_doubles,
            old_position=old_position,
            new_position=new_position,
            passed_go=passed_go,
            landed_tile_id=tile_def.tile_id,
            landed_tile_name=tile_def.name,
            landed_tile_type=tile_def.tile_type.value,
            action_required=action_required,
            action_details=action_details,
            player_money=player.money,
            transaction_id=tx_id,
        )
