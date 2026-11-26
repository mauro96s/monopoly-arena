from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from src.domain.interfaces.user_repository import UserRepositoryProtocol
from src.domain.models.user import User
from src.infrastructure.security.password import hash_password, verify_password
from src.infrastructure.security.token import create_access_token
from src.presentation.dependencies import get_user_repository, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Nombre de usuario único")
    password: str = Field(..., min_length=4, max_length=100, description="Contraseña de acceso")
    email: Optional[str] = Field(None, max_length=128, description="Correo electrónico opcional")
    display_name: Optional[str] = Field(None, max_length=64, description="Nombre público visible")


class LoginRequest(BaseModel):
    username: str = Field(..., description="Nombre de usuario")
    password: str = Field(..., description="Contraseña")


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str = "USER"
    created_at: Optional[str] = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    user_repo: UserRepositoryProtocol = Depends(get_user_repository),
):
    """Registra una nueva cuenta de usuario en la plataforma."""
    clean_username = payload.username.strip().lower()
    existing = user_repo.get_by_username(clean_username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El nombre de usuario '{payload.username}' ya está registrado.",
        )

    pwd_hash = hash_password(payload.password)
    user = User(
        id=None,
        username=clean_username,
        password_hash=pwd_hash,
        email=payload.email.strip().lower() if payload.email else None,
        display_name=payload.display_name.strip() if payload.display_name else payload.username.strip(),
        role="USER",
    )
    saved = user_repo.save(user)
    token = create_access_token(user_id=saved.id, username=saved.username)  # type: ignore

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=saved.id,  # type: ignore
            username=saved.username,
            email=saved.email,
            display_name=saved.display_name,
            role=saved.role,
            created_at=saved.created_at.isoformat() if saved.created_at else None,
        ),
    )


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: LoginRequest,
    user_repo: UserRepositoryProtocol = Depends(get_user_repository),
):
    """Inicia sesión y genera un Bearer token para el usuario."""
    clean_username = payload.username.strip().lower()
    user = user_repo.get_by_username(clean_username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Revisa usuario y contraseña.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user_id=user.id, username=user.username)  # type: ignore

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,  # type: ignore
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            created_at=user.created_at.isoformat() if user.created_at else None,
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Retorna la información del perfil del usuario autenticado."""
    return UserResponse(
        id=current_user.id,  # type: ignore
        username=current_user.username,
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )
