import logging
from decimal import Decimal

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.openpix.com.br/api/v1"


def _headers() -> dict:
    return {"Authorization": settings.OPENPIX_APP_ID, "Content-Type": "application/json"}


async def create_charge(
    amount: Decimal,
    order_id: str,
    customer_name: str = "Cliente",
    expiration_seconds: int = 600,
) -> dict:
    """
    Cria cobrança Pix na OpenPix.

    Retorna:
        correlation_id  — ID da cobrança (salvar em orders.payment_ref)
        pix_copy_paste  — código copia-e-cola para enviar ao cliente
        qr_image        — imagem QR code (data:image/png;base64,...) ou None
    """
    payload = {
        "correlationID": order_id,
        "value": int(amount * 100),  # centavos
        "comment": f"ZaPedido #{order_id[:8].upper()}",
        "expiresIn": expiration_seconds,
        "customer": {"name": customer_name},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_BASE_URL}/charge",
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    charge = data["charge"]
    return {
        "correlation_id": charge["correlationID"],
        "pix_copy_paste": charge.get("brCode", ""),
        "qr_image": charge.get("qrCodeImage"),
    }
