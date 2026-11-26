import unittest
from src.infrastructure.database import Base, SessionLocal, engine
from src.infrastructure.repositories.sql_theme_repository import SqlThemeRepository
from src.infrastructure.repositories.sql_game_repository import SqlGameRepository
from src.domain.themes import ThemeRegistry, ThemeDefinition, GroupThemeMetadata, TileThemeMetadata
from src.domain.themes.classic import CLASSIC_THEME
from src.domain.themes.harry_potter import HARRY_POTTER_THEME
from src.domain.themes.card_models import DeckType, CardEffectType, ThemeCardDefinition
from src.domain.exceptions import InvalidGameActionError
from src.presentation.routers.games_router import (
    list_available_themes,
    get_theme_by_id,
    clone_theme,
    create_custom_theme,
    update_custom_theme,
    delete_custom_theme,
    create_game,
    CloneThemeRequest,
    SaveThemeRequest,
    GroupThemeSchema,
    TileThemeSchema,
    CardThemeSchema,
)
from src.presentation.schemas.action_schemas import CreateGameRequest
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.models.enums import GameVariant


class TestThemeWorkshop(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self.theme_repo = SqlThemeRepository(self.session)
        self.game_repo = SqlGameRepository(self.session)
        self.themes_to_cleanup = []
        self.games_to_cleanup = []

    def tearDown(self):
        for tid in self.themes_to_cleanup:
            try:
                self.theme_repo.delete(tid)
            except Exception:
                pass
        for gid in self.games_to_cleanup:
            try:
                self.game_repo.delete(gid)
            except Exception:
                pass
        self.session.close()

    def test_official_harry_potter_theme_completeness(self):
        """Verifica que el nuevo tema oficial 'harry_potter' (Mundo Mágico) tenga 40 casillas y barajas válidas."""
        hp = ThemeRegistry.get_theme("harry_potter")
        self.assertIsNotNone(hp)
        self.assertEqual(hp.theme_id, "harry_potter")
        self.assertEqual(hp.name, "Mundo Mágico")
        self.assertEqual(hp.currency_symbol, "⚡")
        self.assertEqual(hp.currency_code, "GAL")
        self.assertTrue(hp.is_official)
        self.assertTrue(hp.is_readonly)

        # 40 casillas correspondientes al circuito de Monopoly
        self.assertEqual(len(hp.tiles), 40)
        classic_board = BoardRuleRegistry.get_board(GameVariant.CLASSIC)
        for tile_id in classic_board.keys():
            self.assertIn(tile_id, hp.tiles)
            tile_meta = hp.tiles[tile_id]
            self.assertTrue(len(tile_meta.name) > 0)
            self.assertTrue(len(tile_meta.short_name) > 0)

        # Barajas completas
        self.assertEqual(len(hp.chance_cards), 16)
        self.assertEqual(len(hp.community_chest_cards), 16)

        # Efectos válidos
        for card in hp.chance_cards + hp.community_chest_cards:
            self.assertIsInstance(card.effect_type, CardEffectType)

    def test_clone_official_theme_to_editable(self):
        """Clonar un tema oficial crea un nuevo tema editable sin mutar el original ni permitir sobrescribir solo lectura."""
        # 1. Clonar vía endpoint router
        clone_req = CloneThemeRequest(
            target_theme_id="hp_custom_magic",
            target_name="Mundo Mágico Personalizado",
            target_description="Mi versión con hechizos modificados",
        )
        cloned_resp = clone_theme(
            theme_id="harry_potter",
            payload=clone_req,
            theme_repo=self.theme_repo,
        )
        self.themes_to_cleanup.append(cloned_resp.theme_id)

        self.assertEqual(cloned_resp.theme_id, "hp_custom_magic")
        self.assertEqual(cloned_resp.name, "Mundo Mágico Personalizado")
        self.assertFalse(cloned_resp.is_official)
        self.assertFalse(cloned_resp.is_readonly)
        self.assertEqual(cloned_resp.parent_theme_id, "harry_potter")
        self.assertEqual(cloned_resp.currency_symbol, "⚡")
        self.assertEqual(len(cloned_resp.tiles), 40)
        self.assertEqual(len(cloned_resp.chance_cards), 16)

        # 2. El tema oficial original no muta y sigue intacto
        orig_hp = ThemeRegistry.get_theme("harry_potter")
        self.assertEqual(orig_hp.name, "Mundo Mágico")
        self.assertTrue(orig_hp.is_readonly)

        # 3. Intentar sobrescribir tema de solo lectura debe fallar
        save_req = SaveThemeRequest(
            name="Intento de Hack",
            groups=[],
            tiles={},
            chance_cards=[],
            community_chest_cards=[],
        )
        with self.assertRaises(Exception):
            update_custom_theme("harry_potter", save_req, self.theme_repo)

    def test_theme_persistence_and_game_creation(self):
        """Persiste un tema personalizado con cartas y casillas editadas y permite crear una partida con dicho tema."""
        custom_theme_id = "steampunk_2026"
        custom_theme = ThemeDefinition(
            theme_id=custom_theme_id,
            name="Revolución Steampunk",
            description="Engranajes, vapor y cobre victoriano",
            currency_symbol="⚙️",
            currency_code="GEAR",
            chance_deck_name="Engranajes del Destino",
            community_chest_deck_name="Depósito Central",
            is_official=False,
            is_readonly=False,
            groups=[
                GroupThemeMetadata(key="BROWN", name="Subterráneos de Cobre", color_hex="#B87333", icon="settings")
            ],
            tiles={
                "GO": TileThemeMetadata("GO", 0, "Gran Caldera Central", "Caldera", icon="flame"),
                "MEDITERRANEAN_AVE": TileThemeMetadata("MEDITERRANEAN_AVE", 1, "Callejón del Pistón", "Pistón", banner_color="#B87333"),
            },
            chance_cards=[
                ThemeCardDefinition(
                    card_id="STEAM_CARD_1",
                    deck=DeckType.CHANCE,
                    title="Sobrepresión de Vapor",
                    description="Vendes vapor comprimido. Cobra 150 ⚙️.",
                    effect_type=CardEffectType.COLLECT_FROM_BANK,
                    params={"amount": 150},
                    icon="wind",
                )
            ],
            community_chest_cards=[],
        )

        saved = self.theme_repo.save(custom_theme)
        self.themes_to_cleanup.append(saved.theme_id)
        self.assertEqual(saved.theme_id, custom_theme_id)

        # Recargar desde repositorio
        reloaded = self.theme_repo.get_by_theme_id(custom_theme_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.currency_symbol, "⚙️")
        self.assertEqual(len(reloaded.chance_cards), 1)
        self.assertEqual(reloaded.chance_cards[0].title, "Sobrepresión de Vapor")

        # Iniciar partida vinculada a este tema
        game_req = CreateGameRequest(
            code="STEAM_GAME",
            theme_id=custom_theme_id,
        )
        game_resp = create_game(game_req, game_repo=self.game_repo)
        self.games_to_cleanup.append(game_resp.id)
        self.assertEqual(game_resp.theme_id, custom_theme_id)

        # ThemeRegistry resuelve el tema persistido dinámicamente
        resolved = ThemeRegistry.get_theme(custom_theme_id)
        self.assertEqual(resolved.name, "Revolución Steampunk")

    def test_theme_workshop_endpoints_crud(self):
        """Valida catálogo enriquecido, creación, actualización y eliminación de temas personalizados."""
        # 1. Catálogo disponible
        themes_avail = list_available_themes(theme_repo=self.theme_repo)
        theme_ids = [t["theme_id"] for t in themes_avail]
        self.assertIn("classic", theme_ids)
        self.assertIn("harry_potter", theme_ids)

        # 2. Crear tema personalizado vía endpoint
        create_req = SaveThemeRequest(
            theme_id="cyberpunk_neon",
            name="Cyberpunk 2099",
            description="Calles de neón y megacorporaciones",
            currency_symbol="₿",
            currency_code="BTC",
            chance_deck_name="Hacks de Red",
            community_chest_deck_name="Caja de Créditos",
            groups=[
                GroupThemeSchema(key="DARK_BLUE", name="Megacorps", color_hex="#00FFFF", icon="cpu")
            ],
            tiles={
                "BOARDWALK": TileThemeSchema(tile_id="BOARDWALK", position=39, name="Torre Arasaka", short_name="Arasaka", banner_color="#00FFFF")
            },
            chance_cards=[
                CardThemeSchema(
                    card_id="CYBER_HACK_1",
                    deck="CHANCE",
                    title="Hackeo a Datacenter",
                    description="Robas 200 créditos de una megacorp.",
                    effect_type="COLLECT_FROM_BANK",
                    params={"amount": 200},
                    icon="terminal",
                )
            ],
            community_chest_cards=[],
        )
        created = create_custom_theme(payload=create_req, theme_repo=self.theme_repo)
        self.themes_to_cleanup.append(created.theme_id)
        self.assertEqual(created.name, "Cyberpunk 2099")
        self.assertEqual(created.currency_symbol, "₿")

        # 3. Consultar tema por ID
        fetched = get_theme_by_id(created.theme_id, theme_repo=self.theme_repo)
        self.assertEqual(fetched.theme_id, "cyberpunk_neon")
        self.assertEqual(len(fetched.chance_cards), 1)

        # 4. Actualizar tema personalizado
        update_req = SaveThemeRequest(
            name="Cyberpunk 2099 Deluxe",
            description="Versión mejorada",
            currency_symbol="₿",
            currency_code="BTC",
            groups=created.groups,
            tiles=created.tiles,
            chance_cards=created.chance_cards,
            community_chest_cards=created.community_chest_cards,
        )
        updated = update_custom_theme(created.theme_id, payload=update_req, theme_repo=self.theme_repo)
        self.assertEqual(updated.name, "Cyberpunk 2099 Deluxe")

        # 5. Intentar eliminar tema oficial protegido debe fallar
        with self.assertRaises(Exception):
            delete_custom_theme("classic", theme_repo=self.theme_repo)

        # 6. Eliminar tema personalizado
        del_res = delete_custom_theme(created.theme_id, theme_repo=self.theme_repo)
        self.assertTrue(del_res["success"])
        self.assertIsNone(self.theme_repo.get_by_theme_id(created.theme_id))


if __name__ == "__main__":
    unittest.main()
