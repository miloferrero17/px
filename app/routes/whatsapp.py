# Módulos Built-in
import flask
from flask import request, current_app

import os
import requests
import time
from dotenv import load_dotenv

# Terceros
from requests.auth import HTTPBasicAuth
from twilio.twiml.messaging_response import MessagingResponse

# Propios
import app.services.twilio_service as twilio
import app.services.wisper as wisper
import app.services.vision as vision
import app.message_p as engine

from app.routes import routes as bp  # <- usamos el mismo blueprint "routes"

# Cargar variables de entorno y constantes locales
load_dotenv()
TMP_DIR = "/tmp"

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "px_meta_2025")


@bp.route("/", methods=["GET", "POST"])
def whatsapp_reply():
    if flask.request.method == 'GET':
        return "✅ Server is running and accessible via GET request."

    sender_number = flask.request.form.get('From')
    message_body  = flask.request.form.get("Body", "").strip()
    num_media     = int(flask.request.form.get("NumMedia", 0))
    media_url     = flask.request.form.get("MediaUrl0")
    media_type    = flask.request.form.get("MediaContentType0")

    file_path = ""
    tiene_adjunto = 0
    description = ""
    transcription = ""
    pdf_text = ""

    if num_media > 0:
        # Crear carpeta temporal para el archivo recibido
        clean_sender = sender_number.replace(":", "_").replace("+", "")
        folder = os.path.join(TMP_DIR, f"{clean_sender}_media")
        os.makedirs(folder, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        extension = media_type.split("/")[-1]
        nombre_del_archivo = f"{clean_sender}_{timestamp}.{extension}"
        file_path = os.path.join(folder, nombre_del_archivo)

        try:
            reply_path = download_file(media_url, file_path)

            if media_type.startswith("audio"):
                print("🎙️ Es audio")
                twilio.send_whatsapp_message("Te estoy escuchando ...", sender_number)
                transcription = wisper.transcribir_audio_cloud(reply_path)
                print(f"📝 Transcripción: {transcription}")
                message_body = transcription
                tiene_adjunto = 1

            elif media_type.startswith("image"):
                print("🖼️ Es imagen")
                twilio.send_whatsapp_message("Dejame ver tu imagen ...", sender_number)
                description = vision.describe_image(reply_path)
                #print(f"🧠 Descripción generada: {description}")
                message_body = message_body + description
                tiene_adjunto = 1

            elif media_type == "application/pdf":
                print("📄 Es PDF")
                twilio.send_whatsapp_message("Dejame ver tu archivo ...", sender_number)
                pdf_text = vision.extract_text_from_pdf(reply_path)
                pdf_text = vision.resumir_texto_largo(pdf_text)
                print(f"📄 Texto resumido del PDF:\n{pdf_text[:300]}...")
                message_body = message_body + pdf_text
                tiene_adjunto = 1
            else:
                print("⚠️ Tipo de archivo no soportado:", media_type)
                twilio.send_whatsapp_message(
                    "⚠️ Tipo de archivo no soportado. Enviá audio, imagen o PDF.", sender_number
                )

        except Exception as e:
            print("❌ Error procesando media:", str(e))
            twilio.send_whatsapp_message("❌ Hubo un problema procesando el archivo. Intentalo de nuevo.", sender_number)
            return str(MessagingResponse())

    # En todos los casos (texto, transcripción, imagen, PDF)
    try:
        engine.handle_incoming_message(
            message_body, sender_number, tiene_adjunto, media_type,
            file_path, transcription, description, pdf_text
        )
    except Exception as e:
        print(f"❌ Error en engine: {e}")
        twilio.send_whatsapp_message("❌ Ocurrió un error interno al procesar tu mensaje.", sender_number)

    return str(MessagingResponse())


def download_file(media_url: str, file_path: str) -> str:
    """Descarga un archivo multimedia desde Twilio con autenticación."""
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
        if not account_sid or not auth_token:
            raise ValueError("TWILIO_ACCOUNT_SID o TWILIO_AUTH_TOKEN no están definidos")

        response = requests.get(media_url, auth=HTTPBasicAuth(account_sid, auth_token), timeout=10)
        response.raise_for_status()

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(response.content)

        print(f"✅ Archivo descargado en: {file_path}")
        return file_path

    except Exception as e:
        print(f"❌ Error al descargar archivo desde {media_url}: {e}")
        raise

@bp.route("/whatsapp/meta/webhook", methods=["GET", "POST"])
def meta_webhook():
    """
    Webhook de Meta WhatsApp Cloud API.
    - GET: verificación inicial (hub.challenge)
    - POST: eventos de mensajes, estados, etc.
    """

    # 1) Verificación inicial de Meta (GET)
    if request.method == "GET":
        mode      = request.args.get("hub.mode")
        token     = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == META_VERIFY_TOKEN and challenge:
            current_app.logger.info("META WEBHOOK VERIFY OK")
            return challenge, 200

        current_app.logger.warning(
            "META WEBHOOK VERIFY FAIL: mode=%s token=%s", mode, token
        )
        return "Forbidden", 403

    # 2) Eventos normales (POST)
    data = request.get_json(silent=True) or {}
    current_app.logger.info("META WHATSAPP WEBHOOK EVENT: %s", data)

    # Más adelante acá llamamos al engine.handle_incoming_message, etc.
    return "EVENT_RECEIVED", 200
