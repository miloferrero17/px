import os
from twilio.rest import Client
from datetime import datetime
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
import json

# Cargar variables de entorno
load_dotenv()

# Configuración de Twilio
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

# Validación de configuración
if not account_sid or  not auth_token or not twilio_whatsapp_number:
    raise ValueError(
        "⚠️ Faltan variables de entorno: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN o TWILIO_WHATSAPP_NUMBER."
    )

# Inicialización del cliente Twilio
client = Client(account_sid, auth_token)

# app/services/twilio_service.py
import logging

logger = logging.getLogger("twilio_service")


def send_whatsapp_message(body, to, media_url=None):
    """
    Envía un mensaje de WhatsApp utilizando Twilio y retorna el SID.
    - Sin emojis en logs (evita UnicodeEncodeError en Windows).
    - No loguea PII (no imprime el número completo).
    - Acepta media_url como str o lista (Twilio prefiere lista).
    """
    try:
        if not str(to).startswith("whatsapp:"):
            logger.warning("Número malformado: debe comenzar con 'whatsapp:'")

        media_param = None
        if media_url:
            media_param = media_url if isinstance(media_url, (list, tuple)) else [media_url]

        message = client.messages.create(
            from_=f"whatsapp:{twilio_whatsapp_number}",
            body=body,
            to=to,
            media_url=media_param
        )

        logger.info("Mensaje enviado correctamente (provider=twilio, sid=%s)", message.sid)
        return message.sid  # ← devolvemos el SID (string)

    except Exception as e:
        logger.error("Error al enviar WhatsApp (provider=twilio): %s", e)
        raise RuntimeError(f"Error al enviar el mensaje de WhatsApp: {e}")


def download_file(sender, media_url, media_type, folder):
    """
    Descarga y guarda archivos multimedia de WhatsApp (audio o imagen).
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        response = requests.get(media_url, auth=HTTPBasicAuth(account_sid, auth_token))

        if response.status_code == 200:
            file_extension = media_type.split("/")[-1]
            file_name = f"{folder}/{sender.replace(':', '_')}_{timestamp}.{file_extension}"

            with open(file_name, "wb") as file:
                file.write(response.content)

            print(f"✅ Archivo recibido y guardado como {file_name}")
            return file_name
        else:
            print(f"⚠️ Error al descargar el archivo. Código HTTP: {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ Error al descargar archivo desde {media_url}: {e}")
        return None

# ▶️ Probalo con tus datos
if __name__ == "__main__":
    send_whatsapp_message("+5491133585362")

'''
def send_whatsapp_buttons_real(to, body, buttons):
    """
    Envía un mensaje interactivo de WhatsApp con botones reales usando la API HTTP de Twilio.
    """
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    payload = {
        "To": to,
        "From": f"whatsapp:{twilio_whatsapp_number}",
        "Body": body,
        "PersistentAction": ",".join([f"reply:{btn}" for btn in buttons])
    }

    response = requests.post(url, headers=headers, data=payload, auth=HTTPBasicAuth(account_sid, auth_token))

    if response.status_code == 201:
        print("✅ Mensaje con botones enviado correctamente.")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")

def enviar_mensaje_si_no(to_number):


    message = client.messages.create(
        from_='whatsapp:+14155238886',  # Número de Twilio para WhatsApp
        to=f'whatsapp:{to_number}',
        content_sid='HXe63573ff8b82fca080364e4ed927a36c',  # Tu plantilla con botones
        content_variables='{"1":"Emilio"}'  # Si usaste un placeholder {{1}}, podés reemplazarlo
    )

    print(f"✅ Mensaje enviado. SID: {message.sid}")
    print(f"📬 Estado del mensaje: {message.status}") 
'''

