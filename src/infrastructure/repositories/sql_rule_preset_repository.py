import json
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.domain.interfaces.rule_preset_repository import RulePresetRepositoryProtocol
from src.domain.models.rule_preset import RulePreset
from src.domain.rules.ruleset_config import RulesetConfig
from src.domain.exceptions import InvalidGameActionError
from src.infrastructure.orm.models import RulePresetModel


class SqlRulePresetRepository(RulePresetRepositoryProtocol):
    def __init__(self, session: Session):
        self._session = session
        self._ensure_table_and_seed()

    def _ensure_table_and_seed(self) -> None:
        """Asegura la creación de la tabla e inserta los presets predeterminados del sistema."""
        try:
            self._session.execute(text("""
                CREATE TABLE IF NOT EXISTS rule_presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    description VARCHAR(255) NOT NULL DEFAULT '',
                    ruleset_config VARCHAR(1024) NOT NULL DEFAULT '{}',
                    is_system_default BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            self._session.commit()
        except Exception:
            self._session.rollback()

        # Sembrar presets predeterminados si la tabla está vacía
        try:
            count = self._session.query(RulePresetModel).count()
            if count == 0:
                self._seed_default_presets()
        except Exception:
            self._session.rollback()

    def _seed_default_presets(self) -> None:
        p1 = RulePresetModel(
            name="Oficial Clásico",
            description="Reglamento estándar oficial: victoria por último jugador en pie, inventario estricto de 32 casas y subastas obligatorias.",
            ruleset_config=json.dumps(RulesetConfig(
                victory_mode="LAST_MAN_STANDING",
                strict_even_building=True,
                strict_bank_supply=True,
                auctions_enabled=True,
                free_parking_jackpot=False,
                double_salary_on_exact_go=False,
                collect_rent_in_jail=True,
                go_salary=200,
            ).to_dict()),
            is_system_default=True,
        )

        p2 = RulePresetModel(
            name="Mesa Rápida (Fin al Agotar Calles)",
            description="Partida ágil: finaliza en cuanto se adquiere la última propiedad libre. Los jugadores en la cárcel quedan descalificados del podio.",
            ruleset_config=json.dumps(RulesetConfig(
                victory_mode="ALL_PROPERTIES_SOLD",
                disqualify_jailed_on_quick_end=True,
                property_valuation_mode="PURCHASE_PRICE",
                strict_even_building=True,
                strict_bank_supply=True,
                auctions_enabled=True,
                free_parking_jackpot=False,
                double_salary_on_exact_go=False,
                collect_rent_in_jail=True,
                go_salary=200,
            ).to_dict()),
            is_system_default=True,
        )

        self._session.add_all([p1, p2])
        self._session.commit()

    def _to_domain(self, model: RulePresetModel) -> RulePreset:
        raw_config = getattr(model, "ruleset_config", "{}")
        try:
            cfg_dict = json.loads(raw_config) if isinstance(raw_config, str) else (raw_config or {})
        except Exception:
            cfg_dict = {}

        return RulePreset(
            id=model.id,
            name=model.name,
            description=model.description or "",
            ruleset_config=RulesetConfig.from_dict(cfg_dict),
            is_system_default=bool(model.is_system_default),
            created_at=model.created_at,
        )

    def get_by_id(self, preset_id: int) -> Optional[RulePreset]:
        model = self._session.query(RulePresetModel).filter(RulePresetModel.id == preset_id).first()
        return self._to_domain(model) if model else None

    def get_by_name(self, name: str) -> Optional[RulePreset]:
        model = self._session.query(RulePresetModel).filter(RulePresetModel.name == name).first()
        return self._to_domain(model) if model else None

    def list_all(self) -> List[RulePreset]:
        models = self._session.query(RulePresetModel).order_by(
            RulePresetModel.is_system_default.desc(),
            RulePresetModel.created_at.asc()
        ).all()
        return [self._to_domain(m) for m in models]

    def save(self, preset: RulePreset) -> RulePreset:
        cfg_json = json.dumps(preset.ruleset_config.to_dict())

        if preset.id is None:
            model = RulePresetModel(
                name=preset.name,
                description=preset.description,
                ruleset_config=cfg_json,
                is_system_default=preset.is_system_default,
                created_at=preset.created_at,
            )
            self._session.add(model)
            self._session.commit()
            self._session.refresh(model)
            preset.id = model.id
            return preset
        else:
            model = self._session.query(RulePresetModel).filter(RulePresetModel.id == preset.id).first()
            if model:
                model.name = preset.name
                model.description = preset.description
                model.ruleset_config = cfg_json
                model.is_system_default = preset.is_system_default
                self._session.commit()
            return preset

    def delete(self, preset_id: int) -> bool:
        model = self._session.query(RulePresetModel).filter(RulePresetModel.id == preset_id).first()
        if not model:
            return False
        if model.is_system_default:
            raise InvalidGameActionError("No se pueden eliminar los presets predeterminados del sistema.")
        self._session.delete(model)
        self._session.commit()
        return True
