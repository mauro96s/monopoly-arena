import unittest
from typing import Optional, List
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.models import Game, Player, PropertyState, Transaction
from src.domain.models.enums import GameVariant, GameStatus
from src.domain.exceptions import InsufficientFundsError, PropertyAlreadyOwnedError, InvalidGameActionError
from src.application.use_cases.buy_property import BuyPropertyUseCase
from src.application.dtos.action_dtos import BuyPropertyInputDTO


class InMemoryGameRepository(GameRepositoryProtocol):
    def __init__(self):
        self.games = {}

    def get_by_id(self, game_id: int) -> Optional[Game]:
        return self.games.get(game_id)

    def get_by_code(self, code: str) -> Optional[Game]:
        return next((g for g in self.games.values() if g.code == code), None)

    def list_all(self, limit: int = 20) -> List[Game]:
        return list(self.games.values())[:limit]

    def save(self, game: Game) -> Game:
        if game.id is None:
            game.id = len(self.games) + 1
        self.games[game.id] = game
        return game


class InMemoryPlayerRepository(PlayerRepositoryProtocol):
    def __init__(self):
        self.players = {}

    def get_by_id(self, player_id: int) -> Optional[Player]:
        return self.players.get(player_id)

    def list_by_game(self, game_id: int) -> List[Player]:
        return [p for p in self.players.values() if p.game_id == game_id]

    def save(self, player: Player) -> Player:
        if player.id is None:
            player.id = len(self.players) + 1
        self.players[player.id] = player
        return player


class InMemoryPropertyRepository(PropertyRepositoryProtocol):
    def __init__(self):
        self.properties = {}

    def get_by_tile(self, game_id: int, tile_id: str) -> Optional[PropertyState]:
        return self.properties.get((game_id, tile_id))

    def list_by_game(self, game_id: int) -> List[PropertyState]:
        return [p for (gid, _), p in self.properties.items() if gid == game_id]

    def list_by_owner(self, game_id: int, owner_id: int) -> List[PropertyState]:
        return [p for p in self.properties.values() if p.game_id == game_id and p.owner_id == owner_id]

    def save(self, property_state: PropertyState) -> PropertyState:
        if property_state.id is None:
            property_state.id = len(self.properties) + 1
        self.properties[(property_state.game_id, property_state.tile_id)] = property_state
        return property_state


class InMemoryTransactionRepository(TransactionRepositoryProtocol):
    def __init__(self):
        self.transactions = []

    def record(self, transaction: Transaction) -> Transaction:
        if transaction.id is None:
            transaction.id = len(self.transactions) + 1
        self.transactions.append(transaction)
        return transaction

    def list_by_game(self, game_id: int, limit: int = 50) -> List[Transaction]:
        return [t for t in self.transactions if t.game_id == game_id][:limit]


class TestPureDomainAndUseCase(unittest.TestCase):
    def setUp(self):
        self.game_repo = InMemoryGameRepository()
        self.player_repo = InMemoryPlayerRepository()
        self.prop_repo = InMemoryPropertyRepository()
        self.tx_repo = InMemoryTransactionRepository()

        self.use_case = BuyPropertyUseCase(
            game_repo=self.game_repo,
            player_repo=self.player_repo,
            property_repo=self.prop_repo,
            transaction_repo=self.tx_repo,
        )

        self.game = self.game_repo.save(
            Game(id=None, code="SALA777", variant=GameVariant.CLASSIC, status=GameStatus.IN_PROGRESS)
        )
        self.player = self.player_repo.save(
            Player(id=None, game_id=self.game.id, name="Carlos", token="Dedal", money=1500)
        )

    def test_buy_boardwalk_successfully(self):
        dto = BuyPropertyInputDTO(game_id=self.game.id, player_id=self.player.id, tile_id="BOARDWALK")
        result = self.use_case.execute(dto)

        self.assertEqual(result.price_paid, 400)
        self.assertEqual(result.remaining_balance, 1100)
        self.assertEqual(self.player.money, 1100)
        self.assertEqual(len(self.tx_repo.transactions), 1)

    def test_buy_tile_that_cannot_be_purchased_fails(self):
        # GO (Salida) no puede comprarse
        dto = BuyPropertyInputDTO(game_id=self.game.id, player_id=self.player.id, tile_id="GO")
        with self.assertRaises(InvalidGameActionError):
            self.use_case.execute(dto)

    def test_insufficient_funds(self):
        self.player.money = 100
        dto = BuyPropertyInputDTO(game_id=self.game.id, player_id=self.player.id, tile_id="BOARDWALK")
        with self.assertRaises(InsufficientFundsError):
            self.use_case.execute(dto)


if __name__ == "__main__":
    unittest.main()
