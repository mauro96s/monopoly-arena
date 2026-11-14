from typing import Optional, List
from src.application.dtos.action_dtos import BankActionInputDTO, BankActionOutputDTO
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.models.transaction import Transaction
from src.domain.models.enums import TransactionType
from src.domain.exceptions import (
    GameNotFoundError,
    PlayerNotFoundError,
    InsufficientFundsError,
    InvalidGameActionError,
)

# Catálogo oficial de Cartas de Fortuna (Comunidad y Suerte)
CHANCE_COMMUNITY_CATALOG = {
    # Cobros / Ingresos
    "PASS_GO": {"amount": 200, "is_credit": True, "desc": "Cobró $200 por pasar por la SALIDA"},
    "BANK_ERROR": {"amount": 200, "is_credit": True, "desc": "Error de la Banca a tu favor (Cobras $200)"},
    "TAX_REFUND": {"amount": 20, "is_credit": True, "desc": "Devolución de impuestos sobre la renta (Cobras $20)"},
    "INHERITANCE": {"amount": 100, "is_credit": True, "desc": "Heredas $100"},
    "STOCK_SALE": {"amount": 50, "is_credit": True, "desc": "De la venta de tus acciones obtienes $50"},
    "CONSULTANT_FEE": {"amount": 25, "is_credit": True, "desc": "Recibes $25 por servicios de consultoría"},
    "BEAUTY_CONTEST": {"amount": 100, "is_credit": True, "desc": "Segundo premio en concurso de belleza (Cobras $100)"},
    "LIFE_INSURANCE": {"amount": 100, "is_credit": True, "desc": "Tu póliza de seguro de vida vence (Cobras $100)"},
    "DIVIDENDS": {"amount": 50, "is_credit": True, "desc": "El Banco te paga dividendos de $50"},
    "BUILDING_LOAN": {"amount": 150, "is_credit": True, "desc": "Tu préstamo para construcción vence (Cobras $150)"},
    "CHANCE_REWARD": {"amount": 50, "is_credit": True, "desc": "Premio de Tarjeta Suerte / Arca"},

    # Pagos / Multas
    "INCOME_TAX": {"amount": 200, "is_credit": False, "desc": "Pagó $200 de Impuesto sobre Ingresos al Banco"},
    "LUXURY_TAX": {"amount": 100, "is_credit": False, "desc": "Pagó $100 de Impuesto de Lujo al Banco"},
    "DOCTOR_FEE": {"amount": 50, "is_credit": False, "desc": "Honorarios médicos (Pagas $50)"},
    "HOSPITAL_FEE": {"amount": 100, "is_credit": False, "desc": "Factura del Hospital (Pagas $100)"},
    "SCHOOL_FEES": {"amount": 50, "is_credit": False, "desc": "Pagas colegiatura escolar de $50"},
    "SPEEDING_FINE": {"amount": 15, "is_credit": False, "desc": "Multa por exceso de velocidad (Pagas $15)"},
    "CHANCE_PENALTY": {"amount": 50, "is_credit": False, "desc": "Multa de Tarjeta Suerte / Arca"},
}


class BankActionUseCase:
    """
    Caso de Uso: Operaciones Directas con la Banca, Suerte, Arca Comunal y Reparaciones.
    Soporta todas las cartas oficiales de Monopoly clásico.
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

    def execute(self, dto: BankActionInputDTO) -> BankActionOutputDTO:
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no existe.")

        player = self._player_repo.get_by_id(dto.player_id)
        if not player or player.game_id != dto.game_id:
            raise PlayerNotFoundError(f"Jugador {dto.player_id} no válido.")

        all_players = self._player_repo.list_by_game(game.id)

        # 1. Caso Especial: Reparaciones Generales
        if dto.action_type in ("REPAIRS_CHEST", "REPAIRS_CHANCE"):
            player_props = self._property_repo.list_by_owner(game.id, player.id)
            total_houses = sum(p.houses_count for p in player_props)
            total_hotels = sum(p.hotels_count for p in player_props)

            if dto.action_type == "REPAIRS_CHEST":
                # Arca Comunal: $25 por casa, $100 por hotel
                cost = (total_houses * 25) + (total_hotels * 100)
                card_name = "Reparaciones de Calle (Arca: $25/casa, $100/hotel)"
            else:
                # Suerte: $40 por casa, $115 por hotel
                cost = (total_houses * 40) + (total_hotels * 115)
                card_name = "Reparaciones Generales (Suerte: $40/casa, $115/hotel)"

            if not player.can_afford(cost):
                raise InsufficientFundsError(f"Fondos insuficientes para reparaciones (${cost} requeridos, saldo: ${player.money}).")

            player.deduct_money(cost)
            self._player_repo.save(player)

            desc = f"{player.name} pagó ${cost} por {card_name} ({total_houses} casas, {total_hotels} hoteles)"
            tx = self._transaction_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=TransactionType.TAX_PAYMENT,
                    amount=cost,
                    description=desc,
                    source_player_id=player.id,
                    target_player_id=None,
                )
            )

            if dto.auto_advance_turn and all_players:
                game.advance_turn(len(all_players))
                self._game_repo.save(game)

            return BankActionOutputDTO(
                game_id=game.id,
                player_id=player.id,
                player_name=player.name,
                amount=cost,
                is_credit=False,
                remaining_balance=player.money,
                transaction_id=tx.id if tx.id else 0,
                current_turn=game.current_turn,
                current_player_index=game.current_player_index,
            )

        # 2. Caso Especial: Cumpleaños (Cobrar $10 a cada rival)
        if dto.action_type == "BIRTHDAY":
            rivals = [p for p in all_players if p.id != player.id]
            total_collected = 0
            for r in rivals:
                fee = min(r.money, 10)
                r.deduct_money(fee)
                player.add_money(fee)
                total_collected += fee
                self._player_repo.save(r)

            self._player_repo.save(player)
            desc = f"¡Es el cumpleaños de {player.name}! Cobró $10 a cada rival (Total: ${total_collected})"
            tx = self._transaction_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=TransactionType.PLAYER_TRADE,
                    amount=total_collected,
                    description=desc,
                    source_player_id=None,
                    target_player_id=player.id,
                )
            )

            if dto.auto_advance_turn and all_players:
                game.advance_turn(len(all_players))
                self._game_repo.save(game)

            return BankActionOutputDTO(
                game_id=game.id,
                player_id=player.id,
                player_name=player.name,
                amount=total_collected,
                is_credit=True,
                remaining_balance=player.money,
                transaction_id=tx.id if tx.id else 0,
                current_turn=game.current_turn,
                current_player_index=game.current_player_index,
            )

        # 3. Caso Especial: Fiesta / Beneficencia (Pagar $50 a cada rival)
        if dto.action_type == "CHARITY":
            rivals = [p for p in all_players if p.id != player.id]
            total_cost = 50 * len(rivals)
            if not player.can_afford(total_cost):
                raise InsufficientFundsError(f"Fondos insuficientes (${total_cost} requeridos para pagar $50 a cada jugador).")

            for r in rivals:
                player.deduct_money(50)
                r.add_money(50)
                self._player_repo.save(r)

            self._player_repo.save(player)
            desc = f"{player.name} pagó $50 a cada rival por Noche de Ópera / Beneficencia (Total: ${total_cost})"
            tx = self._transaction_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=TransactionType.PLAYER_TRADE,
                    amount=total_cost,
                    description=desc,
                    source_player_id=player.id,
                    target_player_id=None,
                )
            )

            if dto.auto_advance_turn and all_players:
                game.advance_turn(len(all_players))
                self._game_repo.save(game)

            return BankActionOutputDTO(
                game_id=game.id,
                player_id=player.id,
                player_name=player.name,
                amount=total_cost,
                is_credit=False,
                remaining_balance=player.money,
                transaction_id=tx.id if tx.id else 0,
                current_turn=game.current_turn,
                current_player_index=game.current_player_index,
            )

        # 4. Catálogo estándar de cartas y operaciones
        card_info = CHANCE_COMMUNITY_CATALOG.get(dto.action_type)
        if card_info:
            amount = dto.custom_amount if dto.custom_amount and dto.custom_amount > 0 else card_info["amount"]
            is_credit = card_info["is_credit"]
            desc = dto.description or f"{player.name}: {card_info['desc']}"
        else:
            raise InvalidGameActionError(f"Operación bancaria o carta desconocida: '{dto.action_type}'.")

        # Aplicar débito o crédito
        if is_credit:
            player.add_money(amount)
            src_id = None
            tgt_id = player.id
        else:
            if not player.can_afford(amount):
                raise InsufficientFundsError(f"Fondos insuficientes (${amount} requeridos, saldo: ${player.money}).")
            player.deduct_money(amount)
            src_id = player.id
            tgt_id = None

        self._player_repo.save(player)

        tx = self._transaction_repo.record(
            Transaction(
                id=None,
                game_id=game.id,
                turn_number=game.current_turn,
                transaction_type=TransactionType.BANK_TRANSFER if is_credit else TransactionType.TAX_PAYMENT,
                amount=amount,
                description=desc,
                source_player_id=src_id,
                target_player_id=tgt_id,
            )
        )

        if dto.auto_advance_turn and all_players:
            game.advance_turn(len(all_players))
            self._game_repo.save(game)

        return BankActionOutputDTO(
            game_id=game.id,
            player_id=player.id,
            player_name=player.name,
            amount=amount,
            is_credit=is_credit,
            remaining_balance=player.money,
            transaction_id=tx.id if tx.id else 0,
            current_turn=game.current_turn,
            current_player_index=game.current_player_index,
        )
