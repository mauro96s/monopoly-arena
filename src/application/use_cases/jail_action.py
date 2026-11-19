import random
from typing import Optional
from src.application.dtos.action_dtos import JailActionInputDTO, JailActionOutputDTO
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
    InsufficientFundsError,
    InvalidGameActionError,
)


class JailActionUseCase:
    """
    Caso de Uso: Gestión Estricta de la Cárcel según Reglas Oficiales.
    - PAY_FINE: Pagar $50, liberarse y quedar habilitado para tirar dados en este turno.
    - USE_CARD: Usar tarjeta, liberarse y quedar habilitado para tirar dados.
    - TRY_DOUBLES:
        * Bloqueado si acumula 2 turnos previos (3er turno obligatorio pago de fianza).
        * Si saca dobles: se libera y avanza esas casillas inmediatamente (sin turno extra).
        * Si no saca dobles: suma turno en prisión y su turno termina (avanza al rival).
    """

    def __init__(
        self,
        game_repo: GameRepositoryProtocol,
        player_repo: PlayerRepositoryProtocol,
        transaction_repo: TransactionRepositoryProtocol,
        property_repo: Optional[PropertyRepositoryProtocol] = None,
    ):
        self._game_repo = game_repo
        self._player_repo = player_repo
        self._tx_repo = transaction_repo
        self._property_repo = property_repo

    def execute(self, dto: JailActionInputDTO) -> JailActionOutputDTO:
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")

        player = self._player_repo.get_by_id(dto.player_id)
        if not player or player.game_id != dto.game_id:
            raise PlayerNotFoundError(f"Jugador {dto.player_id} no válido.")

        all_players = self._player_repo.list_by_game(game.id)
        active_player = all_players[game.current_player_index % len(all_players)]
        if dto.action != "GO_TO_JAIL" and player.id != active_player.id:
            raise InvalidGameActionError(
                f"Acción bloqueada: No es el turno de {player.name}. Es el turno de {active_player.name}."
            )

        amount_paid = 0
        desc = ""
        dice_1 = None
        dice_2 = None
        is_doubles = None
        new_position = player.position
        action_required = None
        action_details = None

        if dto.action == "PAY_FINE":
            if not player.in_jail:
                raise InvalidGameActionError(f"{player.name} no está en prisión.")
            if not player.can_afford(50):
                raise InsufficientFundsError(f"Saldo insuficiente para pagar fianza de $50 (Saldo: ${player.money}).")

            player.deduct_money(50)
            player.in_jail = False
            player.jail_turns = 0
            amount_paid = 50
            desc = f"⚖️ {player.name} pagó fianza de $50 y salió libre de la Cárcel (listo para tirar dados)"

            # Habilitar tirada de dados para este turno
            game.has_rolled_dice = False
            game.consecutive_doubles = 0
            self._game_repo.save(game)
            self._player_repo.save(player)

        elif dto.action == "USE_CARD":
            if not player.in_jail:
                raise InvalidGameActionError(f"{player.name} no está en prisión.")
            if player.out_of_jail_cards > 0:
                player.out_of_jail_cards -= 1

            player.in_jail = False
            player.jail_turns = 0
            desc = f"🎫 {player.name} usó una tarjeta de Salga Libre de la Cárcel (listo para tirar dados)"

            game.has_rolled_dice = False
            game.consecutive_doubles = 0
            self._game_repo.save(game)
            self._player_repo.save(player)

        elif dto.action == "TRY_DOUBLES":
            if not player.in_jail:
                raise InvalidGameActionError(f"{player.name} no está en prisión.")

            # REGLA OBLIGATORIA DEL 3ER TURNO
            if player.jail_turns >= 3:
                raise InvalidGameActionError(
                    "Es tu 3er turno en la Cárcel: las reglas oficiales prohíben intentar dobles y obligan a pagar la fianza de $50 o usar tarjeta para salir."
                )

            # Tirar dados
            if dto.dice_1 and dto.dice_2:
                dice_1 = dto.dice_1
                dice_2 = dto.dice_2
            else:
                dice_1 = random.randint(1, 6)
                dice_2 = random.randint(1, 6)

            total_roll = dice_1 + dice_2
            is_doubles = (dice_1 == dice_2)

            if is_doubles:
                # ¡Sale de prisión y se mueve inmediatamente!
                player.in_jail = False
                player.jail_turns = 0
                new_position = (10 + total_roll) % 40
                player.position = new_position
                self._player_repo.save(player)

                # Salir de la cárcel con dobles NO da turno extra
                game.has_rolled_dice = True
                game.consecutive_doubles = 0

                # Evaluar casilla de destino
                board = BoardRuleRegistry.get_board(game.variant)
                tile_strategy = next((s for s in board.values() if s.definition.position == new_position), None)
                tile_name = tile_strategy.definition.name if tile_strategy else f"Casilla #{new_position}"

                # Ejecución automática de casilla si aplica
                if tile_strategy and tile_strategy.can_be_purchased() and self._property_repo:
                    prop = self._property_repo.get_by_tile(game.id, tile_strategy.definition.tile_id)
                    if not prop or prop.owner_id is None:
                        action_required = "BUY_PROPERTY"
                        action_details = {
                            "tile_id": tile_strategy.definition.tile_id,
                            "tile_name": tile_name,
                            "price": tile_strategy.definition.price,
                            "base_rent": tile_strategy.definition.base_rent,
                            "can_afford": player.can_afford(tile_strategy.definition.price),
                        }
                    elif prop.owner_id != player.id and not prop.is_mortgaged:
                        # Auto renta
                        owner = self._player_repo.get_by_id(prop.owner_id)
                        all_props = self._property_repo.list_by_owner(game.id, prop.owner_id)
                        calculated_rent = tile_strategy.calculate_rent(prop, all_props, total_roll)
                        rent_to_pay = min(player.money, calculated_rent)
                        player.deduct_money(rent_to_pay)
                        if owner:
                            owner.add_money(rent_to_pay)
                            self._player_repo.save(owner)
                        self._player_repo.save(player)

                        self._tx_repo.record(
                            Transaction(
                                id=None,
                                game_id=game.id,
                                turn_number=game.current_turn,
                                transaction_type=TransactionType.PAY_RENT,
                                amount=rent_to_pay,
                                description=f"💸 {player.name} pagó ${rent_to_pay} de renta a {owner.name if owner else 'Rival'} tras salir de prisión",
                                source_player_id=player.id,
                                target_player_id=owner.id if owner else None,
                                tile_id=tile_strategy.definition.tile_id,
                            )
                        )
                        action_required = "RENT_PAID_AUTOMATICALLY"
                        action_details = {"owner_name": owner.name if owner else "Rival", "rent_amount": rent_to_pay, "tile_name": tile_name}
                elif tile_strategy and tile_strategy.definition.tile_type == TileType.TAX:
                    tax_amount = tile_strategy.definition.price or 100
                    tax_to_pay = min(player.money, tax_amount)
                    player.deduct_money(tax_to_pay)
                    self._player_repo.save(player)
                    self._tx_repo.record(
                        Transaction(
                            id=None,
                            game_id=game.id,
                            turn_number=game.current_turn,
                            transaction_type=TransactionType.TAX_PAYMENT,
                            amount=tax_to_pay,
                            description=f"🏛️ {player.name} pagó ${tax_to_pay} de impuestos tras salir de prisión",
                            source_player_id=player.id,
                            target_player_id=None,
                            tile_id=tile_strategy.definition.tile_id,
                        )
                    )
                    action_required = "TAX_PAID_AUTOMATICALLY"
                    action_details = {"tax_amount": tax_to_pay, "tile_name": tile_name}
                else:
                    action_required = "NEUTRAL"
                    action_details = {"tile_name": tile_name}

                desc = f"🎲 {player.name} sacó dobles ({dice_1}+{dice_2}) y salió libre de la Cárcel avanzando a {tile_name}"
                self._game_repo.save(game)
            else:
                # No sacó dobles -> Suma turno y finaliza su turno inmediatamente
                player.jail_turns += 1
                self._player_repo.save(player)
                desc = f"🔒 {player.name} tiró {dice_1}+{dice_2} ({total_roll}) sin dobles y sigue en prisión (Turno #{player.jail_turns} cumplido)"

                # Termina turno y pasa al rival
                game.advance_turn(len(all_players))
                self._game_repo.save(game)

        elif dto.action == "GO_TO_JAIL":
            player.in_jail = True
            player.jail_turns = 0
            player.position = 10
            desc = f"👮 {player.name} fue enviado a la Cárcel"
            self._player_repo.save(player)
            if dto.auto_advance_turn and all_players:
                game.advance_turn(len(all_players))
                game.has_rolled_dice = False
                game.consecutive_doubles = 0
                self._game_repo.save(game)
                self._game_repo.save(game)
        else:
            raise InvalidGameActionError(f"Acción de cárcel desconocida: '{dto.action}'.")

        tx = self._tx_repo.record(
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

        return JailActionOutputDTO(
            game_id=game.id,
            player_id=player.id,
            player_name=player.name,
            in_jail=player.in_jail,
            jail_turns=player.jail_turns,
            amount_paid=amount_paid,
            remaining_balance=player.money,
            transaction_id=tx.id if tx.id else 0,
            dice_1=dice_1,
            dice_2=dice_2,
            is_doubles=is_doubles,
            new_position=new_position,
            action_required=action_required,
            action_details=action_details,
            current_turn=game.current_turn,
            current_player_index=game.current_player_index,
        )
