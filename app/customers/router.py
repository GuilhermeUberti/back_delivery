import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.deps import get_current_user
from app.auth.models import User
from app.customers import service
from app.customers.schemas import CustomerDetail, CustomerOut

router = APIRouter()


@router.get("", response_model=list[CustomerOut])
async def list_customers(
    search: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_customers(current_user.restaurant_id, db, search)


@router.get("/{customer_id}", response_model=CustomerDetail)
async def get_customer(
    customer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    detail = await service.get_customer_detail(customer_id, current_user.restaurant_id, db)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return detail
