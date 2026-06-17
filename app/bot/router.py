import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.bot import engine
from app.orders.models import Order

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_phone(payload: dict) -> str | None:
    phone = payload.get("phone", "")
    return phone.replace("@c.us", "").strip() or None


def _extract_text(payload: dict) -> str | None:
    text_obj = payload.get("text") or {}
    return text_obj.get("message", "").strip() or None


# ---------- WhatsApp ----------

@router.post("/webhook")
async def whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    if payload.get("fromMe") or payload.get("type") != "ReceivedCallback":
        return {"status": "ignored"}

    phone = _extract_phone(payload)
    text = _extract_text(payload)
    instance_id = payload.get("instanceId", "")

    if not phone or not text or not instance_id:
        logger.debug("Webhook missing fields: phone=%s text=%s instance=%s", phone, text, instance_id)
        return {"status": "ignored"}

    await engine.process_message(
        zapi_instance_id=instance_id,
        whatsapp=phone,
        text=text,
        db=db,
    )

    return {"status": "ok"}


# ---------- Pix (OpenPix) ----------

@router.post("/payment/pix")
async def pix_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Webhook de confirmação de pagamento Pix da OpenPix.
    Payload: {"event": "OPENPIX:CHARGE_COMPLETED", "charge": {"correlationID": "...", ...}}
    """
    from app.config import settings as cfg

    # Valida token de webhook configurado no painel OpenPix
    webhook_token = request.headers.get("x-webhook-token", "")
    if cfg.OPENPIX_WEBHOOK_TOKEN and webhook_token != cfg.OPENPIX_WEBHOOK_TOKEN:
        logger.warning("OpenPix webhook: invalid token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    event = payload.get("event", "")
    if "CHARGE_COMPLETED" not in event:
        return {"status": "ignored"}

    charge = payload.get("charge") or {}
    correlation_id = charge.get("correlationID", "")
    if not correlation_id:
        return {"status": "ignored"}

    result = await db.execute(
        select(Order).where(
            and_(Order.payment_ref == correlation_id, Order.payment_status == "awaiting")
        )
    )
    order = result.scalar_one_or_none()
    if order:
        await engine.confirm_payment(order.id, db)
    else:
        logger.warning("OpenPix webhook: order not found for correlationID=%s", correlation_id)

    return {"status": "ok"}


# ---------- Cartão (Mercado Pago) ----------

@router.post("/payment/card")
async def card_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Webhook IPN do Mercado Pago.
    Valida assinatura e confirma o pedido quando pagamento aprovado.
    """
    body = await request.body()

    # Validate MP signature
    x_signature = request.headers.get("x-signature", "")
    x_request_id = request.headers.get("x-request-id", "")
    if x_signature:
        from app.payments.mercadopago import validate_webhook_signature
        if not validate_webhook_signature(x_signature, x_request_id, body):
            logger.warning("MP webhook: invalid signature")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        import json
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    action = payload.get("action", "")
    if action not in ("payment.created", "payment.updated"):
        return {"status": "ignored"}

    payment_id = (payload.get("data") or {}).get("id")
    if not payment_id:
        return {"status": "ignored"}

    try:
        from app.payments.mercadopago import get_payment
        payment = await get_payment(str(payment_id))
    except Exception as exc:
        logger.error("MP webhook: failed to fetch payment %s: %s", payment_id, exc)
        return {"status": "error"}

    if payment.get("status") != "approved":
        return {"status": "ignored"}

    # external_reference stores our order_id
    order_id_str = payment.get("external_reference", "")
    preference_id = payment.get("preference_id", "")

    if not order_id_str and not preference_id:
        logger.warning("MP webhook: no reference in payment %s", payment_id)
        return {"status": "ignored"}

    # Look up order by external_reference (order_id) or preference_id (payment_ref)
    import uuid as _uuid
    order = None

    if order_id_str:
        try:
            oid = _uuid.UUID(order_id_str)
            result = await db.execute(
                select(Order).where(
                    and_(Order.id == oid, Order.payment_status == "awaiting")
                )
            )
            order = result.scalar_one_or_none()
        except ValueError:
            pass

    if not order and preference_id:
        result = await db.execute(
            select(Order).where(
                and_(Order.payment_ref == preference_id, Order.payment_status == "awaiting")
            )
        )
        order = result.scalar_one_or_none()

    if order:
        await engine.confirm_payment(order.id, db)
    else:
        logger.warning("MP webhook: order not found for payment %s", payment_id)

    return {"status": "ok"}
