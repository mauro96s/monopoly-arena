import asyncio
import unittest
from fastapi import HTTPException

from src.infrastructure.database import Base, SessionLocal, engine
from src.infrastructure.repositories.sql_game_repository import SqlGameRepository
from src.infrastructure.repositories.sql_player_repository import SqlPlayerRepository
from src.infrastructure.repositories.sql_user_repository import SqlUserRepository
from src.infrastructure.repositories.sql_theme_repository import SqlThemeRepository
from src.infrastructure.repositories.sql_rule_preset_repository import SqlRulePresetRepository
from src.infrastructure.security.password import hash_password, verify_password
from src.infrastructure.security.token import create_access_token, decode_access_token
from src.presentation.routers.auth_router import (
    register,
    login,
    get_me,
    RegisterRequest,
    LoginRequest,
)
from src.presentation.routers.games_router import (
    create_game,
    get_game_by_code,
    join_game_room,
    start_game_room,
    JoinGameRequest,
)
from src.presentation.schemas.action_schemas import CreateGameRequest
from src.presentation.websocket_manager import ConnectionManager, broadcast_game_event_sync
from src.domain.models.enums import GameStatus


class MockWebSocket:
    def __init__(self):
        self.sent_messages = []
        self.closed = False

    async def accept(self):
        pass

    async def send_json(self, data: dict):
        self.sent_messages.append(data)

    async def close(self):
        self.closed = True


class TestAuthAndLobby(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self.game_repo = SqlGameRepository(self.session)
        self.player_repo = SqlPlayerRepository(self.session)
        self.user_repo = SqlUserRepository(self.session)
        self.theme_repo = SqlThemeRepository(self.session)
        self.preset_repo = SqlRulePresetRepository(self.session)
        self.games_to_cleanup = []

    def tearDown(self):
        for gid in self.games_to_cleanup:
            try:
                self.game_repo.delete(gid)
            except Exception:
                pass
        self.session.close()

    def test_security_hash_and_token(self):
        # 1. Hashing
        pwd = "SecretPassword123!"
        hashed = hash_password(pwd)
        self.assertTrue(verify_password(pwd, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

        # 2. Token creation and decoding
        token = create_access_token(user_id=42, username="player_one")
        decoded = decode_access_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["sub"], 42)
        self.assertEqual(decoded["username"], "player_one")

        # Invalid token
        self.assertIsNone(decode_access_token("invalid.token.payload"))

    def test_auth_endpoints_register_login_me(self):
        # 1. Register new user with unique username
        username = "wizard_test_user"
        reg_req = RegisterRequest(
            username=username,
            password="MagicalPassword99!",
            email="builder_test@hogwarts.local",
            display_name="El Mago",
        )
        # Limpiar si ya existiera de una ejecución previa
        existing = self.user_repo.get_by_username(username)
        if not existing:
            auth_res = register(reg_req, user_repo=self.user_repo)
            self.assertEqual(auth_res.user.username, username)
            self.assertEqual(auth_res.user.display_name, "El Mago")
            self.assertIsNotNone(auth_res.user.id)
            user_id = auth_res.user.id
        else:
            user_id = existing.id

        # 2. Duplicate registration fails (400)
        with self.assertRaises(HTTPException) as ctx:
            register(reg_req, user_repo=self.user_repo)
        self.assertEqual(ctx.exception.status_code, 400)

        # 3. Login success
        login_req = LoginRequest(username=username, password="MagicalPassword99!")
        auth_token = login(login_req, user_repo=self.user_repo)
        self.assertEqual(auth_token.token_type, "bearer")
        self.assertIsNotNone(auth_token.access_token)

        # 4. Login invalid password fails (401)
        with self.assertRaises(HTTPException) as ctx:
            login(LoginRequest(username=username, password="WrongPassword!"), user_repo=self.user_repo)
        self.assertEqual(ctx.exception.status_code, 401)

        # 5. /auth/me
        current_user = self.user_repo.get_by_id(user_id)
        me = get_me(current_user=current_user)
        self.assertEqual(me.username, username)
        self.assertEqual(me.email, "builder_test@hogwarts.local")

    def test_lobby_cycle_by_code_join_and_start(self):
        # 1. Registrar usuario anfitrión si no existe
        host_uname = "host_lobby_player"
        host_entity = self.user_repo.get_by_username(host_uname)
        if not host_entity:
            auth_host = register(
                RegisterRequest(username=host_uname, password="Password123!"),
                user_repo=self.user_repo,
            )
            host_entity = self.user_repo.get_by_id(auth_host.user.id)

        # 2. Crear sala por el anfitrión con código único
        code = f"SALA_{hash_password('salt')[:6].upper()}"
        game_payload = CreateGameRequest(code=code, variant="CLASSIC", theme_id="classic")
        game = create_game(
            payload=game_payload,
            current_user=host_entity,
            game_repo=self.game_repo,
            preset_repo=self.preset_repo,
        )
        self.games_to_cleanup.append(game.id)
        self.assertEqual(game.code, code)
        self.assertEqual(game.owner_user_id, host_entity.id)
        self.assertEqual(game.status, GameStatus.WAITING.value)

        # 3. Buscar sala por código
        found_game = get_game_by_code(code=code, game_repo=self.game_repo)
        self.assertEqual(found_game.id, game.id)

        # Código inexistente -> 404
        with self.assertRaises(HTTPException) as ctx:
            get_game_by_code(code="INEXISTENTE_XYZ", game_repo=self.game_repo)
        self.assertEqual(ctx.exception.status_code, 404)

        # 4. Iniciar con 0 jugadores falla (400)
        with self.assertRaises(HTTPException) as ctx:
            start_game_room(
                game_id=game.id,
                current_user=host_entity,
                game_repo=self.game_repo,
                player_repo=self.player_repo,
                theme_repo=self.theme_repo,
            )
        self.assertEqual(ctx.exception.status_code, 400)

        # 5. Unirse Jugador 1
        p1 = join_game_room(
            game_id=game.id,
            payload=JoinGameRequest(name="Harry", token="Sombrero"),
            current_user=host_entity,
            game_repo=self.game_repo,
            player_repo=self.player_repo,
        )
        self.assertEqual(p1.name, "Harry")
        self.assertEqual(p1.token, "Sombrero")
        self.assertEqual(p1.user_id, host_entity.id)

        # Intento de duplicar nombre -> 400
        with self.assertRaises(HTTPException) as ctx:
            join_game_room(
                game_id=game.id,
                payload=JoinGameRequest(name="harry", token="Auto"),
                current_user=None,
                game_repo=self.game_repo,
                player_repo=self.player_repo,
            )
        self.assertEqual(ctx.exception.status_code, 400)

        # Intento de duplicar token -> 400
        with self.assertRaises(HTTPException) as ctx:
            join_game_room(
                game_id=game.id,
                payload=JoinGameRequest(name="Ron", token="Sombrero"),
                current_user=None,
                game_repo=self.game_repo,
                player_repo=self.player_repo,
            )
        self.assertEqual(ctx.exception.status_code, 400)

        # Unirse Jugador 2 (invitado)
        p2 = join_game_room(
            game_id=game.id,
            payload=JoinGameRequest(name="Hermione", token="Gato"),
            current_user=None,
            game_repo=self.game_repo,
            player_repo=self.player_repo,
        )
        self.assertEqual(p2.name, "Hermione")
        self.assertIsNone(p2.user_id)

        # 6. Iniciar sala exitosamente
        started = start_game_room(
            game_id=game.id,
            current_user=host_entity,
            game_repo=self.game_repo,
            player_repo=self.player_repo,
            theme_repo=self.theme_repo,
        )
        self.assertEqual(started.status, GameStatus.IN_PROGRESS.value)
        self.assertEqual(started.current_turn, 1)
        self.assertEqual(started.current_player_index, 0)

        # Mazos barajados en la entidad
        saved_game = self.game_repo.get_by_id(game.id)
        self.assertIsNotNone(saved_game.chance_deck_order)
        self.assertIsNotNone(saved_game.community_chest_deck_order)
        self.assertGreater(len(saved_game.chance_deck_order), 0)
        self.assertGreater(len(saved_game.community_chest_deck_order), 0)

        # Intento de unirse a partida ya iniciada -> 400
        with self.assertRaises(HTTPException) as ctx:
            join_game_room(
                game_id=game.id,
                payload=JoinGameRequest(name="Neville", token="Perro"),
                current_user=None,
                game_repo=self.game_repo,
                player_repo=self.player_repo,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_websocket_connection_manager(self):
        manager = ConnectionManager()
        mock_ws = MockWebSocket()

        # Connect
        asyncio.run(manager.connect(game_id=10, websocket=mock_ws))
        self.assertEqual(manager.get_connected_count(10), 1)

        # Broadcast
        asyncio.run(manager.broadcast(game_id=10, event_type="TEST_EVENT", data={"msg": "Hola"}))
        self.assertEqual(len(mock_ws.sent_messages), 1)
        self.assertEqual(mock_ws.sent_messages[0]["event"], "TEST_EVENT")
        self.assertEqual(mock_ws.sent_messages[0]["data"]["msg"], "Hola")

        # Disconnect
        asyncio.run(manager.disconnect(game_id=10, websocket=mock_ws))
        self.assertEqual(manager.get_connected_count(10), 0)

        # Broadcast sync helper executes without error even when no loop is running
        broadcast_game_event_sync(game_id=999, event_type="EVENT_SYNC", data={})


if __name__ == "__main__":
    unittest.main()
