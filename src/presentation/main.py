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


# Auto-creación de tablas para entornos locales/desarrollo rápido
@app.on_event("startup")
def on_startup():
    if settings.DEBUG:
        Base.metadata.create_all(bind=engine)
