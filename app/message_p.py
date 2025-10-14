# message_p.py actualizado

# Módulos Build-in
from datetime import datetime, timezone, timedelta
import os
import json
#from zoneinfo import ZoneInfo  # Python 3.9+
#from typing import Optional
#from dateutil.parser import isoparse
#import requests



# Módulos de 3eros
import app.services.twilio_service as twilio
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



@log_latency
def handle_incoming_message(body, to, tiene_adjunto, media_type, file_path, transcription, description, pdf_text):

    body = (body or "")
    from datetime import datetime, timezone

    numero_limpio = limpiar_numero(to)

    WELCOME_MSG = (
    "👋 Hola, soy el asistente de PX Salud.\n\n"
    "Para comenzar, por favor escribí el DNI de la persona que necesita atención médica.")


    tx = Transactions()
    ev = Events()
    msj = Messages()

    # 1) Obtener contacto + event_id (antes del guard para conocer TTL del evento)
    contacto, event_id = obtener_o_crear_contacto(numero_limpio)

    # Contexto base de la sesión
    contexto_agente = ev.get_description_by_event_id(event_id) or ""
    base_context = json.dumps([{"role": "system", "content": contexto_agente}])
    nodo_inicio = ev.get_nodo_inicio_by_event_id(event_id) or 206
    # TTL del evento (fallback 5)
    TTL_MIN = ev.get_time_by_event_id(event_id) or 5

    # 2) Guard de sesión: si corresponde, ENVIAR WELCOME y NO procesar este mensaje
    if message1(tx, numero_limpio, TTL_MIN):
        op_log("engine", "welcome_guard_enter", "OK",
           to_phone=numero_limpio,
           extra={
               "event_id": event_id,
               "nodo_inicio": nodo_inicio
           })
        send_whatsapp_with_metrics(
        WELCOME_MSG, to, None,
        nodo_id=nodo_inicio,   # ya calculado arriba
        tx_id=None)             # aún no existe TX nueva



        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

        # contact_id robusto (objeto o dict)
        contact_id = (
            getattr(contacto, "contact_id", None)
            or getattr(contacto, "id", None)
            or (contacto.get("contact_id") if isinstance(contacto, dict) else None)
            or (contacto.get("id") if isinstance(contacto, dict) else None)
        )

        # ==== inspección de TX previa ====
        try:
            last_info = tx.get_last_tx_info_by_phone(numero_limpio)  # UNA lectura
            if not last_info:
                op_log("engine", "prev_tx_check", "OK", to_phone=numero_limpio,
                    extra={"status": "no_prev_tx"})
            else:
                last_name = (last_info.get("name") or "").strip()
                if last_name == "Cerrada":
                    op_log("engine", "prev_tx_check", "OK", to_phone=numero_limpio,
                        extra={"status": "already_closed", "prev_tx_id": last_info.get("id")})
                else:
                    # ==== cerrar TX abierta previa ====
                    t_close = time.perf_counter()
                    try:
                        tx.update(
                            id=last_info["id"],
                            contact_id=contact_id,
                            phone=numero_limpio,
                            name="Cerrada",
                            timestamp=now_utc,
                            event_id=event_id,
                        )
                        op_log("supabase", "close_previous_tx", "OK", t0=t_close,
                            extra={"prev_tx_id": last_info["id"]})
                    except Exception as e:
                        op_log("supabase", "close_previous_tx", "ERROR", t0=t_close, error=str(e),
                            extra={"prev_tx_id": last_info.get("id")})
        except Exception as e:
            op_log("engine", "prev_tx_check", "ERROR", to_phone=numero_limpio, error=str(e))

        # ==== construir historial con WELCOME incluido ====
        history = json.loads(base_context)
        history.append({"role": "assistant", "content": WELCOME_MSG})
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
                data_created=now_utc
            )
            op_log("supabase", "insert_transaction", "OK", t0=t_tx, to_phone=numero_limpio,
                extra={
                    "contact_id": contact_id,
                    "event_id": event_id,
                    "new_tx_id": new_tx_id,
                    "conv_len": len(conversation_json or "")
                })
        except Exception as e:
            op_log("supabase", "insert_transaction", "ERROR", t0=t_tx, to_phone=numero_limpio, error=str(e))
            return "Ok"

        if not new_tx_id:
            op_log("engine", "insert_transaction_postcheck", "ERROR", error_code="TX_PK_MISSING")
            return "Ok"

        # ==== guardar WELCOME en messages (también con logs) ====
        t_msg = time.perf_counter()
        try:
            msj.add(
                msg_key=nodo_inicio,   # ya calculado arriba
                text=WELCOME_MSG,
                phone=numero_limpio,
                event_id=event_id
            )
            op_log("supabase", "insert_message", "OK", t0=t_msg, extra={"msg_key": nodo_inicio})
        except Exception as e:
            op_log("supabase", "insert_message", "ERROR", t0=t_msg, error=str(e))

        op_log("engine", "welcome_guard_exit", "OK",
            to_phone=numero_limpio,
            extra={"new_tx_id": new_tx_id})

        return "Ok"


    # 3) Gestionar sesión y registrar mensaje
    msg_key, conversation_str, conversation_history, open_tx_id = gestionar_sesion_y_mensaje(
    contacto, event_id, body, numero_limpio,
    nodo_inicio=nodo_inicio,
    base_context=base_context,)

    op_log("engine", "session_continue", "OK",
       extra={"msg_key": msg_key, "open_tx_id": open_tx_id})


    # 4) Manejo de adjuntos SOLO si NO estamos en consentimiento (204) ni DNI (206)
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
            if adj_kind == "audio":
                twilio.send_whatsapp_message("✅ Recibí tu audio, lo transcribo…", to, None)

            
    # 5) Ejecutar workflow
    variables = inicializar_variables(body, numero_limpio, contacto, event_id, msg_key, conversation_str, conversation_history)
    variables["open_tx_id"] = open_tx_id
    variables = ejecutar_workflow(variables)


    # 6) Enviar respuesta y actualizar transacción
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
        ultimo_mensaje = msj.get_latest_by_phone(numero_limpio)  # ← 1 query
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
def enviar_respuesta_y_actualizar(variables, contacto, event_id, to):
    import json
    tx = Transactions()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    # 1) Enviar respuesta (si hay)
    mensaje_a_enviar = variables.get("response_text") or ""
    if mensaje_a_enviar:
        variables["request_id"] = send_whatsapp_with_metrics(
    mensaje_a_enviar, to, variables.get("url"),
    nodo_id=variables.get("nodo_destino"),
    request_id=variables.get("request_id"),   # si venía, lo respeta; si no, el helper genera uno
    tx_id=variables.get("open_tx_id") )


    # 2) === Fuente de verdad: conversation_str devuelto por el nodo (incluye metas) ===
    try:
        history = json.loads(variables.get("conversation_str") or "[]")
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    # Evitar duplicado: si el último ya es el mismo assistant, no lo volvemos a agregar
    if mensaje_a_enviar:
        tail = history[-1] if history else {}
        tail_is_same = (
            isinstance(tail, dict)
            and tail.get("role") == "assistant"
            and (tail.get("content") or "") == mensaje_a_enviar
        )
        if not tail_is_same:
            history.append({"role": "assistant", "content": mensaje_a_enviar})

    # Sincronizar variables para próximos nodos/turnos
    variables["conversation_history"] = history
    variables["conversation_str"] = json.dumps(history)

    # 3) Persistir conversación y estado de la transacción
    open_tx_id = variables.get("open_tx_id")
    if open_tx_id is None:
        # Fallback por si en algún flujo no llegó el id (no debería pasar ya)
        open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id)

    estado = "Cerrada" if variables.get("result") == "Cerrada" else "Abierta"

    t_upd = time.perf_counter()
    try:
        tx.update(
            id=open_tx_id,
            contact_id=contacto.contact_id,
            phone=variables["numero_limpio"],
            name=estado,
            conversation=variables["conversation_str"],  # lo que armó el nodo (con metas)
            timestamp=now_utc,
            event_id=event_id
        )
        op_log("supabase", "update_transaction", "OK", t0=t_upd,
            extra={"tx_id": open_tx_id, "fields": ["conversation","timestamp","name"]})
    except Exception as e:
        op_log("supabase", "update_transaction", "ERROR", t0=t_upd,
            error=str(e), extra={"tx_id": open_tx_id})
        # si falla la actualización, mejor no seguir con cierre
        estado = "Abierta"

    if estado == "Cerrada":

        op_log("engine", "close_transaction_intent", "OK",
           extra={
               "tx_id": open_tx_id,
               "nodo_destino": variables.get("nodo_destino")
           })
        send_whatsapp_with_metrics(
        "¡Gracias! Tu consulta quedó registrada. Pronto te brindaremos asistencia.", to, None,
        nodo_id=variables.get("nodo_destino"),
        tx_id=variables.get("open_tx_id")
        )
        
        try:
            Messages().add(
                msg_key=variables.get("nodo_destino"),
                text="¡Gracias! Tu consulta quedó registrada. Pronto te brindaremos asistencia.",
                phone=variables["numero_limpio"],
                event_id=event_id
            )
        except Exception as e:
            print(f"[MSG LOG] cierre: {e}")

        # === Enviar y persistir MEDICAL DIGEST SOLO si cerró en nodo 202 ===
        try:
            if str(variables.get("nodo_destino")) == "202":
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
                    blocks = ["DNI: {(national_id or '').strip() or NO_INFO}"]
                    if urgency_line:
                        blocks.append(urgency_line)
                    blocks.extend([
                        f"Motivo de consulta: {NO_INFO}",
                        f"Sintomatología y evolución: {NO_INFO}",
                        f"Orientación diagnóstica: {NO_INFO}",
                        f"Exámenes complementarios sugeridos: {NO_INFO}",
                        f"Tratamiento sugerido: {NO_INFO}",
                    ])
                    digest_text = "\n\n".join(blocks)
                    digest_json = {
                        "national_id": (national_id or "").strip() or NO_INFO,
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
                    except Exception as e_send:
                        print(f"[medical_digest] error enviando a médico: {e_send}")
                else:
                    print("[medical_digest] WHATSAPP_MEDICAL_DIGEST_TO vacío: se persistió pero NO se envió.")

        except Exception as e:
            print(f"[medical_digest] error general en hook de cierre nodo 202: {e}")
        op_log("supabase", "close_transaction", "OK", extra={"tx_id": open_tx_id  })
        
    # 4) Log en tabla messages (evitar filas vacías/duplicadas)
    if (variables.get("response_text") or "").strip() and estado != "Cerrada":
        try:
            Messages().add(
                msg_key=variables.get("nodo_destino"),
                text=variables["response_text"],
                phone=variables["numero_limpio"],
                group_id=variables.get("group_id", 0),
                question_id=variables.get("question_id", 0),
                event_id=event_id
            )
        except Exception as e:
            print(f"[MSG LOG] add response: {e}")


import hashlib
from app.obs.logs import provider_call, log_provider_result, set_request_id
from app.obs.logs import CTX_REQUEST_ID

def send_whatsapp_with_metrics(text, to, media_url, *, nodo_id=None, request_id=None, tx_id=None):
    """
    Envía un WhatsApp y registra logs centralizados:
    - PROVIDER_CALL (latencia/status)
    - PROVIDER_RESULT (provider_ref, tamaños, to_hash)
    Sin PII de contenido.
    """
    # mantiene tu comportamiento: generar request_id si falta
    rid = request_id or CTX_REQUEST_ID.get() or set_request_id(None)

    # PII-safe
    to_hash = hashlib.sha256((to or "").encode("utf-8")).hexdigest()[:12]
    bytes_len = len((text or "").encode("utf-8"))

    # medir latencia y status de la call
    with provider_call("twilio", "send_whatsapp_message"):
        sid = twilio.send_whatsapp_message(text, to, media_url)

    # referencia del proveedor + metadatos útiles para join
    log_provider_result(
        provider="twilio",
        operation="send_whatsapp_message",
        provider_ref=sid,     # Twilio SID
        bytes_len=bytes_len,
        to_hash=to_hash,
        extra={"node_id": nodo_id, "tx_id": tx_id}
    )
    return rid
