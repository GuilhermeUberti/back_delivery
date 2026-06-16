import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


# ---------- Category ----------

class CategoryCreate(BaseModel):
    name: str
    position: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    position: int | None = None
    active: bool | None = None


class CategoryOut(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    position: int
    active: bool

    model_config = {"from_attributes": True}


# ---------- MenuItem ----------

class MenuItemCreate(BaseModel):
    category_id: uuid.UUID
    name: str
    description: str | None = None
    price: Decimal = Field(gt=0)
    image_url: str | None = None
    position: int = 0


class MenuItemUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0)
    image_url: str | None = None
    active: bool | None = None
    position: int | None = None


class MenuItemOut(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    active: bool
    position: int

    model_config = {"from_attributes": True}


class CategoryWithItems(CategoryOut):
    items: list[MenuItemOut] = []


# ---------- Reorder ----------

class ReorderItem(BaseModel):
    id: uuid.UUID
    position: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem]


# ---------- Upload ----------

class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str


class UploadUrlResponse(BaseModel):
    upload_url: str
    public_url: str
    key: str
