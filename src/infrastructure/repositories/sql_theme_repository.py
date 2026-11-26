import json
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.domain.interfaces.theme_repository import ThemeRepositoryProtocol
from src.domain.themes.models import (
    ThemeDefinition,
    GroupThemeMetadata,
    TileThemeMetadata,
)
from src.domain.themes.card_models import DeckType, CardEffectType, ThemeCardDefinition
from src.domain.exceptions import InvalidGameActionError
from src.infrastructure.orm.models import ThemeModel
from src.domain.themes.theme_registry import ThemeRegistry


class SqlThemeRepository(ThemeRepositoryProtocol):
    """
    Repositorio SQL para la persistencia, clonación y consulta de temas visuales.
    Permite almacenar personalizaciones de casillas, grupos y cartas de Fortuna y Arca Comunal.
    """

    def __init__(self, session: Session):
        self._session = session
        self._ensure_table()
        # Conectar este repositorio a ThemeRegistry para resolución dinámica
        ThemeRegistry.set_repository(self)

    def _ensure_table(self) -> None:
        """Crea la tabla themes de forma no destructiva si no existe."""
        try:
            self._session.execute(text("""
                CREATE TABLE IF NOT EXISTS themes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    theme_id VARCHAR(64) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description VARCHAR(255) NOT NULL DEFAULT '',
                    currency_symbol VARCHAR(16) NOT NULL DEFAULT '$',
                    currency_code VARCHAR(16) NOT NULL DEFAULT 'USD',
                    chance_deck_name VARCHAR(64) NOT NULL DEFAULT 'Fortuna',
                    community_chest_deck_name VARCHAR(64) NOT NULL DEFAULT 'Arca Comunal',
                    is_official BOOLEAN NOT NULL DEFAULT 0,
                    is_readonly BOOLEAN NOT NULL DEFAULT 0,
                    parent_theme_id VARCHAR(64),
                    owner_user_id VARCHAR(64),
                    groups_json TEXT NOT NULL DEFAULT '[]',
                    tiles_json TEXT NOT NULL DEFAULT '{}',
                    chance_cards_json TEXT NOT NULL DEFAULT '[]',
                    community_chest_cards_json TEXT NOT NULL DEFAULT '[]',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            self._session.commit()
        except Exception:
            self._session.rollback()

    def _to_domain(self, model: ThemeModel) -> ThemeDefinition:
        try:
            groups_raw = json.loads(model.groups_json) if model.groups_json else []
        except Exception:
            groups_raw = []
        groups = [
            GroupThemeMetadata(
                key=g["key"],
                name=g["name"],
                color_hex=g["color_hex"],
                text_color=g.get("text_color", "#FFFFFF"),
                icon=g.get("icon", "home"),
            )
            for g in groups_raw
        ]

        try:
            tiles_raw = json.loads(model.tiles_json) if model.tiles_json else {}
        except Exception:
            tiles_raw = {}
        tiles = {}
        for tid, t in tiles_raw.items():
            tiles[tid] = TileThemeMetadata(
                tile_id=t["tile_id"],
                position=t["position"],
                name=t["name"],
                short_name=t.get("short_name", t["name"]),
                icon=t.get("icon"),
                banner_color=t.get("banner_color"),
            )

        try:
            chance_raw = json.loads(model.chance_cards_json) if model.chance_cards_json else []
        except Exception:
            chance_raw = []
        chance_cards = []
        for c in chance_raw:
            try:
                eff = CardEffectType(c["effect_type"])
            except Exception:
                eff = CardEffectType.COLLECT_FROM_BANK
            chance_cards.append(
                ThemeCardDefinition(
                    card_id=c["card_id"],
                    deck=DeckType.CHANCE,
                    title=c["title"],
                    description=c["description"],
                    effect_type=eff,
                    params=c.get("params", {}),
                    icon=c.get("icon"),
                )
            )

        try:
            chest_raw = json.loads(model.community_chest_cards_json) if model.community_chest_cards_json else []
        except Exception:
            chest_raw = []
        community_chest_cards = []
        for c in chest_raw:
            try:
                eff = CardEffectType(c["effect_type"])
            except Exception:
                eff = CardEffectType.COLLECT_FROM_BANK
            community_chest_cards.append(
                ThemeCardDefinition(
                    card_id=c["card_id"],
                    deck=DeckType.COMMUNITY_CHEST,
                    title=c["title"],
                    description=c["description"],
                    effect_type=eff,
                    params=c.get("params", {}),
                    icon=c.get("icon"),
                )
            )

        return ThemeDefinition(
            theme_id=model.theme_id,
            name=model.name,
            description=model.description or "",
            currency_symbol=model.currency_symbol or "$",
            currency_code=model.currency_code or "USD",
            chance_deck_name=model.chance_deck_name or "Fortuna",
            community_chest_deck_name=model.community_chest_deck_name or "Arca Comunal",
            is_official=bool(model.is_official),
            is_readonly=bool(model.is_readonly),
            parent_theme_id=model.parent_theme_id,
            owner_user_id=model.owner_user_id,
            groups=groups,
            tiles=tiles,
            chance_cards=chance_cards,
            community_chest_cards=community_chest_cards,
        )

    def get_by_theme_id(self, theme_id: str) -> Optional[ThemeDefinition]:
        model = self._session.query(ThemeModel).filter(ThemeModel.theme_id == theme_id).first()
        return self._to_domain(model) if model else None

    def list_all(self) -> List[ThemeDefinition]:
        models = self._session.query(ThemeModel).order_by(
            ThemeModel.is_official.desc(),
            ThemeModel.created_at.asc()
        ).all()
        return [self._to_domain(m) for m in models]

    def save(self, theme: ThemeDefinition) -> ThemeDefinition:
        theme_dict = theme.to_dict()
        model = self._session.query(ThemeModel).filter(ThemeModel.theme_id == theme.theme_id).first()

        if model:
            if model.is_readonly:
                raise InvalidGameActionError(f"El tema '{theme.theme_id}' es de solo lectura y no puede modificarse.")
            model.name = theme.name
            model.description = theme.description
            model.currency_symbol = theme.currency_symbol
            model.currency_code = theme.currency_code
            model.chance_deck_name = theme.chance_deck_name
            model.community_chest_deck_name = theme.community_chest_deck_name
            model.groups_json = json.dumps(theme_dict["groups"])
            model.tiles_json = json.dumps(theme_dict["tiles"])
            model.chance_cards_json = json.dumps(theme_dict["chance_cards"])
            model.community_chest_cards_json = json.dumps(theme_dict["community_chest_cards"])
            self._session.commit()
            self._session.refresh(model)
        else:
            model = ThemeModel(
                theme_id=theme.theme_id,
                name=theme.name,
                description=theme.description,
                currency_symbol=theme.currency_symbol,
                currency_code=theme.currency_code,
                chance_deck_name=theme.chance_deck_name,
                community_chest_deck_name=theme.community_chest_deck_name,
                is_official=theme.is_official,
                is_readonly=theme.is_readonly,
                parent_theme_id=theme.parent_theme_id,
                owner_user_id=theme.owner_user_id,
                groups_json=json.dumps(theme_dict["groups"]),
                tiles_json=json.dumps(theme_dict["tiles"]),
                chance_cards_json=json.dumps(theme_dict["chance_cards"]),
                community_chest_cards_json=json.dumps(theme_dict["community_chest_cards"]),
            )
            self._session.add(model)
            self._session.commit()
            self._session.refresh(model)

        ThemeRegistry.register_theme(theme)
        return self._to_domain(model)

    def delete(self, theme_id: str) -> bool:
        model = self._session.query(ThemeModel).filter(ThemeModel.theme_id == theme_id).first()
        if not model:
            return False
        if model.is_readonly or model.is_official:
            raise InvalidGameActionError(f"No se puede eliminar el tema protegido '{theme_id}'.")

        self._session.delete(model)
        self._session.commit()
        ThemeRegistry.unregister_theme(theme_id)
        return True
