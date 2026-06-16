import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, and_, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.orders.models import Order, OrderItem
from app.orders.schemas import OrderSummary

VALID_STATUSES = {"pending", "confirmed", "preparing", "ready", "delivered", "cancelled"}
TERMINAL_STATUSES = {"delivered", "cancelled"}


async def list_orders(
    restaurant_id: uuid.UUID,
    db: AsyncSession,
    status: str | None = None,
    date: datetime | None = None,
) -> list[Order]:
    filters = [Order.restaurant_id == restaurant_id]
    if status:
        filters.append(Order.status == status)
    if date:
        start = date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end = date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
        filters.append(Order.created_at.between(start, end))

    result = await db.execute(
        select(Order)
        .where(and_(*filters))
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())


async def get_order(order_id: uuid.UUID, restaurant_id: uuid.UUID, db: AsyncSession) -> Order | None:
    result = await db.execute(
        select(Order)
        .where(and_(Order.id == order_id, Order.restaurant_id == restaurant_id))
        .options(selectinload(Order.items))
    )
    return result.scalar_one_or_none()


async def update_status(order: Order, new_status: str, db: AsyncSession) -> Order:
    if new_status not in VALID_STATUSES:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Status inválido. Permitidos: {', '.join(sorted(VALID_STATUSES))}",
        )
    if order.status in TERMINAL_STATUSES:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Pedido já está em status terminal: {order.status}",
        )

    order.status = new_status
    order.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(order)

    # Notify customer on WhatsApp (fire-and-forget)
    await _notify_customer(order, new_status, db)

    return order


async def _notify_customer(order: Order, new_status: str, db: AsyncSession) -> None:
    from sqlalchemy import select
    from app.customers.models import Customer
    from app.auth.models import Restaurant
    from app.bot.zapi import notify_status

    try:
        customer_result = await db.execute(select(Customer).where(Customer.id == order.customer_id))
        customer = customer_result.scalar_one_or_none()

        restaurant_result = await db.execute(select(Restaurant).where(Restaurant.id == order.restaurant_id))
        restaurant = restaurant_result.scalar_one_or_none()

        if customer and restaurant:
            await notify_status(customer.whatsapp, new_status, restaurant.zapi_instance, restaurant.zapi_token)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Failed to notify customer for order %s", order.id)


async def get_today_summary(restaurant_id: uuid.UUID, db: AsyncSession) -> OrderSummary:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    result = await db.execute(
        select(
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(case((Order.status != "cancelled", Order.total), else_=0)), 0).label("total_revenue"),
            func.count(case((Order.status == "cancelled", 1))).label("cancelled_orders"),
        ).where(
            and_(
                Order.restaurant_id == restaurant_id,
                Order.created_at.between(start, end),
                Order.payment_status == "paid",
            )
        )
    )
    row = result.one()

    total_orders = row.total_orders or 0
    total_revenue = Decimal(str(row.total_revenue or 0))
    cancelled = row.cancelled_orders or 0
    paid_orders = total_orders - cancelled
    average_ticket = (total_revenue / paid_orders) if paid_orders > 0 else Decimal("0")

    return OrderSummary(
        total_orders=total_orders,
        total_revenue=total_revenue,
        average_ticket=average_ticket,
        cancelled_orders=cancelled,
    )
