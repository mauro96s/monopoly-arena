import unittest
from src.domain.models.enums import GameStatus, GameVariant
from src.domain.models.game import Game
from src.domain.models.player import Player
from src.domain.models.property import PropertyState
from src.domain.models.rule_preset import RulePreset
from src.domain.exceptions import InvalidGameActionError
from src.domain.rules.quick_end_evaluator import QuickEndEvaluator
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.rules.ruleset_config import RulesetConfig
from src.infrastructure.database import Base, SessionLocal, engine
from src.infrastructure.repositories.sql_game_repository import SqlGameRepository
from src.infrastructure.repositories.sql_player_repository import SqlPlayerRepository
from src.infrastructure.repositories.sql_property_repository import SqlPropertyRepository
from src.infrastructure.repositories.sql_transaction_repository import SqlTransactionRepository
from src.infrastructure.repositories.sql_rule_preset_repository import SqlRulePresetRepository
from src.application.use_cases.buy_property import BuyPropertyUseCase
from src.application.use_cases.auction_property import AuctionPropertyUseCase
from src.application.dtos.action_dtos import BuyPropertyInputDTO, AuctionPropertyInputDTO
from src.presentation.routers.games_router import create_game, list_rule_presets, create_rule_preset, delete_rule_preset
from src.presentation.schemas.action_schemas import CreateGameRequest, CreateRulePresetRequest


class TestRulePresetsAndQuickEnd(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self.preset_repo = SqlRulePresetRepository(self.session)
        self.game_repo = SqlGameRepository(self.session)
        self.player_repo = SqlPlayerRepository(self.session)
        self.property_repo = SqlPropertyRepository(self.session)
        self.tx_repo = SqlTransactionRepository(self.session)
        self.games_to_cleanup = []

    def tearDown(self):
        for gid in self.games_to_cleanup:
            try:
                self.game_repo.delete(gid)
            except Exception:
                pass
        self.session.close()

    def test_preset_repository_seeding_and_crud(self):
        """Validates default preset seeding, custom preset creation, protection of system defaults, and deletion."""
        presets = self.preset_repo.list_all()
        self.assertGreaterEqual(len(presets), 2)

        # Check default presets
        classic = next((p for p in presets if p.name == "Oficial Clásico"), None)
        quick = next((p for p in presets if p.name == "Mesa Rápida (Fin al Agotar Calles)"), None)
        self.assertIsNotNone(classic)
        self.assertIsNotNone(quick)
        self.assertTrue(classic.is_system_default)
        self.assertTrue(quick.is_system_default)
        self.assertEqual(quick.ruleset_config.victory_mode, "ALL_PROPERTIES_SOLD")
        self.assertTrue(quick.ruleset_config.disqualify_jailed_on_quick_end)

        # Save custom preset
        custom_preset = RulePreset(
            id=None,
            name="Mesa Relampago Custom",
            description="Regla personalizada de prueba",
            ruleset_config=RulesetConfig(
                victory_mode="ALL_PROPERTIES_SOLD",
                disqualify_jailed_on_quick_end=False,
                property_valuation_mode="MORTGAGE_VALUE",
            ),
            is_system_default=False,
        )
        saved = self.preset_repo.save(custom_preset)
        self.assertIsNotNone(saved.id)

        fetched = self.preset_repo.get_by_id(saved.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Mesa Relampago Custom")
        self.assertFalse(fetched.is_system_default)

        # Cannot delete system default
        with self.assertRaises(InvalidGameActionError):
            self.preset_repo.delete(classic.id)

        # Can delete custom preset
        deleted = self.preset_repo.delete(saved.id)
        self.assertTrue(deleted)
        self.assertIsNone(self.preset_repo.get_by_id(saved.id))

    def test_quick_end_evaluator_triggers_when_all_properties_sold(self):
        """When victory_mode is ALL_PROPERTIES_SOLD and the last property is acquired, game finishes."""
        rules = RulesetConfig(
            victory_mode="ALL_PROPERTIES_SOLD",
            disqualify_jailed_on_quick_end=True,
            property_valuation_mode="PURCHASE_PRICE",
        )
        game = self.game_repo.save(Game(
            id=None,
            code="QUICK1",
            variant=GameVariant.CLASSIC,
            ruleset_config=rules,
            status=GameStatus.IN_PROGRESS,
        ))
        self.games_to_cleanup.append(game.id)

        p1 = self.player_repo.save(Player(id=None, game_id=game.id, name="Alice", token="car", money=2000, position=1))
        p2 = self.player_repo.save(Player(id=None, game_id=game.id, name="Bob", token="hat", money=1000, position=3))

        board = BoardRuleRegistry.get_board(GameVariant.CLASSIC)
        purchasable_tile_ids = [tile_id for tile_id, s in board.items() if s.can_be_purchased()]
        self.assertEqual(len(purchasable_tile_ids), 28)

        # Assign 27 of 28 properties to Alice
        for tile_id in purchasable_tile_ids[:-1]:
            strat = board[tile_id]
            self.property_repo.save(PropertyState(
                id=None,
                game_id=game.id,
                tile_id=tile_id,
                tile_position=strat.definition.position,
                owner_id=p1.id,
            ))

        # Evaluate before last property: should not trigger
        result = QuickEndEvaluator.evaluate_after_property_acquired(
            game=game,
            property_repo=self.property_repo,
            player_repo=self.player_repo,
            game_repo=self.game_repo,
            transaction_repo=self.tx_repo,
        )
        self.assertFalse(result.triggered)
        reloaded = self.game_repo.get_by_id(game.id)
        self.assertEqual(reloaded.status, GameStatus.IN_PROGRESS)

        # Bob acquires the 28th (last) property
        last_tile_id = purchasable_tile_ids[-1]
        self.property_repo.save(PropertyState(
            id=None,
            game_id=game.id,
            tile_id=last_tile_id,
            tile_position=board[last_tile_id].definition.position,
            owner_id=p2.id,
        ))

        # Evaluate after last property: should trigger quick end
        result = QuickEndEvaluator.evaluate_after_property_acquired(
            game=game,
            property_repo=self.property_repo,
            player_repo=self.player_repo,
            game_repo=self.game_repo,
            transaction_repo=self.tx_repo,
        )
        self.assertTrue(result.triggered)
        self.assertIn("Cierre Rápido", result.reason)
        self.assertEqual(len(result.rankings), 2)
        # Alice owns 27 properties + $2000, so Alice should be rank 1
        self.assertEqual(result.rankings[0]["player_id"], p1.id)
        self.assertEqual(result.rankings[0]["rank"], 1)

        # Reload game and check FINISHED
        reloaded = self.game_repo.get_by_id(game.id)
        self.assertEqual(reloaded.status, GameStatus.FINISHED)

    def test_quick_end_evaluator_disqualifies_jailed_players(self):
        """When disqualify_jailed_on_quick_end is True, a jailed player cannot win regardless of net worth."""
        rules = RulesetConfig(
            victory_mode="ALL_PROPERTIES_SOLD",
            disqualify_jailed_on_quick_end=True,
            property_valuation_mode="PURCHASE_PRICE",
        )
        game = self.game_repo.save(Game(
            id=None,
            code="QUICK2",
            variant=GameVariant.CLASSIC,
            ruleset_config=rules,
            status=GameStatus.IN_PROGRESS,
        ))
        self.games_to_cleanup.append(game.id)

        # Alice is in jail but has $50,000
        p1 = self.player_repo.save(Player(id=None, game_id=game.id, name="Alice", token="car", money=50000, position=10, in_jail=True))
        # Bob is free but has only $1,500
        p2 = self.player_repo.save(Player(id=None, game_id=game.id, name="Bob", token="hat", money=1500, position=3, in_jail=False))

        board = BoardRuleRegistry.get_board(GameVariant.CLASSIC)
        purchasable_tile_ids = [tile_id for tile_id, s in board.items() if s.can_be_purchased()]

        # All 28 properties owned
        for i, tile_id in enumerate(purchasable_tile_ids):
            self.property_repo.save(PropertyState(
                id=None,
                game_id=game.id,
                tile_id=tile_id,
                tile_position=board[tile_id].definition.position,
                owner_id=p1.id if i < 20 else p2.id,
            ))

        result = QuickEndEvaluator.evaluate_after_property_acquired(
            game=game,
            property_repo=self.property_repo,
            player_repo=self.player_repo,
            game_repo=self.game_repo,
            transaction_repo=self.tx_repo,
        )
        self.assertTrue(result.triggered)

        # Bob (free) must be champion (rank 1), Alice disqualified
        bob_ranking = result.rankings[0]
        alice_ranking = result.rankings[1]

        self.assertEqual(bob_ranking["player_id"], p2.id)
        self.assertEqual(bob_ranking["rank"], 1)
        self.assertFalse(bob_ranking["is_disqualified"])

        self.assertEqual(alice_ranking["player_id"], p1.id)
        self.assertEqual(alice_ranking["rank"], 2)
        self.assertTrue(alice_ranking["is_disqualified"])
        self.assertIn("cárcel", alice_ranking["disqualification_reason"].lower())

    def test_quick_end_evaluator_all_jailed_fallback(self):
        """If all eligible players are in jail at quick end, fallback selects highest net worth with explanation."""
        rules = RulesetConfig(
            victory_mode="ALL_PROPERTIES_SOLD",
            disqualify_jailed_on_quick_end=True,
            property_valuation_mode="PURCHASE_PRICE",
        )
        game = self.game_repo.save(Game(
            id=None,
            code="QUICK3",
            variant=GameVariant.CLASSIC,
            ruleset_config=rules,
            status=GameStatus.IN_PROGRESS,
        ))
        self.games_to_cleanup.append(game.id)

        p1 = self.player_repo.save(Player(id=None, game_id=game.id, name="Alice", token="car", money=5000, position=10, in_jail=True))
        p2 = self.player_repo.save(Player(id=None, game_id=game.id, name="Bob", token="hat", money=1500, position=10, in_jail=True))

        board = BoardRuleRegistry.get_board(GameVariant.CLASSIC)
        purchasable_tile_ids = [tile_id for tile_id, s in board.items() if s.can_be_purchased()]
        for tile_id in purchasable_tile_ids:
            self.property_repo.save(PropertyState(
                id=None,
                game_id=game.id,
                tile_id=tile_id,
                tile_position=board[tile_id].definition.position,
                owner_id=p1.id,
            ))

        result = QuickEndEvaluator.evaluate_after_property_acquired(
            game=game,
            property_repo=self.property_repo,
            player_repo=self.player_repo,
            game_repo=self.game_repo,
            transaction_repo=self.tx_repo,
        )
        self.assertTrue(result.triggered)
        self.assertIn("todos los jugadores estaban en la cárcel", result.reason.lower())
        self.assertEqual(result.rankings[0]["player_id"], p1.id)

    def test_property_valuation_mode_mortgage_value(self):
        """When valuation mode is MORTGAGE_VALUE, property value counts as 50% face value."""
        rules = RulesetConfig(
            victory_mode="ALL_PROPERTIES_SOLD",
            disqualify_jailed_on_quick_end=False,
            property_valuation_mode="MORTGAGE_VALUE",
        )
        game = self.game_repo.save(Game(
            id=None,
            code="QUICK4",
            variant=GameVariant.CLASSIC,
            ruleset_config=rules,
            status=GameStatus.IN_PROGRESS,
        ))
        self.games_to_cleanup.append(game.id)

        p1 = self.player_repo.save(Player(id=None, game_id=game.id, name="Alice", token="car", money=1000, position=1))

        board = BoardRuleRegistry.get_board(GameVariant.CLASSIC)
        purchasable_tile_ids = [tile_id for tile_id, s in board.items() if s.can_be_purchased()]
        for tile_id in purchasable_tile_ids:
            self.property_repo.save(PropertyState(
                id=None,
                game_id=game.id,
                tile_id=tile_id,
                tile_position=board[tile_id].definition.position,
                owner_id=p1.id,
            ))

        result = QuickEndEvaluator.evaluate_after_property_acquired(
            game=game,
            property_repo=self.property_repo,
            player_repo=self.player_repo,
            game_repo=self.game_repo,
            transaction_repo=self.tx_repo,
        )
        self.assertTrue(result.triggered)

        total_mortgage_val = sum(board[tid].definition.price // 2 for tid in purchasable_tile_ids)
        alice_ranking = result.rankings[0]
        self.assertEqual(alice_ranking["properties_value"], total_mortgage_val)
        self.assertEqual(alice_ranking["net_worth"], 1000 + total_mortgage_val)

    def test_buy_property_use_case_triggers_quick_end(self):
        """End-to-end integration: BuyPropertyUseCase finishes game when last property is bought."""
        rules = RulesetConfig(
            victory_mode="ALL_PROPERTIES_SOLD",
            disqualify_jailed_on_quick_end=True,
        )
        game = self.game_repo.save(Game(
            id=None,
            code="BUYEND",
            variant=GameVariant.CLASSIC,
            ruleset_config=rules,
            status=GameStatus.IN_PROGRESS,
        ))
        self.games_to_cleanup.append(game.id)

        p1 = self.player_repo.save(Player(id=None, game_id=game.id, name="Alice", token="car", money=5000, position=1))
        p2 = self.player_repo.save(Player(id=None, game_id=game.id, name="Bob", token="dog", money=5000, position=3))

        board = BoardRuleRegistry.get_board(GameVariant.CLASSIC)
        purchasable_tile_ids = [tile_id for tile_id, s in board.items() if s.can_be_purchased()]

        # 27 properties already owned by p1
        for tile_id in purchasable_tile_ids[:-1]:
            self.property_repo.save(PropertyState(
                id=None,
                game_id=game.id,
                tile_id=tile_id,
                tile_position=board[tile_id].definition.position,
                owner_id=p1.id,
            ))

        # p2 buys the 28th property via BuyPropertyUseCase
        last_tile_id = purchasable_tile_ids[-1]
        use_case = BuyPropertyUseCase(
            game_repo=self.game_repo,
            player_repo=self.player_repo,
            property_repo=self.property_repo,
            transaction_repo=self.tx_repo,
        )

        output = use_case.execute(
            BuyPropertyInputDTO(
                game_id=game.id,
                player_id=p2.id,
                tile_id=last_tile_id,
                auto_advance_turn=False,
            )
        )

        self.assertTrue(output.is_game_finished)
        self.assertIsNotNone(output.quick_end_details)
        self.assertEqual(output.quick_end_details["victory_mode"], "ALL_PROPERTIES_SOLD")

        # Verify game is saved as FINISHED
        reloaded_game = self.game_repo.get_by_id(game.id)
        self.assertEqual(reloaded_game.status, GameStatus.FINISHED)

    def test_auction_property_use_case_triggers_quick_end(self):
        """End-to-end integration: AuctionPropertyUseCase finishes game when last property is auctioned."""
        rules = RulesetConfig(
            victory_mode="ALL_PROPERTIES_SOLD",
            disqualify_jailed_on_quick_end=True,
        )
        game = self.game_repo.save(Game(
            id=None,
            code="AUCTEND",
            variant=GameVariant.CLASSIC,
            ruleset_config=rules,
            status=GameStatus.IN_PROGRESS,
        ))
        self.games_to_cleanup.append(game.id)

        p1 = self.player_repo.save(Player(id=None, game_id=game.id, name="Alice", token="car", money=5000, position=1))
        p2 = self.player_repo.save(Player(id=None, game_id=game.id, name="Bob", token="dog", money=5000, position=3))

        board = BoardRuleRegistry.get_board(GameVariant.CLASSIC)
        purchasable_tile_ids = [tile_id for tile_id, s in board.items() if s.can_be_purchased()]

        # 27 properties already owned by p1
        for tile_id in purchasable_tile_ids[:-1]:
            self.property_repo.save(PropertyState(
                id=None,
                game_id=game.id,
                tile_id=tile_id,
                tile_position=board[tile_id].definition.position,
                owner_id=p1.id,
            ))

        # p2 wins 28th property in auction
        last_tile_id = purchasable_tile_ids[-1]
        use_case = AuctionPropertyUseCase(
            game_repo=self.game_repo,
            player_repo=self.player_repo,
            property_repo=self.property_repo,
            transaction_repo=self.tx_repo,
        )

        output = use_case.execute(
            AuctionPropertyInputDTO(
                game_id=game.id,
                winner_player_id=p2.id,
                tile_id=last_tile_id,
                winning_bid=250,
                auto_advance_turn=False,
            )
        )

        self.assertTrue(output.is_game_finished)
        self.assertIsNotNone(output.quick_end_details)

        reloaded_game = self.game_repo.get_by_id(game.id)
        self.assertEqual(reloaded_game.status, GameStatus.FINISHED)

    def test_games_router_preset_endpoints_and_create_game_with_preset(self):
        """Validates games router rule preset endpoints and game creation initialized with a preset."""
        # 1. List presets via router
        presets = list_rule_presets(preset_repo=self.preset_repo)
        self.assertGreaterEqual(len(presets), 2)
        quick_preset = next((p for p in presets if p.ruleset_config.get("victory_mode") == "ALL_PROPERTIES_SOLD"), None)
        self.assertIsNotNone(quick_preset)

        # 2. Create new custom preset via router
        new_preset_req = CreateRulePresetRequest(
            name="Preset Router Test",
            description="Created via endpoint",
            ruleset_config={
                "victory_mode": "ALL_PROPERTIES_SOLD",
                "disqualify_jailed_on_quick_end": False,
                "property_valuation_mode": "MORTGAGE_VALUE",
                "free_parking_jackpot": True,
            },
        )
        created_preset = create_rule_preset(payload=new_preset_req, preset_repo=self.preset_repo)
        self.assertEqual(created_preset.name, "Preset Router Test")
        self.assertFalse(created_preset.is_system_default)

        # 3. Create game using this preset_id
        game_req = CreateGameRequest(
            code="PRESET_ROUTER",
            rule_preset_id=created_preset.id,
        )
        game_resp = create_game(payload=game_req, game_repo=self.game_repo, preset_repo=self.preset_repo)
        self.games_to_cleanup.append(game_resp.id)
        self.assertEqual(game_resp.ruleset_config["victory_mode"], "ALL_PROPERTIES_SOLD")
        self.assertFalse(game_resp.ruleset_config["disqualify_jailed_on_quick_end"])
        self.assertTrue(game_resp.ruleset_config["free_parking_jackpot"])

        # 4. Delete the custom preset via router
        del_resp = delete_rule_preset(preset_id=created_preset.id, preset_repo=self.preset_repo)
        self.assertTrue(del_resp.get("success", False))


if __name__ == "__main__":
    unittest.main()
