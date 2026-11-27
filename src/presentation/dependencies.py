from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from src.infrastructure.database import get_db
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.interfaces.rule_preset_repository import RulePresetRepositoryProtocol
from src.domain.interfaces.theme_repository import ThemeRepositoryProtocol
from src.domain.interfaces.user_repository import UserRepositoryProtocol
from src.domain.models.user import User
from src.infrastructure.repositories.sql_rule_preset_repository import SqlRulePresetRepository
from src.infrastructure.repositories.sql_theme_repository import SqlThemeRepository
from src.infrastructure.repositories.sql_user_repository import SqlUserRepository
from src.infrastructure.security.token import decode_access_token
from src.infrastructure.repositories.sql_game_repository import SqlGameRepository
from src.infrastructure.repositories.sql_player_repository import SqlPlayerRepository
from src.infrastructure.repositories.sql_property_repository import SqlPropertyRepository
from src.infrastructure.repositories.sql_transaction_repository import SqlTransactionRepository
from src.application.use_cases.buy_property import BuyPropertyUseCase
from src.application.use_cases.auction_property import AuctionPropertyUseCase
from src.application.use_cases.transfer_money import TransferMoneyUseCase
from src.application.use_cases.pay_rent import PayRentUseCase
from src.application.use_cases.build_house import BuildHouseUseCase
from src.application.use_cases.sell_building import SellBuildingUseCase
from src.application.use_cases.mortgage_property import MortgagePropertyUseCase
from src.application.use_cases.declare_bankruptcy import DeclareBankruptcyUseCase
from src.application.use_cases.jail_action import JailActionUseCase
from src.application.use_cases.bank_action import BankActionUseCase
from src.application.use_cases.roll_dice import RollDiceUseCase
from src.application.use_cases.finish_game import FinishGameUseCase
from src.application.use_cases.draw_card import DrawCardUseCase


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


def get_auction_property_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> AuctionPropertyUseCase:
    return AuctionPropertyUseCase(
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


def get_sell_building_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> SellBuildingUseCase:
    return SellBuildingUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        property_repo=property_repo,
        transaction_repo=transaction_repo,
    )


def get_declare_bankruptcy_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> DeclareBankruptcyUseCase:
    return DeclareBankruptcyUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        property_repo=property_repo,
        transaction_repo=transaction_repo,
    )


def get_draw_card_use_case(
    game_repo: GameRepositoryProtocol = Depends(get_game_repository),
    player_repo: PlayerRepositoryProtocol = Depends(get_player_repository),
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
    transaction_repo: TransactionRepositoryProtocol = Depends(get_transaction_repository),
) -> DrawCardUseCase:
    return DrawCardUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        property_repo=property_repo,
        tx_repo=transaction_repo,
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
    property_repo: PropertyRepositoryProtocol = Depends(get_property_repository),
) -> JailActionUseCase:
    return JailActionUseCase(
        game_repo=game_repo,
        player_repo=player_repo,
        transaction_repo=transaction_repo,
        property_repo=property_repo,
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


get_move_player_by_dice_use_case = get_roll_dice_use_case


def get_rule_preset_repository(db: Session = Depends(get_db)) -> RulePresetRepositoryProtocol:
    return SqlRulePresetRepository(db)


def get_theme_repository(db: Session = Depends(get_db)) -> ThemeRepositoryProtocol:
    return SqlThemeRepository(db)


def get_user_repository(db: Session = Depends(get_db)) -> UserRepositoryProtocol:
    return SqlUserRepository(db)


def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    user_repo: UserRepositoryProtocol = Depends(get_user_repository),
) -> Optional[User]:
    """
    Retorna el usuario autenticado si se proporciona un Bearer token válido.
    Si no hay token o es inválido, retorna None garantizando compatibilidad hacia atrás.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    return user_repo.get_by_id(int(payload["sub"]))


def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """Exige autenticación estricta (401 si no hay usuario válido)."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Token ausente o inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def assert_can_act_for_player(
    game: object,
    target_player: object,
    current_user: Optional[User] = None,
) -> None:
    """
    Control de autoría multijugador (SRP):
    - Si target_player.user_id es None (partida local o invitado en mesa), se permite la acción.
    - Si target_player.user_id tiene un usuario vinculado, exige que current_user esté autenticado
      y que current_user.id == target_player.user_id (o current_user.id == game.owner_user_id como anfitrión).
      En caso contrario responde 403 Forbidden.
    """
    if not target_player or getattr(target_player, "user_id", None) is None:
        return

    if not isinstance(current_user, User):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acción denegada: El jugador '{getattr(target_player, 'name', 'objetivo')}' pertenece a una cuenta registrada. Debes iniciar sesión con esa cuenta o ser el anfitrión de la sala.",
        )

    is_player_owner = (current_user.id == getattr(target_player, "user_id", None))
    game_owner = getattr(game, "owner_user_id", None)
    is_room_host = (game_owner is not None and current_user.id == game_owner)

    if not (is_player_owner or is_room_host):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acción denegada: No tienes autorización para actuar por el jugador '{getattr(target_player, 'name', 'objetivo')}'. Solo el usuario propietario o el anfitrión pueden ejecutar esta acción.",
        )
