from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import service
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.config import settings

router = APIRouter()

_COOKIE_OPTS = {
    "httponly": True,
    "samesite": "lax",
    "secure": not settings.EFI_SANDBOX,  # secure=True em produção
}


def _set_auth_cookies(response: Response, user: User) -> TokenResponse:
    access_token = service.create_access_token(user.id, user.restaurant_id)
    refresh_token = service.create_refresh_token(user.id, user.restaurant_id)

    response.set_cookie(
        "access_token",
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **_COOKIE_OPTS,
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        **_COOKIE_OPTS,
    )
    return TokenResponse(access_token=access_token)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        user = await service.register_restaurant(
            restaurant_name=body.restaurant_name,
            whatsapp_number=body.whatsapp_number,
            owner_name=body.owner_name,
            email=body.email,
            password=body.password,
            db=db,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail ou número de WhatsApp já cadastrado",
        )

    _set_auth_cookies(response, user)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await service.authenticate(body.email, body.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )
    return _set_auth_cookies(response, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    import uuid

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token inválido ou expirado",
    )

    if not refresh_token:
        raise credentials_error

    payload = service.decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise credentials_error

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise credentials_error

    user = await service.get_user_by_id(user_id, db)
    if not user:
        raise credentials_error

    return _set_auth_cookies(response, user)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"detail": "Logout realizado com sucesso"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
