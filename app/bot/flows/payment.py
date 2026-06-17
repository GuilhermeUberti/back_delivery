import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Restaurant
from app.bot.flows.greeting import FlowResult
from app.customers.service import get_or_create as get_or_create_customer
from app.orders.models import Order, OrderItem

logger = logging.getLogger(__name__)


async def handle(state, text: str, restaurant: Restaurant, db: AsyncSession) -> FlowResult:
    text_lower = text.strip().lower()

    if text_lower not in ("1", "2", "pix", "cartão", "cartao", "card"):
        return FlowResult(
            next_step="payment",
            messages=["Escolha a forma de pagamento:\n\n*1* — Pix\n*2* — Cartão de crédito/débito"],
            data=state.data,
        )

    method = "pix" if text_lower in ("1", "pix") else "credit_card"

    # Reuse existing order if a previous attempt failed — avoids duplicate orders on retry
    existing_order_id = state.data.get("order_id")
    if existing_order_id:
        try:
            oid = uuid.UUID(existing_order_id)
            result = await db.execute(select(Order).where(Order.id == oid))
            order = result.scalar_one_or_none()
            if order and order.payment_status == "awaiting":
                order.payment_method = method
                await db.commit()
                new_data = {**state.data, "payment_method": method}
                customer = await get_or_create_customer(
                    restaurant_id=restaurant.id,
                    whatsapp=state.whatsapp,
                    db=db,
                    address=state.data.get("address"),
                )
                if method == "pix":
                    return await _handle_pix(restaurant, new_data, order, customer.name or "Cliente")
                else:
                    return await _handle_card(new_data, order)
        except (ValueError, Exception):
            pass

    customer = await get_or_create_customer(
        restaurant_id=restaurant.id,
        whatsapp=state.whatsapp,
        db=db,
        address=state.data.get("address"),
    )

    order_id = uuid.uuid4()
    total = Decimal(state.data.get("total", "0"))
    order = Order(
        id=order_id,
        restaurant_id=restaurant.id,
        customer_id=customer.id,
        status="pending",
        payment_method=method,
        payment_status="awaiting",
        subtotal=Decimal(state.data.get("subtotal", "0")),
        delivery_fee=Decimal(state.data.get("delivery_fee", "0")),
        total=total,
        address=state.data.get("address"),
    )
    db.add(order)
    await db.flush()

    for cart_item in (state.cart or []):
        db.add(OrderItem(
            id=uuid.uuid4(),
            order_id=order_id,
            menu_item_id=cart_item.get("menu_item_id"),
            name=cart_item["name"],
            price=Decimal(str(cart_item["price"])),
            quantity=cart_item["quantity"],
            notes=cart_item.get("notes"),
        ))

    await db.commit()

    new_data = {**state.data, "order_id": str(order_id), "payment_method": method}

    if method == "pix":
        return await _handle_pix(restaurant, new_data, order, customer.name or "Cliente")
    else:
        return await _handle_card(new_data, order)


async def _handle_pix(
    restaurant: Restaurant, data: dict, order: Order, customer_name: str
) -> FlowResult:
    from app.payments.efi import create_charge
    from app.orders.models import Order as OrderModel
    from app.database import AsyncSessionLocal

    if not restaurant.pix_key:
        return FlowResult(
            next_step="payment",
            messages=["❌ Este restaurante ainda não configurou a chave Pix. Entre em contato diretamente."],
            data=data,
        )

    try:
        charge = await create_charge(
            amount=order.total,
            pix_key=restaurant.pix_key,
            order_id=str(order.id),
            customer_name=customer_name,
            expiration_seconds=600,
        )
    except Exception as exc:
        logger.exception("Efí Bank create_charge failed for order %s: %s", order.id, exc)
        return FlowResult(
            next_step="payment",
            messages=["❌ Erro ao gerar cobrança Pix. Tente novamente ou escolha outra forma de pagamento."],
            data=data,
        )

    # Persist payment_ref (txid)
    async with AsyncSessionLocal() as db2:
        result = await db2.execute(select(OrderModel).where(OrderModel.id == order.id))
        persisted = result.scalar_one_or_none()
        if persisted:
            persisted.payment_ref = charge["txid"]
            await db2.commit()

    messages = []

    if charge.get("qr_image"):
        messages.append(("image", charge["qr_image"], f"QR Code Pix — ZaPedido #{str(order.id)[:8].upper()}"))

    pix_msg = (
        f"⚡ *Pagamento via Pix*\n\n"
        f"*Valor:* R$ {float(order.total):.2f}".replace(".", ",") + "\n\n"
        f"*Código Pix copia-e-cola:*\n`{charge['pix_copy_paste']}`\n\n"
        f"⏳ Você tem *10 minutos* para efetuar o pagamento.\n"
        f"Assim que confirmarmos, avisaremos aqui."
    )
    messages.append(pix_msg)

    return FlowResult(next_step="awaiting_payment", messages=messages, data=data)


async def _handle_card(data: dict, order: Order) -> FlowResult:
    from app.payments.mercadopago import create_preference
    from app.orders.models import Order as OrderModel
    from app.database import AsyncSessionLocal

    try:
        preference = await create_preference(
            order_id=str(order.id),
            total=order.total,
        )
    except Exception as exc:
        logger.exception("Mercado Pago create_preference failed for order %s: %s", order.id, exc)
        return FlowResult(
            next_step="payment",
            messages=["❌ Erro ao gerar link de pagamento. Tente novamente ou escolha outra forma de pagamento."],
            data=data,
        )

    # Persist payment_ref (preference_id)
    async with AsyncSessionLocal() as db2:
        result = await db2.execute(select(OrderModel).where(OrderModel.id == order.id))
        persisted = result.scalar_one_or_none()
        if persisted:
            persisted.payment_ref = preference["preference_id"]
            await db2.commit()

    link = preference["sandbox_init_point"] or preference["init_point"]

    card_msg = (
        f"💳 *Pagamento via Cartão*\n\n"
        f"*Valor:* R$ {float(order.total):.2f}".replace(".", ",") + "\n\n"
        f"Acesse o link abaixo para pagar:\n{link}\n\n"
        f"⏳ Você tem *15 minutos* para efetuar o pagamento.\n"
        f"Assim que confirmarmos, avisaremos aqui."
    )

    return FlowResult(next_step="awaiting_payment", messages=[card_msg], data=data)


async def handle_awaiting(state, text: str, restaurant: Restaurant, db: AsyncSession) -> FlowResult:
    return FlowResult(
        next_step="awaiting_payment",
        messages=[
            "⏳ Aguardando confirmação do pagamento.\n\n"
            "Assim que o pagamento for confirmado, você receberá uma mensagem aqui. 😊"
        ],
        data=state.data,
    )
