# message_p.py actualizado

# Módulos Build-in
from datetime import datetime, timezone, timedelta
import os
import json
import hashlib

#from zoneinfo import ZoneInfo  # Python 3.9+
#from typing import Optional
#from dateutil.parser import isoparse
#import requests
from typing import Optional



# Módulos de 3eros
import app.services.twilio_service as twilio
from app.services.messaging import send_message

from twilio.twiml.messaging_response import MessagingResponse

# Módulos propios
from app.Model.users import Users   
from app.Model.enums import Role
from app.Model.engine import Engine
from app.Model.contacts import Contacts
from app.Model.messages import Messages
from app.Model.transactions import Transactions
from app.Model.questions import Questions
from app.Model.events import Events
from app.Model.privacy_consents import PrivacyConsents

from app.Utils.table_cleaner import TableCleaner
from app.flows.workflow_logic import ejecutar_nodo

import app.services.brain as brain
import app.services.uploader as uploader
import app.services.decisions as decs
#import app.services.embedding as vector
from app.services.decisions import next_node_fofoca_sin_logica, limpiar_numero, calcular_diferencia_en_minutos,ejecutar_codigo_guardado, calcular_diferencia_desde_info

entorno = os.getenv("ENV", "undefined")

import time
import functools

from app.Model.medical_digests import MedicalDigests
from app.flows.workflows_utils import generar_medical_digest
from app.obs.logs import log_latency
from app.obs.logs import provider_call, log_provider_result, set_request_id
from app.obs.logs import CTX_REQUEST_ID
from app.obs.logs import op_log


WELCOME_MSG_DNI = (
    "👋 Hola, soy el asistente del Sanatorio San Roque (potenciado por PacienteX).\n\n"
    "Por favor, escribí el *DNI de la persona que necesita atención médica*."
)

MEDICAL_DIGEST_DISCLAIMER = (
    "PX presenta respuestas autodeclaradas por el/la paciente para agilizar la entrevista "
    "y con ello brinda información general de tipo orientativa, no médica. La orientación "
    "mostrada es informativa y no sustituye juicio clínico y médico. No utilice este resumen "
    "para clasificar urgencias ni para prescribir sin evaluación. PX no realiza triage clínico "
    "ni emite diagnósticos, indicaciones ni prescripciones. Si los síntomas cambian o se agravan, "
    "priorice revaloración inmediata según protocolos del servicio. La evaluación y priorización "
    "asistencial es responsabilidad exclusiva del equipo de salud. PX no es una plataforma de "
    "historia clínica ni debe ser utilizada como tal.")





def _get_contact_id(contacto) -> Optional[int]:
    """Resuelve contact_id  (objeto o dict).Se usa para cerrar TX vieja o abrir nuevaa"""
    if contacto is None:
        return None
    return (getattr(contacto, "contact_id", None)
        or getattr(contacto, "id", None)
        or (contacto.get("contact_id") if isinstance(contacto, dict) else None)
        or (contacto.get("id") if isinstance(contacto, dict) else None)  )


def _build_session_context(ev: Events, event_id: int):
    """
    Arma el contexto base de la sesión.
    Devuelve (contexto_agente, base_context_json, nodo_inicio, ttl_min).
    """
    contexto_agente = ev.get_description_by_event_id(event_id) or ""
    base_context = json.dumps([{"role": "system", "content": contexto_agente}])  #se pasa para gestionar sesion y mensje

    nodo_inicio = ev.get_nodo_inicio_by_event_id(event_id) or 206

    ttl_min = ev.get_time_by_event_id(event_id) or 5
    return contexto_agente, base_context, nodo_inicio, ttl_min


def _run_welcome_guard( tx: Transactions, msj: Messages, 
    numero_limpio: str, to: str, contact_id: Optional[int], event_id: int, base_context: str,
    nodo_inicio: int, ttl_min: int, welcome_msg: str, ) -> Optional[str]:
    """
    Ejecuta el guard de bienvenida.
    - Si message1 == True:
        * envía welcome
        * cierra TX previa (si está abierta)
        * abre TX nueva con historial (system + welcome)
        * guarda welcome en messages
        * loguea todo
        * devuelve "Ok" (para cortar flujo).
    - Si message1 == False: devuelve None y el flujo sigue normal.
    """
    if not message1(tx, numero_limpio, ttl_min):
        return None #continua el flujo

    

    # Enviar welcome
    send_whatsapp_with_metrics( welcome_msg, to, None, nodo_id=nodo_inicio, tx_id=None, ) # aún no existe TX nueva
    op_log("engine", "welcome_guard_enter", "OK", to_phone=numero_limpio,  extra={"event_id": event_id, "nodo_inicio": nodo_inicio}, )
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    # ==== inspección de TX previa ====
    try:
        last_info = tx.get_last_tx_info_by_phone(numero_limpio)  # UNA lectura
        if not last_info:
            op_log("engine","prev_tx_check","OK",  to_phone=numero_limpio, extra={"status": "no_prev_tx"},  )  #caso no hay tx previa
        else:
            last_name = (last_info.get("name") or "").strip()
            if last_name == "Cerrada":
                op_log(  "engine","prev_tx_check","OK", to_phone=numero_limpio,
                    extra={"status": "already_closed", "prev_tx_id": last_info.get("id")},     ) #la tx previa ya esta cerrada
            else:
                # ==== cerrar TX abierta previa ====
                t_close = time.perf_counter()
                try:
                    tx.update( id=last_info["id"], contact_id=contact_id, phone=numero_limpio, name="Cerrada", timestamp=now_utc, event_id=event_id,     )
                    op_log( "supabase", "close_previous_tx",  "OK", t0=t_close,  extra={"prev_tx_id": last_info["id"]},     )
                except Exception as e:
                    op_log(   "supabase",  "close_previous_tx",   "ERROR",   t0=t_close,   error=str(e), extra={"prev_tx_id": last_info.get("id")},  )
    except Exception as e:
        op_log( "engine", "prev_tx_check", "ERROR", to_phone=numero_limpio,  error=str(e), )

    # ==== construir historial con WELCOME incluido ====
    history = json.loads(base_context)
    history.append({"role": "assistant", "content": welcome_msg})
    conversation_json = json.dumps(history)

    # ==== abrir TX nueva (loguear sí o sí resultado) ====
    t_tx = time.perf_counter()
    new_tx_id = None
    try:
        new_tx_id = tx.add(
            contact_id=contact_id,
            phone=numero_limpio,
            name="Abierta",
            event_id=event_id,
            conversation=conversation_json,  # incluye system + welcome
            timestamp=now_utc,
            data_created=now_utc,
        )
        op_log(  "supabase","insert_transaction", "OK", t0=t_tx, to_phone=numero_limpio, extra={"contact_id": contact_id,"event_id": event_id,"new_tx_id": new_tx_id,"conv_len": len(conversation_json or ""),}, )
    except Exception as e:
        op_log("supabase","insert_transaction","ERROR",t0=t_tx,to_phone=numero_limpio,error=str(e),)
        return "Ok"

    if not new_tx_id:
        op_log("engine","insert_transaction_postcheck","ERROR",error_code="TX_PK_MISSING",)
        return "Ok"

    # ==== guardar WELCOME en messages (también con logs) ====
    t_msg = time.perf_counter()
    try:
        msj.add(msg_key=nodo_inicio,text=welcome_msg,phone=numero_limpio,event_id=event_id,)
        op_log("supabase","insert_message","OK",t0=t_msg,extra={"msg_key": nodo_inicio},)
    except Exception as e:
        op_log(            "supabase","insert_message","ERROR",t0=t_msg,error=str(e),)

    op_log(
        "engine","welcome_guard_exit","OK",to_phone=numero_limpio,extra={"new_tx_id": new_tx_id},)

    return "Ok"


def _aplicar_adjuntos_si_corresponde( msg_key,tiene_adjunto,media_type,description,pdf_text, transcription,to, conversation_history,):
    """
    Maneja adjuntos solo si NO estamos en consentimiento (204) ni DNI (206).
    Devuelve (adj_handled, conversation_history, conversation_str).
    """
    if msg_key in (204, 206):
        # Igual que antes: no procesamos adjuntos en estos nodos
        return False, conversation_history, json.dumps(conversation_history)

    adj_handled, adj_summary, adj_kind = procesar_adjuntos(
        tiene_adjunto, media_type, description, pdf_text, transcription, to
    )
    if adj_handled and adj_summary:
        conversation_history.append(
            {
                "role": "user",
                "content": f"[Adjunto {adj_kind}] {adj_summary}",
            }
        )
        conversation_str = json.dumps(conversation_history)
        if adj_kind == "audio":
            twilio.send_whatsapp_message("✅ Recibí tu audio, lo transcribo…", to, None)
        return True, conversation_history, conversation_str

    return False, conversation_history, json.dumps(conversation_history)

@log_latency
def handle_incoming_message( body,to,tiene_adjunto,media_type,file_path,transcription, description,pdf_text,):

    #Normalizo input
    body = (body or "")
    numero_limpio = limpiar_numero(to)

    tx = Transactions()
    ev = Events()
    msj = Messages()

    # 1) Obtener contacto + event_id (antes del guard para conocer TTL del evento)
    contacto, event_id = obtener_o_crear_contacto(numero_limpio)

    # 2) Contexto base de la sesión
    contexto_agente, base_context, nodo_inicio, TTL_MIN = _build_session_context(
        ev, event_id
    )

    # 3) contact_id  (objeto o dict) - lo usamos para TX
    contact_id = _get_contact_id(contacto)

    # 4) Guard de sesión: si corresponde, ENVIAR WELCOME y NO procesar este mensaje
    guard_result = _run_welcome_guard( tx=tx,msj=msj, numero_limpio=numero_limpio,to=to, contact_id=contact_id,event_id=event_id,base_context=base_context,nodo_inicio=nodo_inicio,ttl_min=TTL_MIN,  welcome_msg=WELCOME_MSG_DNI,)
    if guard_result is not None:
        # Ya se envió el welcome y se abrió la TX; no procesamos este mensaje
        return guard_result

    # 5) Gestionar sesión y registrar mensaje
    msg_key, conversation_str, conversation_history, open_tx_id = gestionar_sesion_y_mensaje( contacto, event_id, body, numero_limpio,nodo_inicio=nodo_inicio,base_context=base_context,)

    op_log( "engine","session_continue","OK",extra={"msg_key": msg_key, "open_tx_id": open_tx_id},)

    # 6) Manejo de adjuntos (solo si no estamos en consentimiento (204) ni DNI (206))
    _, conversation_history, conversation_str = _aplicar_adjuntos_si_corresponde( msg_key, tiene_adjunto, media_type, description,pdf_text,transcription,to,  conversation_history,  )

    # 7) Ejecutar workflow
    variables = inicializar_variables(
        body,
        numero_limpio,
        contacto,
        event_id,
        msg_key,
        conversation_str,
        conversation_history,
    )
    variables["open_tx_id"] = open_tx_id
    variables = ejecutar_workflow(variables)

    # 8) Enviar respuesta y actualizar transacción
    enviar_respuesta_y_actualizar(variables, contacto, event_id, to)

    return "Ok"


@log_latency
def message1(tx, numero_limpio: str, ttl_minutos: int) -> bool:
    """
    True si corresponde enviar la bienvenida 
    Lógica:
      - Sin transacciones previas -> True (welcome)
      - Última = 'Cerrada'       -> True (welcome)
      - Última = 'Abierta' y diff_min > ttl_minutos -> True (welcome)
      - En cualquier otro caso -> False (seguir flujo normal)
    """
    t0 = time.perf_counter()
    try:
        info = tx.get_last_tx_info_by_phone(numero_limpio)

        # 1) primera vez → welcome
        if info is None:
            op_log("engine", "message1_decision", "OK", t0=t0,
                   to_phone=numero_limpio,
                   extra={"reason": "no_prev_tx"})
            return True

        last_name = (info.get("name") or "").strip()

        # 2) última cerrada → welcome
        if last_name == "Cerrada":
            op_log("engine", "message1_decision", "OK", t0=t0,
                   to_phone=numero_limpio,
                   extra={"reason": "prev_tx_closed", "prev_tx_id": info.get("id")})
            return True

        # 3) última abierta → evaluar TTL
        diff_min = calcular_diferencia_desde_info(info)  # puede devolver None
        try:
            diff_i = int(diff_min) if diff_min is not None else None
            ttl_i = int(ttl_minutos)
        except Exception:
            # si no podemos convertir, no forzamos welcome para evitar spam
            diff_i, ttl_i = None, int(ttl_minutos)

        if diff_i is not None and diff_i > ttl_i:
            op_log("engine", "message1_decision", "OK", t0=t0,
                   to_phone=numero_limpio,
                   extra={"reason": "ttl_expired", "prev_tx_id": info.get("id"),
                          "diff_min": diff_i, "ttl_min": ttl_i})
            return True

        # 4) mantener sesión abierta
        op_log("engine", "message1_decision", "OK", t0=t0,
               to_phone=numero_limpio,
               extra={"reason": "keep_session", "prev_tx_id": info.get("id"),
                      "diff_min": diff_i, "ttl_min": ttl_i})
        return False

    except Exception as e:
        # En error: ser conservadores (no mandar welcome para no spamear)
        op_log("engine", "message1_decision", "ERROR", t0=t0,
               to_phone=numero_limpio, error=str(e))
        return False




@log_latency
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
        #twilio.send_whatsapp_message(summary, to, None)
        return True, summary, "audio"

    # Otros tipos: no responde
    return False, None, None

from app.obs.logs import op_log

@log_latency
def obtener_o_crear_contacto(numero_limpio, request_id=None, tx_id=None):
    """
    Lee/crea contacto con logs centralizados.
    - Camino existe: 1 query
    - Camino no existe: 2 queries
    - Sin PII en logs (no imprimimos teléfono)
    """
    ctt, ev, msj = Contacts(), Events(), Messages()

    # 1) Buscar por phone (1 query)
    t0 = time.perf_counter()
    try:
        contacto = ctt.get_by_phone(numero_limpio)
        op_log(provider="supabase", operation="select_contact_by_phone",
               status="OK", t0=t0, tx_id=tx_id, request_id=request_id)
    except Exception:
        op_log(provider="supabase", operation="select_contact_by_phone",
               status="ERROR", t0=t0, tx_id=tx_id, request_id=request_id,
               error_code="ERR_SBX_SELECT")
        raise

    # 2) Si no existe, crear y luego traer por ID (no volver a get_by_phone)
    if contacto is None:
        event_id = 1  # default

        t1 = time.perf_counter()
        try:
            contact_id = ctt.add(event_id=event_id, name="Juan", phone=numero_limpio)
            op_log("supabase", "insert_contact", "OK", t1, tx_id=tx_id, request_id=request_id)
        except Exception:
            op_log("supabase", "insert_contact", "ERROR", t1, tx_id=tx_id, request_id=request_id,
                   error_code="ERR_SBX_UPSERT")
            raise

        t2 = time.perf_counter()
        try:
            contacto = ctt.get_by_id(contact_id)
            op_log("supabase", "select_contact_by_id", "OK", t2, tx_id=tx_id, request_id=request_id)
        except Exception:
            op_log("supabase", "select_contact_by_id", "ERROR", t2, tx_id=tx_id, request_id=request_id,
                   error_code="ERR_SBX_SELECT")
            raise

        # Mensaje y nodo inicial (no agrega lecturas extra relevantes)
        try:
            msg_key = ev.get_nodo_inicio_by_event_id(event_id)
            msj.add(msg_key=msg_key, text="Nuevo contacto", phone=numero_limpio,
                    event_id=event_id, question_id=0)
        except Exception:
            # No log detallado para evitar PII accidental
            pass

        return contacto, event_id

    # 3) Si existe, usar event_id ya presente (evita get_event_id_by_phone)
    event_id = getattr(contacto, "event_id", None) or 1
    return contacto, event_id

@log_latency
def gestionar_sesion_y_mensaje(contacto, event_id, body, numero_limpio, *, nodo_inicio, base_context):
    """
    - 1 sola lectura a TX (get_open_row)
    - Devuelve también open_tx_id para evitar otra query después
    """
    tx, msj = Transactions(), Messages()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
    body_text = (body or "").strip()

    # 1) Traer la TX 'abierta' (si existe)
    open_row = tx.get_open_row(contacto.contact_id)  # ← 1 query

    def _abrir_nueva_tx():
        print("[NUEVA] creo transacción ")
        return tx.add(  # ← capturamos el ID
            contact_id=contacto.contact_id,
            phone=numero_limpio,
            name="Abierta",
            event_id=event_id,
            conversation=base_context,
            timestamp=now_utc,
            data_created=now_utc
        )

    if open_row is None:
        # No hay TX → crear nueva
        open_tx_id = _abrir_nueva_tx()
        msg_key = nodo_inicio
        conversation_history = json.loads(base_context)
    else:
        # Hay TX vigente
        open_tx_id = open_row.id
        conversation_str_existente = open_row.conversation or base_context
        conversation_history = json.loads(conversation_str_existente)

        # Último msg_key del histórico (1 lectura a Messages)
        ultimo_mensaje = msj.get_latest_by_phone_and_event_id(numero_limpio, event_id) # ← 1 query
        msg_key = ultimo_mensaje.msg_key if ultimo_mensaje else nodo_inicio

    # Agregar el mensaje del usuario al historial en memoria + persistir en messages
    if body_text:
        conversation_history.append({"role": "user", "content": body_text})
        msj.add(msg_key=msg_key, text=body_text, phone=numero_limpio, event_id=event_id)

    conversation_str = json.dumps(conversation_history)
    return msg_key, conversation_str, conversation_history, open_tx_id

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
        #print(f"Ejecutando nodo {variables['nodo_destino']}")
        contexto_actualizado = ejecutar_nodo(variables["nodo_destino"], variables)
        if contexto_actualizado:
            variables.update(contexto_actualizado)
        if variables.get("subsiguiente") == 1:
            break
    if not (variables.get("response_text") or "").strip():
        candidate = (variables.get("next_node_question") or "").strip()
        if candidate:
            variables["response_text"] = candidate

    return variables


@log_latency
def _enviar_respuesta_principal(variables, to: str) -> str:
    """
    Envía la respuesta principal al paciente (response_text), si existe,
    usando send_whatsapp_with_metrics. Devuelve el texto enviado (o "" si no había).
    """
    mensaje_a_enviar = (variables.get("response_text") or "").strip()
    if not mensaje_a_enviar:
        return ""

    variables["request_id"] = send_whatsapp_with_metrics( mensaje_a_enviar,  to,variables.get("url"),  nodo_id=variables.get("nodo_destino"),request_id=variables.get("request_id"),   # si venía, lo respeta
        tx_id=variables.get("open_tx_id"),
    )
    return mensaje_a_enviar

def _sincronizar_historial_desde_variables(variables, mensaje_a_enviar: str):
    """
    Toma conversation_str de variables, lo convierte en lista,
    agrega el mensaje del assistant si no está repetido
    y vuelve a guardar conversation_history / conversation_str en variables.
    Devuelve la lista history. ACTUALIZA EL HISTORIAS
    """
    import json

    try:
        history = json.loads(variables.get("conversation_str") or "[]")
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    if mensaje_a_enviar:
        tail = history[-1] if history else {}
        tail_is_same = ( isinstance(tail, dict)   and tail.get("role") == "assistant"   and (tail.get("content") or "") == mensaje_a_enviar     )
        if not tail_is_same:
            history.append({"role": "assistant", "content": mensaje_a_enviar})

    variables["conversation_history"] = history
    variables["conversation_str"] = json.dumps(history)
    return history


def _actualizar_transaccion_y_estado(variables, contacto, event_id, now_utc: str):
    """
    Actualiza la transacción en Supabase con el nuevo estado y conversación.
    - Usa open_tx_id de variables si existe; si no, hace fallback a get_open_transaction_id_by_contact_id.
    - Devuelve (open_tx_id, estado).
    """
    tx = Transactions()

    open_tx_id = variables.get("open_tx_id")
    if open_tx_id is None:
        try:
            open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id)
        except Exception:
            open_tx_id = None

    estado = "Cerrada" if variables.get("result") == "Cerrada" else "Abierta"

    t_upd = time.perf_counter()
    try:
        tx.update( id=open_tx_id,contact_id=contacto.contact_id,phone=variables["numero_limpio"],name=estado,conversation=variables["conversation_str"],  timestamp=now_utc,event_id=event_id,)
        op_log("supabase","update_transaction","OK",t0=t_upd,extra={"tx_id": open_tx_id, "fields": ["conversation", "timestamp", "name"]},)
    except Exception as e:
        op_log("supabase","update_transaction","ERROR",t0=t_upd,error=str(e),extra={"tx_id": open_tx_id},)
        # si falla la actualización, mejor no seguir con cierre
        estado = "Abierta"

    # sincronizamos por si el fallback encontró algo
    variables["open_tx_id"] = open_tx_id
    return open_tx_id, estado

def _generar_y_enviar_medical_digest_si_corresponde(variables, contacto, event_id, open_tx_id):
    """
    Genera, persiste y envía el medical digest SOLO si:
    - la transacción cerró, y
    - el nodo_destino es 202.
    Maneja errores internos sin romper el flujo principal.
    """
    try:
        if str(variables.get("nodo_destino")) != "202":
            return

        conversation_str = variables.get("conversation_str") or ""
        national_id = getattr(contacto, "national_id", None)

        # Generar digest (LLM) con fallback mínimo
        try:
            digest_text, digest_json = generar_medical_digest(conversation_str, national_id)
        except Exception as e_llm:
            print(f"[medical_digest] extractor LLM falló: {e_llm}")
            try:
                from app.flows.workflows_utils import _extract_urgency_line
                urgency_line = _extract_urgency_line(conversation_str)
            except Exception:
                urgency_line = ""
            NO_INFO = "No informado"
            dni_valor = (national_id or "").strip() or NO_INFO
            blocks = [f"DNI: {dni_valor}"]
            if urgency_line:
                blocks.append(urgency_line)
            blocks.extend(
                [
                    f"Motivo de consulta: {NO_INFO}",
                    f"Sintomatología y evolución: {NO_INFO}",
                    f"Orientación diagnóstica: {NO_INFO}",
                    f"Exámenes complementarios sugeridos: {NO_INFO}",
                    f"Tratamiento sugerido: {NO_INFO}",
                ]
            )
            digest_text = "\n\n".join(blocks)
            digest_json = {
                "national_id": dni_valor,
                "urgency_line": urgency_line,
                "chief_complaint": NO_INFO,
                "symptoms_course": NO_INFO,
                "clinical_assessment": NO_INFO,
                "suggested_tests": NO_INFO,
                "treatment_plan": NO_INFO,
            }

        # 1) Persistir (idempotente por tx_id)
        try:
            MedicalDigests().add_row(
                contact_id=contacto.contact_id,
                tx_id=open_tx_id if open_tx_id is not None else 0,
                digest_text=digest_text,
                digest_json=json.dumps(digest_json, ensure_ascii=False),
            )
        except Exception as e_db:
            print(f"[medical_digest] error persistiendo: {e_db}")

        # 2) Enviar por WhatsApp si hay destinatario en .env (número limpio)
        dest_clean = os.getenv("WHATSAPP_MEDICAL_DIGEST_TO", "").strip()
        if dest_clean:
            try:
                dest_formatted = "whatsapp:+" + dest_clean
                twilio.send_whatsapp_message(digest_text, dest_formatted, None)
                twilio.send_whatsapp_message(MEDICAL_DIGEST_DISCLAIMER, dest_formatted, None)
            except Exception as e_send:
                print(f"[medical_digest] error enviando a médico: {e_send}")
        else:
            print("[medical_digest] WHATSAPP_MEDICAL_DIGEST_TO vacío: se persistió pero NO se envió.")
    except Exception as e:
        print(f"[medical_digest] error general en hook de cierre nodo 202: {e}")
@log_latency
def enviar_respuesta_y_actualizar(variables, contacto, event_id, to):
    """
    Paso final del flujo:
    - Envía la respuesta principal al paciente (si existe).
    - Sincroniza el historial de conversación desde variables.
    - Actualiza la transacción en Supabase.
    - Si la TX se cierra:
        * envía mensaje de cierre ("¡Gracias!"),
        * registra el cierre en messages,
        * genera/persiste/envía el medical digest si corresponde.
    - Si la TX sigue abierta:
        * registra la respuesta en messages (evitando duplicados vacíos).
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    # 1) Enviar respuesta (si hay) usando helper
    mensaje_a_enviar = _enviar_respuesta_principal(variables, to)

    # 2) Sincronizar historial desde conversation_str devuelto por el nodo
    history = _sincronizar_historial_desde_variables(variables, mensaje_a_enviar)

    # 3) Persistir conversación y estado de la transacción
    open_tx_id, estado = _actualizar_transaccion_y_estado(variables,contacto,event_id,now_utc,)

    # 4) Si la transacción se cerró, enviar cierre + medical digest (si aplica)
    if estado == "Cerrada":
        op_log("engine","close_transaction_intent","OK",
            extra={"tx_id": open_tx_id,"nodo_destino": variables.get("nodo_destino"),}, )

        # Mensaje de cierre al paciente
        send_whatsapp_with_metrics("¡Gracias!",to,None,nodo_id=variables.get("nodo_destino"),tx_id=variables.get("open_tx_id"),)

        try:
            Messages().add(msg_key=variables.get("nodo_destino"),text="¡Gracias!",phone=variables["numero_limpio"],event_id=event_id,)
        except Exception as e:
            print(f"[MSG LOG] cierre: {e}")

        # Medical Digest SOLO si cerró en nodo 202
        _generar_y_enviar_medical_digest_si_corresponde(variables,contacto,event_id,open_tx_id,)

        op_log("supabase","close_transaction","OK",extra={"tx_id": open_tx_id},)

    # 5) Log en tabla messages (evitar filas vacías/duplicadas) si la TX sigue abierta
    if (variables.get("response_text") or "").strip() and estado != "Cerrada":
        try:
            Messages().add(msg_key=variables.get("nodo_destino"),text=variables["response_text"],phone=variables["numero_limpio"],group_id=variables.get("group_id", 0),question_id=variables.get("question_id", 0),event_id=event_id,)
        except Exception as e:
            print(f"[MSG LOG] add response: {e}")



def send_whatsapp_with_metrics(text, to, media_url, *, nodo_id=None, request_id=None, tx_id=None):
    """
    Envía un WhatsApp usando el proveedor configurado (Twilio o Meta)
    a través de app.services.messaging.send_message y registra logs
    centralizados (PROVIDER_CALL + PROVIDER_RESULT).
    """
    # mantiene tu comportamiento: generar request_id si falta
    rid = request_id or CTX_REQUEST_ID.get() or set_request_id(None)

    # Leemos el provider desde las vars de entorno
    provider = os.getenv("WHATSAPP_PROVIDER", "twilio").lower()

    # PII-safe
    to_hash = hashlib.sha256((to or "").encode("utf-8")).hexdigest()[:12]
    bytes_len = len((text or "").encode("utf-8"))

    # medir latencia y status de la call
    with provider_call(provider, "send_whatsapp_message"):
        # messaging.send_message se encarga de llamar a Twilio o Meta
        provider_ref = send_message(text, to)

    # referencia del proveedor + metadatos útiles para join
    log_provider_result(
        provider=provider,
        operation="send_whatsapp_message",
        provider_ref=provider_ref,   # SID de Twilio o wamid de Meta
        bytes_len=bytes_len,
        to_hash=to_hash,
        extra={"node_id": nodo_id, "tx_id": tx_id},
    )

    return rid

