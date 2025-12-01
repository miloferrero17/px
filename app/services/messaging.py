import os

import app.services.twilio_service as twilio
from app.services import meta_whatsapp_service as meta

# Por defecto seguimos usando Twilio,
# más adelante en /etc/px.env podremos poner WHATSAPP_PROVIDER=meta
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "twilio")


def send_message(body: str, to: str):
    """
    Capa de abstracción para enviar mensajes de WhatsApp.

    - Si WHATSAPP_PROVIDER = "meta"  -> usa Cloud API de Meta
    - Si WHATSAPP_PROVIDER = "twilio" (default) -> usa Twilio
    """
    if WHATSAPP_PROVIDER == "meta":
        return meta.send_whatsapp_message(body, to)
    else:
        # comportamiento actual: Twilio
        return twilio.send_whatsapp_message(body, to)
