import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.customers.models import Customer
from app.orders.models import Order
from app.customers.schemas import CustomerDetail, CustomerOrderSummary


async def get_or_create(
    restaurant_id: uuid.UUID,
    whatsapp: str,
    db: AsyncSession,
    name: str | None = None,
    address: str | None = None,
) -> Customer:
    result = await db.execute(
        select(Customer).where(
            and_(Customer.restaurant_id == restaurant_id, Customer.whatsapp == whatsapp)
        )
    )
    customer = result.scalar_one_or_none()

    if customer:
        if name and not customer.name:
            customer.name = name
        if address:
            customer.address = address
        await db.commit()
        await db.refresh(customer)
        return customer

    customer = Customer(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        whatsapp=whatsapp,
        name=name,
        address=address,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


async def list_customers(
    restaurant_id: uuid.UUID,
    db: AsyncSession,
    search: str | None = None,
) -> list[Customer]:
    filters = [Customer.restaurant_id == restaurant_id]
    if search:
        filters.append(
            Customer.whatsapp.ilike(f"%{search}%") | Customer.name.ilike(f"%{search}%")
        )

    result = await db.execute(
        select(Customer).where(and_(*filters)).order_by(Customer.created_at.desc())
    )
    return list(result.scalars().all())


async def get_customer_detail(
    customer_id: uuid.UUID,
    restaurant_id: uuid.UUID,
    db: AsyncSession,
) -> CustomerDetail | None:
    result = await db.execute(
        select(Customer).where(
            and_(Customer.id == customer_id, Customer.restaurant_id == restaurant_id)
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        return None

    summary_result = await db.execute(
        select(
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total), 0).label("total_spent"),
            func.max(Order.created_at).label("last_order_at"),
        ).where(
            and_(
                Order.customer_id == customer_id,
                Order.payment_status == "paid",
                Order.status != "cancelled",
            )
        )
    )
    row = summary_result.one()

    return CustomerDetail(
        **{c: getattr(customer, c) for c in ["id", "restaurant_id", "whatsapp", "name", "address", "created_at"]},
        summary=CustomerOrderSummary(
            total_orders=row.total_orders or 0,
            total_spent=Decimal(str(row.total_spent or 0)),
            last_order_at=row.last_order_at,
        ),
    )
