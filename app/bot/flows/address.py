from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Restaurant
from app.bot.flows.greeting import FlowResult


def _fmt_price(value) -> str:
    return f"R$ {float(value):.2f}".replace(".", ",")


async def handle(state, text: str, restaurant: Restaurant, db: AsyncSession) -> FlowResult:
    text_stripped = text.strip()
    text_lower = text_stripped.lower()
    cart = list(state.cart or [])

    is_pickup = text_lower in ("r", "retirar", "retirada", "buscar")

    if len(text_stripped) < 5 and not is_pickup:
        return FlowResult(
            next_step="address",
            messages=[
                "Por favor, informe o endereço completo (rua, número e bairro).\n\n"
                "Ou digite *R* para retirar no local."
            ],
            data=state.data,
        )

    address = "Retirada no local" if is_pickup else text_stripped
    delivery_fee = 0.0 if is_pickup else float(restaurant.delivery_fee or 0)
    subtotal = sum(float(i["price"]) * i["quantity"] for i in cart)
    total = subtotal + delivery_fee

    fee_line = "Grátis (retirada no local)" if is_pickup else _fmt_price(delivery_fee)

    payment_msg = (
        f"💰 *Resumo do pedido:*\n\n"
        f"Subtotal: {_fmt_price(subtotal)}\n"
        f"Taxa de entrega: {fee_line}\n"
        f"*Total: {_fmt_price(total)}*\n\n"
        f"Como deseja pagar?\n"
        f"*1* — Pix\n"
        f"*2* — Cartão de crédito/débito"
    )

    new_data = {
        **state.data,
        "address": address,
        "pickup": is_pickup,
        "delivery_fee": str(delivery_fee),
        "subtotal": str(subtotal),
        "total": str(total),
    }

    return FlowResult(
        next_step="payment",
        messages=[payment_msg],
        data=new_data,
    )
