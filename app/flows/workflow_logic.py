import app.obs.logs as obs_logs

def ejecutar_nodo(nodo_id, variables):
    tx_obj = variables.get("tx")
    req_id = variables.get("request_id")
    tx_id  = getattr(tx_obj, "id", None) or variables.get("tx_id")
    rid = obs_logs.CTX_REQUEST_ID.get() or req_id or obs_logs.set_request_id(None)
    variables["request_id"] = rid
    obs_logs.set_request_id(req_id)   
    obs_logs.set_tx_id(tx_id)

    NODOS = {201:nodo_201,
             202:nodo_202,
             203:nodo_203,
             204:nodo_204,
             205:nodo_205,
             206:nodo_206,
             210: nodo_210,}

    with obs_logs.node_ctx(nodo_id, tx_id=tx_id, request_id=req_id):
        result = NODOS[nodo_id](variables)

    if isinstance(result, dict):
        obs_logs.enrich_exit_with_next(result.get("nodo_destino"), result.get("decision"))
    return result



#############################################################
# PX GUARDIA
#############################################################

def nodo_204(variables):
    """
    Nodo Consentimiento ley de datos 25.326
    - Llega acá solo si:
        * ya tenemos DNI válido (en variables["national_id"])
        * y todavía NO había consentimiento en privacy_consents
    - Interpreta la respuesta del usuario (Si/No).
    - Si acepta, registra consentimiento por DNI hasheado y avanza a 205.
    - Si rechaza, cierra la consulta.
    """
    import json, hashlib, re, unicodedata
    from app.Model.privacy_consents import PrivacyConsents

    # Contexto
    numero_limpio = variables.get("numero_limpio")
    contacto = variables.get("contacto")
    national_id = ""
    if contacto is not None:
        national_id = (getattr(contacto, "national_id", "") or "").strip()
    cierre = "Entiendo. No podemos continuar sin tu consentimiento.\n"

    last_raw = (variables.get("body") or "").strip()

    def _norm(s: str) -> str:
        # quita tildes, pasa a minúsculas y limpia puntuación
        s = ''.join(
            c for c in unicodedata.normalize('NFD', s)
            if unicodedata.category(c) != 'Mn'
        )
        s = s.lower()
        s = re.sub(r"[^\w\s]+", " ", s)   # elimina signos/emoji
        s = re.sub(r"\s+", " ", s).strip()
        return s

    text = _norm(last_raw)

    # positivos: si, acepto, ok, 1  (palabra completa)
    pos = (
        bool(re.search(r"\bsi\b", text)) or
        bool(re.search(r"\bacepto\b", text)) or
        bool(re.search(r"\bok\b", text)) or
        text == "1"
    )

    # negativos: no, nunca, 0  (palabra completa)
    neg = (
        bool(re.search(r"\bno\b", text)) or
        bool(re.search(r"\bnunca\b", text)) or
        text == "0"
    )

    # la negación domina
    result = 1 if (pos and not neg) else 0

    if result == 1:
        # ✅ consentimiento afirmativo -> registrar y luego avanzar a 205

        try:
            contact_id = getattr(contacto, "contact_id", None)
            if contact_id is not None and national_id:
                dni_hash = hashlib.sha256(national_id.encode("utf-8")).hexdigest()
                consents = PrivacyConsents()
                consents.add_row(
                    contact_id=contact_id,
                    phone_hash="",                # opcional, ya no lo usamos para chequear
                    dni_hash=dni_hash,
                )
                print(f"[CONSENT] fila creada en privacy_consents ")
        except Exception as e:
            print(f"[CONSENT] error guardando consentimiento: {e}")

        # No hace falta responder nada acá: el siguiente nodo (205) hará la pregunta correspondiente.
        return {
            "nodo_destino": 205,
            "subsiguiente": 0,  # seguimos en el mismo ciclo
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    if result == 0:
        # ❌ consentimiento negativo -> cerrar
        return {
            "nodo_destino": 204,
            "subsiguiente": 1,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": cierre,
            "group_id": None,
            "question_id": None,
            "result": "Cerrada",
        }

    # Si no pudimos clasificar la respuesta claramente (ni positivo ni negativo),
    # podés decidir si re-preguntar o tratarlo como negativo.
    # Por ahora lo tratamos como negativo seguro:
    return {
        "nodo_destino": 204,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": cierre,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada",
    }



def nodo_206(variables):
    """
    Nodo DNI
    - Valida el primer mensaje del usuario después del welcome.
    - Si es inválido, pide reingreso una sola vez.
    - Si vuelve a ser inválido, cierra la consulta.
    - Si es válido, guarda en contacts.dni y revisa consentimiento.
    """
    import re, json, hashlib
    from app.Model.privacy_consents import PrivacyConsents

    # Mensajes
    REASK = "El documento de identidad debe tener 7 u 8 números. Por favor, volvé a ingresarlo."
    FAIL  = "No pude validar tu documento de identidad. Cerramos la consulta por ahora."
    CONSENT_MSG = (
        "Sus datos serán tratados por el Sanatorio para orientarlo médicamente. "
        "PacienteX actúa como su proveedor tecnológico. Más información: Política de Privacidad.\n\n"
        "Antes de continuar, necesitamos su consentimiento para tratar sus datos personales.\n\n"
        "Si estás de acuerdo, por favor responde *Si*."
    )
    # 1) Normalizar y validar lo que escribió el usuario
    body = (variables.get("body") or "").strip()
    national_id = re.sub(r"\D+", "", body)  # deja solo dígitos

    if national_id and 7 <= len(national_id) <= 8:
        # Éxito: guardamos para el siguiente nodo y persistimos en contacts.dni
        variables["national_id"] = national_id
        ctt = variables.get("ctt")            # Contacts()
        contacto = variables.get("contacto")  # registro de contacto actual

        try:
            # Actualiza SOLO el campo dni sin tocar name/phone/event_id
            ctt.set_national_id(contact_id=contacto.contact_id, national_id=national_id)
        except Exception as e:
            print(f"[DNI] no se pudo guardar en contacts: {e}")

        # 2) Chequear consentimiento por DNI hasheado
        dni_hash = hashlib.sha256(national_id.encode("utf-8")).hexdigest()
        consents = PrivacyConsents()

        ya_tiene_consent = consents.has_consent(dni_hash=dni_hash)

        if ya_tiene_consent:
            # ✅ Ya tenemos consentimiento para este DNI -> avanzar directo a 205
            return {
                "nodo_destino": 205,            # siguiente paso: motivo/triage
                "subsiguiente": 0,              # permite continuar en el mismo ciclo
                "conversation_str": variables.get("conversation_str", ""),
                "response_text": "",
                "group_id": None,
                "question_id": None,
                "result": "Abierta",
            }

        # 3) NO tiene consentimiento -> enviar texto legal y pasar a nodo 204
        try:
            history = json.loads(variables.get("conversation_str") or "[]")
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []

        history.append({"role": "assistant", "content": CONSENT_MSG})
        new_cs = json.dumps(history)

        return {
            "nodo_destino": 204,            # ahora esperamos "Si/No" en nodo 204
            "subsiguiente": 1,              # el próximo mensaje (respuesta) va a nodo 204
            "conversation_str": new_cs,
            "response_text": CONSENT_MSG,   # se envía el texto de consentimiento
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # 2) Cargar historial para ver si ya pedimos reintento
    try:
        history = json.loads(variables.get("conversation_str") or "[]")
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    # Contamos cuántas veces ya enviamos el mensaje de reintento
    reasks = sum(
        1
        for m in history
        if isinstance(m, dict)
        and m.get("role") == "assistant"
        and m.get("content") == REASK
    )

    if reasks == 0:
        # Primer falla -> pedir reingreso
        history.append({"role": "assistant", "content": REASK})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 206,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": REASK,
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # Segunda falla -> cerrar consulta
    history.append({"role": "assistant", "content": FAIL})
    new_cs = json.dumps(history)
    return {
        "nodo_destino": 206,   # no importa: el flujo se corta por 'Cerrada'
        "subsiguiente": 1,
        "conversation_str": new_cs,
        "response_text": FAIL,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada",
    }

def nodo_205(variables):
    """
    Nodo ¿Que te trae a la guardia?
    """
    response_text = "¿Cuál es el *motivo de su consulta* en la guardia? \n\n💬 Puede responder con texto, foto o audio e incluir todos los detalles que considere relevantes."

    tx = variables["tx"]
    contacto = variables.get("contacto")
    contact_id = getattr(contacto, "contact_id", None)

    if contact_id:
        fingerprint = tx.sha256_text(response_text)
        status0, _ = tx.set_question_zero(contact_id, fingerprint=fingerprint)
        if status0 == "skip0":
            response_text = ""
    

    return {
        "nodo_destino": 201,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": None,
        "question_id": 0,
        "result": "Abierta"
    }

def nodo_201(variables):
    """
    Nodo que decide:
    - Si el último mensaje del paciente es un motivo de consulta médico válido.
    - Y si necesita intervención médica urgente o se pueden hacer más preguntas.
    """
    import app.services.brain as brain
    import json

    tx = variables["tx"]
    ctt = variables["ctt"]
    numero_limpio = variables["numero_limpio"]
    
    conversation_str = variables.get("conversation_str") or ""

    try:
        conversation_history = json.loads(conversation_str) if conversation_str else []
        if not isinstance(conversation_history, list):
            conversation_history = []
    except Exception:
        conversation_history = []
    
    REASK = "Para continuar, describa brevemente cuál es el *motivo de su consulta médica*: qué síntomas presenta y desde cuándo."
    FAIL = "No fue posible determinar de manera clara el motivo de su consulta médica, vamos a dar por finalizada esta conversación. Si lo desea, podrá iniciar una nueva consulta."



    mensaje_urgencia = (
        "En base a la siguiente conversación:\n"
        f"{conversation_str}\n\n"
        "clasifique lo siguiente:\n\n"
        "1) Si el último mensaje contiene un motivo de consulta MÉDICO válido. "
        "Esto se devuelve en el campo booleano \"is_medical_reason\":\n"
        "- true  -> si describe algún problema de salud, síntoma, dolor, malestar, lesión o accidente "
        "por el que una persona razonablemente consultaría a una guardia. Puede ser un texto corto, informal "
        "o con faltas de ortografía, pero se entiende que habla de un problema de salud.\n"
        "- false -> si no es un motivo médico de consulta (saludos, temas administrativos como obra social, "
        "precios, dirección u horarios, chistes, solo emojis o texto con el que no se puede entender el motivo "
        "de consulta).\n\n"
        "2) SOLO si \"is_medical_reason\" es true, clasifique la urgencia en el campo \"urgency\":\n"
        "- \"urgent\"              -> si observa signos que sugieren necesidad de evaluación médica humana rápida "
        "(síntomas potencialmente graves o de riesgo de vida).\n"
        "- \"need_more_questions\" -> si es un motivo médico pero sin signos claros de emergencia vital inmediata; "
        "en esos casos es razonable seguir haciendo preguntas médicas.\n"
        "- \"n/a\"                 -> cuando \"is_medical_reason\" es false (no debe evaluar la urgencia).\n\n"
        "Reglas obligatorias:\n"
        "- Si \"is_medical_reason\" es false, DEBE devolver siempre \"urgency\": \"n/a\".\n"
        "- Si \"is_medical_reason\" es true, DEBE devolver \"urgency\": \"urgent\" o \"need_more_questions\" "
        "(nunca \"n/a\").\n"
        "- Use exactamente estos valores de texto para \"urgency\" (respetando mayúsculas y minúsculas).\n"
        "- No genere preguntas nuevas; solo clasifique.\n"
        "- Responda ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin comillas alrededor y sin backticks, "
        "con este formato exacto:\n"
        "  {\"is_medical_reason\": true/false, \"urgency\": \"urgent\"/\"need_more_questions\"/\"n/a\"}\n"
    )

    mensaje_urgencia_dic = [{
        "role": "system",
        "content": mensaje_urgencia
    }]
    result_raw = brain.ask_openai(mensaje_urgencia_dic)

    # 1) Intentar parsear el JSON { "is_medical_reason": ..., "urgency": ... }
    try:
        data = json.loads(result_raw)
        is_medical_reason = data.get("is_medical_reason")
        urgency = data.get("urgency")
    except Exception:
        print(f"[nodo_201] Error parseando JSON de urgencia. raw={result_raw!r}")
        # Si no pudimos parsear, nos comportamos como si NO hubiera motivo médico
        is_medical_reason = False
        urgency = "n/a"

    # 2) Si NO es un motivo médico válido -> re-preguntar UNA vez y luego cerrar
    if is_medical_reason is False:
        # Contar cuántas veces ya enviamos el mensaje de reintento
        reasks = sum(
            1
            for m in conversation_history
            if isinstance(m, dict)
            and m.get("role") == "assistant"
            and m.get("content") == REASK
        )

        if reasks == 0:
            # Primera vez que sale false -> re-preguntamos
            conversation_history.append({"role": "assistant", "content": REASK})
            new_cs = json.dumps(conversation_history)
            variables["conversation_str"] = new_cs

            return {
                "nodo_destino": 201,   # volvemos a este nodo a esperar nueva respuesta
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": REASK,
                "group_id": None,
                "question_id": None,
                "result": "Abierta"
            }
        else:
            # Segunda vez que sale false -> cerramos la consulta
            conversation_history.append({"role": "assistant", "content": FAIL})
            new_cs = json.dumps(conversation_history)
            variables["conversation_str"] = new_cs

            return {
                "nodo_destino": 201,   # da igual, la marcamos cerrada
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": FAIL,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada"
            }

    # 3) Si SÍ es motivo médico válido -> decidir urgencia
    if is_medical_reason is True and urgency == "urgent":
        nodo_destino = 202
    else:
        # is_medical_reason True + "need_more_questions"
        # o algo raro pero no False explícito -> mandamos a Sherlock
        nodo_destino = 203

    return {
        "nodo_destino": nodo_destino,
        "subsiguiente": 0,
        "conversation_str": conversation_str,
        "response_text": "",
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }

SHOW_URGENCY_TO_PATIENT = False  # cambiar a True si queremos mostrar la linea al paciente

def nodo_202(variables):
    """
    Nodo de generación de reporte médico final usando el historial de conversación.
    """
    import app.services.brain as brain
    from app.message_p import send_whatsapp_with_metrics
    from app.Model.messages import Messages
    import json, re, os

    ctt = variables["ctt"]
    ev = variables["ev"]
    numero_limpio = variables["numero_limpio"]

    sender_number = "whatsapp:+" + numero_limpio
    send_whatsapp_with_metrics(
        "Estoy pensando, dame unos segundos...",
        sender_number,
        None,
        nodo_id=202,
        tx_id=variables.get("open_tx_id"),
    )

    try:
        Messages().add(msg_key=202, text="Estoy pensando, dame unos segundos...", phone=numero_limpio, event_id=ctt.get_event_id_by_phone(numero_limpio))
    except Exception as e:
        print(f"[MSG LOG] nodo_202 thinking: {e}")

    conversation_history = variables["conversation_history"]

    event_id = ctt.get_event_id_by_phone(numero_limpio)
    mensaje_reporte = ev.get_reporte_by_event_id(event_id)

    conversation_history.append({"role": "system", "content": mensaje_reporte})
    # 1) Pedimos al LLM el reporte COMPLETO (incluye línea de urgencia)
    full_report_text = brain.ask_openai(conversation_history)
    # 2) Según configuración, generamos la versión que ve el paciente
    patient_report_text = full_report_text
    if not SHOW_URGENCY_TO_PATIENT:
        # Regex compatible con la que usás en _extract_urgency_line
        urgency_pattern = re.compile(
            r"^(?:[🟥🟧🟨🟩⬜]\uFE0F?){5}\s+Urgencia Estimada[^\n\r]*\s*$",
            re.MULTILINE,
        )
        # Eliminamos solo esa línea, dejamos el resto igual
        patient_report_text = urgency_pattern.sub("", full_report_text).lstrip("\n")

    # 3) Enviar AL PACIENTE solo la versión filtrada (o completa si SHOW_URGENCY_TO_PATIENT=True)
    send_whatsapp_with_metrics(
        patient_report_text,
        sender_number,
        None,
        nodo_id=202,
        tx_id=variables.get("open_tx_id"),
    )



    try:
        Messages().add(msg_key=202, text=patient_report_text, phone=numero_limpio, event_id=event_id)
    except Exception as e:
        print(f"[MSG LOG] nodo_202 reporte: {e}")


    # guardar el reporte en el historial
    conversation_history.append({"role": "assistant", "content": full_report_text})
    variables["conversation_history"] = conversation_history
    variables["conversation_str"] = json.dumps(conversation_history)

    disclaimer_text = (
        "PX es una herramienta informativa y de acompañamiento comunicacional. No modifica el triage ni la priorización clínica realizada por el personal de salud del establecimiento al que Usted ha concurrido. PX no brinda diagnóstico, indicaciones médicas, prescripciones ni reemplaza la evaluación presencial por profesionales de la salud. La información y orientación provistas son generales y no constituyen consejo médico. Ante dudas o empeoramiento, consulte el personal de salud del establecimiento al que Usted ha concurrido"    )
    # enviar disclaimer al paciente
    send_whatsapp_with_metrics(
        disclaimer_text,
        sender_number,
        None,
        nodo_id=202,
        tx_id=variables.get("open_tx_id"),
    )



    try:
        Messages().add(msg_key=202,  text=disclaimer_text, phone=numero_limpio,  event_id=event_id   )
    except Exception as e:
        print(f"[MSG LOG] nodo_202 disclaimer: {e}")
    
    digest_offer_text = "📄 ¿Querés recibir el *Resumen Médico* de tu consulta?"

    conversation_history.append({
        "role": "assistant",
        "content": digest_offer_text,
    })


    return {
        "nodo_destino": 210,                     # ahora esperamos la respuesta en el nodo 210
        "subsiguiente": 1,                       # cortar ciclo, enviar la pregunta al paciente
        "conversation_str": variables["conversation_str"],
        "response_text": digest_offer_text,      # se envía por el pipeline estándar
        "group_id": None,
        "question_id": None,
        "result": "Abierta",                     #la TX sigue abierta
    }

def nodo_203(variables):
    """
    Nodo "Sherlock": hace preguntas activas al paciente usando GPT para completar el triage.
    Ahora:
    - Valida si la última respuesta del paciente es coherente con la pregunta.
    - Genera la próxima pregunta (o rehace la misma) en una sola llamada a OpenAI.
    """
    import json
    import re
    from typing import Optional

    import app.services.brain as brain
    from app.message_p import send_whatsapp_with_metrics
    from app.Model.messages import Messages
    from app.flows import workflows_utils

    tx = variables["tx"]
    ctt = variables["ctt"]
    msj = variables["msj"]
    ev = variables["ev"]
    numero_limpio = variables["numero_limpio"]

    sender_number = "whatsapp:+" + numero_limpio
    contacto = ctt.get_by_phone(numero_limpio)
    contact_id = getattr(contacto, "contact_id", None)

    # Historial de conversación
    conversation_str = variables.get("conversation_str") or "[]"
    try:
        conversation_history = json.loads(conversation_str)
        if not isinstance(conversation_history, list):
            raise ValueError("conversation_history no es lista")
    except Exception as e:
        print(f"[nodo_203] Error parseando conversation_str: {e}. conversation_str={conversation_str!r}")
        conversation_history = []

    event_id = ctt.get_event_id_by_phone(numero_limpio)

    # Estado de preguntas ya realizadas
    cursor, last_fp, last_sent_at = tx.get_question_state(contact_id)
    max_preguntas = int(ev.get_cant_preguntas_by_event_id(event_id))
    max_preguntas_str = str(max_preguntas)

    question_prefix_pattern = re.compile( r"^(\d+)/" + re.escape(max_preguntas_str) + r" - ")


    # Textos para respuestas off-topic
    OFFTOPIC_NOTICE = (
        "Para poder continuar, por favor responda la pregunta de forma completa."
    )
    OFFTOPIC_FAIL = (
        "No fue posible continuar con este cuestionario. Vamos a dar por finalizada esta conversación. "
        "Si lo desea, podrá iniciar una nueva consulta."    )

    # Contar cuántas veces ya se le avisó que su respuesta no estaba relacionada
    last_question_index = workflows_utils.get_last_question_index(conversation_history, max_preguntas_str, OFFTOPIC_NOTICE, )
    if last_question_index is None:
        # Si por alguna razón todavía no encontramos una pregunta numerada,no contamos off-topic previos.
        offtopic_notices = 0
    else:
        offtopic_notices = sum(
            1
            for m in conversation_history[last_question_index + 1 :]
            if isinstance(m, dict)
            and m.get("role") == "assistant"
            and OFFTOPIC_NOTICE in (m.get("content") or "")        )
    last_question_number = None
    if last_question_index is not None and 0 <= last_question_index < len(conversation_history):
        msg = conversation_history[last_question_index]
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            content = (msg.get("content") or "").strip()
            for line in content.splitlines():
                line = line.strip()
                m = question_prefix_pattern.match(line)
                if m:
                    try:
                        last_question_number = int(m.group(1))
                    except ValueError:
                        last_question_number = None
                    break

    # Si ya hicimos todas las preguntas, pasamos a 202 (reporte)
    if cursor >= max_preguntas:
        return {
            "nodo_destino": 202,
            "subsiguiente": 0,
            "conversation_str": conversation_str,
            "response_text": "",
            "group_id": None,
            "question_id": cursor,  # ya terminó el bloque de preguntas
            "result": "Abierta"
        }

    # Intro solo la primera vez
    if cursor == 0:
        mensaje_intro = (
            "Por los síntomas que describe, voy a necesitar hacerle "   + max_preguntas_str +   " preguntas para comprender mejor su situación."   )
        send_whatsapp_with_metrics(
            mensaje_intro,
            sender_number,
            None,
            nodo_id=203,
            tx_id=variables.get("open_tx_id"),
        )

        try:
            Messages().add(  msg_key=203,  text=mensaje_intro, phone=numero_limpio,  event_id=event_id )
        except Exception as e:
            print(f"[MSG LOG] nodo_203 intro: {e}")

    # el prompt: solo clasifica si la respuesta es clínica y genera la próxima pregunta
    mensaje_def_triage_str = (
        "A continuación se muestra la conversación completa hasta ahora, donde el último mensaje con "
        "\"role\": \"user\" es la última respuesta del paciente:\n\n"
        f"{conversation_str}\n\n"
        "Tu tarea ahora es:\n"
        "1) Analizar la última respuesta del paciente.\n"
        "2) Decidir si esa respuesta es CLÍNICAMENTE RELEVANTE (aunque no responda exactamente todos los detalles "
        "   de la pregunta anterior) o si no aporta información sobre su salud.\n"
        "3) Si la respuesta es clínicamente relevante, generar la mejor próxima pregunta MÉDICA para continuar el triage.\n\n"
        "Definiciones para \"is_on_topic\":\n"
        "- Considerá \"is_on_topic\": true cuando la última respuesta del paciente contiene información "
        "  relacionada con su salud, síntomas, dolor, malestar, antecedentes, medicamentos, embarazo, "
        "  contexto clínico, etc. Esto incluye respuestas que describen un síntoma o mencionan otros síntomas, "
        "  aunque no respondan todos los detalles pedidos.\n"
        "- Considerá \"is_on_topic\": false cuando la última respuesta NO es clínica ni aporta información útil "
        "  sobre la salud del paciente. \n"
        "Debés devolver un JSON con las siguientes claves:\n"
        "- \"is_on_topic\": true/false\n"
        "- \"next_question\": texto de la próxima pregunta médica que se le hará al paciente, SIN numeración, "
        "  sin comillas alrededor y sin prefijos. Debe ser una única pregunta clara, centrada en obtener "
        "  información clínica relevante para el triage.\n"
        "  Al generar \"next_question\":\n"
        "    * DEBÉS usar la información ya mencionada por el paciente (por ejemplo: mocos, fiebre, dolor, etc.).\n"
        "    * NO repitas exactamente una pregunta que ya se haya hecho en la conversación.\n"
        "    * Evitá preguntas genéricas como \"¿Puede contarme un poco más sobre sus síntomas?\" si ya se usaron; "
        "      en su lugar hacé preguntas más ESPECÍFICAS (por ejemplo: duración, intensidad, fiebre asociada, "
        "      color de las secreciones, factores desencadenantes, antecedentes, etc.).\n"
        "  Puede hacer uso o no de las funcionalidades del celular (texto, fotos, adjuntar archivos).\n"
        "  Debe incluir exactamente UN emoji neutral al final de la pregunta, pero no uses emojis de caras, manos, "
        "  corazones, fiesta, fuego ni \"100\".\n"
        "IMPORTANTE:\n"
        "- Respondé ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin explicaciones y sin backticks.\n"
        "- El formato debe ser exactamente:\n"
        "  {\"is_on_topic\": true/false, \"next_question\": \"...\"}\n" )


    mensaje_def_triage = [{
        "role": "system",
        "content": mensaje_def_triage_str  }]

    raw = brain.ask_openai(mensaje_def_triage)

    # Parsear JSON devuelto
    try:
        data = json.loads(raw)
        is_on_topic = data.get("is_on_topic")
        next_question = (data.get("next_question") or "").strip()
    except Exception as e:
        print(f"[nodo_203] Error parseando JSON de Sherlock. raw={raw!r} err={e}")
        # Si algo falla, como fallback mínimo: tratamos la respuesta como on-topic
        # y usamos una pregunta genérica para no romper el flujo.
        is_on_topic = True
        next_question = "¿Puede contarme un poco más sobre sus síntomas? 🩺"

    advance = (is_on_topic is True)


    if last_question_number is not None:
        question_id_current = last_question_number
    else:
        question_id_current = cursor if cursor > 0 else 1

    # === 1) Caso OFF-TOPIC: respuesta incoherente con la pregunta ===
    if is_on_topic is False:
        if offtopic_notices == 0:
            # Primera vez que responde cualquier cosa -> aclarar y repetir EXACTAMENTE la misma pregunta
            question_id = question_id_current

            last_question_line = None

            # Intentamos recuperar literalmente la última pregunta numerada (ej: "2/5 - ¿Desde cuándo...?")
            if last_question_index is not None and 0 <= last_question_index < len(conversation_history):
                msg = conversation_history[last_question_index]
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    content = (msg.get("content") or "").strip()
                    

                    for line in content.splitlines():
                        line = line.strip()
                        if question_prefix_pattern.match(line):
                            last_question_line = line

                            break

            if last_question_line:
                # UX: aviso + misma pregunta literal (incluyendo el prefijo N/max - ...)
                response_text = OFFTOPIC_NOTICE + "\n\n" + last_question_line
            else:
                # Fallback a comportamiento anterior si no encontramos la pregunta
                prefijo = f"{question_id}/{max_preguntas_str} - "
                if not next_question:
                    next_question = "¿Podría responder a la pregunta anterior relacionada con su salud? 🩺"
                response_text = OFFTOPIC_NOTICE + "\n\n" + prefijo + next_question

            # Registramos este aviso en el historial para que el próximo turno cuente como segundo intento
            conversation_history.append({
                "role": "assistant",
                "content": response_text,
            })
            new_cs = json.dumps(conversation_history)

            return {
                "nodo_destino": 203,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": response_text,
                "group_id": None,
                "question_id": question_id,
                "result": "Abierta"
            }
        else:
            # Segunda vez que responde mal -> cerrar la conversación
            response_text = OFFTOPIC_FAIL

            conversation_history.append({
                "role": "assistant",
                "content": response_text,
            })
            new_cs = json.dumps(conversation_history)

            return {
                "nodo_destino": 203,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": response_text,
                "group_id": None,
                "question_id": question_id_current,
                "result": "Cerrada"
            }

    # === 2) Caso ON-TOPIC: respuesta útil -> avanzar pregunta ===
    if advance:
        # Avanzamos a una nueva pregunta (cursor + 1)
        base_index = max(cursor, (last_question_number or 0))
        proposed_question_id = base_index + 1

        # El fingerprint incluye el número de pregunta propuesto,
        # así cada paso de triage es único aunque el texto se repita.
        fingerprint = tx.sha256_text(f"{proposed_question_id}:{next_question}")

        status, new_cursor = tx.register_question_attempt_by_contact(
            contact_id,
            fingerprint=fingerprint,
            debounce_seconds=90,
        )

        if status == "new":
            # Usamos el cursor que devuelve la DB (debería coincidir con proposed_question_id)
            question_id = new_cursor
        else:
            # En caso de duplicado o debounce, nos aseguramos de no retroceder
            question_id = max(proposed_question_id, new_cursor or proposed_question_id)
    else:
        # No avanzamos el contador: insistimos en la misma posición
        question_id = question_id_current

    question_id_str = str(question_id)
    prefijo = f"{question_id_str}/{max_preguntas_str} - "

    # Si por alguna razón vino vacío, ponemos una pregunta genérica
    if not next_question:
        next_question = "¿Podría contarme un poco más sobre sus síntomas? 🩺"

    response_text = prefijo + next_question

    return {
        "nodo_destino": 203,
        "subsiguiente": 1,
        "conversation_str": json.dumps(conversation_history),
        "response_text": response_text,
        "group_id": None,
        "question_id": question_id,
        "result": "Abierta"
    }

def nodo_210(variables):
    """
    Nodo de respuesta a la oferta de Resumen Médico.

    NUEVA LÓGICA:
    - Siempre asegura que exista un digest persistido para la transacción (tx_id),
      aunque el paciente responda NO.
    - Si responde SÍ: envía digest + disclaimer
    - Si responde NO / random: NO envía digest (pero ya quedó guardado igual)
    """
    import json
    from app.flows import workflows_utils
    from app.Model.medical_digests import MedicalDigests
    from app.Model.events import Events
    from app.message_p import MEDICAL_DIGEST_DISCLAIMER

    body = (variables.get("body") or "").strip()
    conversation_str = variables.get("conversation_str") or "[]"

    # Cargamos historial
    try:
        history = json.loads(conversation_str)
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    contacto = variables.get("contacto")
    event_id = variables.get("event_id") or getattr(contacto, "event_id", 1)
    tx_id = variables.get("open_tx_id")

    national_id = getattr(contacto, "national_id", None) if contacto is not None else None
    contact_id = getattr(contacto, "contact_id", None) or 0

    decision = workflows_utils.interpret_yes_no_for_digest(body)
    # 1 = sí, 0 = no, -1 = no clasificable (lo tratamos como NO)

    # =========================================================
    # 0) ASEGURAR DIGEST PERSISTIDO SIEMPRE (si hay tx_id)
    # =========================================================
    digest_text = None
    digest_json = {}

    if tx_id:
        # A) Intentar recuperar digest ya persistido
        try:
            rows = MedicalDigests().get("tx_id", tx_id)
            if rows:
                digest_text = getattr(rows[0], "digest_text", None)
        except Exception:
            digest_text = None

        # B) Si no existe, generarlo y persistirlo
        if not digest_text:
            try:
                try:
                    digest_instructions = Events().get_assistant_by_event_id(event_id)
                except Exception:
                    digest_instructions = None

                digest_text, digest_json = workflows_utils.generar_medical_digest(
                    conversation_str,
                    national_id,
                    digest_instructions,
                )
            except Exception:
                digest_text = (
                    "No pudimos generar el resumen médico en este momento. "
                    "Si lo necesitás, volvé a escribir a la guardia para que lo revisen."
                )
                digest_json = {}

            # Persistir digest (ideal: UNIQUE(tx_id) para idempotencia)
            try:
                MedicalDigests().add_row(
                    contact_id=contact_id,
                    tx_id=tx_id,
                    digest_text=digest_text,
                    digest_json=json.dumps(digest_json, ensure_ascii=False),
                )
            except Exception:
                pass

    # =========================================================
    # 1) RESPONDER SEGÚN DECISIÓN (enviar o no enviar)
    # =========================================================
    if decision == 1:
        # enviar resumen médico
        combined_text = f"{digest_text or ''}\n\n{MEDICAL_DIGEST_DISCLAIMER}".strip()

        history.append({"role": "assistant", "content": combined_text})
        variables["digest_answer"] = "yes"  # para que message_p lo persista si corresponde

        return {
            "nodo_destino": 210,
            "subsiguiente": 1,
            "conversation_str": json.dumps(history),
            "response_text": combined_text,
            "group_id": None,
            "question_id": None,
            "result": "Cerrada",
        }

    # NO / random: no enviar digest (pero ya está guardado si había tx_id)
    negative_text = "Perfecto. No te enviaremos el resumen médico. ¡Gracias!"

    history.append({"role": "assistant", "content": negative_text})
    variables["digest_answer"] = "no"

    return {
        "nodo_destino": 210,
        "subsiguiente": 1,
        "conversation_str": json.dumps(history),
        "response_text": negative_text,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada",
    }
