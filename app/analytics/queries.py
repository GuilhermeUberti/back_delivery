import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, and_, func, text, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.orders.models import Order, OrderItem
from app.customers.models import Customer


def _period_range(period: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if period == "week":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now - timedelta(days=30)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


async def get_summary(restaurant_id: uuid.UUID, period: str, db: AsyncSession) -> dict:
    start, end = _period_range(period)

    result = await db.execute(
        select(
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total), 0).label("total_revenue"),
            func.coalesce(func.avg(Order.total), 0).label("average_ticket"),
        ).where(
            and_(
                Order.restaurant_id == restaurant_id,
                Order.created_at.between(start, end),
                Order.payment_status == "paid",
                Order.status != "cancelled",
            )
        )
    )
    row = result.one()
    return {
        "period": period,
        "total_orders": row.total_orders or 0,
        "total_revenue": Decimal(str(row.total_revenue or 0)),
        "average_ticket": Decimal(str(row.average_ticket or 0)),
    }


async def get_revenue_by_day(restaurant_id: uuid.UUID, period: str, db: AsyncSession) -> list[dict]:
    start, end = _period_range(period)

    result = await db.execute(
        select(
            func.date(Order.created_at).label("day"),
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.total), 0).label("revenue"),
        ).where(
            and_(
                Order.restaurant_id == restaurant_id,
                Order.created_at.between(start, end),
                Order.payment_status == "paid",
                Order.status != "cancelled",
            )
        ).group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    )
    return [{"day": str(row.day), "orders": row.orders, "revenue": Decimal(str(row.revenue))} for row in result]


async def get_top_items(restaurant_id: uuid.UUID, period: str, db: AsyncSession, limit: int = 10) -> list[dict]:
    start, end = _period_range(period)

    result = await db.execute(
        select(
            OrderItem.name,
            func.sum(OrderItem.quantity).label("quantity_sold"),
            func.sum(OrderItem.price * OrderItem.quantity).label("revenue"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            and_(
                Order.restaurant_id == restaurant_id,
                Order.created_at.between(start, end),
                Order.payment_status == "paid",
                Order.status != "cancelled",
            )
        )
        .group_by(OrderItem.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(limit)
    )
    return [
        {"name": row.name, "quantity_sold": row.quantity_sold, "revenue": Decimal(str(row.revenue))}
        for row in result
    ]


async def get_peak_hours(restaurant_id: uuid.UUID, period: str, db: AsyncSession) -> list[dict]:
    start, end = _period_range(period)

    result = await db.execute(
        select(
            func.extract("hour", Order.created_at).label("hour"),
            func.count(Order.id).label("orders"),
        ).where(
            and_(
                Order.restaurant_id == restaurant_id,
                Order.created_at.between(start, end),
                Order.payment_status == "paid",
                Order.status != "cancelled",
            )
        )
        .group_by(func.extract("hour", Order.created_at))
        .order_by(func.extract("hour", Order.created_at))
    )
    return [{"hour": int(row.hour), "orders": row.orders} for row in result]


async def get_customers_summary(restaurant_id: uuid.UUID, period: str, db: AsyncSession) -> dict:
    start, end = _period_range(period)

    # clientes que fizeram o primeiro pedido no período = novos
    new_customers = await db.execute(
        select(func.count(Customer.id)).where(
            and_(
                Customer.restaurant_id == restaurant_id,
                Customer.created_at.between(start, end),
            )
        )
    )

    # clientes que fizeram pedido no período mas foram criados antes = recorrentes
    returning_customers = await db.execute(
        select(func.count(func.distinct(Order.customer_id))).where(
            and_(
                Order.restaurant_id == restaurant_id,
                Order.created_at.between(start, end),
                Order.payment_status == "paid",
            )
        ).join(Customer, Customer.id == Order.customer_id)
        .where(Customer.created_at < start)
    )

    return {
        "new": new_customers.scalar() or 0,
        "returning": returning_customers.scalar() or 0,
    }
