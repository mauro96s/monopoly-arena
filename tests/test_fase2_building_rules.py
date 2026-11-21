import unittest
from src.domain.models.enums import GameVariant, GameStatus
from src.domain.models.game import Game
from src.domain.models.player import Player
from src.domain.models.property import PropertyState
from src.domain.exceptions import InvalidGameActionError
from src.infrastructure.database import Base, SessionLocal, engine
from src.infrastructure.repositories.sql_game_repository import SqlGameRepository
from src.infrastructure.repositories.sql_player_repository import SqlPlayerRepository
from src.infrastructure.repositories.sql_property_repository import SqlPropertyRepository
from src.infrastructure.repositories.sql_transaction_repository import SqlTransactionRepository
from src.application.use_cases.build_house import BuildHouseUseCase
from src.application.use_cases.sell_building import SellBuildingUseCase
from src.application.use_cases.mortgage_property import MortgagePropertyUseCase
from src.application.dtos.action_dtos import (
    BuildHouseInputDTO,
    SellBuildingInputDTO,
    MortgageInputDTO,
)


class TestFase2BuildingRules(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self.game_repo = SqlGameRepository(self.session)
        self.player_repo = SqlPlayerRepository(self.session)
        self.property_repo = SqlPropertyRepository(self.session)
        self.tx_repo = SqlTransactionRepository(self.session)

        self.build_use_case = BuildHouseUseCase(
            self.game_repo, self.player_repo, self.property_repo, self.tx_repo
        )
        self.sell_use_case = SellBuildingUseCase(
            self.game_repo, self.player_repo, self.property_repo, self.tx_repo
        )
        self.mortgage_use_case = MortgagePropertyUseCase(
            self.game_repo, self.player_repo, self.property_repo, self.tx_repo
        )

        # Crear partida de prueba
        self.game = self.game_repo.save(
            Game(
                id=None,
                code="FASE2_TEST",
                variant=GameVariant.CLASSIC,
                status=GameStatus.IN_PROGRESS,
                available_houses=32,
                available_hotels=12,
            )
        )

        # Crear jugador acaudalado
        self.player = self.player_repo.save(
            Player(
                id=None,
                game_id=self.game.id,
                name="Magnate",
                token="Sombrero",
                money=10000,
            )
        )

        # Grupo Marrón: MEDITERRANEAN_AVE (pos 1), BALTIC_AVE (pos 3)
        self.med = self.property_repo.save(
            PropertyState(
                id=None,
                game_id=self.game.id,
                tile_id="MEDITERRANEAN_AVE",
                tile_position=1,
                owner_id=self.player.id,
                houses_count=0,
                hotels_count=0,
                is_mortgaged=False,
            )
        )
        self.baltic = self.property_repo.save(
            PropertyState(
                id=None,
                game_id=self.game.id,
                tile_id="BALTIC_AVE",
                tile_position=3,
                owner_id=self.player.id,
                houses_count=0,
                hotels_count=0,
                is_mortgaged=False,
            )
        )

    def tearDown(self):
        if self.game.id:
            self.game_repo.delete(self.game.id)
        self.session.close()

    def test_even_building_success_and_uneven_rejection(self):
        """Verifica la regla oficial de construcción uniforme."""
        # 1. Construir en Mediterráneo (0 -> 1 casa). Baltica sigue en 0. Válido.
        res1 = self.build_use_case.execute(
            BuildHouseInputDTO(self.game.id, self.player.id, "MEDITERRANEAN_AVE")
        )
        self.assertEqual(res1.new_houses_count, 1)
        self.assertEqual(res1.available_houses, 31)

        # 2. Intentar construir una 2da casa en Mediterráneo teniendo Baltica en 0 -> Debe fallar por no uniforme.
        with self.assertRaises(InvalidGameActionError) as ctx:
            self.build_use_case.execute(
                BuildHouseInputDTO(self.game.id, self.player.id, "MEDITERRANEAN_AVE")
            )
        self.assertIn("Construcción no uniforme", str(ctx.exception))

        # 3. Igualar construyendo en Báltica (0 -> 1 casa). Válido.
        res2 = self.build_use_case.execute(
            BuildHouseInputDTO(self.game.id, self.player.id, "BALTIC_AVE")
        )
        self.assertEqual(res2.new_houses_count, 1)
        self.assertEqual(res2.available_houses, 30)

    def test_building_blocked_if_any_property_in_group_is_mortgaged(self):
        """Verifica que no se pueda construir si alguna propiedad del grupo está hipotecada."""
        self.baltic.is_mortgaged = True
        self.property_repo.save(self.baltic)

        with self.assertRaises(InvalidGameActionError) as ctx:
            self.build_use_case.execute(
                BuildHouseInputDTO(self.game.id, self.player.id, "MEDITERRANEAN_AVE")
            )
        self.assertIn("está hipotecada", str(ctx.exception))

    def test_bank_housing_shortage(self):
        """Verifica que no se pueda construir si el banco se queda sin casas físicas."""
        self.game.available_houses = 0
        self.game_repo.save(self.game)

        with self.assertRaises(InvalidGameActionError) as ctx:
            self.build_use_case.execute(
                BuildHouseInputDTO(self.game.id, self.player.id, "MEDITERRANEAN_AVE")
            )
        self.assertIn("no dispone de casas físicas", str(ctx.exception))

    def test_hotel_construction_returns_4_houses_to_bank(self):
        """Construir un hotel toma 1 hotel y devuelve 4 casas al banco."""
        # Colocar 4 casas en ambas
        self.med.houses_count = 4
        self.property_repo.save(self.med)
        self.baltic.houses_count = 4
        self.property_repo.save(self.baltic)

        self.game.available_houses = 10
        self.game.available_hotels = 5
        self.game_repo.save(self.game)

        res = self.build_use_case.execute(
            BuildHouseInputDTO(self.game.id, self.player.id, "MEDITERRANEAN_AVE")
        )
        self.assertEqual(res.new_hotels_count, 1)
        self.assertEqual(res.new_houses_count, 0)
        # El banco devuelve 4 casas (10 + 4 = 14) y resta 1 hotel (5 - 1 = 4)
        self.assertEqual(res.available_houses, 14)
        self.assertEqual(res.available_hotels, 4)

    def test_even_selling_and_hotel_downgrade(self):
        """Verifica la venta uniforme y degradación de hoteles al 50% del valor."""
        self.med.houses_count = 2
        self.property_repo.save(self.med)
        self.baltic.houses_count = 1
        self.property_repo.save(self.baltic)

        # Intentar vender de Báltica (nivel 1) teniendo Mediterráneo en 2 -> Rechazo no uniforme
        with self.assertRaises(InvalidGameActionError) as ctx:
            self.sell_use_case.execute(
                SellBuildingInputDTO(self.game.id, self.player.id, "BALTIC_AVE")
            )
        self.assertIn("Venta no uniforme", str(ctx.exception))

        # Vender de Mediterráneo (nivel 2 -> 1): 50% de $50 = $25
        initial_money = self.player.money
        res = self.sell_use_case.execute(
            SellBuildingInputDTO(self.game.id, self.player.id, "MEDITERRANEAN_AVE")
        )
        self.assertEqual(res.new_houses_count, 1)
        self.assertEqual(res.refund_amount, 25)
        self.assertEqual(res.remaining_balance, initial_money + 25)

    def test_hotel_downgrade_with_houses_available_vs_shortage(self):
        """Verifica degradación de hotel a 4 casas, y escasez con liquidación uniforme."""
        # 1. Ambos con Hotel
        self.med.hotels_count = 1
        self.med.houses_count = 0
        self.property_repo.save(self.med)
        self.baltic.hotels_count = 1
        self.baltic.houses_count = 0
        self.property_repo.save(self.baltic)

        # Banco tiene 4 casas disponibles -> puede degradar normalmente a 4 casas
        self.game.available_houses = 4
        self.game.available_hotels = 2
        self.game_repo.save(self.game)

        res = self.sell_use_case.execute(
            SellBuildingInputDTO(self.game.id, self.player.id, "MEDITERRANEAN_AVE")
        )
        self.assertEqual(res.new_hotels_count, 0)
        self.assertEqual(res.new_houses_count, 4)
        # Se tomaron 4 casas (4 - 4 = 0) y se devolvió 1 hotel (2 + 1 = 3)
        self.assertEqual(res.available_houses, 0)
        self.assertEqual(res.available_hotels, 3)

        # 2. Ahora Báltica tiene hotel pero el banco tiene 0 casas (< 4 disponibles)
        # Intentar degradar individualmente -> Rechazo por escasez
        with self.assertRaises(InvalidGameActionError) as ctx:
            self.sell_use_case.execute(
                SellBuildingInputDTO(self.game.id, self.player.id, "BALTIC_AVE", sell_entire_group=False)
            )
        self.assertIn("Escasez de casas en el Banco", str(ctx.exception))

        # Con sell_entire_group=True, se liquida el hotel a 0
        res_group = self.sell_use_case.execute(
            SellBuildingInputDTO(self.game.id, self.player.id, "BALTIC_AVE", sell_entire_group=True)
        )
        self.assertEqual(res_group.new_hotels_count, 0)
        self.assertEqual(res_group.new_houses_count, 0)
        # 5 niveles * $25 = $125
        self.assertEqual(res_group.refund_amount, 125)

    def test_mortgage_blocked_if_any_property_in_group_has_buildings(self):
        """Verifica que no se pueda hipotecar una calle si alguna propiedad del grupo tiene casas."""
        self.med.houses_count = 1
        self.property_repo.save(self.med)
        self.baltic.houses_count = 0
        self.property_repo.save(self.baltic)

        # Intentar hipotecar Báltica (que tiene 0 casas) debe fallar porque Mediterráneo tiene 1 casa
        with self.assertRaises(InvalidGameActionError) as ctx:
            self.mortgage_use_case.execute(
                MortgageInputDTO(self.game.id, self.player.id, "BALTIC_AVE")
            )
        self.assertIn("tiene edificios construidos", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
