import unittest
from src.domain.models.enums import GameVariant, GameStatus
from src.domain.models.game import Game
from src.domain.models.player import Player
from src.domain.models.property import PropertyState
from src.domain.rules.ruleset_config import RulesetConfig
from src.domain.themes.classic import CLASSIC_THEME, CLASSIC_CHANCE_CARDS, CLASSIC_COMMUNITY_CHEST_CARDS
from src.domain.themes.card_models import DeckType, CardEffectType
from src.infrastructure.database import Base, SessionLocal, engine
from src.infrastructure.repositories.sql_game_repository import SqlGameRepository
from src.infrastructure.repositories.sql_player_repository import SqlPlayerRepository
from src.infrastructure.repositories.sql_property_repository import SqlPropertyRepository
from src.infrastructure.repositories.sql_transaction_repository import SqlTransactionRepository
from src.application.use_cases.draw_card import DrawCardUseCase
from src.application.use_cases.roll_dice import RollDiceUseCase
from src.application.dtos.action_dtos import DrawCardInputDTO, RollDiceInputDTO


class TestCardDecksAndEffects(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self.game_repo = SqlGameRepository(self.session)
        self.player_repo = SqlPlayerRepository(self.session)
        self.property_repo = SqlPropertyRepository(self.session)
        self.tx_repo = SqlTransactionRepository(self.session)

        self.draw_card_uc = DrawCardUseCase(
            self.game_repo, self.player_repo, self.property_repo, self.tx_repo
        )
        self.roll_dice_uc = RollDiceUseCase(
            self.game_repo, self.player_repo, self.property_repo, self.tx_repo
        )

        self.game = self.game_repo.save(
            Game(
                id=None,
                code="CARD_TEST",
                variant=GameVariant.CLASSIC,
                theme_id="classic",
                status=GameStatus.IN_PROGRESS,
                available_houses=32,
                available_hotels=12,
                ruleset_config=RulesetConfig(free_parking_jackpot=True),
            )
        )

        self.player1 = self.player_repo.save(
            Player(
                id=None,
                game_id=self.game.id,
                name="Alice",
                token="Sombrero",
                money=1500,
                position=0,
            )
        )
        self.player2 = self.player_repo.save(
            Player(
                id=None,
                game_id=self.game.id,
                name="Bob",
                token="Coche",
                money=1500,
                position=0,
            )
        )
        self.player3 = self.player_repo.save(
            Player(
                id=None,
                game_id=self.game.id,
                name="Charlie",
                token="Barco",
                money=1500,
                position=0,
            )
        )

    def tearDown(self):
        if self.game.id:
            self.game_repo.delete(self.game.id)
        self.session.close()

    def test_theme_cards_count_and_types(self):
        """Verifica que el catálogo clásico contenga 16 cartas de Fortuna y 16 de Arca Comunal."""
        self.assertEqual(len(CLASSIC_CHANCE_CARDS), 16)
        self.assertEqual(len(CLASSIC_COMMUNITY_CHEST_CARDS), 16)
        self.assertEqual(len(CLASSIC_THEME.chance_cards), 16)
        self.assertEqual(len(CLASSIC_THEME.community_chest_cards), 16)

        # Verificar que todos los IDs sean únicos
        all_ids = [c.card_id for c in CLASSIC_CHANCE_CARDS] + [c.card_id for c in CLASSIC_COMMUNITY_CHEST_CARDS]
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_collect_from_bank_effect(self):
        """Efecto COLLECT_FROM_BANK: Acredita dinero de la Banca al jugador."""
        res = self.draw_card_uc.execute(
            DrawCardInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                deck_type="CHANCE",
                card_id="CHANCE_BANK_DIVIDEND",  # $50
            )
        )
        self.assertEqual(res.amount_delta, 50)
        p1 = self.player_repo.get_by_id(self.player1.id)
        self.assertEqual(p1.money, 1550)

    def test_pay_to_bank_and_free_parking_pool(self):
        """Efecto PAY_TO_BANK: Descuenta dinero y alimenta el pozo si free_parking_jackpot=True."""
        res = self.draw_card_uc.execute(
            DrawCardInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                deck_type="CHANCE",
                card_id="CHANCE_SPEEDING_FINE",  # $15
            )
        )
        self.assertEqual(res.amount_delta, -15)
        p1 = self.player_repo.get_by_id(self.player1.id)
        self.assertEqual(p1.money, 1485)

        game_after = self.game_repo.get_by_id(self.game.id)
        self.assertEqual(game_after.free_parking_pool, 15)

    def test_collect_from_all_effect(self):
        """Efecto COLLECT_FROM_ALL: Cobra a cada rival activo (Cumpleaños: $10 c/u)."""
        res = self.draw_card_uc.execute(
            DrawCardInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                deck_type="COMMUNITY_CHEST",
                card_id="COMMUNITY_BIRTHDAY",  # $10 de cada rival (Bob y Charlie)
            )
        )
        self.assertEqual(res.amount_delta, 20)
        p1 = self.player_repo.get_by_id(self.player1.id)
        p2 = self.player_repo.get_by_id(self.player2.id)
        p3 = self.player_repo.get_by_id(self.player3.id)
        self.assertEqual(p1.money, 1520)
        self.assertEqual(p2.money, 1490)
        self.assertEqual(p3.money, 1490)

    def test_pay_to_all_effect(self):
        """Efecto PAY_TO_ALL: Paga a cada rival activo (Presidente de Junta: $50 c/u)."""
        res = self.draw_card_uc.execute(
            DrawCardInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                deck_type="CHANCE",
                card_id="CHANCE_CHAIRMAN_BOARD",  # $50 a cada rival
            )
        )
        self.assertEqual(res.amount_delta, -100)
        p1 = self.player_repo.get_by_id(self.player1.id)
        p2 = self.player_repo.get_by_id(self.player2.id)
        p3 = self.player_repo.get_by_id(self.player3.id)
        self.assertEqual(p1.money, 1400)
        self.assertEqual(p2.money, 1550)
        self.assertEqual(p3.money, 1550)

    def test_repairs_per_building_effect(self):
        """Efecto REPAIRS_PER_BUILDING: Calcula $25 por casa y $100 por hotel."""
        # Alice posee MEDITERRANEAN con 3 casas y BALTIC con 1 hotel
        self.property_repo.save(
            PropertyState(
                id=None,
                game_id=self.game.id,
                tile_id="MEDITERRANEAN_AVE",
                tile_position=1,
                owner_id=self.player1.id,
                houses_count=3,
                hotels_count=0,
                is_mortgaged=False,
            )
        )
        self.property_repo.save(
            PropertyState(
                id=None,
                game_id=self.game.id,
                tile_id="BALTIC_AVE",
                tile_position=3,
                owner_id=self.player1.id,
                houses_count=0,
                hotels_count=1,
                is_mortgaged=False,
            )
        )

        res = self.draw_card_uc.execute(
            DrawCardInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                deck_type="CHANCE",
                card_id="CHANCE_GENERAL_REPAIRS",  # 3*25 + 1*100 = $175
            )
        )
        self.assertEqual(res.amount_delta, -175)
        p1 = self.player_repo.get_by_id(self.player1.id)
        self.assertEqual(p1.money, 1500 - 175)

    def test_move_to_position_and_collect_go(self):
        """Efecto MOVE_TO_POSITION: Traslada al jugador y cobra Salida si cruza GO."""
        self.player1.position = 30
        self.player_repo.save(self.player1)

        # Avanza a Illinois (casilla 24). Como 24 < 30, cruza Salida -> cobra $200
        res = self.draw_card_uc.execute(
            DrawCardInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                deck_type="CHANCE",
                card_id="CHANCE_ADVANCE_ILLINOIS",  # target_pos: 24
            )
        )
        self.assertEqual(res.new_position, 24)
        self.assertTrue(res.passed_go)
        self.assertEqual(res.amount_delta, 200)
        p1 = self.player_repo.get_by_id(self.player1.id)
        self.assertEqual(p1.position, 24)
        self.assertEqual(p1.money, 1700)

    def test_move_relative_effect(self):
        """Efecto MOVE_RELATIVE: Retrocede 3 casillas sin cobrar Salida."""
        self.player1.position = 7  # Casilla Suerte 1
        self.player_repo.save(self.player1)

        res = self.draw_card_uc.execute(
            DrawCardInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                deck_type="CHANCE",
                card_id="CHANCE_GO_BACK_3",  # -3 pasos
            )
        )
        self.assertEqual(res.new_position, 4)  # 7 - 3 = 4 (Income Tax)
        self.assertFalse(res.passed_go)
        p1 = self.player_repo.get_by_id(self.player1.id)
        self.assertEqual(p1.position, 4)

    def test_move_nearest_railroad_with_multiplier(self):
        """Efecto MOVE_NEAREST_TYPE: Avanza a la estación más cercana pagando el doble si tiene dueño."""
        # Bob posee Ferrocarril de Pensilvania (casilla 15)
        self.property_repo.save(
            PropertyState(
                id=None,
                game_id=self.game.id,
                tile_id="RAILROAD_PENNSYLVANIA",
                tile_position=15,
                owner_id=self.player2.id,
                houses_count=0,
                hotels_count=0,
                is_mortgaged=False,
            )
        )

        # Alice está en casilla 7 (Suerte 1). La estación más cercana es la 15 (Pensilvania)
        self.player1.position = 7
        self.player_repo.save(self.player1)

        res = self.draw_card_uc.execute(
            DrawCardInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                deck_type="CHANCE",
                card_id="CHANCE_ADVANCE_NEAREST_RAILROAD_1",
            )
        )
        self.assertEqual(res.new_position, 15)
        self.assertEqual(res.landed_tile_action, "SPECIAL_RENT_PAID")
        self.assertEqual(res.landed_tile_details["multiplier"], 2)
        # Renta base de 1 ferrocarril = $25. Doble = $50.
        self.assertEqual(res.landed_tile_details["rent_paid"], 50)

        p1 = self.player_repo.get_by_id(self.player1.id)
        p2 = self.player_repo.get_by_id(self.player2.id)
        self.assertEqual(p1.money, 1450)
        self.assertEqual(p2.money, 1550)

    def test_go_to_jail_effect(self):
        """Efecto GO_TO_JAIL: Envía a prisión (casilla 10), in_jail=True y avanza turno."""
        res = self.draw_card_uc.execute(
            DrawCardInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                deck_type="CHANCE",
                card_id="CHANCE_GO_TO_JAIL",
            )
        )
        self.assertEqual(res.new_position, 10)
        self.assertTrue(res.in_jail)
        p1 = self.player_repo.get_by_id(self.player1.id)
        self.assertTrue(p1.in_jail)
        self.assertEqual(p1.position, 10)

    def test_get_out_of_jail_card_retention(self):
        """Retención: La carta 'Salga de la Cárcel Gratis' no regresa al fondo del mazo mientras el jugador la conserve."""
        res = self.draw_card_uc.execute(
            DrawCardInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                deck_type="CHANCE",
                card_id="CHANCE_GET_OUT_OF_JAIL",
            )
        )
        self.assertEqual(res.out_of_jail_cards_count, 1)
        p1 = self.player_repo.get_by_id(self.player1.id)
        self.assertEqual(p1.out_of_jail_cards, 1)

        # Verificar que la carta NO esté en el orden de cartas disponibles en el juego
        game_after = self.game_repo.get_by_id(self.game.id)
        self.assertNotIn("CHANCE_GET_OUT_OF_JAIL", game_after.chance_deck_order)

    def test_roll_dice_automatic_card_draw_on_chance_tile(self):
        """RollDiceUseCase: Al caer en casilla de Suerte (#7), se roba y ejecuta una carta automáticamente."""
        self.player1.position = 3
        self.player_repo.save(self.player1)

        # Tirar 2 y 2 -> cae en casilla 7 (CHANCE_1)
        roll_res = self.roll_dice_uc.execute(
            RollDiceInputDTO(
                game_id=self.game.id,
                player_id=self.player1.id,
                dice_1=2,
                dice_2=2,
            )
        )
        self.assertEqual(roll_res.landed_tile_id, "CHANCE_1")
        self.assertEqual(roll_res.action_required, "DRAW_CHANCE")
        self.assertIn("card_id", roll_res.action_details)
        self.assertIn("title", roll_res.action_details)
        self.assertIn("description", roll_res.action_details)


if __name__ == "__main__":
    unittest.main()
