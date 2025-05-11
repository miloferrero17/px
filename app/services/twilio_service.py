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

def send_whatsapp_message(body, to, media_url=None):
    """
    Envía un mensaje de WhatsApp utilizando Twilio y loguea el resultado.
    """
    if not to.startswith("whatsapp:"):
        print(f"⚠️ Número malformado: '{to}' — debería comenzar con 'whatsapp:'")

    try:
        message = client.messages.create(
            from_=f'whatsapp:{twilio_whatsapp_number}',
            body=body,
            to=to,
            media_url=media_url if media_url else None
        )
        print(f"✅ Mensaje enviado a {to}. SID: {message.sid}")
        return message
    except Exception as e:
        print(f"❌ Error al enviar mensaje de WhatsApp a {to}: {e}")
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


'''
import os
from twilio.rest import Client
from datetime import datetime
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth


# Load variables from .env file
load_dotenv()

# Configuración de Twilio
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

# Validación de configuración
if not account_sid or not auth_token or not twilio_whatsapp_number:
    raise ValueError(
        "Configura las variables de entorno TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_WHATSAPP_NUMBER."
    )

# Inicialización del cliente Twilio
client = Client(account_sid, auth_token)

def send_whatsapp_message(body, to, media_url = None):
    """
    Envía un mensaje de WhatsApp utilizando Twilio.

    Parámetros:
        body (str): Contenido del mensaje.
        to (str): Número de WhatsApp del destinatario, en formato internacional (e.g., 'whatsapp:+123456789').

    Retorna:
        Message: Objeto de mensaje Twilio con los detalles del envío.

    Lanza:
        RuntimeError: Si ocurre algún error al enviar el mensaje.
    """
    try:
        message = client.messages.create(
            from_=f'whatsapp:{twilio_whatsapp_number}',
            body=body,
            to=to,
            media_url=media_url if media_url else None
        )
        return message
    except Exception as e:
        raise RuntimeError(f"Error al enviar el mensaje de WhatsApp: {e}")
    

def download_file(sender, media_url, media_type, folder):
    """ Descarga y guarda archivos de WhatsApp (audio o imagen) """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    response = requests.get(media_url,
                            auth=HTTPBasicAuth(account_sid,
                                              auth_token))
    if response.status_code == 200:
        file_extension = media_type.split("/")[-1]
        file_name = f"{folder}/{sender.replace(':', '_')}_{timestamp}.{file_extension}"

        with open(file_name, "wb") as file:
            file.write(response.content)

        print(f"✅ Archivo recibido y guardado como {file_name}")
        return {file_name}
    else:
        print(
            f"⚠️ Error al descargar el archivo. Código HTTP: {response.status_code}"
        )
        return f"⚠️ Error al descargar el archivo. Código HTTP: {response.status_code}"
'''