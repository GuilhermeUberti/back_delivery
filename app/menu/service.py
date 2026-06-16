import uuid
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.menu.models import Category, MenuItem
from app.menu.schemas import (
    CategoryCreate, CategoryUpdate,
    MenuItemCreate, MenuItemUpdate,
    ReorderItem, UploadUrlResponse,
)


# ---------- R2 ----------

def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def generate_upload_url(restaurant_id: uuid.UUID, filename: str, content_type: str) -> UploadUrlResponse:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    key = f"menu/{restaurant_id}/{uuid.uuid4()}.{ext}"

    upload_url = _r2_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key, "ContentType": content_type},
        ExpiresIn=300,
    )
    return UploadUrlResponse(
        upload_url=upload_url,
        public_url=f"{settings.R2_PUBLIC_URL}/{key}",
        key=key,
    )


# ---------- Categories ----------

async def list_categories(restaurant_id: uuid.UUID, db: AsyncSession) -> list[Category]:
    result = await db.execute(
        select(Category)
        .where(and_(Category.restaurant_id == restaurant_id, Category.deleted_at.is_(None)))
        .order_by(Category.position)
    )
    return list(result.scalars().all())


async def list_categories_with_items(restaurant_id: uuid.UUID, db: AsyncSession) -> list[Category]:
    result = await db.execute(
        select(Category)
        .where(and_(Category.restaurant_id == restaurant_id, Category.deleted_at.is_(None)))
        .options(selectinload(Category.items))
        .order_by(Category.position)
    )
    return list(result.scalars().all())


async def get_category(category_id: uuid.UUID, restaurant_id: uuid.UUID, db: AsyncSession) -> Category | None:
    result = await db.execute(
        select(Category).where(
            and_(
                Category.id == category_id,
                Category.restaurant_id == restaurant_id,
                Category.deleted_at.is_(None),
            )
        )
    )
    return result.scalar_one_or_none()


async def create_category(restaurant_id: uuid.UUID, data: CategoryCreate, db: AsyncSession) -> Category:
    category = Category(id=uuid.uuid4(), restaurant_id=restaurant_id, **data.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(category: Category, data: CategoryUpdate, db: AsyncSession) -> Category:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(category, field, value)
    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(category: Category, db: AsyncSession) -> None:
    category.deleted_at = datetime.now(timezone.utc)
    category.active = False
    await db.commit()


async def reorder_categories(restaurant_id: uuid.UUID, items: list[ReorderItem], db: AsyncSession) -> None:
    for item in items:
        result = await db.execute(
            select(Category).where(
                and_(Category.id == item.id, Category.restaurant_id == restaurant_id)
            )
        )
        category = result.scalar_one_or_none()
        if category:
            category.position = item.position
    await db.commit()


# ---------- Menu Items ----------

async def list_items(
    restaurant_id: uuid.UUID,
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
    include_inactive: bool = False,
) -> list[MenuItem]:
    filters = [MenuItem.restaurant_id == restaurant_id, MenuItem.deleted_at.is_(None)]
    if category_id:
        filters.append(MenuItem.category_id == category_id)
    if not include_inactive:
        filters.append(MenuItem.active.is_(True))

    result = await db.execute(
        select(MenuItem).where(and_(*filters)).order_by(MenuItem.position)
    )
    return list(result.scalars().all())


async def get_item(item_id: uuid.UUID, restaurant_id: uuid.UUID, db: AsyncSession) -> MenuItem | None:
    result = await db.execute(
        select(MenuItem).where(
            and_(
                MenuItem.id == item_id,
                MenuItem.restaurant_id == restaurant_id,
                MenuItem.deleted_at.is_(None),
            )
        )
    )
    return result.scalar_one_or_none()


async def create_item(restaurant_id: uuid.UUID, data: MenuItemCreate, db: AsyncSession) -> MenuItem:
    item = MenuItem(id=uuid.uuid4(), restaurant_id=restaurant_id, **data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_item(item: MenuItem, data: MenuItemUpdate, db: AsyncSession) -> MenuItem:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_item(item: MenuItem, db: AsyncSession) -> None:
    item.deleted_at = datetime.now(timezone.utc)
    item.active = False
    await db.commit()


async def reorder_items(restaurant_id: uuid.UUID, items: list[ReorderItem], db: AsyncSession) -> None:
    for item in items:
        result = await db.execute(
            select(MenuItem).where(
                and_(MenuItem.id == item.id, MenuItem.restaurant_id == restaurant_id)
            )
        )
        menu_item = result.scalar_one_or_none()
        if menu_item:
            menu_item.position = item.position
    await db.commit()
