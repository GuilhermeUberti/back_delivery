from dataclasses import dataclass, field

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Restaurant
from app.menu.models import Category


@dataclass
class FlowResult:
    next_step: str
    messages: list[str]
    cart: list[dict] | None = None  # None = preserve existing cart; [] = intentional reset
    data: dict = field(default_factory=dict)


async def handle(state, text: str, restaurant: Restaurant, db: AsyncSession) -> FlowResult:
    result = await db.execute(
        select(Category)
        .where(and_(Category.restaurant_id == restaurant.id, Category.active.is_(True), Category.deleted_at.is_(None)))
        .order_by(Category.position)
    )
    categories = list(result.scalars().all())

    if not categories:
        return FlowResult(
            next_step="greeting",
            messages=["Olá! Nosso cardápio está sendo atualizado. Tente novamente em breve! 😊"],
        )

    cat_list = "\n".join(f"{i + 1}. {c.name}" for i, c in enumerate(categories))
    welcome = (
        f"Olá! Bem-vindo ao *{restaurant.name}*! 👋\n\n"
        f"Escolha uma categoria:\n{cat_list}\n\n"
        f"Responda com o *número* da categoria desejada."
    )

    return FlowResult(
        next_step="browsing",
        messages=[welcome],
        cart=[],
        data={
            "mode": "category",
            "categories": [{"id": str(c.id), "name": c.name} for c in categories],
        },
    )
