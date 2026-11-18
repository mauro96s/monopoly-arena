from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.presentation.routers import games_router, actions_router, views_router
from src.infrastructure.database import Base, engine


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="API de Gestión y Documentación de Partidas de Monopoly (Monopoly Clásico & Expansiones)",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configuración de CORS para el Frontend interactivo (Vercel, Localhost, etc.)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # En producción se puede restringir al dominio de Vercel
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Vistas HTML (Frontend)
    app.include_router(views_router.router)

    # Rutas API v1
    app.include_router(games_router.router, prefix=settings.API_V1_STR)
    app.include_router(actions_router.router, prefix=settings.API_V1_STR)

    # Rutas de acción y partidas directas (fallback para compatibilidad sin prefijo /api/v1)
    app.include_router(games_router.router)
    app.include_router(actions_router.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()


from sqlalchemy import inspect, text

# Auto-creación y migración de tablas para entornos locales/desarrollo rápido
@app.on_event("startup")
def on_startup():
    if settings.DEBUG:
        Base.metadata.create_all(bind=engine)
    
    # Migración segura de columnas adicionales
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if "games" in tables:
            game_cols = [c["name"] for c in inspector.get_columns("games")]
            with engine.begin() as conn:
                if "has_rolled_dice" not in game_cols:
                    conn.execute(text("ALTER TABLE games ADD COLUMN has_rolled_dice BOOLEAN NOT NULL DEFAULT 0"))
                if "consecutive_doubles" not in game_cols:
                    conn.execute(text("ALTER TABLE games ADD COLUMN consecutive_doubles INTEGER NOT NULL DEFAULT 0"))
        if "players" in tables:
            player_cols = [c["name"] for c in inspector.get_columns("players")]
            with engine.begin() as conn:
                if "out_of_jail_cards" not in player_cols:
                    conn.execute(text("ALTER TABLE players ADD COLUMN out_of_jail_cards INTEGER NOT NULL DEFAULT 0"))
    except Exception as e:
        print(f"Aviso migración de esquema: {e}")
