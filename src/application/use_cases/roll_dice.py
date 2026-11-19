import random
from typing import Optional
from src.application.dtos.action_dtos import RollDiceInputDTO, RollDiceOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType, TileType, GameStatus
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    InvalidGameActionError,
)


class RollDiceUseCase:
    """
    Caso de Uso: Tirar Dados y Mover Jugador por el Tablero en Vivo (Reglas Oficiales).
    - Máquina de Estados Estricta: 1 sola tirada por turno (a menos que saque dobles).
    - Bloqueo en Cárcel: Si está en prisión no puede moverse libremente por aquí.
    - Regla de Dobles: Turno extra si saca par; si acumula 3 dobles seguidos va a la Cárcel.
    - Paso por la Salida (GO): Acredita +$200 automático y registra en el Ledger.
    - Activación Post-Movimiento Inmediata:
        * Calle sin dueño -> BUY_PROPERTY.
        * Propiedad de rival -> Ejecuta y registra PAY_RENT automáticamente.
        * Impuestos -> Descuenta monto fijo y registra TAX_PAYMENT automáticamente.
        * Casilla 30 (Vaya a la Cárcel) -> Envía a posición 10, in_jail = True y finaliza turno.
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
        # 1. Validar partida
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")
        if game.status == GameStatus.FINISHED:
            raise InvalidGameActionError("La partida ya ha finalizado.")

        all_players = self._player_repo.list_by_game(dto.game_id)
        if not all_players:
            raise InvalidGameActionError("La partida no tiene jugadores registrados.")

        # 2. Validar jugador activo
        active_player = all_players[game.current_player_index % len(all_players)]
        if dto.player_id is not None and dto.player_id != active_player.id:
            raise InvalidGameActionError(
                f"Acción bloqueada: No es el turno del jugador {dto.player_id}. Es el turno de {active_player.name}."
            )
        player = active_player

        # 3. Bloqueo si está en la cárcel
        if player.in_jail and not dto.is_jail_attempt:
            raise InvalidGameActionError(
                f"{player.name} está en la Cárcel. Debe pagar la fianza de $50, usar una tarjeta o intentar sacar dobles en el panel de Cárcel."
            )

        # 4. Control de Tirada Única por Turno (a menos que tenga turno extra por dobles)
        if game.has_rolled_dice and not dto.is_jail_attempt:
            raise InvalidGameActionError(
                f"{player.name} ya ha tirado los dados en este turno. Resuelve la acción de la casilla o pasa el turno."
            )

        # 5. Calcular o simular dados
        effective_sum = dto.dice_sum if dto.dice_sum is not None else dto.total_roll

        if dto.dice_1 is not None and dto.dice_2 is not None:
            dice_1 = int(dto.dice_1)
            dice_2 = int(dto.dice_2)
            total_roll = dice_1 + dice_2
        elif effective_sum and effective_sum > 0:
            total_roll = int(effective_sum)
            dice_1 = total_roll // 2
            dice_2 = total_roll - dice_1
        else:
            dice_1 = random.randint(1, 6)
            dice_2 = random.randint(1, 6)
            total_roll = dice_1 + dice_2

        is_doubles = (dice_1 == dice_2)
        old_position = player.position

        # 6. Regla de Dobles Consecutivos
        extra_turn = False
        if is_doubles:
            game.consecutive_doubles += 1
            if game.consecutive_doubles >= 3:
                # ¡3 dobles seguidos! Directo a la Cárcel y finaliza turno
                player.in_jail = True
                player.jail_turns = 0
                player.position = 10
                self._player_repo.save(player)

                jail_tx = self._tx_repo.record(
                    Transaction(
                        id=None,
                        game_id=game.id,
                        turn_number=game.current_turn,
                        transaction_type=TransactionType.BANK_TRANSFER,
                        amount=0,
                        description=f"🚨 {player.name} sacó 3 dobles consecutivos ({dice_1}+{dice_2}) y fue enviado directo a la Cárcel",
                        source_player_id=None,
                        target_player_id=player.id,
                        tile_id="JAIL",
                    )
                )

                # Fin de turno forzado
                game.advance_turn(len(all_players))
                game.has_rolled_dice = False
                game.consecutive_doubles = 0
                self._game_repo.save(game)

                return RollDiceOutputDTO(
                    game_id=game.id,
                    player_id=player.id,
                    player_name=player.name,
                    dice_1=dice_1,
                    dice_2=dice_2,
                    total_roll=total_roll,
                    is_doubles=True,
                    old_position=old_position,
                    new_position=10,
                    passed_go=False,
                    landed_tile_id="JAIL",
                    landed_tile_name="Cárcel / Visitas",
                    landed_tile_type="JAIL",
                    action_required="WENT_TO_JAIL",
                    action_details={"reason": "3_CONSECUTIVE_DOUBLES", "jail_turns": 1},
                    player_money=player.money,
                    player_status="IN_JAIL",
                    in_jail=True,
                    extra_turn=False,
                    has_rolled_dice=False,
                    consecutive_doubles=0,
                    current_turn=game.current_turn,
                    current_player_index=game.current_player_index,
                    transaction_id=jail_tx.id,
                )
            else:
                # Menos de 3 dobles: otorga turno extra
                extra_turn = True
                # Permitimos tirar de nuevo marcando has_rolled_dice = False
                game.has_rolled_dice = False
        else:
            # No sacó dobles: ya usó su tirada única de este turno
            game.consecutive_doubles = 0
            game.has_rolled_dice = True

        # 7. Movimiento y Detección de Salida (GO)
        new_position = (old_position + total_roll) % 40
        passed_go = (new_position < old_position)
        go_tx_id = None
        if passed_go:
            player.add_money(200)
            go_tx = self._tx_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=TransactionType.PASS_GO,
                    amount=200,
                    description=f"🚩 {player.name} pasó por la SALIDA y cobró $200 de la Banca",
                    source_player_id=None,
                    target_player_id=player.id,
                    tile_id="GO",
                )
            )
            go_tx_id = go_tx.id

        # 8. Localizar definición de casilla
        board = BoardRuleRegistry.get_board(game.variant)
        tile_strategy = next((s for s in board.values() if s.definition.position == new_position), None)
        if not tile_strategy:
            raise InvalidGameActionError(f"Casilla no encontrada en posición {new_position}.")

        tile_def = tile_strategy.definition
        last_tx_id = go_tx_id

        # 9. Evaluar casilla de destino
        # CASO A: Casilla 30 (¡Vaya a la Cárcel!)
        if new_position == 30:
            player.in_jail = True
            player.jail_turns = 0
            player.position = 10  # Trasladar a prisión
            self._player_repo.save(player)

            jail_tx = self._tx_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=TransactionType.BANK_TRANSFER,
                    amount=0,
                    description=f"👮 {player.name} cayó en ¡Vaya a la Cárcel! y fue arrestado",
                    source_player_id=None,
                    target_player_id=player.id,
                    tile_id="GO_TO_JAIL",
                )
            )

            # Fin de turno forzado al ir a prisión (pierde cualquier turno extra)
            game.advance_turn(len(all_players))
            game.has_rolled_dice = False
            game.consecutive_doubles = 0
            self._game_repo.save(game)

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
                player_status="IN_JAIL",
                in_jail=True,
                extra_turn=False,
                has_rolled_dice=False,
                consecutive_doubles=0,
                current_turn=game.current_turn,
                current_player_index=game.current_player_index,
                transaction_id=jail_tx.id,
            )

        # Actualizar posición definitiva del jugador
        player.position = new_position
        self._player_repo.save(player)

        action_required = "NEUTRAL"
        action_details = {}

        # CASO B: Propiedad comprable (Calles, Ferrocarriles, Servicios)
        if tile_strategy.can_be_purchased():
            prop = self._property_repo.get_by_tile(game.id, tile_def.tile_id)
            if not prop or prop.owner_id is None:
                # Sin dueño -> Puede comprarla
                action_required = "BUY_PROPERTY"
                action_details = {
                    "price": tile_def.price,
                    "base_rent": tile_def.base_rent,
                    "group": tile_def.group.value,
                    "can_afford": player.can_afford(tile_def.price),
                    "tile_id": tile_def.tile_id,
                    "tile_name": tile_def.name,
                }
            elif prop.owner_id == player.id:
                # Propiedad propia
                action_required = "OWNED_BY_SELF"
                action_details = {
                    "houses_count": prop.houses_count,
                    "hotels_count": prop.hotels_count,
                    "tile_name": tile_def.name,
                }
            else:
                # Propiedad de un rival
                if prop.is_mortgaged:
                    action_required = "MORTGAGED_NO_RENT"
                    action_details = {"owner_id": prop.owner_id, "tile_name": tile_def.name}
                else:
                    # ¡EJECUTAR Y REGISTRAR AUTOMÁTICAMENTE EL PAY_RENT!
                    owner = self._player_repo.get_by_id(prop.owner_id)
                    all_props = self._property_repo.list_by_owner(game.id, prop.owner_id)
                    calculated_rent = tile_strategy.calculate_rent(prop, all_props, total_roll)

                    # Cobro automático de renta
                    rent_to_pay = min(player.money, calculated_rent)
                    if rent_to_pay > 0:
                        player.deduct_money(rent_to_pay)
                        if owner:
                            owner.add_money(rent_to_pay)
                            self._player_repo.save(owner)
                        self._player_repo.save(player)

                    rent_tx = self._tx_repo.record(
                        Transaction(
                            id=None,
                            game_id=game.id,
                            turn_number=game.current_turn,
                            transaction_type=TransactionType.PAY_RENT,
                            amount=rent_to_pay,
                            description=f"💸 {player.name} cayó en {tile_def.name} y pagó ${rent_to_pay} de renta a {owner.name if owner else 'Rival'}",
                            source_player_id=player.id,
                            target_player_id=owner.id if owner else None,
                            tile_id=tile_def.tile_id,
                        )
                    )
                    last_tx_id = rent_tx.id

                    action_required = "RENT_PAID_AUTOMATICALLY"
                    action_details = {
                        "owner_id": prop.owner_id,
                        "owner_name": owner.name if owner else "Rival",
                        "rent_amount": rent_to_pay,
                        "tile_name": tile_def.name,
                    }

        # CASO C: Casilla de Impuestos (TAX)
        elif tile_def.tile_type == TileType.TAX:
            # ¡DESCONTAR AUTOMÁTICAMENTE EL MONTO FIJO!
            tax_amount = tile_def.price or 100
            tax_to_pay = min(player.money, tax_amount)
            if tax_to_pay > 0:
                player.deduct_money(tax_to_pay)
                self._player_repo.save(player)

            tax_tx = self._tx_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=TransactionType.TAX_PAYMENT,
                    amount=tax_to_pay,
                    description=f"🏛️ {player.name} cayó en {tile_def.name} y pagó ${tax_to_pay} de impuestos a la Banca",
                    source_player_id=player.id,
                    target_player_id=None,
                    tile_id=tile_def.tile_id,
                )
            )
            last_tx_id = tax_tx.id

            action_required = "TAX_PAID_AUTOMATICALLY"
            action_details = {
                "tax_amount": tax_to_pay,
                "tile_name": tile_def.name,
            }

        # CASO D: Casilla Neutral (Salida, Visitas, Parking)
        else:
            action_required = "NEUTRAL"
            action_details = {"tile_name": tile_def.name}

        # Registrar movimiento en historial si no hubo otra transacción
        if not last_tx_id:
            move_tx = self._tx_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=TransactionType.BANK_TRANSFER,
                    amount=0,
                    description=f"🎲 {player.name} tiró {dice_1}+{dice_2} ({total_roll}) y se movió a {tile_def.name} (casilla {new_position})",
                    source_player_id=None,
                    target_player_id=player.id,
                    tile_id=tile_def.tile_id,
                )
            )
            last_tx_id = move_tx.id

        # Avance opcional de turno si se solicitó explícitamente y no hay turno extra
        if dto.auto_advance_turn and not extra_turn and all_players:
            game.advance_turn(len(all_players))

        # Guardar estado de la partida
        self._game_repo.save(game)

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
            player_status="ACTIVE",
            in_jail=False,
            extra_turn=extra_turn,
            has_rolled_dice=game.has_rolled_dice,
            consecutive_doubles=game.consecutive_doubles,
            current_turn=game.current_turn,
            current_player_index=game.current_player_index,
            transaction_id=last_tx_id,
        )


MovePlayerByDiceUseCase = RollDiceUseCase
