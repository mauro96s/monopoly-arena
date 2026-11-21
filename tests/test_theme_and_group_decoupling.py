import unittest
from src.domain.models.enums import GameVariant, PropertyGroup, TileType, GameStatus
from src.domain.models.game import Game
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.themes import (
    ThemeRegistry,
    ThemeDefinition,
    GroupThemeMetadata,
    TileThemeMetadata,
    CLASSIC_THEME,
)
from src.infrastructure.database import Base, SessionLocal, engine
from src.infrastructure.repositories.sql_game_repository import SqlGameRepository


class TestThemeAndGroupDecoupling(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self.game_repo = SqlGameRepository(self.session)

    def tearDown(self):
        self.session.close()

    def test_board_rule_registry_get_group_tile_ids(self):
        """Verifica que BoardRuleRegistry resuelva los IDs de casillas por grupo dinámicamente."""
        brown_tiles = BoardRuleRegistry.get_group_tile_ids(GameVariant.CLASSIC, PropertyGroup.BROWN)
        self.assertEqual(brown_tiles, {"MEDITERRANEAN_AVE", "BALTIC_AVE"})

        dark_blue_tiles = BoardRuleRegistry.get_group_tile_ids(GameVariant.CLASSIC, PropertyGroup.DARK_BLUE)
        self.assertEqual(dark_blue_tiles, {"PARK_PLACE", "BOARDWALK"})

        railroads = BoardRuleRegistry.get_group_tile_ids(GameVariant.CLASSIC, PropertyGroup.RAILROAD)
        self.assertEqual(len(railroads), 4)
        self.assertIn("RAILROAD_READING", railroads)
        self.assertIn("RAILROAD_SHORT_LINE", railroads)

    def test_board_rule_registry_get_board_groups(self):
        """Verifica que se obtengan todos los grupos registrados con sus miembros."""
        groups = BoardRuleRegistry.get_board_groups(GameVariant.CLASSIC)
        self.assertIn(PropertyGroup.BROWN, groups)
        self.assertIn(PropertyGroup.RED, groups)
        self.assertIn(PropertyGroup.DARK_BLUE, groups)
        self.assertEqual(len(groups[PropertyGroup.RED]), 3)

    def test_classic_theme_loaded_and_complete(self):
        """Verifica que el tema clásico oficial contenga las 40 casillas y metadatos visuales."""
        theme = ThemeRegistry.get_theme("classic")
        self.assertEqual(theme.theme_id, "classic")
        self.assertEqual(theme.currency_symbol, "$")
        self.assertEqual(len(theme.tiles), 40)

        # Verificar nombres cortos de casillas clave
        go_tile = theme.get_tile("GO")
        self.assertIsNotNone(go_tile)
        self.assertEqual(go_tile.short_name, "Salida")

        med_tile = theme.get_tile("MEDITERRANEAN_AVE")
        self.assertIsNotNone(med_tile)
        self.assertEqual(med_tile.short_name, "Mediterráneo")

        boardwalk = theme.get_tile("BOARDWALK")
        self.assertIsNotNone(boardwalk)
        self.assertEqual(boardwalk.short_name, "Paseo Tablado")

    def test_theme_registry_open_closed_principle(self):
        """
        Demuestra OCP: registrar un tema completamente nuevo (ej. Pokémon o Harry Potter)
        sin modificar las clases de dominio ni los casos de uso preexistentes.
        """
        pokemon_theme = ThemeDefinition(
            theme_id="pokemon",
            name="Monopoly Pokémon Kanto Edition",
            description="Edición ambientada en la región de Kanto con Pokémon clásicos",
            currency_symbol="₽",
            currency_code="POKE_DOLLAR",
            groups=[
                GroupThemeMetadata(key="BROWN", name="Pueblo Paleta", color_hex="#8B4513", icon="home"),
                GroupThemeMetadata(key="DARK_BLUE", name="Liga Pokémon", color_hex="#1D4ED8", icon="crown"),
            ],
            tiles={
                "GO": TileThemeMetadata("GO", 0, "Laboratorio de Oak (Cobras ₽200)", "Lab Oak", icon="star"),
                "MEDITERRANEAN_AVE": TileThemeMetadata("MEDITERRANEAN_AVE", 1, "Ruta 1", "Ruta 1", banner_color="#8B4513"),
                "BALTIC_AVE": TileThemeMetadata("BALTIC_AVE", 3, "Pueblo Paleta", "Pueblo Paleta", banner_color="#8B4513"),
                "BOARDWALK": TileThemeMetadata("BOARDWALK", 39, "Meseta Añil", "Meseta Añil", banner_color="#1D4ED8"),
            }
        )

        ThemeRegistry.register_theme(pokemon_theme)
        self.assertTrue(ThemeRegistry.has_theme("pokemon"))

        retrieved = ThemeRegistry.get_theme("pokemon")
        self.assertEqual(retrieved.name, "Monopoly Pokémon Kanto Edition")
        self.assertEqual(retrieved.currency_symbol, "₽")
        self.assertEqual(retrieved.get_tile("BOARDWALK").short_name, "Meseta Añil")

        # Fallback a clásico para temas inexistentes
        unknown = ThemeRegistry.get_theme("inexistente_123")
        self.assertEqual(unknown.theme_id, "classic")

    def test_game_theme_id_persistence(self):
        """Verifica que el campo theme_id persista correctamente en el modelo de base de datos."""
        game = Game(
            id=None,
            code="THEME_TEST_01",
            variant=GameVariant.CLASSIC,
            theme_id="pokemon",
            status=GameStatus.WAITING,
        )
        saved = self.game_repo.save(game)
        self.assertIsNotNone(saved.id)
        self.assertEqual(saved.theme_id, "pokemon")

        reloaded = self.game_repo.get_by_id(saved.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.theme_id, "pokemon")

        # Limpiar
        self.game_repo.delete(saved.id)


if __name__ == "__main__":
    unittest.main()
