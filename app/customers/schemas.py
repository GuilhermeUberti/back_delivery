import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CustomerOut(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    whatsapp: str
    name: str | None
    address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerOrderSummary(BaseModel):
    total_orders: int
    total_spent: Decimal
    last_order_at: datetime | None


class CustomerDetail(CustomerOut):
    summary: CustomerOrderSummary
