import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.auth.models import Restaurant, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def _make_token(data: dict, expires_delta: timedelta) -> str:
    payload = data | {"exp": datetime.now(timezone.utc) + expires_delta}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: uuid.UUID, restaurant_id: uuid.UUID) -> str:
    return _make_token(
        {"sub": str(user_id), "rid": str(restaurant_id), "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: uuid.UUID, restaurant_id: uuid.UUID) -> str:
    return _make_token(
        {"sub": str(user_id), "rid": str(restaurant_id), "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return {}


async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(user_id: uuid.UUID, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate(email: str, password: str, db: AsyncSession) -> User | None:
    user = await get_user_by_email(email, db)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def register_restaurant(
    restaurant_name: str,
    whatsapp_number: str,
    owner_name: str,
    email: str,
    password: str,
    db: AsyncSession,
) -> User:
    restaurant = Restaurant(
        id=uuid.uuid4(),
        name=restaurant_name,
        whatsapp_number=whatsapp_number,
    )
    db.add(restaurant)
    await db.flush()

    user = User(
        id=uuid.uuid4(),
        restaurant_id=restaurant.id,
        name=owner_name,
        email=email,
        password_hash=hash_password(password),
        role="owner",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
