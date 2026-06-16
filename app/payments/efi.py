import logging
import ssl
from decimal import Decimal

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_SANDBOX_URL = "https://pix-h.api.efipay.com.br"
_PROD_URL = "https://pix.api.efipay.com.br"


def _make_ssl_context() -> ssl.SSLContext | bool:
    """
    Produção: mTLS obrigatório pelo Banco Central do Brasil.
    Sandbox: aceita sem certificado, mas com verificação desabilitada.
    """
    if settings.EFI_CERT_PATH and settings.EFI_KEY_PATH:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_cert_chain(settings.EFI_CERT_PATH, settings.EFI_KEY_PATH)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if settings.EFI_SANDBOX:
        return False  # httpx: verify=False desativa verificação em sandbox
    raise RuntimeError("EFI_CERT_PATH e EFI_KEY_PATH são obrigatórios em produção")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(verify=_make_ssl_context(), timeout=30)


def _base() -> str:
    return _SANDBOX_URL if settings.EFI_SANDBOX else _PROD_URL


async def _get_token() -> str:
    async with _client() as client:
        resp = await client.post(
            f"{_base()}/oauth/token",
            auth=(settings.EFI_CLIENT_ID, settings.EFI_CLIENT_SECRET),
            json={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def _get_qrcode(token: str, loc_id: int) -> str | None:
    async with _client() as client:
        resp = await client.get(
            f"{_base()}/v2/qrcode/{loc_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.is_success:
            return resp.json().get("imagemQrcode")  # já vem como data:image/png;base64,...
    return None


async def create_charge(
    amount: Decimal,
    pix_key: str,
    order_id: str,
    customer_name: str = "Cliente",
    expiration_seconds: int = 600,
) -> dict:
    """
    Cria cobrança Pix na Efí Bank.

    Retorna:
        txid            — ID da cobrança (salvar em orders.payment_ref)
        pix_copy_paste  — código copia-e-cola para enviar ao cliente
        qr_image        — imagem QR code (data:image/png;base64,...) para enviar via Z-API
    """
    token = await _get_token()

    payload = {
        "calendario": {"expiracao": expiration_seconds},
        "devedor": {"nome": customer_name},
        "valor": {"original": f"{float(amount):.2f}"},
        "chave": pix_key,
        "solicitacaoPagador": f"ZaPedido #{order_id[:8].upper()}",
    }

    async with _client() as client:
        resp = await client.post(
            f"{_base()}/v2/cob",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()

    txid: str = data["txid"]
    pix_copy_paste: str = data.get("pixCopiaECola", "")
    loc_id: int | None = (data.get("loc") or {}).get("id")

    qr_image: str | None = None
    if loc_id:
        try:
            qr_image = await _get_qrcode(token, loc_id)
        except Exception as exc:
            logger.warning("Failed to fetch QR code for loc_id=%s: %s", loc_id, exc)

    return {"txid": txid, "pix_copy_paste": pix_copy_paste, "qr_image": qr_image}
