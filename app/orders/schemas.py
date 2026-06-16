import uuid
from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel


# ---------- Order Item ----------

class OrderItemOut(BaseModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID | None
    name: str
    price: Decimal
    quantity: int
    notes: str | None

    model_config = {"from_attributes": True}


# ---------- Order ----------

class OrderOut(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    customer_id: uuid.UUID
    status: str
    payment_method: str | None
    payment_status: str
    payment_ref: str | None
    subtotal: Decimal | None
    delivery_fee: Decimal | None
    total: Decimal | None
    address: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut] = []

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: str

    def validate_status(self) -> str:
        allowed = {"confirmed", "preparing", "ready", "delivered", "cancelled"}
        if self.status not in allowed:
            raise ValueError(f"Status inválido. Permitidos: {', '.join(sorted(allowed))}")
        return self.status


class OrderSummary(BaseModel):
    total_orders: int
    total_revenue: Decimal
    average_ticket: Decimal
    cancelled_orders: int
