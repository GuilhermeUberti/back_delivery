import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Restaurant
from app.bot.models import ConversationState
from app.bot.zapi import ZAPIClient
from app.bot.flows import greeting, browsing, cart, address, payment

logger = logging.getLogger(__name__)

_HANDLERS = {
    "greeting": greeting.handle,
    "browsing": browsing.handle,
    "cart": cart.handle,
    "address": address.handle,
    "payment": payment.handle,
    "awaiting_payment": payment.handle_awaiting,
}


async def _get_restaurant_by_instance(zapi_instance_id: str, db: AsyncSession) -> Restaurant | None:
    result = await db.execute(
        select(Restaurant).where(
            and_(Restaurant.zapi_instance == zapi_instance_id, Restaurant.active.is_(True))
        )
    )
    return result.scalar_one_or_none()


async def _get_or_create_state(restaurant_id: uuid.UUID, whatsapp: str, db: AsyncSession) -> ConversationState:
    result = await db.execute(
        select(ConversationState).where(
            and_(
                ConversationState.restaurant_id == restaurant_id,
                ConversationState.whatsapp == whatsapp,
            )
        )
    )
    state = result.scalar_one_or_none()

    if not state:
        state = ConversationState(
            id=uuid.uuid4(),
            restaurant_id=restaurant_id,
            whatsapp=whatsapp,
            step="greeting",
            cart=[],
            data={},
        )
        db.add(state)
        await db.flush()

    return state


async def process_message(zapi_instance_id: str, whatsapp: str, text: str, db: AsyncSession) -> None:
    restaurant = await _get_restaurant_by_instance(zapi_instance_id, db)
    if not restaurant:
        logger.warning("No active restaurant for Z-API instance %s", zapi_instance_id)
        return

    state = await _get_or_create_state(restaurant.id, whatsapp, db)

    # Completed orders restart the flow
    if state.step == "done":
        state.step = "greeting"
        state.cart = []
        state.data = {}

    # Global cancel command — works at any step except greeting
    _CANCEL_KEYWORDS = {"cancelar", "cancel", "sair", "reiniciar", "restart", "#"}
    if state.step not in ("greeting",) and text.strip().lower() in _CANCEL_KEYWORDS:
        state.step = "greeting"
        state.cart = []
        state.data = {}
        await db.commit()
        zapi = ZAPIClient(restaurant.zapi_instance, restaurant.zapi_token)
        await zapi.send_text(
            whatsapp,
            "Pedido cancelado. 👋\n\nQuando quiser fazer um novo pedido, é só mandar uma mensagem!",
        )
        return

    handler = _HANDLERS.get(state.step, greeting.handle)

    try:
        result = await handler(state, text, restaurant, db)
    except Exception as exc:
        logger.exception("Flow handler error (step=%s, phone=%s): %s", state.step, whatsapp, exc)
        result = greeting.FlowResult(
            next_step=state.step,
            messages=["Ocorreu um erro interno. Tente novamente em instantes."],
        )

    # Persist new state
    state.step = result.next_step
    state.cart = result.cart if result.cart is not None else (state.cart or [])
    state.data = result.data if result.data is not None else (state.data or {})
    state.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Send messages via Z-API
    zapi = ZAPIClient(restaurant.zapi_instance, restaurant.zapi_token)
    for msg in result.messages:
        if isinstance(msg, tuple):
            kind, *args = msg
            if kind == "image":
                await zapi.send_image(whatsapp, args[0], args[1] if len(args) > 1 else "")
            else:
                await zapi.send_text(whatsapp, args[0])
        else:
            await zapi.send_text(whatsapp, str(msg))


async def confirm_payment(order_id: uuid.UUID, db: AsyncSession) -> None:
    """Called by payment webhooks after confirming a paid order."""
    from app.orders.models import Order
    from app.customers.models import Customer

    result = await db.execute(
        select(Order).where(and_(Order.id == order_id, Order.payment_status == "awaiting"))
    )
    order = result.scalar_one_or_none()
    if not order:
        logger.warning("confirm_payment: order %s not found or already processed", order_id)
        return

    order.payment_status = "paid"
    order.status = "confirmed"
    order.updated_at = datetime.now(timezone.utc)

    # Update conversation state to done
    state_result = await db.execute(
        select(ConversationState).where(
            and_(
                ConversationState.restaurant_id == order.restaurant_id,
                ConversationState.data["order_id"].astext == str(order_id),
            )
        )
    )
    state = state_result.scalar_one_or_none()
    if state:
        state.step = "done"
        state.updated_at = datetime.now(timezone.utc)

    await db.commit()

    # Notify customer
    customer_result = await db.execute(select(Customer).where(Customer.id == order.customer_id))
    customer = customer_result.scalar_one_or_none()

    restaurant_result = await db.execute(select(Restaurant).where(Restaurant.id == order.restaurant_id))
    restaurant = restaurant_result.scalar_one_or_none()

    if customer and restaurant:
        zapi = ZAPIClient(restaurant.zapi_instance, restaurant.zapi_token)
        await zapi.send_text(
            customer.whatsapp,
            f"✅ *Pagamento confirmado!*\n\n"
            f"Seu pedido #{str(order_id)[:8].upper()} foi recebido e está sendo preparado.\n"
            f"Você será notificado a cada atualização. 🍽️",
        )
