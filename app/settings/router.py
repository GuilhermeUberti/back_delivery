from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.deps import get_current_user
from app.auth.models import Restaurant, User

router = APIRouter()


class RestaurantUpdate(BaseModel):
    name: str | None = None
    pix_key: str | None = None
    delivery_fee: Decimal | None = None
    delivery_radius: int | None = None
    open_time: str | None = None
    close_time: str | None = None
    zapi_instance: str | None = None
    zapi_token: str | None = None


@router.get("/restaurant")
async def get_restaurant(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Restaurant).where(Restaurant.id == current_user.restaurant_id))
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurante não encontrado")
    return restaurant


@router.patch("/restaurant")
async def update_restaurant(
    body: RestaurantUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Restaurant).where(Restaurant.id == current_user.restaurant_id))
    restaurant = result.scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurante não encontrado")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(restaurant, field, value)

    await db.commit()
    await db.refresh(restaurant)
    return restaurant
