from typing import Optional, List
from sqlalchemy.orm import Session
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.models.player import Player
from src.infrastructure.orm.models import PlayerModel


class SqlPlayerRepository(PlayerRepositoryProtocol):
    def __init__(self, session: Session):
        self._session = session

    def _to_domain(self, model: PlayerModel) -> Player:
        return Player(
            id=model.id,
            game_id=model.game_id,
            name=model.name,
            token=model.token,
            money=model.money,
            position=model.position,
            is_bankrupt=model.is_bankrupt,
            in_jail=model.in_jail,
            jail_turns=model.jail_turns,
        )

    def get_by_id(self, player_id: int) -> Optional[Player]:
        model = self._session.query(PlayerModel).filter(PlayerModel.id == player_id).first()
        return self._to_domain(model) if model else None

    def list_by_game(self, game_id: int) -> List[Player]:
        models = self._session.query(PlayerModel).filter(PlayerModel.game_id == game_id).order_by(PlayerModel.id.asc()).all()
        return [self._to_domain(m) for m in models]

    def save(self, player: Player) -> Player:
        if player.id is None:
            model = PlayerModel(
                game_id=player.game_id,
                name=player.name,
                token=player.token,
                money=player.money,
                position=player.position,
                is_bankrupt=player.is_bankrupt,
                in_jail=player.in_jail,
                jail_turns=player.jail_turns,
            )
            self._session.add(model)
            self._session.commit()
            self._session.refresh(model)
            player.id = model.id
            return player
        else:
            model = self._session.query(PlayerModel).filter(PlayerModel.id == player.id).first()
            if model:
                model.name = player.name
                model.token = player.token
                model.money = player.money
                model.position = player.position
                model.is_bankrupt = player.is_bankrupt
                model.in_jail = player.in_jail
                model.jail_turns = player.jail_turns
                self._session.commit()
            return player
