from typing import Optional, List
from sqlalchemy.orm import Session
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.models.property import PropertyState
from src.infrastructure.orm.models import PropertyStateModel


class SqlPropertyRepository(PropertyRepositoryProtocol):
    def __init__(self, session: Session):
        self._session = session

    def _to_domain(self, model: PropertyStateModel) -> PropertyState:
        return PropertyState(
            id=model.id,
            game_id=model.game_id,
            tile_id=model.tile_id,
            tile_position=model.tile_position,
            owner_id=model.owner_id,
            houses_count=model.houses_count,
            hotels_count=model.hotels_count,
            is_mortgaged=model.is_mortgaged,
        )

    def get_by_tile(self, game_id: int, tile_id: str) -> Optional[PropertyState]:
        model = (
            self._session.query(PropertyStateModel)
            .filter(PropertyStateModel.game_id == game_id, PropertyStateModel.tile_id == tile_id)
            .first()
        )
        return self._to_domain(model) if model else None

    def list_by_game(self, game_id: int) -> List[PropertyState]:
        models = (
            self._session.query(PropertyStateModel)
            .filter(PropertyStateModel.game_id == game_id)
            .order_by(PropertyStateModel.tile_position.asc())
            .all()
        )
        return [self._to_domain(m) for m in models]

    def list_by_owner(self, game_id: int, owner_id: int) -> List[PropertyState]:
        models = (
            self._session.query(PropertyStateModel)
            .filter(PropertyStateModel.game_id == game_id, PropertyStateModel.owner_id == owner_id)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def save(self, property_state: PropertyState) -> PropertyState:
        if property_state.id is None:
            model = PropertyStateModel(
                game_id=property_state.game_id,
                tile_id=property_state.tile_id,
                tile_position=property_state.tile_position,
                owner_id=property_state.owner_id,
                houses_count=property_state.houses_count,
                hotels_count=property_state.hotels_count,
                is_mortgaged=property_state.is_mortgaged,
            )
            self._session.add(model)
            self._session.commit()
            self._session.refresh(model)
            property_state.id = model.id
            return property_state
        else:
            model = self._session.query(PropertyStateModel).filter(PropertyStateModel.id == property_state.id).first()
            if model:
                model.owner_id = property_state.owner_id
                model.houses_count = property_state.houses_count
                model.hotels_count = property_state.hotels_count
                model.is_mortgaged = property_state.is_mortgaged
                self._session.commit()
            return property_state
