import os
import requests

# ⚠️ COMPLETAR con tus valores de Meta
META_API_VERSION   = os.getenv("META_API_VERSION", "v24.0")
META_WABA_PHONE_ID = os.getenv("META_WABA_PHONE_ID")  # ej: "891909964005536"
META_WABA_TOKEN    = os.getenv("META_WABA_TOKEN")     # tu token de acceso de Meta

GRAPH_URL = f"https://graph.facebook.com/{META_API_VERSION}"


def _normalize_to_number(to: str) -> str:
    """
    Convierte:
      - 'whatsapp:+5492477661029' -> '5492477661029'
      - '+5492477661029' -> '5492477661029'
      - '5492477661029' -> '5492477661029'
    """
    if not to:
        raise ValueError("Destinatario 'to' vacío")

    to = to.replace("whatsapp:", "")
    to = to.replace("+", "")
    return to


def send_whatsapp_message(body: str, to: str):
    """
    Envía un mensaje de texto usando WhatsApp Cloud API (Meta).

    :param body: Texto del mensaje
    :param to: Número del paciente (formato 'whatsapp:+549...' o '+549...' o '549...')
    """
    if not META_WABA_PHONE_ID or not META_WABA_TOKEN:
        raise RuntimeError("META_WABA_PHONE_ID o META_WABA_TOKEN no configurados")

    to_number = _normalize_to_number(to)

    url = f"{GRAPH_URL}/{META_WABA_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_WABA_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "body": body
        },
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    if not resp.ok:
        raise RuntimeError(f"Error Meta WhatsApp API {resp.status_code}: {resp.text}")

    return resp.json()
