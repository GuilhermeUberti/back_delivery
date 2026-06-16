import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.deps import get_current_user
from app.auth.models import User
from app.orders import service
from app.orders.schemas import OrderOut, OrderStatusUpdate, OrderSummary

router = APIRouter()


@router.get("/today/summary", response_model=OrderSummary)
async def today_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_today_summary(current_user.restaurant_id, db)


@router.get("", response_model=list[OrderOut])
async def list_orders(
    status: str | None = Query(default=None),
    date: datetime | None = Query(default=None, description="Formato: YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_orders(current_user.restaurant_id, db, status, date)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await service.get_order(order_id, current_user.restaurant_id, db)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return order


@router.patch("/{order_id}/status", response_model=OrderOut)
async def update_order_status(
    order_id: uuid.UUID,
    body: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await service.get_order(order_id, current_user.restaurant_id, db)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")
    return await service.update_status(order, body.status, db)
