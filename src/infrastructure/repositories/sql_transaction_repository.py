from typing import List
from sqlalchemy.orm import Session
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.models.transaction import Transaction
from src.infrastructure.orm.models import TransactionModel


class SqlTransactionRepository(TransactionRepositoryProtocol):
    def __init__(self, session: Session):
        self._session = session

    def _to_domain(self, model: TransactionModel) -> Transaction:
        return Transaction(
            id=model.id,
            game_id=model.game_id,
            turn_number=model.turn_number,
            transaction_type=model.transaction_type,
            amount=model.amount,
            description=model.description,
            source_player_id=model.source_player_id,
            target_player_id=model.target_player_id,
            tile_id=model.tile_id,
            created_at=model.created_at,
        )

    def record(self, transaction: Transaction) -> Transaction:
        model = TransactionModel(
            game_id=transaction.game_id,
            turn_number=transaction.turn_number,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            description=transaction.description,
            source_player_id=transaction.source_player_id,
            target_player_id=transaction.target_player_id,
            tile_id=transaction.tile_id,
            created_at=transaction.created_at,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        transaction.id = model.id
        return transaction

    def list_by_game(self, game_id: int, limit: int = 50) -> List[Transaction]:
        models = (
            self._session.query(TransactionModel)
            .filter(TransactionModel.game_id == game_id)
            .order_by(TransactionModel.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]
