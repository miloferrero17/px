# Módulos Built-in
import flask
from flask import request, current_app

import os
import requests
import time
from dotenv import load_dotenv
from app.obs.logs import op_log

# Terceros
from requests.auth import HTTPBasicAuth
from twilio.twiml.messaging_response import MessagingResponse

# Propios
import app.services.wisper as wisper
import app.services.vision as vision
import app.message_p as engine
from app.services.messaging import send_message

from app.routes import routes as bp  # <- usamos el mismo blueprint "routes"

# Cargar variables de entorno y constantes locales
load_dotenv()
TMP_DIR = "/tmp"

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "px_meta_2025")
META_WABA_TOKEN = (
    os.getenv("META_WABA_TOKEN")
    or os.getenv("META_ACCESS_TOKEN")
    or os.getenv("META_WHATSAPP_TOKEN")
)

@bp.route("/", methods=["GET", "POST"])
def whatsapp_reply():
    if flask.request.method == 'GET':
        return "✅ Server is running and accessible via GET request."

    sender_number = flask.request.form.get('From')
    message_body  = (flask.request.form.get("Body") or "").strip()
    num_media_raw = flask.request.form.get("NumMedia", 0) or 0
    try:
        num_media = int(num_media_raw)
    except (TypeError, ValueError):
        num_media = 0

    media_url  = flask.request.form.get("MediaUrl0")
    media_type = flask.request.form.get("MediaContentType0")

    # 🛡️ Si no vino el número, no seguimos
    if not sender_number:
        print("⚠️ Request a / sin 'From', se ignora.")
        return str(MessagingResponse())

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
                send_message("Te estoy escuchando ...", sender_number)
                transcription = wisper.transcribir_audio_cloud(reply_path)
                print(f"📝 Transcripción: {transcription}")
                message_body = transcription
                tiene_adjunto = 1

            elif media_type.startswith("image"):
                print("🖼️ Es imagen")
                send_message("Dejame ver tu imagen ...", sender_number)
                description = vision.describe_image(reply_path)
                # print(f"🧠 Descripción generada: {description}")
                message_body = message_body + description
                tiene_adjunto = 1

            elif media_type == "application/pdf":
                print("📄 Es PDF")
                send_message("Dejame ver tu archivo ...", sender_number)
                pdf_text = vision.extract_text_from_pdf(reply_path)
                pdf_text = vision.resumir_texto_largo(pdf_text)
                print(f"📄 Texto resumido del PDF:\n{pdf_text[:300]}...")
                message_body = message_body + pdf_text
                tiene_adjunto = 1
            else:
                print("⚠️ Tipo de archivo no soportado:", media_type)
                send_message( "⚠️ Tipo de archivo no soportado. Enviá audio, imagen o PDF.", sender_number,
    )

        except Exception as e:
            print("❌ Error procesando media:", str(e))
            send_message(
                "❌ Hubo un problema procesando el archivo. Intentalo de nuevo.",
                sender_number,
            )
            return str(MessagingResponse())


    # En todos los casos (texto, transcripción, imagen, PDF)
    try:
        engine.handle_incoming_message(
            message_body,
            sender_number,
            tiene_adjunto,
            media_type,
            file_path,
            transcription,
            description,
            pdf_text,
        )
    except Exception as e:
        print(f"❌ Error en engine: {e}")
        if sender_number:
            try:
                send_message(
                    "❌ Ocurrió un error interno al procesar tu mensaje.",
                    sender_number,
                )
            except Exception as send_err:
                print(
                    f"⚠️ Además falló el envío de mensaje de error por provider: {send_err}"
                )


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
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == META_VERIFY_TOKEN and challenge:
            return challenge, 200
        else:
            return "Forbidden", 403

    # 2) Eventos normales (POST)
    data = request.get_json() or {}

    # Log liviano del webhook (sin raw completo)
    first_entry = (data.get("entry") or [{}])[0]
    first_change = (first_entry.get("changes") or [{}])[0]
    meta_val = first_change.get("value") or {}
    metadata = meta_val.get("metadata") or {}

    op_log(
        provider="meta",
        operation="meta_webhook_received",
        status="OK",
        extra={
            "phone_number_id": metadata.get("phone_number_id"),
            "has_messages": bool(meta_val.get("messages")),
            "has_statuses": bool(meta_val.get("statuses")),
        },
    )


    try:
        # Este es el phone_id PROPIO del entorno (distinto en dev y en prod)
        my_phone_id = os.getenv("META_WABA_PHONE_ID")

        entries = data.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})

                # 🔎 Filtramos por número: si el evento no es para mi línea, lo ignoro
                metadata = (value.get("metadata") or {})
                event_phone_id = metadata.get("phone_number_id")

                if my_phone_id and event_phone_id and event_phone_id != my_phone_id:
                    op_log(
                        provider="meta",
                        operation="meta_webhook_skip_other_phone",
                        status="OK",
                        extra={
                            "event_phone_id": event_phone_id,
                            "my_phone_id": my_phone_id,
                        },
                    )
                    continue


                # Si viene solo status (sent/delivered/read), lo ignoramos por ahora
                if value.get("statuses") and not value.get("messages"):
                    print("ℹ️ Evento de status de Meta (lo ignoramos por ahora)")
                    continue

                messages = value.get("messages", [])
                if not messages:
                    continue

                msg = messages[0]
                msg_type = msg.get("type")
                wa_from = msg.get("from")  # ej: "5492477661029"

                # Normalizamos al formato Twilio-like: whatsapp:+<numero>
                sender_number = f"whatsapp:+{wa_from}" if wa_from else None

                # Variables comunes para el engine
                text_body = ""
                tiene_adjunto = 0
                media_type = None
                file_path = ""
                description = ""
                transcription = ""
                pdf_text = ""

                # 🧾 TEXTO
                if msg_type == "text":
                    text_body = (msg.get("text", {}) or {}).get("body", "") or ""

                # 🖼 IMAGEN
                elif msg_type == "image":
                    media = (msg.get("image") or {})
                    media_id = media.get("id")
                    caption = (media.get("caption") or "")
                    if not media_id:
                        print("⚠️ Imagen Meta sin media_id, se omite.")
                        continue

                    # Mensaje de cortesía al toque
                    send_message("Dejame ver tu imagen ...", sender_number)

                    try:
                        file_path, media_type = download_meta_media(media_id)
                        description = vision.describe_image(file_path)
                        tiene_adjunto = 1
                        # combinamos caption + descripción para el engine
                        text_body = (caption + " " + description).strip()

                    except Exception as e:
                        print(f"❌ Error procesando imagen Meta: {e}")
                        send_message(
                            "❌ Hubo un problema procesando la imagen. Intentalo de nuevo.",
                            sender_number,
                        )
                        continue

                # 🎙 AUDIO
                elif msg_type == "audio":
                    media = (msg.get("audio") or {})
                    media_id = media.get("id")
                    if not media_id:
                        print("⚠️ Audio Meta sin media_id, se omite.")
                        continue

                    # Mensaje de cortesía
                    send_message("Estoy escuchando tu audio ...", sender_number)

                    try:
                        file_path, media_type = download_meta_media(media_id)
                        transcription = wisper.transcribir_audio_cloud(file_path)
                        tiene_adjunto = 1
                        text_body = transcription or ""

                    except Exception as e:
                        print(f"❌ Error procesando audio Meta: {e}")
                        send_message(
                            "❌ Hubo un problema procesando el audio. Intentalo de nuevo.",
                            sender_number,
                        )
                        continue

                # 📄 DOCUMENTO (tratamos PDFs)
                elif msg_type == "document":
                    media = (msg.get("document") or {})
                    media_id = media.get("id")
                    caption = (media.get("caption") or "")
                    mime = media.get("mime_type") or ""

                    if not media_id:
                        print("⚠️ Documento Meta sin media_id, se omite.")
                        continue

                    # Mensaje de cortesía
                    send_message("Dejame ver tu archivo ...", sender_number)

                    try:
                        file_path, media_type = download_meta_media(media_id)
                        # Sólo procesamos de verdad si es PDF
                        effective_mime = mime or media_type
                        if effective_mime == "application/pdf":
                            raw_pdf = vision.extract_text_from_pdf(file_path)
                            pdf_text = vision.resumir_texto_largo(raw_pdf)
                            tiene_adjunto = 1
                            text_body = (caption + " " + pdf_text).strip()
                        else:
                            print(f"⚠️ Documento no-PDF ({effective_mime}), no se procesa.")
                            send_message(
                                "⚠️ Sólo puedo procesar documentos PDF por ahora.",
                                sender_number,
                            )
                            continue

                    except Exception as e:
                        print(f"❌ Error procesando documento Meta: {e}")
                        send_message(
                            "❌ Hubo un problema procesando el archivo. Intentalo de nuevo.",
                            sender_number,
                        )
                        continue

                else:
                    print(f"⚠️ Tipo de mensaje Meta no soportado aún: {msg_type}")
                    continue

                print(f"✅ Meta INCOMING from {sender_number}: {text_body[:120]}")

                if not sender_number or not text_body:
                    print("⚠️ Meta webhook sin sender_number o sin texto útil, se omite.")
                    continue

                # Llamamos al mismo engine que usa Twilio
                import app.message_p as engine

                engine.handle_incoming_message(
                    text_body,      # message_body (texto, transcripción, caption+desc, etc.)
                    sender_number,  # sender_number (whatsapp:+549...)
                    tiene_adjunto,  # 0 / 1
                    media_type,     # p.ej. "image/jpeg", "audio/ogg", "application/pdf"
                    file_path,      # ruta local del archivo
                    transcription,  # si era audio
                    description,    # si era imagen
                    pdf_text        # si era pdf
                )


        return "EVENT_RECEIVED", 200

    except Exception as e:
        print(f"❌ Error procesando webhook Meta: {e}")
        return "ERROR", 500

def download_meta_media(media_id: str) -> tuple[str, str]:
    """
    Descarga un archivo multimedia desde la API de Meta usando el media_id.
    Devuelve (file_path, content_type).
    """
    if not META_WABA_TOKEN:
        raise RuntimeError("META_WABA_TOKEN / META_ACCESS_TOKEN / META_WHATSAPP_TOKEN no está configurado")

    # 1) Pedimos info del media (incluye URL y mime)
    info_url = f"https://graph.facebook.com/v21.0/{media_id}"
    headers = {"Authorization": f"Bearer {META_WABA_TOKEN}"}

    r = requests.get(info_url, headers=headers, timeout=10)
    r.raise_for_status()
    meta_info = r.json()

    file_url = meta_info.get("url")
    content_type = meta_info.get("mime_type") or meta_info.get("content_type") or "application/octet-stream"

    if not file_url:
        raise RuntimeError(f"Meta media {media_id} sin URL")

    # 2) Bajamos el archivo binario
    r2 = requests.get(file_url, headers=headers, timeout=20)
    r2.raise_for_status()

    ext = content_type.split("/")[-1] or "bin"
    folder = os.path.join(TMP_DIR, "meta_media")
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"{media_id}.{ext}")

    with open(file_path, "wb") as f:
        f.write(r2.content)

    print(f"✅ Archivo Meta descargado en: {file_path} ({content_type})")
    return file_path, content_type
