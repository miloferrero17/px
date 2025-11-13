import app.obs.logs as obs_logs

def ejecutar_nodo(nodo_id, variables):
    tx_obj = variables.get("tx")
    req_id = variables.get("request_id")
    tx_id  = getattr(tx_obj, "id", None) or variables.get("tx_id")
    rid = obs_logs.CTX_REQUEST_ID.get() or req_id or obs_logs.set_request_id(None)
    variables["request_id"] = rid
    obs_logs.set_request_id(req_id)   
    obs_logs.set_tx_id(tx_id)

    NODOS = {201:nodo_201, #Discrimina Rojos
             202:nodo_202, #Reporte Guardia
             203:nodo_203, #Sherlock
             204:nodo_204, #Consentimiento Ley
             205:nodo_205, #Motivo Guardia
             305:nodo_305, #Motivo REDSOM
             206:nodo_206, #DNI
             307:nodo_307} #Reporte REDSOM

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
    """
    import json
    import app.services.brain as brain
    import app.services.twilio_service as twilio

    # Contexto
    conversation_str = variables.get("conversation_str", "").strip().lower()
    tx = variables.get("tx")
    ctt = variables.get("ctt")
    ev = variables.get("ev")
    numero_limpio = variables.get("numero_limpio")
    

    last_raw = (variables.get("body") or "").strip()

    import re, unicodedata
    def _norm(s: str) -> str:
        # quita tildes, pasa a minúsculas y limpia puntuación
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
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


    if result==1:
        # consentimiento afirmativo -> avanzar a 205 sin texto adicional
        return {
            "nodo_destino": 305,
            "subsiguiente": 0,
            "conversation_str": variables["conversation_str"],
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }
    cierre = (
        "Entiendo. No podemos continuar sin tu consentimiento. Gracias!\n"
        
    )
    if result==0:
        # consentimiento negativ 
        return {
            "nodo_destino": 204,
            "subsiguiente": 1,
            "conversation_str": variables["conversation_str"],
            "response_text": cierre,
            "group_id": None,
            "question_id": None,
            "result": "Cerrada"
        }

def nodo_206(variables):
    """
    Nodo DNI
    - Valida el primer mensaje del usuario después del welcome.
    - Si es inválido, pide reingreso una sola vez.
    - Si vuelve a ser inválido, cierra la consulta.
    - Si es válido, guarda en contacts.dni y avanza a 206.
    """
    import re, json

    # Mensajes
    REASK = "El documento de identidad debe tener 7 u 8 números. Por favor, volvé a ingresarlo."
    FAIL  = "No pude validar tu documento de identidad. Cerramos la consulta por ahora."

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

        return {
            "nodo_destino": 205,            # siguiente paso: motivo/triage
            "subsiguiente": 0,              # permite continuar en el mismo ciclo
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
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
    response_text = "¿Qué te trae hoy a la guardia? \n\n💬Podés responder con texto, foto o audio e incluir todos los detalles que consideres relevantes."

    tx = variables["tx"]
    contacto = variables.get("contacto")
    contact_id = getattr(contacto, "contact_id", None)

    if contact_id:
        fingerprint = tx.sha256_text(response_text)
        status0, _ = tx.set_question_zero(contact_id, fingerprint=fingerprint)
        if status0 == "skip0":
            response_text = ""
    
    event_id = variables.get("event_id")
    destino = 203 if str(event_id) == "2" else 201
    

    return {
        "nodo_destino": destino,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": None,
        "question_id": 0,
        "result": "Abierta"
    }

def nodo_305(variables):
    """
    Nodo Motivo de Consulta REDSOM
    """
    response_text = "Por favor, describa qué ocurrió. \n\n💬Podés responder con texto, foto o audio e incluir todos los detalles que consideres relevantes."

    tx = variables["tx"]
    contacto = variables.get("contacto")
    contact_id = getattr(contacto, "contact_id", None)

    if contact_id:
        fingerprint = tx.sha256_text(response_text)
        status0, _ = tx.set_question_zero(contact_id, fingerprint=fingerprint)
        if status0 == "skip0":
            response_text = ""
    
    event_id = variables.get("event_id")
    destino = 203 
    

    return {
        "nodo_destino": destino,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": None,
        "question_id": 0,
        "result": "Abierta"
    }

def nodo_201(variables):
    """
    Nodo que decide si el paciente necesita intervención médica urgente.
    Usa el historial de conversación para preguntarle a OpenAI.
    """
    import app.services.brain as brain
    import json

    tx = variables["tx"]
    ctt = variables["ctt"]
    numero_limpio = variables["numero_limpio"]
    conversation_str=variables["conversation_str"]
    conversation_history = json.loads(conversation_str) if conversation_str else []

    mensaje_urgencia = (
        "En base únicamente a la respuesta: " + variables["conversation_str"] +
        "¿El caso requiere intervencion medica humana urgente? "
        "Responde solo con: 1 si la requiere o 0 si necesitás hacer más preguntas para entender mejor la situacion"
    )

    mensaje_urgencia_dic = [{
        "role": "system",
        "content":mensaje_urgencia
    }]
    result1 = brain.ask_openai(mensaje_urgencia_dic)

    if result1.strip() == "1":
        nodo_destino = 202
    else:
        nodo_destino = 203

    return {
        "nodo_destino": nodo_destino,
        "subsiguiente": 0,
        "conversation_str": variables["conversation_str"],
        "response_text": "",
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }

def nodo_202(variables):
    """
    Nodo de generación de reporte médico final usando el historial de conversación.
    """
    import app.services.brain as brain
    import app.services.twilio_service as twilio
    from app.Model.messages import Messages
    import json

    ctt = variables["ctt"]
    ev = variables["ev"]
    numero_limpio = variables["numero_limpio"]

    sender_number = "whatsapp:+" + numero_limpio
    twilio.send_whatsapp_message("Estoy pensando, dame unos segundos...", sender_number, None)

    try:
        Messages().add(msg_key=202, text="Estoy pensando, dame unos segundos...", phone=numero_limpio, event_id=ctt.get_event_id_by_phone(numero_limpio))
    except Exception as e:
        print(f"[MSG LOG] nodo_202 thinking: {e}")

    conversation_history = variables["conversation_history"]

    event_id = ctt.get_event_id_by_phone(numero_limpio)
    mensaje_reporte = ev.get_reporte_by_event_id(event_id)

    conversation_history.append({"role": "system", "content": mensaje_reporte})

    response_text = brain.ask_openai(conversation_history)

    # enviar el reporte ahora, antes de saltar a 307
    twilio.send_whatsapp_message(response_text, sender_number, None)

    try:
        Messages().add(msg_key=202, text=response_text, phone=numero_limpio, event_id=event_id)
    except Exception as e:
        print(f"[MSG LOG] nodo_202 reporte: {e}")

    # guardar el reporte en el historial
    conversation_history.append({"role": "assistant", "content": response_text})
    variables["conversation_history"] = conversation_history
    variables["conversation_str"] = json.dumps(conversation_history)


    return {
    "nodo_destino": 202,     # quedarse aquí
    "subsiguiente": 1,       # sin pasos automáticos siguientes
    "conversation_str": variables["conversation_str"],
    "response_text": "",     # el reporte ya se envió por Twilio
    "group_id": None,
    "question_id": None,
    "result": "Cerrada",
}

def nodo_203(variables):
    """
    Nodo "Sherlock": hace preguntas activas al paciente usando GPT para completar el triage.
    """
    import json
    import app.services.brain as brain
    import app.services.twilio_service as twilio
    from app.Model.messages import Messages 

    tx = variables["tx"]
    ctt = variables["ctt"]
    msj = variables["msj"]
    ev = variables["ev"]
    numero_limpio = variables["numero_limpio"]

    sender_number = "whatsapp:+" + numero_limpio
    contacto = ctt.get_by_phone(numero_limpio)
    contact_id = getattr(contacto, "contact_id", None)

    #print(variables["conversation_str"])
    conversation_str = variables.get("conversation_str") or "[]"
    conversation_history = json.loads(conversation_str) if conversation_str else []

    event_id = ctt.get_event_id_by_phone(numero_limpio)

    # Reemplazo: usar cursor desde transactions
    cursor, last_fp, last_sent_at = tx.get_question_state(contact_id)
    question_id = cursor + 1

    max_preguntas = int(ev.get_cant_preguntas_by_event_id(event_id))
    max_preguntas_str = str(max_preguntas)
    question_id_str = str(question_id)

    if cursor == 0:
        mensaje_intro = "Por los síntomas que planteas voy a necesitar hacerte " + max_preguntas_str + " preguntas para entender mejor que te ocurre."
        twilio.send_whatsapp_message(mensaje_intro, sender_number, None)
        
        try:
            Messages().add(msg_key=203, text=mensaje_intro, phone=numero_limpio, event_id=event_id)
        except Exception as e:
            print(f"[MSG LOG] nodo_203 intro: {e}")

    if question_id > max_preguntas:
        next_node = 307 if str(event_id) == "2" else 202
        return {
            "nodo_destino": next_node,
            "subsiguiente": 0,
            "conversation_str": conversation_str,
            "response_text": "",
            "group_id": None,
            "question_id": question_id,
            "result": "Abierta"
        }

    mensaje_def_triage_str = (
        "Vas a hacerle " + max_preguntas_str + " preguntas con el objetivo de diagnosticarlo medicamente.\n"
        "En cada iteración debes tomar como historico esta charla : " + conversation_str + ",\n"
        "En base a ese historico y buscando hacer el mejor diagnostico tenes que escribir la mejor próxima pregunta. Esta mejor próxima pregunta puede hacer uso o no de las funcionalidades del celular (texto, fotos, adjtunar archivos).\n"
        "Contestame UNICAMENTE con la pregunta; sin números y sin comillas. Agregá exactamente 1 emoji neutral de objeto al FINAL de la oración  "
    "No uses emojis de caras, manos, corazones, fiesta, fuego ni “100”, ni ningún emoji que exprese emociones u opiniones (p. ej.: 🙂, 😟, 👍, 👎, ❤️, 🎉, 🔥, 💯). "
    
    )
    #print(mensaje_def_triage)
    
    mensaje_def_triage = [{
            "role": "assistant",
            "content":mensaje_def_triage_str
        }]


     # 1) Generar texto de la pregunta (sin prefijo)
    pregunta = (brain.ask_openai(mensaje_def_triage) or "").strip()

    # 2) Fingerprint solo del texto de la pregunta
    fingerprint = tx.sha256_text(pregunta)

    # 3) Registrar intento en la TX (idempotencia + debounce 90s)
    status, new_cursor = tx.register_question_attempt_by_contact(
        contact_id,
        fingerprint=fingerprint,
        debounce_seconds=90,
    )

    # 4) Ajustar numeración visible
    if status == "new":
        question_id = new_cursor
        question_id_str = str(question_id)
    else:
        question_id = max(question_id, new_cursor or 0)
        question_id_str = str(question_id)

    # 5) Componer texto final (solo en new/resend)
    prefijo = f"{question_id_str}/{max_preguntas_str} - "
    response_text = prefijo + pregunta if status == "new" else ""


    return {
        "nodo_destino": 203,
        "subsiguiente": 1,
        "conversation_str": json.dumps(conversation_history),
        "response_text": response_text,
        "group_id": None,
        "question_id": question_id,
        "result": "Abierta"
    }


def nodo_307(variables):
    """
    Nodo de cierre para flujo Redsom (event_id=2):
    - Lee el prompt desde events.reporte (event_id=2)
    - Llama al LLM para obtener JSON: {decision, reason, conversation_summary}
    - Guarda en public.redsom_digest
    - NO envía triage ni recomendaciones al paciente
    - Devuelve result='Cerrada' para que enviar_respuesta_y_actualizar mande el mensaje estándar de cierre
    """
    import json
    import app.services.brain as brain
    from app.Model.contacts import Contacts
    from app.Model.transactions import Transactions
    from app.Model.events import Events

    # Dependencia opcional (si ya creaste el model)
    try:
        from app.Model.redsom_digest import RedsomDigest
        have_model = True
    except Exception:
        RedsomDigest = None
        have_model = False

    ctt = variables["ctt"] if variables.get("ctt") else Contacts()
    ev  = variables["ev"]  if variables.get("ev")  else Events()
    tx  = variables["tx"]  if variables.get("tx")  else Transactions()

    numero_limpio = variables.get("numero_limpio")
    contacto = variables.get("contacto")
    contact_id = getattr(contacto, "contact_id", None)

    # 1) Tomar event_id y prompt desde events.reporte
    event_id = variables.get("event_id") or ctt.get_event_id_by_phone(numero_limpio)
    prompt_reporte = ev.get_reporte_by_event_id(event_id) or ""

    # 2) Armar conversación a pasarle al LLM (igual que 202: conversation_history + prompt del evento)
    try:
        conversation_history = variables.get("conversation_history") or []
        if not isinstance(conversation_history, list):
            conversation_history = []
    except Exception:
        conversation_history = []

    conversation_history.append({"role": "system", "content": prompt_reporte})

    # 3) Llamar al LLM y parsear JSON defensivamente
    raw = ""
    try:
        raw = brain.ask_openai(conversation_history) or ""
    except Exception as e:
        print(f"[nodo_307] LLM error: {e}")

    #defailt
    decision = "ACCIDENTE PERSONAL"
    reason = ""
    conversation_summary = "Resumen no disponible."

    try:
        data = json.loads(raw)
        d = (data.get("decision") or "").strip().upper()
        r = (data.get("reason") or "").strip()
        s = (data.get("conversation_summary") or "").strip()
        if d in ("ACCIDENTE PERSONAL", "NO ES ACCIDENTE PERSONAL"):
            decision = d
        if r:
            reason = r
        if s:
            conversation_summary = s
    except Exception as e:
        print(f"[nodo_307] JSON parse error: {e}; raw={raw[:200]}")

    # 4) Obtener tx_id abierto (o el que venga en variables)
    open_tx_id = variables.get("open_tx_id")
    if open_tx_id is None:
        try:
            open_row = tx.get_open_row(contact_id)
            open_tx_id = getattr(open_row, "id", None)
        except Exception as e:
            print(f"[nodo_307] get_open_row error: {e}")
            open_tx_id = None

    # 5) Persistir en public.redsom_digest (idempotente por UNIQUE(tx_id))
    try:
        if open_tx_id and contact_id:
            RedsomDigest().add_row(
                contact_id=contact_id,
                tx_id=open_tx_id,
                event_id=int(event_id) if event_id is not None else 2,
                decision=decision,
                reason=reason,
                conversation_summary=conversation_summary,
            )
        else:
            print(f"[nodo_307] skip persist: contact_id={contact_id} tx_id={open_tx_id}")
    except Exception as e:
        print(f"[nodo_307] persist error: {e}")

    MAX_LEN = 1200
    header = f"*Resumen de consulta*\n\nTipo: {'ACCIDENTE PERSONAL' if decision=='ACCIDENTE PERSONAL' else 'NO ES ACCIDENTE PERSONAL'}"
    reason_line = f"Motivo: {reason}"
    summary_block = f"Síntesis: {conversation_summary}"
    
    _response = f"{header}\n\n{reason_line}\n\n{summary_block}"
    response_text = _response[:MAX_LEN]

    # 6) No mandamos nada al paciente aquí (response_text vacío).
    #    'enviar_respuesta_y_actualizar' cerrará la TX y mandará el mensaje estándar.
    return {
        "nodo_destino": 307,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str"),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada"
    }
