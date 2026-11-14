import unittest
import uuid
from src.infrastructure.database import Base, SessionLocal, engine
from src.infrastructure.repositories import (
    SqlGameRepository,
    SqlPlayerRepository,
    SqlPropertyRepository,
    SqlTransactionRepository,
)
from src.application.use_cases import (
    BuyPropertyUseCase,
    PayRentUseCase,
    BuildHouseUseCase,
    JailActionUseCase,
    BankActionUseCase,
    FinishGameUseCase,
)
from src.application.dtos.action_dtos import (
    BuyPropertyInputDTO,
    PayRentInputDTO,
    BuildHouseInputDTO,
    JailActionInputDTO,
    BankActionInputDTO,
)
from src.domain.models import Game, Player
from src.domain.models.enums import GameVariant, GameStatus
from src.domain.exceptions import InvalidGameActionError, InsufficientFundsError


class TestTacticalMonopolyFeatures(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self.game_repo = SqlGameRepository(self.session)
        self.player_repo = SqlPlayerRepository(self.session)
        self.property_repo = SqlPropertyRepository(self.session)
        self.tx_repo = SqlTransactionRepository(self.session)

        # Crear partida con código único para evitar colisiones
        unique_code = f"TAC-{uuid.uuid4().hex[:6].upper()}"
        self.game = self.game_repo.save(
            Game(id=None, code=unique_code, variant=GameVariant.CLASSIC, status=GameStatus.IN_PROGRESS)
        )

        # Crear 3 jugadores
        self.p1 = self.player_repo.save(Player(id=None, game_id=self.game.id, name="Ana", token="Sombrero", money=1500))
        self.p2 = self.player_repo.save(Player(id=None, game_id=self.game.id, name="Beto", token="Auto", money=1500))
        self.p3 = self.player_repo.save(Player(id=None, game_id=self.game.id, name="Carlos", token="Perro", money=1500))

        # Instanciar Casos de Uso
        self.buy_uc = BuyPropertyUseCase(self.game_repo, self.player_repo, self.property_repo, self.tx_repo)
        self.rent_uc = PayRentUseCase(self.game_repo, self.player_repo, self.property_repo, self.tx_repo)
        self.build_uc = BuildHouseUseCase(self.game_repo, self.player_repo, self.property_repo, self.tx_repo)
        self.jail_uc = JailActionUseCase(self.game_repo, self.player_repo, self.tx_repo)
        self.bank_uc = BankActionUseCase(self.game_repo, self.player_repo, self.property_repo, self.tx_repo)
        self.finish_uc = FinishGameUseCase(self.game_repo, self.player_repo, self.property_repo, self.tx_repo)

    def tearDown(self):
        self.session.close()

    def test_auto_advance_turn_on_buy(self):
        # Ana compra Boardwalk
        self.assertEqual(self.game.current_player_index, 0)
        res = self.buy_uc.execute(BuyPropertyInputDTO(
            game_id=self.game.id, player_id=self.p1.id, tile_id="BOARDWALK", auto_advance_turn=True
        ))
        # El turno avanza automáticamente a Beto (índice 1)
        self.assertEqual(res.current_player_index, 1)

    def test_monopoly_double_rent_rule(self):
        # Beto compra el grupo Marrón completo (MEDITERRANEAN_AVE y BALTIC_AVE)
        self.buy_uc.execute(BuyPropertyInputDTO(game_id=self.game.id, player_id=self.p2.id, tile_id="MEDITERRANEAN_AVE", auto_advance_turn=False))
        self.buy_uc.execute(BuyPropertyInputDTO(game_id=self.game.id, player_id=self.p2.id, tile_id="BALTIC_AVE", auto_advance_turn=False))

        # Ana cae en Mediterráneo. Renta base = $2. Como Beto tiene el monopolio completo marrón, la renta se DUPLICA a $4!
        rent_res = self.rent_uc.execute(PayRentInputDTO(
            game_id=self.game.id, payer_player_id=self.p1.id, tile_id="MEDITERRANEAN_AVE", auto_advance_turn=False
        ))
        self.assertTrue(rent_res.is_monopoly_doubled)
        self.assertEqual(rent_res.rent_amount, 4)
        self.assertEqual(rent_res.owner_id, self.p2.id)

    def test_build_house_requires_monopoly(self):
        # Carlos compra sólo Park Place (sin Boardwalk)
        self.buy_uc.execute(BuyPropertyInputDTO(game_id=self.game.id, player_id=self.p3.id, tile_id="PARK_PLACE", auto_advance_turn=False))

        # Intenta construir sin tener el monopolio azul oscuro -> debe fallar
        with self.assertRaises(InvalidGameActionError):
            self.build_uc.execute(BuildHouseInputDTO(game_id=self.game.id, player_id=self.p3.id, tile_id="PARK_PLACE"))

    def test_jail_pay_fine_action(self):
        # Enviar a Ana a prisión
        jail_res = self.jail_uc.execute(JailActionInputDTO(game_id=self.game.id, player_id=self.p1.id, action="GO_TO_JAIL", auto_advance_turn=False))
        self.assertTrue(jail_res.in_jail)
        self.assertEqual(jail_res.jail_turns, 1)

        # Ana paga la fianza de $50 y queda libre
        free_res = self.jail_uc.execute(JailActionInputDTO(game_id=self.game.id, player_id=self.p1.id, action="PAY_FINE", auto_advance_turn=False))
        self.assertFalse(free_res.in_jail)
        self.assertEqual(free_res.amount_paid, 50)

    def test_finish_game_calculates_podium(self):
        # Beto tiene 1500 + 120 (Mediterraneo y Baltica) = 1620
        # Ana tiene 1500 - 50 = 1450
        # Finalizar juego
        podium = self.finish_uc.execute(self.game.id)
        self.assertEqual(len(podium.rankings), 3)
        self.assertGreaterEqual(podium.rankings[0].net_worth, podium.rankings[1].net_worth)
        self.assertEqual(self.game_repo.get_by_id(self.game.id).status, GameStatus.FINISHED)


if __name__ == "__main__":
    unittest.main()
