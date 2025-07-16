# Módulos Built-in
import flask
from flask import Blueprint, request, current_app, render_template
import os
import requests
import time
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from dateutil.parser import isoparse    



# Módulos de terceros
from requests.auth import HTTPBasicAuth
from twilio.twiml.messaging_response import MessagingResponse
import app.services.twilio_service as twilio
import app.services.wisper as wisper
import app.services.vision as vision
import openai

# Módulos propios
from app.Model.users import Users
import app.message_p as engine
from app.Model.transactions import Transactions
from app.Model.contacts import Contacts


routes = flask.Blueprint("routes", __name__)

# Cargar variables de entorno
load_dotenv()
TMP_DIR = "/tmp"


# —————————————————————————————————————————————————————————————
# 1) Rutas de Whatsapp
# —————————————————————————————————————————————————————————————
@routes.route("/", methods=["GET", "POST"])
def whatsapp_reply():
    if flask.request.method == 'GET':
        return "✅ Server is running and accessible via GET request."

    sender_number = flask.request.form.get('From')
    message_body = flask.request.form.get("Body", "").strip()
    num_media = int(flask.request.form.get("NumMedia", 0))
    media_url = flask.request.form.get("MediaUrl0")
    media_type = flask.request.form.get("MediaContentType0")
    file_path =""
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
                print(f"🧠 Descripción generada: {description}")
                message_body = message_body + description
                tiene_adjunto = 1

            elif media_type == "application/pdf":
                print("📄 Es PDF")
                twilio.send_whatsapp_message("Dejame ver tu archivo ...", sender_number)
                pdf_text = vision.extract_text_from_pdf(reply_path)
                pdf_text = vision.resumir_texto_largo(pdf_text)
                print(f"📄 Texto resumido del PDF:\n{pdf_text[:300]}...")  # Log parcial
                #twilio.send_whatsapp_message("Dejame leer el documento ... ", sender_number)
                message_body = message_body + pdf_text
                tiene_adjunto = 1
            else:
                print("⚠️ Tipo de archivo no soportado:", media_type)
                twilio.send_whatsapp_message("⚠️ Tipo de archivo no soportado. Enviá audio, imagen o PDF.", sender_number)

        except Exception as e:
            print("❌ Error procesando media:", str(e))
            twilio.send_whatsapp_message("❌ Hubo un problema procesando el archivo. Intentalo de nuevo.", sender_number)
            return str(MessagingResponse())  # Twilio necesita respuesta válida

    # En todos los casos (texto, transcripción, imagen, PDF)
    try:
        engine.handle_incoming_message(message_body, sender_number, tiene_adjunto, media_type, file_path, transcription, description,pdf_text)
    except Exception as e:
        print(f"❌ Error en engine: {e}")
        twilio.send_whatsapp_message("❌ Ocurrió un error interno al procesar tu mensaje.", sender_number)

    # Siempre devolver algo válido para Twilio
    return str(MessagingResponse())


def download_file(media_url: str, file_path: str) -> str:
    """
    Descarga un archivo multimedia desde Twilio con autenticación.
    """
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")

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


# —————————————————————————————————————————————————————————————
# 2) Rutas web de consulta de DNI y feedback
# —————————————————————————————————————————————————————————————
# app/routes.py

def _consulta():
    # 1) Logging inicial
    current_app.logger.info(
        f"[CONSULTA] method={request.method} args={request.args.to_dict()} form={request.form.to_dict()}"
    )

    # 2) Feedback POST
    if request.method == "POST" and request.form.get("rating") is not None:
        tel      = request.form.get("tel", "").strip()
        txid     = request.form.get("txid")
        try:
            rating     = int(request.form.get("rating", 0))
            comentario = request.form.get("comment", "").strip()
        except ValueError:
            flask.flash("Puntuación inválida", "error")
            return flask.redirect(flask.url_for("routes.index", tel=tel, txid=txid))

        tx = Transactions()
        try:
            tx.update(
                id=int(txid),
                puntuacion=rating,
                comentario=comentario
            )
            flask.flash("¡Gracias por tu feedback!", "success")
        except Exception:
            current_app.logger.exception("Error guardando feedback:")
            flask.flash("No se pudo guardar tu feedback", "error")

        current_app.logger.info(
            f"Feedback registrado: tx={txid}, tel={tel}, rating={rating}, comment={comentario}"
        )
        return render_template("feedback_thanks.html")

    # 3) Flujo GET
    tel  = request.values.get("tel", "").strip()
    txid = request.values.get("txid")

    # 3.1 Solicitar teléfono si no hay
    if not tel:
        return render_template("index.html", step="phone")

    # 3.2 Validar contacto
    contacto = Contacts().get_by_phone(tel)
    if not contacto:
        flask.flash(f"El teléfono {tel} no está registrado.", "error")
        return render_template("index.html", step="phone")

    # 3.3 Listar sesiones si no hay txid
    if not txid:
        sesiones = Transactions().get_by_contact_id(contacto.contact_id)
        sesiones.sort(key=lambda s: s.timestamp, reverse=True)

        sesiones_formateadas = []
        for s in sesiones:
            raw_ts = s.timestamp
            if isinstance(raw_ts, str):
                dt = isoparse(raw_ts)
            else:
                dt = raw_ts

            dt_ajustada = dt - timedelta(hours=3)
            
            
            
            '''if isinstance(raw_ts, str):
                try:
                    dt = datetime.fromisoformat(raw_ts)
                except ValueError:
                    dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
            else:
                dt = raw_ts
            dt_ajustada = dt - timedelta(hours=3)
            '''
            
            
            sesiones_formateadas.append({
                "id":        s.id,
                "timestamp": dt_ajustada.strftime("%Y-%m-%d | %H:%M")
            })

        return render_template(
            "index.html",
            step="select",
            telefono=tel,
            sesiones=sesiones_formateadas
        )

    # 3.4 Mostrar Q/A de la transacción
    convo_str = Transactions().get_conversation_by_id(txid) or "[]"
    try:
        messages = json.loads(convo_str)
    except json.JSONDecodeError:
        current_app.logger.warning(f"JSON inválido: {convo_str!r}")
        messages = []

    interacciones = [m for m in messages if m.get("role") in ("assistant", "user")]
    return render_template(
        "index.html",
        step="qa",
        interacciones=interacciones,
        telefono=tel,
        txid=txid
    )

# Endpoints GET y POST que llaman a la lógica unificada
@routes.route("/consulta", methods=["GET"])
def index():
    try:
        return _consulta()
    except Exception:
        # Re-lanzamos para que el error original quede en CloudWatch
        raise

@routes.route("/consulta", methods=["POST"])
def feedback():
    try:
        return _consulta()
    except Exception:
        raise

'''



@routes.route("/consulta", methods=["GET"])
def index():
    tel  = flask.request.values.get("tel", "").strip()
    txid = flask.request.values.get("txid")

    if not tel:
        return flask.render_template("index.html", step="phone")

    contacto = Contacts().get_by_phone(tel)
    if not contacto:
        flask.flash(f"El teléfono {tel} no está registrado.", "error")
        return flask.render_template("index.html", step="phone")

    # paso 2: listado de sesiones/consultas
    if not txid:
        sesiones = Transactions().get_by_contact_id(contacto.contact_id)
        # orden descendente por timestamp raw
        sesiones.sort(key=lambda s: s.timestamp, reverse=True)

        sesiones_formateadas = []
        for s in sesiones:
            raw_ts = s.timestamp
            # 1) parsear si viene como string
            if isinstance(raw_ts, str):
                try:
                    # si está en ISO (2025-05-02T14:30:00)
                    dt = datetime.fromisoformat(raw_ts)
                except ValueError:
                    # si está en "YYYY-MM-DD HH:MM:SS"
                    dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
            else:
                dt = raw_ts  # ya es datetime

            # 2) restar 5 horas
            dt_ajustada = dt - timedelta(hours=3)

            # 3) formatear
            sesiones_formateadas.append({
                "id": s.id,
                "timestamp": dt_ajustada.strftime("%Y-%m-%d | %H:%M")
            })

        return flask.render_template(
            "index.html",
            step="select",
            telefono=tel,
            sesiones=sesiones_formateadas
        )

    # paso 3: Q/A igual que antes…
    convo_str = Transactions().get_conversation_by_id(txid) or "[]"
    try:
        messages = json.loads(convo_str)
    except json.JSONDecodeError:
        flask.current_app.logger.warning(f"JSON inválido: {convo_str!r}")
        messages = []

    interacciones = [m for m in messages if m.get("role") in ("assistant", "user")]
    return flask.render_template(
        "index.html",
        step="qa",
        interacciones=interacciones,
        telefono=tel,
        txid=txid
    )

@routes.route("/consulta/feedback", methods=["POST"])
def feedback():
    tel   = flask.request.form.get("tel", "").strip()
    txid  = flask.request.form.get("txid")
    
    try:
        rating     = int(flask.request.form.get("rating", 0))
        comentario = flask.request.form.get("comment", "").strip()
    except ValueError:
        flask.flash("Puntuación inválida", "error")
        return flask.redirect(flask.url_for("routes.index", tel=tel, txid=txid))

    # guardá en BD incluyendo el txid
    
    tx = Transactions()
    try:
        # Asumimos que txid es el id de la transacción en la tabla
        tx.update(
            id=int(txid),
            puntuacion=rating,
            comentario=comentario
        )
        flask.flash("¡Gracias por tu feedback!", "success")
    
    except Exception as e:
        flask.current_app.logger.error(f"Error guardando feedback: {e}")
        flask.flash("No se pudo guardar tu feedback", "error")

    # por ahora sólo logueamos:
    flask.current_app.logger.info(
        f"Feedback para tx {txid} de {tel}: rating={rating}, comment={comentario}"
    )
    return flask.render_template("feedback_thanks.html")
'''