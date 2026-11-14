import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.database import Base
from src.infrastructure.repositories import (
    SqlGameRepository,
    SqlPlayerRepository,
    SqlPropertyRepository,
    SqlTransactionRepository,
)
from src.application.use_cases.buy_property import BuyPropertyUseCase
from src.application.dtos.action_dtos import BuyPropertyInputDTO
from src.domain.models import Game, Player
from src.domain.models.enums import GameVariant, GameStatus
from src.domain.exceptions import InsufficientFundsError, PropertyAlreadyOwnedError


class TestBuyPropertyUseCase(unittest.TestCase):
    def setUp(self):
        # Base de datos en memoria para pruebas desacopladas
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Repositorios
        self.game_repo = SqlGameRepository(self.session)
        self.player_repo = SqlPlayerRepository(self.session)
        self.property_repo = SqlPropertyRepository(self.session)
        self.tx_repo = SqlTransactionRepository(self.session)

        # Caso de Uso
        self.use_case = BuyPropertyUseCase(
            game_repo=self.game_repo,
            player_repo=self.player_repo,
            property_repo=self.property_repo,
            transaction_repo=self.tx_repo,
        )

        # Sembrar partida y jugador
        self.game = self.game_repo.save(
            Game(id=None, code="TEST101", variant=GameVariant.CLASSIC, status=GameStatus.IN_PROGRESS)
        )
        self.player = self.player_repo.save(
            Player(id=None, game_id=self.game.id, name="Test Player", token="Car", money=1500)
        )

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_successful_property_purchase(self):
        # Comprar Boardwalk (precio 400 en Classic)
        dto = BuyPropertyInputDTO(
            game_id=self.game.id,
            player_id=self.player.id,
            tile_id="BOARDWALK",
        )
        result = self.use_case.execute(dto)

        self.assertEqual(result.price_paid, 400)
        self.assertEqual(result.remaining_balance, 1100)
        self.assertEqual(result.tile_name, "Paseo Tablado (Boardwalk)")

        # Verificar persistencia en base de datos
        prop = self.property_repo.get_by_tile(self.game.id, "BOARDWALK")
        self.assertIsNotNone(prop)
        self.assertEqual(prop.owner_id, self.player.id)

    def test_insufficient_funds_fails(self):
        # Dejar al jugador con poco dinero
        self.player.money = 50
        self.player_repo.save(self.player)

        dto = BuyPropertyInputDTO(
            game_id=self.game.id,
            player_id=self.player.id,
            tile_id="BOARDWALK",
        )
        with self.assertRaises(InsufficientFundsError):
            self.use_case.execute(dto)

    def test_property_already_owned_fails(self):
        dto = BuyPropertyInputDTO(
            game_id=self.game.id,
            player_id=self.player.id,
            tile_id="MEDITERRANEAN_AVE",
        )
        self.use_case.execute(dto)

        # Intentar comprarla de nuevo
        with self.assertRaises(PropertyAlreadyOwnedError):
            self.use_case.execute(dto)


if __name__ == "__main__":
    unittest.main()
