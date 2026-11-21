from typing import Optional, List
from src.application.dtos.action_dtos import DeclareBankruptcyInputDTO, DeclareBankruptcyOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType, GameStatus
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    InvalidGameActionError,
)


class DeclareBankruptcyUseCase:
    """
    Caso de Uso: Cierre Formal de Bancarrota y Transferencia/Liquidación de Activos.
    Implementa las reglas oficiales del Monopoly clásico:
    1. Liquidación forzosa previa de casas y hoteles al 50% regresando al inventario físico del Banco.
    2. Escenario A (Quiebra ante otro jugador):
       - Transferencia del efectivo y tarjetas de cárcel al acreedor.
       - Transferencia de propiedades al acreedor.
       - Interés obligatorio: el acreedor paga inmediatamente al Banco el 10% del valor de hipoteca por cada propiedad hipotecada.
       - Si deshipoteca en ese momento, paga solo el valor base (50%).
       - Si la conserva hipotecada, se marca 'transfer_interest_paid = True' para que no vuelva a pagar el 10% al deshipotecar después.
    3. Escenario B (Quiebra ante el Banco):
       - Efectivo y tarjetas vuelven al Banco.
       - Propiedades quedan libres (owner_id = None, is_mortgaged = False) y se encolan en pending_auction_tiles para subasta pública.
    4. Cierre o continuación:
       - Si queda solo 1 jugador activo, finaliza la partida (GameStatus.FINISHED) proclamando al ganador.
       - Si quedan 2 o más, avanza limpiamente al siguiente jugador activo.
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

    def execute(self, dto: DeclareBankruptcyInputDTO) -> DeclareBankruptcyOutputDTO:
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")
        if game.status == GameStatus.FINISHED:
            raise InvalidGameActionError("La partida ya ha finalizado.")

        bankrupt_player = self._player_repo.get_by_id(dto.bankrupt_player_id)
        if not bankrupt_player or bankrupt_player.game_id != dto.game_id:
            raise PlayerNotFoundError(f"Jugador {dto.bankrupt_player_id} no válido.")

        if bankrupt_player.is_bankrupt:
            raise InvalidGameActionError(f"{bankrupt_player.name} ya se encuentra en bancarrota.")

        creditor_player = None
        if dto.creditor_player_id is not None:
            if dto.creditor_player_id == dto.bankrupt_player_id:
                raise InvalidGameActionError("Un jugador no puede declararse en bancarrota frente a sí mismo.")
            creditor_player = self._player_repo.get_by_id(dto.creditor_player_id)
            if not creditor_player or creditor_player.game_id != dto.game_id:
                raise PlayerNotFoundError(f"Acreedor {dto.creditor_player_id} no encontrado.")
            if creditor_player.is_bankrupt:
                raise InvalidGameActionError(f"El acreedor {creditor_player.name} está en bancarrota.")

        # =========================================================================
        # PASO 1: Liquidación Forzosa de Edificios (Casas y Hoteles al 50%)
        # =========================================================================
        owned_properties = self._property_repo.list_by_owner(game.id, bankrupt_player.id)
        building_liquidation_cash = 0
        houses_recovered = 0
        hotels_recovered = 0

        for prop in owned_properties:
            if prop.houses_count > 0 or prop.hotels_count > 0:
                tile_strat = BoardRuleRegistry.get_strategy(game.variant, prop.tile_id)
                house_cost = tile_strat.definition.house_cost if tile_strat else 50
                refund_per_building = house_cost // 2

                if prop.hotels_count > 0:
                    hotels_recovered += prop.hotels_count
                    # 1 hotel = 5 niveles (4 casas + 1 hotel)
                    building_liquidation_cash += prop.hotels_count * (5 * refund_per_building)
                    prop.hotels_count = 0

                if prop.houses_count > 0:
                    houses_recovered += prop.houses_count
                    building_liquidation_cash += prop.houses_count * refund_per_building
                    prop.houses_count = 0

                self._property_repo.save(prop)

        # Regresar edificios físicos a la reserva del Banco
        game.available_houses += houses_recovered
        game.available_hotels += hotels_recovered
        bankrupt_player.money += building_liquidation_cash

        # =========================================================================
        # PASO 2: Liquidación o Transferencia según el tipo de acreedor
        # =========================================================================
        cash_to_transfer = max(0, bankrupt_player.money)
        bankrupt_player.money = 0

        properties_transferred: List[str] = []
        released_to_auction: List[str] = []
        mortgage_interest_paid = 0
        unmortgage_principal_paid = 0

        if creditor_player is not None:
            # --- ESCENARIO A: BANCARROTA ANTE OTRO JUGADOR ---
            creditor_player.add_money(cash_to_transfer)
            creditor_player.out_of_jail_cards += bankrupt_player.out_of_jail_cards
            bankrupt_player.out_of_jail_cards = 0

            for prop in owned_properties:
                prop.owner_id = creditor_player.id
                tile_strat = BoardRuleRegistry.get_strategy(game.variant, prop.tile_id)
                price = tile_strat.definition.price if tile_strat else 100
                mortgage_val = price // 2

                if prop.is_mortgaged:
                    # 10% obligatorio de interés al Banco por transferencia
                    fee_10_percent = int(mortgage_val * 0.10)
                    if creditor_player.can_afford(fee_10_percent):
                        creditor_player.deduct_money(fee_10_percent)
                    mortgage_interest_paid += fee_10_percent

                    # Si además el acreedor decide deshipotecar de inmediato
                    if dto.unmortgage_transferred_properties:
                        if creditor_player.can_afford(mortgage_val):
                            creditor_player.deduct_money(mortgage_val)
                            prop.is_mortgaged = False
                            prop.transfer_interest_paid = False
                            unmortgage_principal_paid += mortgage_val
                        else:
                            # No le alcanza para el valor base: se mantiene hipotecada
                            prop.transfer_interest_paid = True
                    else:
                        # Se conserva hipotecada pero con el 10% ya pagado
                        prop.transfer_interest_paid = True
                else:
                    prop.transfer_interest_paid = False

                self._property_repo.save(prop)
                properties_transferred.append(prop.tile_id)

            self._player_repo.save(creditor_player)

        else:
            # --- ESCENARIO B: BANCARROTA ANTE EL BANCO ---
            bankrupt_player.out_of_jail_cards = 0
            for prop in owned_properties:
                prop.owner_id = None
                prop.is_mortgaged = False
                prop.transfer_interest_paid = False
                prop.houses_count = 0
                prop.hotels_count = 0
                self._property_repo.save(prop)

                released_to_auction.append(prop.tile_id)
                if prop.tile_id not in game.pending_auction_tiles:
                    game.pending_auction_tiles.append(prop.tile_id)

        # =========================================================================
        # PASO 3: Actualizar Estado del Jugador y Ciclo de la Partida
        # =========================================================================
        bankrupt_player.is_bankrupt = True
        self._player_repo.save(bankrupt_player)

        all_players = self._player_repo.list_by_game(game.id)
        active_players = [p for p in all_players if not p.is_bankrupt]
        remaining_count = len(active_players)

        is_game_finished = False
        winner_id = None
        winner_name = None

        if remaining_count <= 1:
            # ¡Fin de partida! Proclamar al único superviviente
            game.status = GameStatus.FINISHED
            is_game_finished = True
            if active_players:
                winner = active_players[0]
                winner_id = winner.id
                winner_name = winner.name
        else:
            # Avanzar limpiamente el turno al siguiente jugador activo
            game.advance_to_next_active_player(all_players)

        self._game_repo.save(game)

        # =========================================================================
        # PASO 4: Registrar en el Ledger de Transacciones
        # =========================================================================
        target_name = creditor_player.name if creditor_player else "el Banco"
        audit_desc = (
            f"💀 {bankrupt_player.name} se declaró en BANCARROTA frente a {target_name}. "
            f"Transferido: ${cash_to_transfer} y {len(owned_properties)} propiedad(es). "
            f"Edificios liquidados: {houses_recovered} casas, {hotels_recovered} hoteles devueltos al Banco."
        )

        tx = self._transaction_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=TransactionType.BANKRUPTCY,
                amount=cash_to_transfer,
                description=audit_desc,
                source_player_id=bankrupt_player.id,
                target_player_id=creditor_player.id if creditor_player else None,
                tile_id=None,
            )
        )

        return DeclareBankruptcyOutputDTO(
            game_id=game.id,
            bankrupt_player_id=bankrupt_player.id,  # type: ignore
            bankrupt_player_name=bankrupt_player.name,
            creditor_player_id=creditor_player.id if creditor_player else None,
            creditor_player_name=creditor_player.name if creditor_player else None,
            cash_transferred=cash_to_transfer,
            properties_transferred=properties_transferred,
            liquidated_houses=houses_recovered,
            liquidated_hotels=hotels_recovered,
            mortgage_interest_paid_to_bank=mortgage_interest_paid,
            unmortgage_principal_paid_to_bank=unmortgage_principal_paid,
            released_to_auction_tiles=released_to_auction,
            remaining_active_players_count=remaining_count,
            is_game_finished=is_game_finished,
            winner_player_id=winner_id,
            winner_player_name=winner_name,
            transaction_id=tx.id if tx.id else 0,
            message=f"{bankrupt_player.name} ha sido eliminado. Sus activos fueron liquidados/transferidos a {target_name}.",
        )
