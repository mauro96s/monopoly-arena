from fastapi import Depends
from sqlalchemy.orm import Session
from src.infrastructure.database import get_db
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.infrastructure.repositories.sql_game_repository import SqlGameRepository
from src.infrastructure.repositories.sql_player_repository import SqlPlayerRepository
from src.infrastructure.repositories.sql_property_repository import SqlPropertyRepository
from src.infrastructure.repositories.sql_transaction_repository import SqlTransactionRepository
from src.application.use_cases.buy_property import BuyPropertyUseCase
from src.application.use_cases.transfer_money import TransferMoneyUseCase
from src.application.use_cases.pay_rent import PayRentUseCase
from src.application.use_cases.build_house import BuildHouseUseCase
from src.application.use_cases.mortgage_property import MortgagePropertyUseCase
from src.application.use_cases.jail_action import JailActionUseCase
from src.application.use_cases.bank_action import BankActionUseCase
from src.application.use_cases.roll_dice import RollDiceUseCase
from src.application.use_cases.finish_game import FinishGameUseCase


# Inyección de Repositorios cumpliendo Dependency Inversion
def get_game_repository(db: Session = Depends(get_db)) -> GameRepositoryProtocol:
    return SqlGameRepository(db)


def get_player_repository(db: Session = Depends(get_db)) -> PlayerRepositoryProtocol:
    return SqlPlayerRepository(db)


def get_property_repository(db: Session = Depends(get_db)) -> PropertyRepositoryProtocol:
    return SqlPropertyRepository(db)


def get_transaction_repository(db: Session = Depends(get_db)) -> TransactionRepositoryProtocol:
    return SqlTransactionRepository(db)


# Inyección de Casos de Uso
def get_buy_property_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> BuyPropertyUseCase:
    return BuyPropertyUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        property_repo=property_repo,
        transaction_repo=transaction_repo,
    )


def get_transfer_money_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> TransferMoneyUseCase:
    return TransferMoneyUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        transaction_repo=transaction_repo,
    )


def get_pay_rent_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> PayRentUseCase:
    return PayRentUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        property_repo=property_repo,
        transaction_repo=transaction_repo,
    )


def get_build_house_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> BuildHouseUseCase:
    return BuildHouseUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        property_repo=property_repo,
        transaction_repo=transaction_repo,
    )


def get_mortgage_property_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> MortgagePropertyUseCase:
    return MortgagePropertyUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        property_repo=property_repo,
        transaction_repo=transaction_repo,
    )


def get_jail_action_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> JailActionUseCase:
    return JailActionUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        transaction_repo=transaction_repo,
    )


def get_bank_action_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> BankActionUseCase:
    return BankActionUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        property_repo=property_repo,
        transaction_repo=transaction_repo,
    )


def get_finish_game_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> FinishGameUseCase:
    return FinishGameUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        property_repo=property_repo,
        transaction_repo=transaction_repo,
    )


def get_roll_dice_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> RollDiceUseCase:
    return RollDiceUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        property_repo=property_repo,
        transaction_repo=transaction_repo,
    )
