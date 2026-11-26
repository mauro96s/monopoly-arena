import json
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.models.game import Game
from src.domain.rules.ruleset_config import RulesetConfig
from src.infrastructure.orm.models import GameModel


class SqlGameRepository(GameRepositoryProtocol):
    def __init__(self, session: Session):
        self._session = session
        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """Asegura de forma no destructiva que las columnas nuevas existan en bases de datos SQLite existentes."""
        for col_def in [
            "theme_id VARCHAR(32) DEFAULT 'classic'",
            "available_houses INTEGER DEFAULT 32",
            "available_hotels INTEGER DEFAULT 12",
            "ruleset_config VARCHAR(512) DEFAULT '{}'",
            "free_parking_pool INTEGER DEFAULT 0",
            "pending_auction_tiles VARCHAR(512) DEFAULT '[]'",
            "chance_deck_order VARCHAR(1024) DEFAULT '[]'",
            "community_chest_deck_order VARCHAR(1024) DEFAULT '[]'",
        ]:
            try:
                self._session.execute(text(f"ALTER TABLE games ADD COLUMN {col_def}"))
                self._session.commit()
            except Exception:
                self._session.rollback()

    def _to_domain(self, model: GameModel) -> Game:
        houses = getattr(model, "available_houses", 32)
        hotels = getattr(model, "available_hotels", 12)
        pool = getattr(model, "free_parking_pool", 0)

        # Parsear ruleset_config
        raw_ruleset = getattr(model, "ruleset_config", "{}")
        try:
            ruleset_dict = json.loads(raw_ruleset) if isinstance(raw_ruleset, str) else (raw_ruleset or {})
        except Exception:
            ruleset_dict = {}
        ruleset = RulesetConfig.from_dict(ruleset_dict)

        # Parsear pending_auction_tiles
        raw_auctions = getattr(model, "pending_auction_tiles", "[]")
        try:
            auctions_list = json.loads(raw_auctions) if isinstance(raw_auctions, str) else (raw_auctions or [])
        except Exception:
            auctions_list = []

        # Parsear chance_deck_order
        raw_chance = getattr(model, "chance_deck_order", "[]")
        try:
            chance_list = json.loads(raw_chance) if isinstance(raw_chance, str) else (raw_chance or [])
        except Exception:
            chance_list = []

        # Parsear community_chest_deck_order
        raw_community = getattr(model, "community_chest_deck_order", "[]")
        try:
            community_list = json.loads(raw_community) if isinstance(raw_community, str) else (raw_community or [])
        except Exception:
            community_list = []

        return Game(
            id=model.id,
            code=model.code,
            variant=model.variant,
            theme_id=getattr(model, "theme_id", "classic") or "classic",
            status=model.status,
            current_turn=model.current_turn,
            current_player_index=model.current_player_index,
            created_at=model.created_at,
            has_rolled_dice=bool(getattr(model, "has_rolled_dice", False)),
            consecutive_doubles=int(getattr(model, "consecutive_doubles", 0)),
            available_houses=32 if houses is None else int(houses),
            available_hotels=12 if hotels is None else int(hotels),
            ruleset_config=ruleset,
            free_parking_pool=0 if pool is None else int(pool),
            pending_auction_tiles=auctions_list,
            chance_deck_order=chance_list,
            community_chest_deck_order=community_list,
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
        ruleset_json = json.dumps(game.get_ruleset().to_dict())
        auctions_json = json.dumps(game.pending_auction_tiles)
        chance_json = json.dumps(game.chance_deck_order)
        community_json = json.dumps(game.community_chest_deck_order)

        if game.id is None:
            model = GameModel(
                code=game.code,
                variant=game.variant,
                theme_id=game.theme_id,
                status=game.status,
                current_turn=game.current_turn,
                current_player_index=game.current_player_index,
                created_at=game.created_at,
                has_rolled_dice=game.has_rolled_dice,
                consecutive_doubles=game.consecutive_doubles,
                available_houses=game.available_houses,
                available_hotels=game.available_hotels,
                ruleset_config=ruleset_json,
                free_parking_pool=game.free_parking_pool,
                pending_auction_tiles=auctions_json,
                chance_deck_order=chance_json,
                community_chest_deck_order=community_json,
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
                model.theme_id = game.theme_id
                model.status = game.status
                model.current_turn = game.current_turn
                model.current_player_index = game.current_player_index
                model.has_rolled_dice = game.has_rolled_dice
                model.consecutive_doubles = game.consecutive_doubles
                model.available_houses = game.available_houses
                model.available_hotels = game.available_hotels
                model.ruleset_config = ruleset_json
                model.free_parking_pool = game.free_parking_pool
                model.pending_auction_tiles = auctions_json
                model.chance_deck_order = chance_json
                model.community_chest_deck_order = community_json
                self._session.commit()
            return game

    def delete(self, game_id: int) -> bool:
        model = self._session.query(GameModel).filter(GameModel.id == game_id).first()
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True

    def delete_bulk(self, game_ids: list[int]) -> int:
        if not game_ids:
            return 0
        models = self._session.query(GameModel).filter(GameModel.id.in_(game_ids)).all()
        count = len(models)
        for m in models:
            self._session.delete(m)
        self._session.commit()
        return count

    def delete_all(self) -> int:
        models = self._session.query(GameModel).all()
        count = len(models)
        for m in models:
            self._session.delete(m)
        self._session.commit()
        return count
