import hashlib
import hmac
import logging
from decimal import Decimal

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://api.mercadopago.com"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


async def create_preference(order_id: str, total: Decimal) -> dict:
    if not settings.MP_ACCESS_TOKEN:
        raise RuntimeError("MP_ACCESS_TOKEN não configurado")
    """
    Cria preferência de pagamento no Mercado Pago.

    Retorna:
        preference_id   — ID da preferência (salvar em orders.payment_ref)
        init_point      — link de pagamento para enviar ao cliente
    """
    payload = {
        "items": [
            {
                "title": f"ZaPedido #{order_id[:8].upper()}",
                "quantity": 1,
                "unit_price": float(total),
                "currency_id": "BRL",
            }
        ],
        "external_reference": order_id,
        "notification_url": settings.MP_NOTIFICATION_URL,
        "auto_return": "approved",
        "back_urls": {
            "success": settings.MP_NOTIFICATION_URL or "https://zapedido.com.br",
            "failure": settings.MP_NOTIFICATION_URL or "https://zapedido.com.br",
            "pending": settings.MP_NOTIFICATION_URL or "https://zapedido.com.br",
        },
        "statement_descriptor": "ZAPEDIDO",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_BASE}/checkout/preferences",
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "preference_id": data["id"],
        "init_point": data["init_point"],
        "sandbox_init_point": data.get("sandbox_init_point", ""),
    }


async def get_payment(payment_id: str) -> dict:
    """Busca detalhes de um pagamento pelo ID retornado no webhook IPN."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE}/v1/payments/{payment_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


def validate_webhook_signature(x_signature: str, x_request_id: str, body: bytes) -> bool:
    """
    Valida assinatura do webhook IPN do Mercado Pago.
    Docs: https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks
    """
    try:
        parts = dict(item.split("=", 1) for item in x_signature.split(","))
        ts = parts.get("ts", "")
        received_hash = parts.get("v1", "")

        manifest = f"id:{x_request_id};request-id:{x_request_id};ts:{ts};"
        computed = hmac.new(
            settings.MP_ACCESS_TOKEN.encode(),
            manifest.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed, received_hash)
    except Exception:
        return False
