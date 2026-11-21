from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.infrastructure.database import Base
from src.domain.models.enums import GameStatus, GameVariant, TransactionType


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GameModel(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(16), unique=True, index=True, nullable=False)
    variant = Column(SQLEnum(GameVariant), default=GameVariant.CLASSIC, nullable=False)
    theme_id = Column(String(32), default="classic", nullable=False)
    status = Column(SQLEnum(GameStatus), default=GameStatus.WAITING, nullable=False)
    current_turn = Column(Integer, default=1, nullable=False)
    current_player_index = Column(Integer, default=0, nullable=False)
    has_rolled_dice = Column(Boolean, default=False, nullable=False)
    consecutive_doubles = Column(Integer, default=0, nullable=False)
    available_houses = Column(Integer, default=32, nullable=False)
    available_hotels = Column(Integer, default=12, nullable=False)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

    # Relaciones
    players = relationship("PlayerModel", back_populates="game", cascade="all, delete-orphan")
    properties = relationship("PropertyStateModel", back_populates="game", cascade="all, delete-orphan")
    transactions = relationship("TransactionModel", back_populates="game", cascade="all, delete-orphan")


class PlayerModel(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(64), nullable=False)
    token = Column(String(32), nullable=False)  # ej: "Sombrero", "Coche", "Perro"
    money = Column(Integer, default=1500, nullable=False)
    position = Column(Integer, default=0, nullable=False)
    is_bankrupt = Column(Boolean, default=False, nullable=False)
    in_jail = Column(Boolean, default=False, nullable=False)
    jail_turns = Column(Integer, default=0, nullable=False)
    out_of_jail_cards = Column(Integer, default=0, nullable=False)

    # Relaciones
    game = relationship("GameModel", back_populates="players")
    owned_properties = relationship("PropertyStateModel", back_populates="owner")


class PropertyStateModel(Base):
    __tablename__ = "property_states"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    tile_id = Column(String(64), nullable=False, index=True)
    tile_position = Column(Integer, nullable=False)
    owner_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True, index=True)
    houses_count = Column(Integer, default=0, nullable=False)
    hotels_count = Column(Integer, default=0, nullable=False)
    is_mortgaged = Column(Boolean, default=False, nullable=False)

    # Relaciones
    game = relationship("GameModel", back_populates="properties")
    owner = relationship("PlayerModel", back_populates="owned_properties")


class TransactionModel(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_number = Column(Integer, nullable=False)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    amount = Column(Integer, nullable=False)
    description = Column(String(255), nullable=False)
    source_player_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    target_player_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    tile_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

    # Relaciones
    game = relationship("GameModel", back_populates="transactions")
