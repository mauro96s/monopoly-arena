from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator
from src.config import settings

# En entornos Serverless como Vercel con Supabase, NullPool o un pool mínimo
# con pool_pre_ping previene el agotamiento de conexiones de Postgres (pgBouncer/Supavisor).
is_serverless = settings.ENVIRONMENT.lower() in ("production", "staging", "serverless")
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine_kwargs = {}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    if is_serverless:
        # NullPool no mantiene conexiones abiertas inactivas entre invocaciones lambda/serverless
        engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Generador de sesión de base de datos para inyección de dependencias."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
