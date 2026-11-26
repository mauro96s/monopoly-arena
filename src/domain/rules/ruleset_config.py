from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class RulesetConfig:
    """
    Configuración desacoplada de reglas y variantes del juego (OCP & SRP).
    Permite activar reglas de la casa y futuras expansiones sin acoplar los casos de uso.
    """
    strict_even_building: bool = True
    strict_bank_supply: bool = True
    auctions_enabled: bool = True
    free_parking_jackpot: bool = False       # Acumula multas e impuestos en un pozo para quien caiga en Parada Libre
    double_salary_on_exact_go: bool = False  # Paga $400 si cae exactamente en la casilla 0 (Salida)
    collect_rent_in_jail: bool = True        # Permite cobrar rentas a rivales mientras el dueño está preso
    go_salary: int = 200                     # Salario oficial al pasar por la Salida
    victory_mode: str = "LAST_MAN_STANDING"  # "LAST_MAN_STANDING" o "ALL_PROPERTIES_SOLD"
    disqualify_jailed_on_quick_end: bool = True  # Descalifica jugadores en prisión si se activa el fin rápido
    property_valuation_mode: str = "PURCHASE_PRICE"  # "PURCHASE_PRICE" o "MORTGAGE_VALUE"
    enabled_expansions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "RulesetConfig":
        if not data:
            return cls()
        return cls(
            strict_even_building=bool(data.get("strict_even_building", True)),
            strict_bank_supply=bool(data.get("strict_bank_supply", True)),
            auctions_enabled=bool(data.get("auctions_enabled", True)),
            free_parking_jackpot=bool(data.get("free_parking_jackpot", False)),
            double_salary_on_exact_go=bool(data.get("double_salary_on_exact_go", False)),
            collect_rent_in_jail=bool(data.get("collect_rent_in_jail", True)),
            go_salary=int(data.get("go_salary", 200)),
            victory_mode=str(data.get("victory_mode", "LAST_MAN_STANDING")),
            disqualify_jailed_on_quick_end=bool(data.get("disqualify_jailed_on_quick_end", True)),
            property_valuation_mode=str(data.get("property_valuation_mode", "PURCHASE_PRICE")),
            enabled_expansions=list(data.get("enabled_expansions", [])),
        )
