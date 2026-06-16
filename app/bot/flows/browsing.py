from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Restaurant
from app.menu.models import MenuItem
from app.bot.flows.greeting import FlowResult


def _fmt_price(value) -> str:
    return f"R$ {float(value):.2f}".replace(".", ",")


async def handle(state, text: str, restaurant: Restaurant, db: AsyncSession) -> FlowResult:
    mode = state.data.get("mode", "category")

    if mode == "category":
        return await _handle_category_selection(state, text, restaurant, db)
    else:
        return await _handle_item_selection(state, text, restaurant, db)


async def _handle_category_selection(state, text: str, restaurant: Restaurant, db: AsyncSession) -> FlowResult:
    categories = state.data.get("categories", [])

    if not text.isdigit() or not (1 <= int(text) <= len(categories)):
        cat_list = "\n".join(f"{i + 1}. {c['name']}" for i, c in enumerate(categories))
        return FlowResult(
            next_step="browsing",
            messages=[f"Por favor, escolha uma opção válida:\n\n{cat_list}"],
            data=state.data,
        )

    selected = categories[int(text) - 1]

    result = await db.execute(
        select(MenuItem)
        .where(
            and_(
                MenuItem.category_id == selected["id"],
                MenuItem.active.is_(True),
                MenuItem.deleted_at.is_(None),
            )
        )
        .order_by(MenuItem.position)
    )
    items = list(result.scalars().all())

    if not items:
        cat_list = "\n".join(f"{i + 1}. {c['name']}" for i, c in enumerate(categories))
        return FlowResult(
            next_step="browsing",
            messages=[
                f"A categoria *{selected['name']}* está sem itens no momento.\n\n"
                f"Escolha outra categoria:\n{cat_list}"
            ],
            data=state.data,
        )

    messages = []
    for i, item in enumerate(items):
        caption = f"{i + 1}. *{item.name}*\n{_fmt_price(item.price)}"
        if item.description:
            caption += f"\n_{item.description}_"
        if item.image_url:
            messages.append(("image", item.image_url, caption))
        else:
            messages.append(("text", caption))

    item_list = "\n".join(
        f"{i + 1}. {it.name} — {_fmt_price(it.price)}" for i, it in enumerate(items)
    )
    messages.append(("text", f"*{selected['name']}*\n\n{item_list}\n\nDigite o *número* do item desejado.\n*0* para ver o carrinho | *M* para trocar de categoria"))

    new_data = {
        **state.data,
        "mode": "item",
        "items": [
            {"id": str(it.id), "name": it.name, "price": str(it.price), "image_url": it.image_url}
            for it in items
        ],
    }

    return FlowResult(
        next_step="browsing",
        messages=messages,
        data=new_data,
    )


async def _handle_item_selection(state, text: str, restaurant: Restaurant, db: AsyncSession) -> FlowResult:
    text_lower = text.strip().lower()
    items = state.data.get("items", [])
    categories = state.data.get("categories", [])
    cart = list(state.cart or [])

    # Go back to category selection
    if text_lower in ("m", "menu", "categorias", "voltar"):
        cat_list = "\n".join(f"{i + 1}. {c['name']}" for i, c in enumerate(categories))
        return FlowResult(
            next_step="browsing",
            messages=[f"Escolha uma categoria:\n\n{cat_list}"],
            data={**state.data, "mode": "category"},
        )

    # View cart or checkout
    if text_lower in ("0", "f", "finalizar", "carrinho", "ver carrinho"):
        if not cart:
            return FlowResult(
                next_step="browsing",
                messages=["Seu carrinho está vazio. Adicione itens antes de finalizar."],
                data=state.data,
            )
        from app.bot.flows.cart import handle as cart_handle
        return await cart_handle(state, text, restaurant, db)

    # Item number selection
    if not text.isdigit() or not (1 <= int(text) <= len(items)):
        item_list = "\n".join(f"{i + 1}. {it['name']} — {_fmt_price(it['price'])}" for i, it in enumerate(items))
        return FlowResult(
            next_step="browsing",
            messages=[f"Opção inválida. Escolha um número da lista:\n\n{item_list}"],
            data=state.data,
        )

    selected_item = items[int(text) - 1]

    # Add to cart (merge quantity if same item already in cart)
    added = False
    for cart_item in cart:
        if cart_item["menu_item_id"] == selected_item["id"]:
            cart_item["quantity"] += 1
            added = True
            break
    if not added:
        cart.append({
            "menu_item_id": selected_item["id"],
            "name": selected_item["name"],
            "price": selected_item["price"],
            "quantity": 1,
            "notes": None,
        })

    subtotal = sum(float(i["price"]) * i["quantity"] for i in cart)
    confirm = (
        f"✅ *{selected_item['name']}* adicionado ao carrinho!\n\n"
        f"Subtotal atual: {_fmt_price(subtotal)}\n\n"
        f"Digite o número de outro item, *M* para trocar de categoria ou *F* para finalizar o pedido."
    )

    return FlowResult(
        next_step="browsing",
        messages=[confirm],
        cart=cart,
        data=state.data,
    )
