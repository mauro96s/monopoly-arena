from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Player:
    id: Optional[int]
    game_id: int
    name: str
    token: str
    money: int = 1500
    position: int = 0
    is_bankrupt: bool = False
    in_jail: bool = False
    jail_turns: int = 0

    def can_afford(self, amount: int) -> bool:
        return self.money >= amount

    def deduct_money(self, amount: int) -> None:
        if not self.can_afford(amount):
            raise ValueError(f"El jugador {self.name} no tiene suficientes fondos ({self.money} < {amount}).")
        self.money -= amount

    def add_money(self, amount: int) -> None:
        self.money += amount
