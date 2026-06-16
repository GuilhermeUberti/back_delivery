import uuid

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth import service


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessão inválida ou expirada",
    )

    if not access_token:
        raise credentials_error

    payload = service.decode_token(access_token)
    if not payload or payload.get("type") != "access":
        raise credentials_error

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise credentials_error

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_error

    user = await service.get_user_by_id(user_id, db)
    if not user:
        raise credentials_error

    return user


def require_owner(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao proprietário")
    return current_user
