# message_p.py actualizado

# Módulos Build-in
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
from typing import Optional
import json
from dateutil.parser import isoparse
import requests
import time
import os


# Módulos de 3eros
import app.services.twilio_service as twilio
from twilio.twiml.messaging_response import MessagingResponse

# Módulos propios
from app.Model.users import Users   
from app.Model.enums import Role
from app.Model.contacts import Contacts
from app.Model.engine import Engine
from app.Model.messages import Messages
from app.Model.transactions import Transactions
from app.Model.questions import Questions
from app.Model.events import Events
from app.Utils.table_cleaner import TableCleaner
from app.flows.workflow_logic import ejecutar_nodo

import app.services.brain as brain
import app.services.uploader as uploader
import app.services.decisions as decs
#import app.services.embedding as vector
from app.services.decisions import next_node_fofoca_sin_logica, limpiar_numero, calcular_diferencia_en_minutos,ejecutar_codigo_guardado
import app.services.brain as brain
entorno = os.getenv("ENV", "undefined")

import time
import functools
import app.services.twilio_service as twilio


def log_latency(func):
   @functools.wraps(func)
   def wrapper(*args, **kwargs):
       start = time.perf_counter()
       result = func(*args, **kwargs)
       end = time.perf_counter()
       duration_ms = (end - start) * 1000
       print(f"[LATENCIA] {func.__name__} tomó {duration_ms:.2f} ms")
       return result
   return wrapper


@log_latency
def handle_incoming_message(body, to, tiene_adjunto, media_type, file_path, transcription, description, pdf_text):
    body = body + transcription + description + pdf_text
    import json
    from datetime import datetime, timezone

    numero_limpio = limpiar_numero(to)

    WELCOME_MSG = (
        "👋 Hola, soy el asistente de PX Salud.\n"  
        "Antes de continuar necesitamos tu consentimiento según la Ley 25.326.\n\n"

        "👉 Información clave:\n"    
        " • Responsable: PX Salud S.A.\n"    
        " • Finalidad: orientarte sobre tu estado de salud.\n"    
        " • Datos: algunos son obligatorios (DNI, credencial, síntomas).\n"    
        " • Destino: sólo profesionales de salud autorizados.\n"    
        " • Derechos: podés pedir acceso, corrección o borrado en cualquier momento.\n\n"    

        "✅ Si estás de acuerdo respondé 'Acepto'.\n"    
        "❌ Si no, cerrá este chat y no guardaremos tus datos.\n"  
    )

    tx = Transactions()

    # 0) Bienvenida express: si aplica, enviar y sembrar TX NUEVA + ancla (nodo 204), luego RETURN
    if message1(tx, numero_limpio):
        twilio.send_whatsapp_message(WELCOME_MSG, to, None)

        # contacto + evento
        contacto, event_id = obtener_o_crear_contacto(numero_limpio)
        # contexto base de la sesión
        ev = Events()
        contexto_agente = ev.get_description_by_event_id(event_id) or ""
        base_context = json.dumps([{"role": "system", "content": contexto_agente}])

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        ultima_tx = tx.get_last_timestamp_by_phone(numero_limpio)

        # si hay TX vigente pero vencida (>5'), cerrarla
        try:
            if ultima_tx is not None and tx.is_last_transaction_closed(numero_limpio) == 0 \
               and calcular_diferencia_en_minutos(tx, numero_limpio) > 5:
                tx.update(
                    id=ultima_tx["id"],
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    name="Cerrada",
                    timestamp=now_utc,
                    event_id=event_id
                )
        except Exception:
            pass

        # abrir TX nueva si no hay / cerrada / vencida
        try:
            if ultima_tx is None or tx.is_last_transaction_closed(numero_limpio) == 1 \
               or calcular_diferencia_en_minutos(tx, numero_limpio) > 5:
                tx.add(
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    name="Abierta",
                    event_id=event_id,
                    conversation=base_context,
                    timestamp=now_utc,
                    data_created=now_utc
                )
        except Exception:
            pass

        # ANCLA: dejar último msg_key en 204 para que el próximo turno caiga en consentimiento
        try:
            msj = Messages()
            nodo_inicio = ev.get_nodo_inicio_by_event_id(event_id) or 204
            msj.add(
                msg_key=nodo_inicio,
                text="[inicio de sesión]",
                phone=numero_limpio,
                event_id=event_id
            )
        except Exception:
            pass

        # Importante: no seguir con adjuntos ni workflow en este turno
        return "Ok"
    # 1) Obtener o crear contacto
    contacto, event_id = obtener_o_crear_contacto(numero_limpio)

    # 2) Gestionar sesión y registrar mensaje
    msg_key, conversation_str, conversation_history = gestionar_sesion_y_mensaje(
        contacto, event_id, body, numero_limpio
    )

    # 3) Manejo de adjuntos SOLO si NO estamos en consentimiento (204) ni DNI (206)
    adj_handled = False
    if msg_key not in (204, 206):
        adj_handled, adj_summary, adj_kind = procesar_adjuntos(
            tiene_adjunto, media_type, description, pdf_text, transcription, to
        )
        if adj_handled and adj_summary:
            conversation_history.append({
                "role": "user",
                "content": f"[Adjunto {adj_kind}] {adj_summary}"
            })
            conversation_str = json.dumps(conversation_history)

    # 4) Ejecutar workflow
    variables = inicializar_variables(body, numero_limpio, contacto, event_id, msg_key, conversation_str, conversation_history)
    variables = ejecutar_workflow(variables)

    # 5) Enviar respuesta y actualizar transacción
    enviar_respuesta_y_actualizar(variables, contacto, event_id, to)

    return "Ok"


@log_latency


def message1(tx, numero_limpio: str) -> bool:
    """
    True si corresponde enviar la bienvenida:
      - no existe transacción previa, o
      - la última transacción está cerrada.
    """
    try:
        ultima_tx = tx.get_last_timestamp_by_phone(numero_limpio)
        if ultima_tx is None:
            return True
        return tx.is_last_transaction_closed(numero_limpio) == 1
    except Exception:
        # si algo falla, no spammear
        return False



def procesar_adjuntos(tiene_adjunto, media_type, description, pdf_text, transcription, to):
    """
    Envía una respuesta en WhatsApp según el adjunto y devuelve:
    Devuelve
    - True si reconocimos y respondimos el adjunto.
    - summary: texto resumido para guardar en historial/DB.
    - tipo: "image" | "application/pdf" | "audio" | None
    """
    if tiene_adjunto != 1:
        return False, None, None

    # Imagen
    if media_type and media_type.startswith("image"):
        summary = description or "Imagen recibida."
        #twilio.send_whatsapp_message("Estoy analizando tu imagen", to, None)
        #twilio.send_whatsapp_message(summary, to, None)
        return True, summary, "image"

    # PDF
    if media_type == "application/pdf":
        summary = pdf_text or "PDF recibido."
        #body = body + summary
        #twilio.send_whatsapp_message("Estoy analizando tu archivo", to, None)
        #twilio.send_whatsapp_message(summary, to, None)
        return True, summary, "application/pdf"

    # Audio 
    if media_type and media_type.startswith("audio"):
        summary = transcription or "Audio recibido."
        #twilio.send_whatsapp_message("Estoy analizando tu audio", to, None)
        twilio.send_whatsapp_message(summary, to, None)
        return True, summary, "audio"

    # Otros tipos: no responde
    return False, None, None
@log_latency
def obtener_o_crear_contacto(numero_limpio):
    ctt = Contacts()
    ev = Events()
    msj = Messages()

    contacto = ctt.get_by_phone(numero_limpio)
    event_id = 1  


    if contacto is None:
        event_id = 1  # default
        contact_id = ctt.add(event_id=event_id, name="Juan", phone=numero_limpio)
        msg_key = ev.get_nodo_inicio_by_event_id(event_id)
        msj.add(msg_key=msg_key, text="Nuevo contacto", phone=numero_limpio, event_id=event_id, question_id=0)
        print("Contacto creado")
        contacto = ctt.get_by_phone(numero_limpio)
    else:
        #  trae el event_id que ya tiene asignado el contacto
        event_id = ctt.get_event_id_by_phone(numero_limpio) or 1
        print("Contacto ya existente")

    return contacto, event_id

@log_latency
def gestionar_sesion_y_mensaje(contacto, event_id, body, numero_limpio):
    
    
    tx, msj, ev = Transactions(), Messages(), Events()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    # Nodo inicial del evento 
    TTL_MIN = 5                       # ← expiración fija en minutos
    nodo_inicio = ev.get_nodo_inicio_by_event_id(event_id) or 204

    # Contexto del agente para SEMBRAR la sesión (sin historial previo)
    contexto_agente = ev.get_description_by_event_id(event_id) or ""
    base_context = json.dumps([{"role": "system", "content": contexto_agente}])

    # Última transacción del contacto
    ultima_tx = tx.get_last_timestamp_by_phone(numero_limpio)
    body_text = (body or "").strip()

    def _abrir_nueva_tx():
        print("[NUEVA] creo transacción ")
        tx.add(
            contact_id=contacto.contact_id,
            phone=numero_limpio,
            name="Abierta",
            event_id=event_id,
            conversation=base_context,
            timestamp=now_utc,
            data_created=now_utc
        )


    # --- Caso 1: primera vez que escribe (no hay TX previa) ---
    if ultima_tx is None:
        _abrir_nueva_tx()
        msg_key = nodo_inicio
        if body_text:
            msj.add(msg_key=msg_key, text=body_text, phone=numero_limpio, event_id=event_id)

    # --- Caso 2: última sesión estaba CERRADA ---
    elif tx.is_last_transaction_closed(numero_limpio) == 1:
        _abrir_nueva_tx()
        msg_key = nodo_inicio
        if body_text:
            msj.add(msg_key=msg_key, text=body_text, phone=numero_limpio, event_id=event_id)

    # --- Caso 3: la sesión VENCIDA por tiempo ---
    elif calcular_diferencia_en_minutos(tx, numero_limpio) > TTL_MIN:
        tx.update(
            id=ultima_tx["id"],
            contact_id=contacto.contact_id,
            phone=numero_limpio,
            name="Cerrada",
            timestamp=now_utc,
            event_id=event_id
        )
        _abrir_nueva_tx()
        msg_key = nodo_inicio
        if body_text:
            msj.add(msg_key=msg_key, text=body_text, phone=numero_limpio, event_id=event_id)
    # --- Caso 4: sesión VIGENTE ---
    else:
        ultimo_mensaje = msj.get_latest_by_phone(numero_limpio)
        msg_key = ultimo_mensaje.msg_key if ultimo_mensaje else nodo_inicio
        if body_text:
            msj.add(msg_key=msg_key, text=body_text, phone=numero_limpio, event_id=event_id)

    # Cargar historial ACTUAL de la TX ABIERTA (per-sesión) y agregar el usuario
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id) or base_context
    conversation_history = json.loads(conversation_str)

    if body_text:
        conversation_history.append({"role": "user", "content": body_text})

    conversation_str = json.dumps(conversation_history)
    return msg_key, conversation_str, conversation_history

@log_latency
def inicializar_variables(body, numero_limpio, contacto, event_id, msg_key, conversation_str, conversation_history):
    return {
        "body": body,
        "nodo_destino": msg_key,
        "numero_limpio": numero_limpio,
        "msg_key": msg_key,
        "contacto": contacto,
        "event_id": event_id,
        "conversation_str": conversation_str,
        "conversation_history": conversation_history,

        # Campos que tus nodos necesitan
        "msj": Messages(),
        "tx": Transactions(),
        "ev": Events(),
        "ctt": Contacts(),
        "qs": Questions(),
        "eng": Engine(),
        "last_assistant_question": Messages(),
        "aux": Messages(),

        # Estado del flujo
        "response_text": "",

        "result": "",
        "subsiguiente": 0,
        "url": "",
        "group_id": 0,
        "question_id": 0,
        "question_name": "",
        "next_node_question": "",
        "ultimo_mensaje": None,
        "aux_question_fofoca": [{"role": "system", "content": ""}],
        "max_preguntas": 0
    }

@log_latency
def ejecutar_workflow(variables):
    while True:
        print(f"Ejecutando nodo {variables['nodo_destino']}")
        contexto_actualizado = ejecutar_nodo(variables["nodo_destino"], variables)
        if contexto_actualizado:
            variables.update(contexto_actualizado)
        if variables.get("subsiguiente") == 1:
            break
    return variables

@log_latency
def enviar_respuesta_y_actualizar(variables, contacto, event_id, to):
    import json
    tx, now_utc = Transactions(), datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    # Enviar respuesta
    mensaje_a_enviar = variables.get("response_text") or "Hubo un problema interno. Intenta más tarde."
    twilio.send_whatsapp_message(mensaje_a_enviar, to, variables.get("url"))

    # AÑADIR respuesta del asistente al historial ANTES de persistir
    ch = variables.get("conversation_history", [])
    ch.append({"role": "assistant", "content": variables.get("response_text", "")})
    variables["conversation_history"] = ch
    variables["conversation_str"] = json.dumps(ch)

    # Persistir conversación completa
    open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id)
    estado = "Cerrada" if variables.get("result") == "Cerrada" else "Abierta"

    tx.update(
        id=open_tx_id,
        contact_id=contacto.contact_id,
        phone=variables["numero_limpio"],
        name=estado,
        conversation=variables["conversation_str"],
        timestamp=now_utc,
        event_id=event_id
    )

    if estado == "Cerrada":
        twilio.send_whatsapp_message("Gracias!", to, None)

    # Guardar última pregunta / salida del bot (como hacías antes)
    Messages().add(
        msg_key=variables.get("nodo_destino"),
        text=variables.get("response_text"),
        phone=variables["numero_limpio"],
        group_id=variables.get("group_id", 0),
        question_id=variables.get("question_id", 0),
        event_id=event_id
    )


