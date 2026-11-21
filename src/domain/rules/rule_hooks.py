from typing import Protocol, List, Optional
from src.domain.models.game import Game
from src.domain.models.player import Player


class GameRuleHook(Protocol):
    """
    Protocolo para interceptar y modificar eventos del juego siguiendo OCP e ISP.
    Permite a expansiones y reglas de la casa modificar dinámicamente el comportamiento.
    """
    def calculate_go_salary(self, game: Game, player: Player, is_exact_landing: bool) -> int:
        ...

    def process_tax_or_fine(self, game: Game, player: Player, amount: int) -> int:
        ...

    def process_free_parking(self, game: Game, player: Player) -> int:
        ...

    def can_collect_rent(self, game: Game, owner: Player) -> bool:
        ...


class ClassicRulesHook:
    """Implementación oficial estándar del Monopoly clásico."""

    def calculate_go_salary(self, game: Game, player: Player, is_exact_landing: bool) -> int:
        cfg = game.get_ruleset()
        return cfg.go_salary

    def process_tax_or_fine(self, game: Game, player: Player, amount: int) -> int:
        # En el juego clásico, los impuestos y multas van directos al Banco (no al pozo)
        return 0

    def process_free_parking(self, game: Game, player: Player) -> int:
        # En el juego clásico, el Parking Gratuito es solo una casilla de descanso
        return 0

    def can_collect_rent(self, game: Game, owner: Player) -> bool:
        cfg = game.get_ruleset()
        if owner.in_jail and not cfg.collect_rent_in_jail:
            return False
        return True


class FreeParkingJackpotHook:
    """Regla de la casa: Pozo acumulativo en Parking Gratuito."""

    def calculate_go_salary(self, game: Game, player: Player, is_exact_landing: bool) -> int:
        return game.get_ruleset().go_salary

    def process_tax_or_fine(self, game: Game, player: Player, amount: int) -> int:
        if amount > 0:
            game.free_parking_pool += amount
            return amount
        return 0

    def process_free_parking(self, game: Game, player: Player) -> int:
        jackpot = game.free_parking_pool
        if jackpot > 0:
            player.add_money(jackpot)
            game.free_parking_pool = 0
            return jackpot
        return 0

    def can_collect_rent(self, game: Game, owner: Player) -> bool:
        return True


class DoubleSalaryExactGoHook:
    """Regla de la casa: Cobro de salario doble al caer exactamente en la casilla de Salida."""

    def calculate_go_salary(self, game: Game, player: Player, is_exact_landing: bool) -> int:
        cfg = game.get_ruleset()
        base = cfg.go_salary
        return base * 2 if is_exact_landing else base

    def process_tax_or_fine(self, game: Game, player: Player, amount: int) -> int:
        return 0

    def process_free_parking(self, game: Game, player: Player) -> int:
        return 0

    def can_collect_rent(self, game: Game, owner: Player) -> bool:
        return True


class RulesetEngine:
    """
    Despachador central de reglas de juego configurables (Open/Closed Principle).
    """

    @classmethod
    def calculate_go_salary(cls, game: Game, player: Player, is_exact_landing: bool) -> int:
        cfg = game.get_ruleset()
        if cfg.double_salary_on_exact_go and is_exact_landing:
            return DoubleSalaryExactGoHook().calculate_go_salary(game, player, is_exact_landing)
        return ClassicRulesHook().calculate_go_salary(game, player, is_exact_landing)

    @classmethod
    def process_tax_or_fine(cls, game: Game, player: Player, amount: int) -> int:
        cfg = game.get_ruleset()
        if cfg.free_parking_jackpot:
            return FreeParkingJackpotHook().process_tax_or_fine(game, player, amount)
        return ClassicRulesHook().process_tax_or_fine(game, player, amount)

    @classmethod
    def process_free_parking(cls, game: Game, player: Player) -> int:
        cfg = game.get_ruleset()
        if cfg.free_parking_jackpot:
            return FreeParkingJackpotHook().process_free_parking(game, player)
        return ClassicRulesHook().process_free_parking(game, player)

    @classmethod
    def can_collect_rent(cls, game: Game, owner: Player) -> bool:
        cfg = game.get_ruleset()
        if owner.in_jail and not cfg.collect_rent_in_jail:
            return False
        return True
