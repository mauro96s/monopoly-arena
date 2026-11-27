import unittest
from fastapi import HTTPException
from unittest.mock import MagicMock

from src.infrastructure.database import Base, SessionLocal, engine
from src.infrastructure.repositories.sql_game_repository import SqlGameRepository
from src.infrastructure.repositories.sql_player_repository import SqlPlayerRepository
from src.infrastructure.repositories.sql_user_repository import SqlUserRepository
from src.infrastructure.repositories.sql_theme_repository import SqlThemeRepository
from src.infrastructure.repositories.sql_rule_preset_repository import SqlRulePresetRepository
from src.infrastructure.repositories.sql_property_repository import SqlPropertyRepository
from src.infrastructure.repositories.sql_transaction_repository import SqlTransactionRepository
from src.application.use_cases.roll_dice import RollDiceUseCase
from src.domain.models.user import User
from src.domain.models.game import Game
from src.domain.models.player import Player
from src.domain.models.rule_preset import RulePreset
from src.domain.models.enums import GameStatus, GameVariant
from src.domain.rules.ruleset_config import RulesetConfig
from src.domain.themes.models import ThemeDefinition, TileThemeMetadata
from src.presentation.routers.actions_router import roll_dice
from src.presentation.routers.games_router import (
    advance_turn,
    delete_rule_preset,
    update_custom_theme,
    delete_custom_theme,
    SaveThemeRequest,
)
from src.presentation.schemas.action_schemas import RollDiceRequest
from src.presentation.dependencies import assert_can_act_for_player
from src.application.dtos.action_dtos import DrawCardInputDTO
from src.application.use_cases.draw_card import DrawCardUseCase
from src.domain.themes.theme_registry import ThemeRegistry
from src.domain.themes.card_models import ThemeCardDefinition, CardEffectType, DeckType


class TestMultiplayerSecurityAndIntegrity(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self.game_repo = SqlGameRepository(self.session)
        self.player_repo = SqlPlayerRepository(self.session)
        self.user_repo = SqlUserRepository(self.session)
        self.theme_repo = SqlThemeRepository(self.session)
        self.preset_repo = SqlRulePresetRepository(self.session)
        self.property_repo = SqlPropertyRepository(self.session)
        self.tx_repo = SqlTransactionRepository(self.session)
        self.roll_uc = RollDiceUseCase(self.game_repo, self.player_repo, self.property_repo, self.tx_repo)
        self.games_to_cleanup = []
        self.presets_to_cleanup = []
        self.themes_to_cleanup = []

    def tearDown(self):
        for gid in self.games_to_cleanup:
            try:
                self.game_repo.delete(gid)
            except Exception:
                pass
        for pid in self.presets_to_cleanup:
            try:
                self.preset_repo.delete(pid)
            except Exception:
                pass
        for tid in self.themes_to_cleanup:
            try:
                self.theme_repo.delete(tid)
            except Exception:
                pass
        self.session.close()

    def test_multiplayer_turn_authorization_enforcement(self):
        # 1. Crear juego con 2 jugadores vinculados a usuarios distintos
        game = Game(
            id=None,
            code="SECURE01",
            variant=GameVariant.CLASSIC,
            status=GameStatus.IN_PROGRESS,
            owner_user_id=101,
            current_turn=1,
            current_player_index=0,
        )
        saved_game = self.game_repo.save(game)
        self.games_to_cleanup.append(saved_game.id)

        p1 = Player(id=None, game_id=saved_game.id, name="Alice", token="Sombrero", money=1500, position=0, user_id=101)
        p2 = Player(id=None, game_id=saved_game.id, name="Bob", token="Auto", money=1500, position=0, user_id=102)
        saved_p1 = self.player_repo.save(p1)
        saved_p2 = self.player_repo.save(p2)

        user_alice = User(id=101, username="alice", email="alice@test.local", password_hash="h1")
        user_bob = User(id=102, username="bob", email="bob@test.local", password_hash="h2")
        user_charlie = User(id=103, username="charlie", email="charlie@test.local", password_hash="h3")

        # Intentar tirar dados en el turno de Alice como Bob (user_id=102) -> 403 Forbidden
        req = RollDiceRequest(dice1=3, dice2=4)
        with self.assertRaises(HTTPException) as ctx:
            roll_dice(
                game_id=saved_game.id,
                payload=req,
                current_user=user_bob,
                use_case=self.roll_uc,
                game_repo=self.game_repo,
                player_repo=self.player_repo,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("autorización para actuar", ctx.exception.detail)

        # Intentar avanzar turno como Charlie (intruso) -> 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            advance_turn(
                game_id=saved_game.id,
                game_repo=self.game_repo,
                player_repo=self.player_repo,
                tx_repo=MagicMock(),
                current_user=user_charlie,
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Actuar como Alice (dueña del turno) -> Permitido (no lanza 403)
        res = roll_dice(
            game_id=saved_game.id,
            payload=req,
            current_user=user_alice,
            use_case=self.roll_uc,
            game_repo=self.game_repo,
            player_repo=self.player_repo,
        )
        self.assertTrue(res.success)

    def test_local_guest_players_backward_compatibility(self):
        # Partida local con jugadores invitados (user_id=None)
        game = Game(
            id=None,
            code="LOCAL01",
            variant=GameVariant.CLASSIC,
            status=GameStatus.IN_PROGRESS,
            owner_user_id=None,
            current_turn=1,
            current_player_index=0,
        )
        saved_game = self.game_repo.save(game)
        self.games_to_cleanup.append(saved_game.id)

        p1 = Player(id=None, game_id=saved_game.id, name="Invitado1", token="Perro", money=1500, position=0, user_id=None)
        p2 = Player(id=None, game_id=saved_game.id, name="Invitado2", token="Barco", money=1500, position=0, user_id=None)
        self.player_repo.save(p1)
        self.player_repo.save(p2)

        # Cualquier cliente sin login o con login puede actuar (modo mesa/invitado)
        req = RollDiceRequest(dice1=2, dice2=5)
        res = roll_dice(
            game_id=saved_game.id,
            payload=req,
            current_user=None,
            use_case=self.roll_uc,
            game_repo=self.game_repo,
            player_repo=self.player_repo,
        )
        self.assertTrue(res.success)

    def test_preset_ownership_protection(self):
        # Preset creado por usuario 201
        preset = RulePreset(
            id=None,
            name="Reglas Propias de 201",
            description="Exclusivo",
            ruleset_config=RulesetConfig(),
            owner_user_id=201,
        )
        saved_preset = self.preset_repo.save(preset)
        self.presets_to_cleanup.append(saved_preset.id)

        user_202 = User(id=202, username="intruder", email="int@test.local", password_hash="h")
        user_201 = User(id=201, username="owner", email="own@test.local", password_hash="h")

        # Usuario 202 intenta eliminar preset de 201 -> 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            delete_rule_preset(
                preset_id=saved_preset.id,
                current_user=user_202,
                preset_repo=self.preset_repo,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("autorización", ctx.exception.detail.lower())

        # Usuario 201 elimina su propio preset -> Exitoso
        res = delete_rule_preset(
            preset_id=saved_preset.id,
            current_user=user_201,
            preset_repo=self.preset_repo,
        )
        self.assertTrue(res["success"])

    def test_custom_theme_ownership_protection(self):
        # Tema creado por usuario 301
        custom_theme = ThemeDefinition(
            theme_id="custom_theme_301",
            name="Tema Privado",
            owner_user_id="301",
            tiles={
                "GO": TileThemeMetadata(tile_id="GO", position=0, name="Salida", short_name="GO", banner_color="#FFFFFF")
            },
        )
        self.theme_repo.save(custom_theme)
        self.themes_to_cleanup.append("custom_theme_301")

        user_302 = User(id=302, username="user_302", email="302@test.local", password_hash="h")
        user_301 = User(id=301, username="user_301", email="301@test.local", password_hash="h")

        # Usuario 302 intenta editar tema de 301 -> 403 Forbidden
        update_req = SaveThemeRequest(name="Tema Hackeado")
        with self.assertRaises(HTTPException) as ctx:
            update_custom_theme(
                theme_id="custom_theme_301",
                payload=update_req,
                current_user=user_302,
                theme_repo=self.theme_repo,
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Usuario 302 intenta borrar tema de 301 -> 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            delete_custom_theme(
                theme_id="custom_theme_301",
                current_user=user_302,
                theme_repo=self.theme_repo,
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # Usuario 301 puede editarlo
        res_update = update_custom_theme(
            theme_id="custom_theme_301",
            payload=update_req,
            current_user=user_301,
            theme_repo=self.theme_repo,
        )
        self.assertEqual(res_update.name, "Tema Hackeado")

    def test_draw_card_to_unowned_tile_triggers_buy_property(self):
        # Verificar que una carta que desplaza al jugador a una propiedad libre retorna landed_tile_action = BUY_PROPERTY
        game = Game(
            id=None,
            code="CARD01",
            variant=GameVariant.CLASSIC,
            status=GameStatus.IN_PROGRESS,
            current_turn=1,
            current_player_index=0,
            chance_deck_order=["TEST_MOVE"],
        )
        saved_game = self.game_repo.save(game)
        self.games_to_cleanup.append(saved_game.id)

        player = Player(
            id=None,
            game_id=saved_game.id,
            name="Alice",
            token="Sombrero",
            money=1500,
            position=0,
        )
        saved_player = self.player_repo.save(player)

        # Destino pos 3 (Avenida Báltica, purchasable)
        card = ThemeCardDefinition(
            card_id="TEST_MOVE",
            deck=DeckType.CHANCE,
            title="Avanzar a Casilla 3",
            description="Avanza a la casilla 3",
            effect_type=CardEffectType.MOVE_TO_POSITION,
            params={"target_pos": 3},
        )

        mock_theme = MagicMock()
        mock_theme.get_card.return_value = card

        mock_prop_repo = MagicMock()
        mock_prop_repo.get_by_tile.return_value = None

        with unittest.mock.patch.object(ThemeRegistry, "get_theme", return_value=mock_theme):
            uc = DrawCardUseCase(
                game_repo=self.game_repo,
                player_repo=self.player_repo,
                property_repo=mock_prop_repo,
                tx_repo=MagicMock(),
            )
            output = uc.execute(DrawCardInputDTO(
                game_id=saved_game.id,
                player_id=saved_player.id,
                deck_type=DeckType.CHANCE,
            ))
            self.assertEqual(output.landed_tile_action, "BUY_PROPERTY")
            self.assertEqual(output.new_position, 3)


if __name__ == "__main__":
    unittest.main()
