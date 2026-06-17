import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://api.z-api.io/instances/{instance}/token/{token}"


def _clean_phone(phone: str) -> str:
    return phone.replace("@c.us", "").replace("+", "").strip()


class ZAPIClient:
    def __init__(self, instance: str | None = None, token: str | None = None):
        self._instance = instance or settings.ZAPI_INSTANCE
        self._token = token or settings.ZAPI_TOKEN
        self._base = _BASE.format(instance=self._instance, token=self._token)

    async def send_text(self, phone: str, message: str) -> None:
        phone = _clean_phone(phone)
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(
                    f"{self._base}/send-text",
                    json={"phone": phone, "message": message},
                    headers={"Client-Token": settings.ZAPI_CLIENT_TOKEN},
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error("Z-API send_text failed for %s: %s | body: %s", phone, exc, exc.response.text)
            except Exception as exc:
                logger.error("Z-API send_text failed for %s: %s", phone, exc)

    async def send_image(self, phone: str, image_url: str, caption: str = "") -> None:
        phone = _clean_phone(phone)
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.post(
                    f"{self._base}/send-image",
                    json={"phone": phone, "image": image_url, "caption": caption},
                    headers={"Client-Token": settings.ZAPI_CLIENT_TOKEN},
                )
                resp.raise_for_status()
            except Exception as exc:
                logger.error("Z-API send_image failed for %s: %s", phone, exc)

    async def send_text_list(self, phone: str, messages: list[str]) -> None:
        for msg in messages:
            await self.send_text(phone, msg)


STATUS_MESSAGES = {
    "preparing": "👨‍🍳 Seu pedido está sendo preparado! Em breve ficará pronto.",
    "ready": "✅ Seu pedido está pronto! O entregador já está a caminho.",
    "delivered": "🎉 Pedido entregue! Bom apetite! Obrigado pela preferência. 😊",
    "cancelled": "❌ Seu pedido foi cancelado. Entre em contato conosco se tiver dúvidas.",
}


async def notify_status(phone: str, status: str, zapi_instance: str | None, zapi_token: str | None) -> None:
    msg = STATUS_MESSAGES.get(status)
    if not msg:
        return
    client = ZAPIClient(zapi_instance, zapi_token)
    await client.send_text(phone, msg)
