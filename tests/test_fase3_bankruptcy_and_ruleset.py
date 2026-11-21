import unittest
from src.domain.models.enums import GameVariant, GameStatus
from src.domain.models.game import Game
from src.domain.models.player import Player
from src.domain.models.property import PropertyState
from src.domain.rules.ruleset_config import RulesetConfig
from src.domain.rules.rule_hooks import RulesetEngine, ClassicRulesHook, FreeParkingJackpotHook, DoubleSalaryExactGoHook
from src.infrastructure.database import Base, SessionLocal, engine
from src.infrastructure.repositories.sql_game_repository import SqlGameRepository
from src.infrastructure.repositories.sql_player_repository import SqlPlayerRepository
from src.infrastructure.repositories.sql_property_repository import SqlPropertyRepository
from src.infrastructure.repositories.sql_transaction_repository import SqlTransactionRepository
from src.application.use_cases.declare_bankruptcy import DeclareBankruptcyUseCase
from src.application.use_cases.mortgage_property import MortgagePropertyUseCase
from src.application.use_cases.roll_dice import RollDiceUseCase
from src.application.use_cases.pay_rent import PayRentUseCase
from src.application.use_cases.bank_action import BankActionUseCase
from src.application.dtos.action_dtos import (
    DeclareBankruptcyInputDTO,
    MortgageInputDTO,
    RollDiceInputDTO,
    PayRentInputDTO,
    BankActionInputDTO,
)


class TestFase3BankruptcyAndRuleset(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self.game_repo = SqlGameRepository(self.session)
        self.player_repo = SqlPlayerRepository(self.session)
        self.property_repo = SqlPropertyRepository(self.session)
        self.tx_repo = SqlTransactionRepository(self.session)

        self.bankruptcy_uc = DeclareBankruptcyUseCase(
            self.game_repo, self.player_repo, self.property_repo, self.tx_repo
        )
        self.mortgage_uc = MortgagePropertyUseCase(
            self.game_repo, self.player_repo, self.property_repo, self.tx_repo
        )
        self.roll_dice_uc = RollDiceUseCase(
            self.game_repo, self.player_repo, self.property_repo, self.tx_repo
        )
        self.pay_rent_uc = PayRentUseCase(
            self.game_repo, self.player_repo, self.property_repo, self.tx_repo
        )
        self.bank_action_uc = BankActionUseCase(
            self.game_repo, self.player_repo, self.property_repo, self.tx_repo
        )

        self.game = self.game_repo.save(
            Game(
                id=None,
                code="FASE3_TEST",
                variant=GameVariant.CLASSIC,
                status=GameStatus.IN_PROGRESS,
                available_houses=32,
                available_hotels=12,
                ruleset_config=RulesetConfig(),
            )
        )

        self.player1 = self.player_repo.save(
            Player(
                id=None,
                game_id=self.game.id,
                name="Deudor",
                token="Sombrero",
                money=100,
                position=1,
            )
        )
        self.player2 = self.player_repo.save(
            Player(
                id=None,
                game_id=self.game.id,
                name="Acreedor",
                token="Dedal",
                money=2000,
                position=5,
            )
        )

    def tearDown(self):
        if self.game.id:
            self.game_repo.delete(self.game.id)
        self.session.close()

    def test_bankruptcy_to_creditor_with_building_liquidation(self):
        """Liquidación forzosa previa de casas/hoteles al 50% y transferencia de bienes al acreedor."""
        # Deudor es dueño de MEDITERRANEAN_AVE con 2 casas (costo 50 c/u)
        med = self.property_repo.save(
            PropertyState(
                id=None,
                game_id=self.game.id,
                tile_id="MEDITERRANEAN_AVE",
                tile_position=1,
                owner_id=self.player1.id,
                houses_count=2,
                hotels_count=0,
                is_mortgaged=False,
            )
        )
        self.game.available_houses = 30
        self.game_repo.save(self.game)

        # Declarar bancarrota frente al jugador 2
        dto = DeclareBankruptcyInputDTO(
            game_id=self.game.id,
            bankrupt_player_id=self.player1.id,
            creditor_player_id=self.player2.id,
            unmortgage_transferred_properties=False,
        )
        out = self.bankruptcy_uc.execute(dto)

        # Casas liquidadas: 2 casas a 50$/casa = $50 al 50% = $25 c/u -> $50 total
        self.assertEqual(out.liquidated_houses, 2)
        self.assertEqual(out.properties_transferred, ["MEDITERRANEAN_AVE"])

        # Verificar inventario del banco restaurado
        game_after = self.game_repo.get_by_id(self.game.id)
        self.assertEqual(game_after.available_houses, 32)

        # Verificar propiedad transferida a player2 sin casas
        med_after = self.property_repo.get_by_tile(self.game.id, "MEDITERRANEAN_AVE")
        self.assertEqual(med_after.owner_id, self.player2.id)
        self.assertEqual(med_after.houses_count, 0)

        # Verificar estados de jugadores: player1 quebrado con 0$, player2 recibió 100$ inicial + 50$ de liquidación
        p1 = self.player_repo.get_by_id(self.player1.id)
        p2 = self.player_repo.get_by_id(self.player2.id)
        self.assertTrue(p1.is_bankrupt)
        self.assertEqual(p1.money, 0)
        self.assertEqual(p2.money, 2000 + 100 + 50)

        # Como solo queda 1 jugador activo, la partida debe finalizar con p2 ganador
        self.assertTrue(out.is_game_finished)
        self.assertEqual(out.winner_player_id, self.player2.id)
        self.assertEqual(game_after.status, GameStatus.FINISHED)

    def test_mortgaged_property_transfer_and_subsequent_unmortgage(self):
        """Acreedor recibe propiedad hipotecada, paga 10% inmediato y al deshipotecar luego no paga 10% otra vez."""
        # Deudor es dueño de BALTIC_AVE (precio 60, hipoteca 30) hipotecada
        baltic = self.property_repo.save(
            PropertyState(
                id=None,
                game_id=self.game.id,
                tile_id="BALTIC_AVE",
                tile_position=3,
                owner_id=self.player1.id,
                houses_count=0,
                hotels_count=0,
                is_mortgaged=True,
                transfer_interest_paid=False,
            )
        )

        # Bancarrota: acreedor decide conservarla hipotecada por ahora
        dto = DeclareBankruptcyInputDTO(
            game_id=self.game.id,
            bankrupt_player_id=self.player1.id,
            creditor_player_id=self.player2.id,
            unmortgage_transferred_properties=False,
        )
        self.bankruptcy_uc.execute(dto)

        # Acreedor pagó 10% de interés sobre 30$ = 3$ al banco
        # Dinero acreedor: 2000 inicial + 100 (efectivo p1) - 3 (interés al banco) = 2097
        p2 = self.player_repo.get_by_id(self.player2.id)
        self.assertEqual(p2.money, 2097)

        baltic_after = self.property_repo.get_by_tile(self.game.id, "BALTIC_AVE")
        self.assertEqual(baltic_after.owner_id, self.player2.id)
        self.assertTrue(baltic_after.is_mortgaged)
        self.assertTrue(baltic_after.transfer_interest_paid)

        # Ahora el acreedor la deshipoteca más adelante vía MortgagePropertyUseCase
        # El costo normal sería 30 + 10% = 33. Con transfer_interest_paid=True debe costar solo 30!
        res_unmortgage = self.mortgage_uc.execute(
            MortgageInputDTO(
                game_id=self.game.id,
                player_id=self.player2.id,
                tile_id="BALTIC_AVE",
            )
        )
        self.assertFalse(res_unmortgage.is_mortgaged)
        p2_final = self.player_repo.get_by_id(self.player2.id)
        # 2097 - 30 = 2067 (sin el 10% duplicado)
        self.assertEqual(p2_final.money, 2067)

        # El flag transfer_interest_paid debe resetearse a False
        baltic_final = self.property_repo.get_by_tile(self.game.id, "BALTIC_AVE")
        self.assertFalse(baltic_final.transfer_interest_paid)

    def test_mortgaged_property_immediate_unmortgage_on_transfer(self):
        """Acreedor elige deshipotecar de inmediato en la bancarrota."""
        baltic = self.property_repo.save(
            PropertyState(
                id=None,
                game_id=self.game.id,
                tile_id="BALTIC_AVE",
                tile_position=3,
                owner_id=self.player1.id,
                houses_count=0,
                hotels_count=0,
                is_mortgaged=True,
                transfer_interest_paid=False,
            )
        )

        dto = DeclareBankruptcyInputDTO(
            game_id=self.game.id,
            bankrupt_player_id=self.player1.id,
            creditor_player_id=self.player2.id,
            unmortgage_transferred_properties=True,
        )
        out = self.bankruptcy_uc.execute(dto)

        # Debe pagar 10% (3$) + hipoteca base (30$) = 33$
        # Dinero: 2000 + 100 - 33 = 2067
        p2 = self.player_repo.get_by_id(self.player2.id)
        self.assertEqual(p2.money, 2067)

        baltic_after = self.property_repo.get_by_tile(self.game.id, "BALTIC_AVE")
        self.assertFalse(baltic_after.is_mortgaged)
        self.assertEqual(baltic_after.owner_id, self.player2.id)

    def test_bankruptcy_to_bank_enqueues_auctions(self):
        """Bancarrota contra el banco: propiedades se deshipotecan, quedan sin dueño y van a pending_auction_tiles."""
        prop = self.property_repo.save(
            PropertyState(
                id=None,
                game_id=self.game.id,
                tile_id="READING_RR",
                tile_position=5,
                owner_id=self.player1.id,
                houses_count=0,
                hotels_count=0,
                is_mortgaged=True,
            )
        )

        dto = DeclareBankruptcyInputDTO(
            game_id=self.game.id,
            bankrupt_player_id=self.player1.id,
            creditor_player_id=None,
        )
        out = self.bankruptcy_uc.execute(dto)

        self.assertEqual(out.released_to_auction_tiles, ["READING_RR"])
        prop_after = self.property_repo.get_by_tile(self.game.id, "READING_RR")
        self.assertIsNone(prop_after.owner_id)
        self.assertFalse(prop_after.is_mortgaged)

        game_after = self.game_repo.get_by_id(self.game.id)
        self.assertIn("READING_RR", game_after.pending_auction_tiles)

    def test_ruleset_free_parking_jackpot(self):
        """Ruleset hook: impuestos alimentan el pozo de Free Parking y se cobran en la casilla 20."""
        self.game.ruleset_config = RulesetConfig(free_parking_jackpot=True)
        self.game.free_parking_pool = 150
        self.game_repo.save(self.game)

        # Jugador paga impuesto de $100 al banco con BankActionUseCase
        self.bank_action_uc.execute(
            BankActionInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                action_type="PLAYER_PAYS_BANK",
                custom_amount=100,
                description="Impuesto sobre el lujo",
                auto_advance_turn=False,
            )
        )

        game_after_tax = self.game_repo.get_by_id(self.game.id)
        self.assertEqual(game_after_tax.free_parking_pool, 250)

        # Ahora el jugador 1 cae en la casilla 20 (Free Parking)
        p1 = self.player_repo.get_by_id(self.player1.id)
        p1.position = 18
        self.player_repo.save(p1)

        # Tirar dados 1 y 1 para caer en casilla 20
        res_roll = self.roll_dice_uc.execute(
            RollDiceInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                dice_1=1,
                dice_2=1,
            )
        )

        self.assertEqual(res_roll.new_position, 20)
        p1_after = self.player_repo.get_by_id(self.player1.id)
        # Recibe los 250 del pozo: 0 (tras pagar $100) + 250 = 250
        self.assertEqual(p1_after.money, 250)

        game_after_jackpot = self.game_repo.get_by_id(self.game.id)
        self.assertEqual(game_after_jackpot.free_parking_pool, 0)

    def test_ruleset_double_salary_on_exact_go(self):
        """Ruleset hook: caer exacto en GO otorga salario doble ($400)."""
        self.game.ruleset_config = RulesetConfig(double_salary_on_exact_go=True, go_salary=200)
        self.game_repo.save(self.game)

        self.player1.position = 38
        self.player1.money = 500
        self.player_repo.save(self.player1)

        # Tirar 1 y 1 -> nueva posición 0 (GO)
        res_roll = self.roll_dice_uc.execute(
            RollDiceInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                dice_1=1,
                dice_2=1,
            )
        )
        self.assertEqual(res_roll.new_position, 0)
        p1_after = self.player_repo.get_by_id(self.player1.id)
        # 500 + 400 (doble salario) = 900
        self.assertEqual(p1_after.money, 900)

    def test_ruleset_rent_in_jail_disabled(self):
        """Ruleset hook: si collect_rent_in_jail=False, el propietario en la cárcel no cobra renta."""
        self.game.ruleset_config = RulesetConfig(collect_rent_in_jail=False)
        self.game_repo.save(self.game)

        # Propietario (player2) está en la cárcel
        self.player2.in_jail = True
        self.player_repo.save(self.player2)

        # Player2 posee BALTIC_AVE
        self.property_repo.save(
            PropertyState(
                id=None,
                game_id=self.game.id,
                tile_id="BALTIC_AVE",
                tile_position=3,
                owner_id=self.player2.id,
                houses_count=0,
                hotels_count=0,
                is_mortgaged=False,
            )
        )

        # Player1 cae en BALTIC_AVE e intenta pagar renta
        p1_before = self.player_repo.get_by_id(self.player1.id)
        p2_before = self.player_repo.get_by_id(self.player2.id)

        out = self.pay_rent_uc.execute(
            PayRentInputDTO(
                game_id=self.game.id,
                payer_player_id=self.player1.id,
                tile_id="BALTIC_AVE",
                dice_roll=4,
            )
        )
        self.assertEqual(out.rent_amount, 0)
        p1_after = self.player_repo.get_by_id(self.player1.id)
        p2_after = self.player_repo.get_by_id(self.player2.id)
        self.assertEqual(p1_after.money, p1_before.money)
        self.assertEqual(p2_after.money, p2_before.money)


if __name__ == "__main__":
    unittest.main()
