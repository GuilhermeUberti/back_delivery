from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Restaurant
from app.bot.flows.greeting import FlowResult


def _fmt_price(value) -> str:
    return f"R$ {float(value):.2f}".replace(".", ",")


def _cart_summary(cart: list[dict]) -> tuple[str, float]:
    lines = []
    subtotal = 0.0
    for item in cart:
        qty = item["quantity"]
        price = float(item["price"])
        lines.append(f"{qty}x {item['name']} — {_fmt_price(price * qty)}")
        subtotal += price * qty
    return "\n".join(lines), subtotal


async def handle(state, text: str, restaurant: Restaurant, db: AsyncSession) -> FlowResult:
    cart = list(state.cart or [])
    text_lower = text.strip().lower()

    # If arriving here from browsing with an empty command, just show the cart
    if not cart:
        return FlowResult(
            next_step="browsing",
            messages=["Seu carrinho está vazio. Escolha itens do cardápio primeiro."],
            data=state.data,
        )

    # Actions when already in cart step
    if state.step == "cart":
        if text_lower in ("c", "continuar", "adicionar"):
            categories = state.data.get("categories", [])
            cat_list = "\n".join(f"{i + 1}. {c['name']}" for i, c in enumerate(categories))
            return FlowResult(
                next_step="browsing",
                messages=[f"Escolha uma categoria:\n\n{cat_list}"],
                data={**state.data, "mode": "category"},
            )

        if text_lower in ("x", "cancelar"):
            return FlowResult(
                next_step="greeting",
                messages=["Pedido cancelado. Quando quiser, é só mandar uma mensagem! 👋"],
                cart=[],
                data={},
            )

        if text_lower in ("f", "finalizar", "confirmar"):
            return FlowResult(
                next_step="address",
                messages=[
                    "📍 *Qual é o endereço de entrega?*\n\n"
                    "Digite o endereço completo (rua, número e bairro).\n\n"
                    "Ou digite *R* para retirar no local."
                ],
                data=state.data,
            )

    # Show cart (default — arriving from browsing or invalid input in cart step)
    summary, subtotal = _cart_summary(cart)
    msg = (
        f"🛒 *Seu carrinho:*\n\n"
        f"{summary}\n\n"
        f"*Subtotal:* {_fmt_price(subtotal)}\n\n"
        f"*F* — Finalizar pedido\n"
        f"*C* — Continuar comprando\n"
        f"*X* — Cancelar pedido"
    )

    return FlowResult(
        next_step="cart",
        messages=[msg],
        cart=cart,
        data=state.data,
    )
