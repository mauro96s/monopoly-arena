from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "Monopoly Manager API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Base de datos: por defecto SQLite local para desarrollo inmediato con cero fricción.
    # En producción o cuando se conecte Supabase, se define DATABASE_URL en el archivo .env
    DATABASE_URL: str = "sqlite:///./monopoly_local.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None) -> str:
        if not v:
            return "sqlite:///./monopoly_local.db"
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql://", 1)
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
