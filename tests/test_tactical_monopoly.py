import unittest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.infrastructure.database import Base
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
    RollDiceUseCase,
)
from src.application.dtos.action_dtos import (
    BuyPropertyInputDTO,
    PayRentInputDTO,
    BuildHouseInputDTO,
    JailActionInputDTO,
    BankActionInputDTO,
    RollDiceInputDTO,
)
from src.domain.models import Game, Player
from src.domain.models.enums import GameVariant, GameStatus
from src.domain.exceptions import InvalidGameActionError, InsufficientFundsError


class TestTacticalMonopolyFeatures(unittest.TestCase):
    def setUp(self):
        # Base de datos en memoria 100% aislada para tests
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
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
        self.jail_uc = JailActionUseCase(self.game_repo, self.player_repo, self.tx_repo, self.property_repo)
        self.bank_uc = BankActionUseCase(self.game_repo, self.player_repo, self.property_repo, self.tx_repo)
        self.finish_uc = FinishGameUseCase(self.game_repo, self.player_repo, self.property_repo, self.tx_repo)
        self.roll_uc = RollDiceUseCase(self.game_repo, self.player_repo, self.property_repo, self.tx_repo)

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)

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
        self.assertEqual(jail_res.jail_turns, 0)

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

    def test_manual_bank_action_credit_and_debit(self):
        # El Banco paga $200 a Ana
        credit_res = self.bank_uc.execute(BankActionInputDTO(
            game_id=self.game.id,
            player_id=self.p1.id,
            action_type="BANK_PAYS_PLAYER",
            custom_amount=200,
            description="Premio",
            auto_advance_turn=False,
        ))
        self.assertTrue(credit_res.is_credit)
        self.assertEqual(credit_res.remaining_balance, 1700)

        # Ana paga $150 al Banco
        debit_res = self.bank_uc.execute(BankActionInputDTO(
            game_id=self.game.id,
            player_id=self.p1.id,
            action_type="PLAYER_PAYS_BANK",
            custom_amount=150,
            description="Impuesto",
            auto_advance_turn=False,
        ))
        self.assertFalse(debit_res.is_credit)
        self.assertEqual(debit_res.remaining_balance, 1550)

        # Fondos insuficientes
        with self.assertRaises(InsufficientFundsError):
            self.bank_uc.execute(BankActionInputDTO(
                game_id=self.game.id,
                player_id=self.p1.id,
                action_type="PLAYER_PAYS_BANK",
                custom_amount=99999,
                auto_advance_turn=False,
            ))

    def test_advance_turn_jail_turn_increment_and_lock(self):
        from src.presentation.routers.games_router import advance_turn
        from fastapi import HTTPException

        # Poner a Ana en la cárcel
        self.jail_uc.execute(JailActionInputDTO(
            game_id=self.game.id, player_id=self.p1.id, action="GO_TO_JAIL", auto_advance_turn=False
        ))
        ana = self.player_repo.get_by_id(self.p1.id)
        self.assertTrue(ana.in_jail)
        self.assertEqual(ana.jail_turns, 0)

        # Es el turno de Ana (índice 0). Avanzar turno incrementa su turno de cárcel a 1
        advance_turn(self.game.id, self.game_repo, self.player_repo, self.tx_repo)
        ana = self.player_repo.get_by_id(self.p1.id)
        self.assertEqual(ana.jail_turns, 1)

        # Completar la ronda de Beto y Carlos para volver a Ana
        advance_turn(self.game.id, self.game_repo, self.player_repo, self.tx_repo) # Beto
        advance_turn(self.game.id, self.game_repo, self.player_repo, self.tx_repo) # Carlos

        # Ana vuelve a estar en turno con jail_turns = 1. Al avanzar turno se incrementa a 2
        advance_turn(self.game.id, self.game_repo, self.player_repo, self.tx_repo)
        ana = self.player_repo.get_by_id(self.p1.id)
        self.assertEqual(ana.jail_turns, 2)

        # Completar la ronda de nuevo para volver a Ana
        advance_turn(self.game.id, self.game_repo, self.player_repo, self.tx_repo) # Beto
        advance_turn(self.game.id, self.game_repo, self.player_repo, self.tx_repo) # Carlos

        # Ana vuelve a estar en turno con jail_turns = 2. Al avanzar turno se incrementa a 3
        advance_turn(self.game.id, self.game_repo, self.player_repo, self.tx_repo)
        ana = self.player_repo.get_by_id(self.p1.id)
        self.assertEqual(ana.jail_turns, 3)

        # Completar la ronda de nuevo para que sea el turno de Ana con 3 turnos cumplidos
        advance_turn(self.game.id, self.game_repo, self.player_repo, self.tx_repo) # Beto
        advance_turn(self.game.id, self.game_repo, self.player_repo, self.tx_repo) # Carlos

        # Ahora Ana tiene jail_turns = 3 y es su turno. Intentar pasar turno debe bloquearse con HTTP 400
        with self.assertRaises(HTTPException) as cm:
            advance_turn(self.game.id, self.game_repo, self.player_repo, self.tx_repo)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("3 turnos en la Cárcel", cm.exception.detail)

    def test_delete_single_and_bulk_games(self):
        # Crear 2 partidas adicionales
        g1 = self.game_repo.save(Game(id=None, code=f"DEL1-{uuid.uuid4().hex[:4]}", variant=GameVariant.CLASSIC, status=GameStatus.WAITING))
        g2 = self.game_repo.save(Game(id=None, code=f"DEL2-{uuid.uuid4().hex[:4]}", variant=GameVariant.CLASSIC, status=GameStatus.WAITING))

        # Eliminar g1 individualmente
        self.assertTrue(self.game_repo.delete(g1.id))
        self.assertIsNone(self.game_repo.get_by_id(g1.id))

        # Eliminar g2 en lote
        deleted_count = self.game_repo.delete_bulk([g2.id])
        self.assertEqual(deleted_count, 1)
        self.assertIsNone(self.game_repo.get_by_id(g2.id))

    def test_roll_dice_movement_and_pass_go(self):
        # Ana tira 3 + 4 = 7 desde posición 0
        self.p1.position = 0
        self.player_repo.save(self.p1)

        roll_res = self.roll_uc.execute(RollDiceInputDTO(
            game_id=self.game.id, player_id=self.p1.id, dice_1=3, dice_2=4
        ))
        self.assertEqual(roll_res.old_position, 0)
        self.assertEqual(roll_res.new_position, 7)
        self.assertEqual(roll_res.total_roll, 7)
        self.assertFalse(roll_res.passed_go)

        # Simular avance de turno para permitir nueva tirada
        self.game.has_rolled_dice = False
        self.game_repo.save(self.game)

        # Ana se encuentra en pos 38 y tira 3 -> avanza a pos 1 (Mediterráneo) pasando por la SALIDA
        self.p1.position = 38
        self.p1.money = 1000
        self.player_repo.save(self.p1)

        roll_res2 = self.roll_uc.execute(RollDiceInputDTO(
            game_id=self.game.id, player_id=self.p1.id, dice_1=1, dice_2=2
        ))
        self.assertEqual(roll_res2.old_position, 38)
        self.assertEqual(roll_res2.new_position, 1)
        self.assertTrue(roll_res2.passed_go)
        # Saldo aumenta automáticamente en $200
        p1_updated = self.player_repo.get_by_id(self.p1.id)
        self.assertEqual(p1_updated.money, 1200)

    def test_roll_dice_enforce_single_roll_per_turn(self):
        # Ana tira los dados sin sacar dobles (2 + 4 = 6, Av. Oriental)
        self.roll_uc.execute(RollDiceInputDTO(
            game_id=self.game.id, player_id=self.p1.id, dice_1=2, dice_2=4
        ))
        # Intento de 2da tirada en el mismo turno debe ser rechazado
        with self.assertRaises(InvalidGameActionError):
            self.roll_uc.execute(RollDiceInputDTO(
                game_id=self.game.id, player_id=self.p1.id, dice_1=2, dice_2=3
            ))

    def test_roll_dice_doubles_and_3rd_doubles_jail(self):
        # 1er doble: 4 + 4 -> otorga turno extra
        res1 = self.roll_uc.execute(RollDiceInputDTO(
            game_id=self.game.id, player_id=self.p1.id, dice_1=4, dice_2=4
        ))
        self.assertTrue(res1.is_doubles)
        self.assertTrue(res1.extra_turn)
        self.assertEqual(res1.consecutive_doubles, 1)

        # 2do doble: 5 + 5 -> otorga turno extra
        res2 = self.roll_uc.execute(RollDiceInputDTO(
            game_id=self.game.id, player_id=self.p1.id, dice_1=5, dice_2=5
        ))
        self.assertTrue(res2.is_doubles)
        self.assertTrue(res2.extra_turn)
        self.assertEqual(res2.consecutive_doubles, 2)

        # 3er doble: 6 + 6 -> ¡DIRECTO A LA CÁRCEL!
        res3 = self.roll_uc.execute(RollDiceInputDTO(
            game_id=self.game.id, player_id=self.p1.id, dice_1=6, dice_2=6
        ))
        self.assertEqual(res3.action_required, "WENT_TO_JAIL")
        self.assertEqual(res3.new_position, 10)
        self.assertFalse(res3.extra_turn)

        p1_updated = self.player_repo.get_by_id(self.p1.id)
        self.assertTrue(p1_updated.in_jail)
        self.assertEqual(p1_updated.position, 10)

        # Comprobar que avanzó el turno al rival
        g_updated = self.game_repo.get_by_id(self.game.id)
        self.assertEqual(g_updated.current_player_index, 1)

    def test_roll_dice_automatic_rent_and_tax(self):
        # Beto compra BOARDWALK (pos 39)
        self.p2.position = 39
        self.player_repo.save(self.p2)
        self.game.current_player_index = 1
        self.game_repo.save(self.game)

        self.buy_uc.execute(BuyPropertyInputDTO(
            game_id=self.game.id, player_id=self.p2.id, tile_id="BOARDWALK", auto_advance_turn=False
        ))
        beto_balance_after_buy = self.player_repo.get_by_id(self.p2.id).money

        # Ahora es turno de Ana (jugador 0)
        self.game.current_player_index = 0
        self.game.has_rolled_dice = False
        self.game_repo.save(self.game)

        # Ana está en pos 35 y tira 4 -> cae exactamente en BOARDWALK (pos 39)
        self.p1.position = 35
        self.p1.money = 1000
        self.player_repo.save(self.p1)

        res = self.roll_uc.execute(RollDiceInputDTO(
            game_id=self.game.id, player_id=self.p1.id, total_roll=4
        ))
        self.assertEqual(res.action_required, "RENT_PAID_AUTOMATICALLY")
        self.assertEqual(res.action_details["owner_id"], self.p2.id)

        # Saldo de Ana descontado y Beto cobró renta de Boardwalk ($50 renta base)
        p1_after = self.player_repo.get_by_id(self.p1.id)
        p2_after = self.player_repo.get_by_id(self.p2.id)
        self.assertEqual(p1_after.money, 950)
        self.assertEqual(p2_after.money, beto_balance_after_buy + 50)

    def test_jail_flow_try_doubles_and_mandatory_3rd_turn(self):
        # Ana está en la cárcel con 0 turnos acumulados
        self.p1.in_jail = True
        self.p1.jail_turns = 0
        self.p1.position = 10
        self.player_repo.save(self.p1)

        # 1. Tirar en cárcel sin dobles (1 + 2 = 3)
        res_fail = self.jail_uc.execute(JailActionInputDTO(
            game_id=self.game.id, player_id=self.p1.id, action="TRY_DOUBLES", dice_1=1, dice_2=2
        ))
        self.assertTrue(res_fail.in_jail)
        self.assertEqual(res_fail.jail_turns, 1)

        # El turno finalizó y pasó al siguiente jugador
        g1 = self.game_repo.get_by_id(self.game.id)
        self.assertEqual(g1.current_player_index, 1)

        # Devolver turno a Ana (simulando 2da ronda)
        self.game.current_player_index = 0
        self.game_repo.save(self.game)

        # 2. 2do turno en cárcel sin dobles (3 + 4 = 7)
        res_fail2 = self.jail_uc.execute(JailActionInputDTO(
            game_id=self.game.id, player_id=self.p1.id, action="TRY_DOUBLES", dice_1=3, dice_2=4
        ))
        self.assertEqual(res_fail2.jail_turns, 2)

        # Devolver turno a Ana (simulando 3ra ronda)
        self.game.current_player_index = 0
        self.game_repo.save(self.game)

        # 3. 3er turno en cárcel sin dobles (1 + 3 = 4)
        res_fail3 = self.jail_uc.execute(JailActionInputDTO(
            game_id=self.game.id, player_id=self.p1.id, action="TRY_DOUBLES", dice_1=1, dice_2=3
        ))
        self.assertEqual(res_fail3.jail_turns, 3)

        # Devolver turno a Ana (este es su 4to turno / habiendo cumplido sus 3 turnos fallidos)
        self.game.current_player_index = 0
        self.game_repo.save(self.game)

        # 4. Intentar sacar dobles tras 3 turnos cumplidos DEBE ESTAR BLOQUEADO
        with self.assertRaises(InvalidGameActionError):
            self.jail_uc.execute(JailActionInputDTO(
                game_id=self.game.id, player_id=self.p1.id, action="TRY_DOUBLES", dice_1=5, dice_2=5
            ))

        # 5. Pagar fianza obligatoria de $50
        res_pay = self.jail_uc.execute(JailActionInputDTO(
            game_id=self.game.id, player_id=self.p1.id, action="PAY_FINE"
        ))
        self.assertFalse(res_pay.in_jail)
        self.assertEqual(res_pay.amount_paid, 50)
        # Comprobar que game.has_rolled_dice == False (puede tirar para moverse en este turno)
        g_ready = self.game_repo.get_by_id(self.game.id)
        self.assertFalse(g_ready.has_rolled_dice)


if __name__ == "__main__":
    unittest.main()
