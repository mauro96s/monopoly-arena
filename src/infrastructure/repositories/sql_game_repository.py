from typing import Optional
from sqlalchemy.orm import Session
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.models.game import Game
from src.infrastructure.orm.models import GameModel


class SqlGameRepository(GameRepositoryProtocol):
    def __init__(self, session: Session):
        self._session = session

    def _to_domain(self, model: GameModel) -> Game:
        return Game(
            id=model.id,
            code=model.code,
            variant=model.variant,
            status=model.status,
            current_turn=model.current_turn,
            current_player_index=model.current_player_index,
            created_at=model.created_at,
        )

    def get_by_id(self, game_id: int) -> Optional[Game]:
        model = self._session.query(GameModel).filter(GameModel.id == game_id).first()
        return self._to_domain(model) if model else None

    def get_by_code(self, code: str) -> Optional[Game]:
        model = self._session.query(GameModel).filter(GameModel.code == code).first()
        return self._to_domain(model) if model else None

    def list_all(self, limit: int = 20) -> list[Game]:
        models = self._session.query(GameModel).order_by(GameModel.created_at.desc()).limit(limit).all()
        return [self._to_domain(m) for m in models]

    def save(self, game: Game) -> Game:
        if game.id is None:
            model = GameModel(
                code=game.code,
                variant=game.variant,
                status=game.status,
                current_turn=game.current_turn,
                current_player_index=game.current_player_index,
                created_at=game.created_at,
            )
            self._session.add(model)
            self._session.commit()
            self._session.refresh(model)
            game.id = model.id
            return game
        else:
            model = self._session.query(GameModel).filter(GameModel.id == game.id).first()
            if model:
                model.variant = game.variant
                model.status = game.status
                model.current_turn = game.current_turn
                model.current_player_index = game.current_player_index
                self._session.commit()
            return game
