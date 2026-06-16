from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.deps import get_current_user
from app.auth.models import User
from app.analytics import queries

router = APIRouter()

Period = Literal["day", "week", "month"]


@router.get("/summary")
async def summary(
    period: Period = Query(default="day"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await queries.get_summary(current_user.restaurant_id, period, db)


@router.get("/revenue")
async def revenue(
    period: Period = Query(default="week"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await queries.get_revenue_by_day(current_user.restaurant_id, period, db)


@router.get("/top-items")
async def top_items(
    period: Period = Query(default="week"),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await queries.get_top_items(current_user.restaurant_id, period, db, limit)


@router.get("/peak-hours")
async def peak_hours(
    period: Period = Query(default="week"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await queries.get_peak_hours(current_user.restaurant_id, period, db)


@router.get("/customers")
async def customers(
    period: Period = Query(default="month"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await queries.get_customers_summary(current_user.restaurant_id, period, db)
