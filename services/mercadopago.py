"""Mercado Pago PIX charges (Orders API).

Only one payment provider exists for OpsVenda, so unlike BookCase's PIX
integration this is plain functions reading MERCADO_PAGO_ACCESS_TOKEN from
the environment per call (matching services/telemetry.py's style), not a
provider class/ABC. Every function fails soft - a bad response or network
error never raises, callers check the return value.
"""

import logging
import os
import uuid

import requests

from services.pricing import from_cents

logger = logging.getLogger(__name__)

API_URL = "https://api.mercadopago.com"
STATUS_PAGO = {"completed", "approved", "settlement", "accredited"}
REQUEST_TIMEOUT = 10


def is_configured() -> bool:
    return bool(os.environ.get("MERCADO_PAGO_ACCESS_TOKEN", "").strip())


def _headers(idempotency_key: str) -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('MERCADO_PAGO_ACCESS_TOKEN', '').strip()}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": idempotency_key,
    }


def create_pix_charge(amount_cents: int, external_reference: str, description: str = "Assinatura OpsVenda") -> dict:
    """Creates a PIX order. Returns
    {"mp_order_id", "mp_payment_id", "qr_code_text", "qr_code_image", "status"}
    on success, or {"erro": "..."} on any failure - never raises.
    """
    if not is_configured():
        return {"erro": "Mercado Pago não configurado (MERCADO_PAGO_ACCESS_TOKEN ausente)."}

    valor = f"{from_cents(amount_cents):.2f}"
    body = {
        "type": "online",
        "external_reference": external_reference,
        "total_amount": valor,
        "processing_mode": "automatic",
        "description": description,
        "payer": {
            "email": "pagador@opsvenda.montiqtech.com.br",
            "first_name": "Cliente",
            "last_name": "OpsVenda",
            "identification": {"type": "CPF", "number": "00000000000"},
        },
        "items": [
            {
                "title": description,
                "description": description,
                "quantity": 1,
                "unit_price": valor,
                "category_id": "others",
            }
        ],
        "transactions": {
            "payments": [{"amount": valor, "payment_method": {"id": "pix", "type": "bank_transfer"}}]
        },
    }

    try:
        resp = requests.post(
            f"{API_URL}/v1/orders",
            json=body,
            headers=_headers(external_reference or uuid.uuid4().hex),
            timeout=REQUEST_TIMEOUT,
        )
        dados = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error("Falha ao gerar cobrança PIX: %s", exc)
        return {"erro": "Não foi possível gerar a cobrança agora. Tente novamente."}

    if not resp.ok:
        logger.error("Mercado Pago recusou a cobrança PIX: %s %s", resp.status_code, dados)
        return {"erro": "Não foi possível gerar a cobrança agora. Tente novamente."}

    try:
        payment = dados["transactions"]["payments"][0]
        payment_method = payment.get("payment_method", {})
        qr_code_text = payment_method.get("qr_code")
        qr_code_image_b64 = payment_method.get("qr_code_base64")
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Resposta inesperada do Mercado Pago ao gerar PIX: %s (%s)", dados, exc)
        return {"erro": "Resposta inesperada do Mercado Pago. Tente novamente."}

    return {
        "mp_order_id": dados.get("id", external_reference),
        "mp_payment_id": payment.get("id"),
        "qr_code_text": qr_code_text,
        "qr_code_image": f"data:image/png;base64,{qr_code_image_b64}" if qr_code_image_b64 else None,
        "status": dados.get("status", "pending"),
    }


def check_status(mp_order_id: str, mp_payment_id: str | None = None) -> dict | None:
    """Returns {"paid": bool} on success, None on a transport/config error
    (distinct from {"paid": False} - callers should treat None as "couldn't
    check right now", not as "confirmed unpaid").
    """
    if not is_configured() or not mp_order_id:
        return None

    headers = {"Authorization": f"Bearer {os.environ.get('MERCADO_PAGO_ACCESS_TOKEN', '').strip()}"}

    try:
        resp = requests.get(f"{API_URL}/v1/orders/{mp_order_id}", headers=headers, timeout=REQUEST_TIMEOUT)
        order = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error("Falha ao consultar status do pedido PIX %s: %s", mp_order_id, exc)
        return None

    if not resp.ok:
        return None

    if order.get("status") in STATUS_PAGO or order.get("status_detail") in STATUS_PAGO:
        return {"paid": True}

    for payment in order.get("transactions", {}).get("payments", []):
        if payment.get("status") in STATUS_PAGO or payment.get("status_detail") in STATUS_PAGO:
            return {"paid": True}

    if mp_payment_id:
        try:
            resp = requests.get(
                f"{API_URL}/v1/payments/{mp_payment_id}", headers=headers, timeout=REQUEST_TIMEOUT
            )
            payment = resp.json()
        except (requests.RequestException, ValueError):
            return {"paid": False}
        if resp.ok and payment.get("status") in STATUS_PAGO:
            return {"paid": True}

    return {"paid": False}
