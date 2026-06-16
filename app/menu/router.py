import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.deps import get_current_user
from app.auth.models import User
from app.menu import service
from app.menu.schemas import (
    CategoryCreate, CategoryOut, CategoryUpdate, CategoryWithItems,
    MenuItemCreate, MenuItemOut, MenuItemUpdate,
    ReorderRequest, UploadUrlRequest, UploadUrlResponse,
)

router = APIRouter()


# ---------- Upload ----------

@router.post("/upload-url", response_model=UploadUrlResponse)
async def get_upload_url(
    body: UploadUrlRequest,
    current_user: User = Depends(get_current_user),
):
    return service.generate_upload_url(current_user.restaurant_id, body.filename, body.content_type)


# ---------- Categories ----------

@router.get("/categories", response_model=list[CategoryWithItems])
async def list_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_categories_with_items(current_user.restaurant_id, db)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_category(current_user.restaurant_id, body, db)


@router.patch("/categories/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_categories(
    body: ReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.reorder_categories(current_user.restaurant_id, body.items, db)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    category = await service.get_category(category_id, current_user.restaurant_id, db)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
    return await service.update_category(category, body, db)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    category = await service.get_category(category_id, current_user.restaurant_id, db)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
    await service.delete_category(category, db)


# ---------- Menu Items ----------

@router.get("/items", response_model=list[MenuItemOut])
async def list_items(
    category_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_items(current_user.restaurant_id, db, category_id, include_inactive)


@router.post("/items", response_model=MenuItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(
    body: MenuItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    category = await service.get_category(body.category_id, current_user.restaurant_id, db)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
    return await service.create_item(current_user.restaurant_id, body, db)


@router.patch("/items/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_items(
    body: ReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.reorder_items(current_user.restaurant_id, body.items, db)


@router.get("/items/{item_id}", response_model=MenuItemOut)
async def get_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await service.get_item(item_id, current_user.restaurant_id, db)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado")
    return item


@router.patch("/items/{item_id}", response_model=MenuItemOut)
async def update_item(
    item_id: uuid.UUID,
    body: MenuItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await service.get_item(item_id, current_user.restaurant_id, db)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado")

    if body.category_id:
        category = await service.get_category(body.category_id, current_user.restaurant_id, db)
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")

    return await service.update_item(item, body, db)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await service.get_item(item_id, current_user.restaurant_id, db)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado")
    await service.delete_item(item, db)
