from typing import Protocol, List
from src.domain.models.transaction import Transaction


class TransactionRepositoryProtocol(Protocol):
    def record(self, transaction: Transaction) -> Transaction:
        """Registra un movimiento en el ledger de auditoría de la partida."""
        ...

    def list_by_game(self, game_id: int, limit: int = 50) -> List[Transaction]:
        """Obtiene el historial de transacciones para el log de partida."""
        ...
