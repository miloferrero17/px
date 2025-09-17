def ejecutar_nodo(nodo_id, variables):
    NODOS = {
        201: nodo_201,
        202: nodo_202,
        203: nodo_203,
        204: nodo_204,
        205: nodo_205,
        206: nodo_206,
        207: nodo_207,   # credencial / particular / extracción
        208: nodo_208,   # confirmación SI/NO + seteo TX + routing
        209: nodo_209,   # pago: instrucciones + comandos + comprobante->210
        210: nodo_210,   # análisis de comprobante (validaciones)
        211: nodo_211,   # lista de espera
        212: nodo_212,   # admisión (humano)
    }
    try:
        return NODOS[nodo_id](variables)
    except Exception as e:
        import traceback
        print(f"[ENGINE] error en nodo {nodo_id}: {e}")
        traceback.print_exc()
        raise




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
            "nodo_destino": 206,
            "subsiguiente": 0,
            "conversation_str": variables["conversation_str"],
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }
    cierre = (
        "Entiendo. No podemos continuar sin tu consentimiento.\n"
        
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
    #import app.services.twilio_service as twilio
    #import app.services.brain as brain
    #numero_limpio = variables["numero_limpio"]
    #sender_number = "whatsapp:+" + numero_limpio
    #body = variables.get("body", "").strip().lower()
    #twilio.send_whatsapp_message(body, sender_number, None)

    '''
    mensaje_credential = [{
        "role": "system",
        "content":"Extraé de este texto el UNICAMENTE el primer nombre con únicamente la primera letra mayúscula: "+body
    }]'''
    
    #result1 = brain.ask_openai(mensaje_credential)
    #response_text = (result1 + ": ¿Que te trae a la guardia?" )
    response_text = "¿Qué te trae a la guardia? \n\n💬Podés responder con texto, foto o audio y sumar todos los detalles que consideres útiles."
    
    
    return {
        "nodo_destino": 201,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
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
    import json

    ctt = variables["ctt"]
    ev = variables["ev"]
    numero_limpio = variables["numero_limpio"]

    sender_number = "whatsapp:+" + numero_limpio
    twilio.send_whatsapp_message("Estoy pensando, dame unos segundos...", sender_number, None)

    conversation_history = variables["conversation_history"]

    event_id = ctt.get_event_id_by_phone(numero_limpio)
    mensaje_reporte = ev.get_reporte_by_event_id(event_id)

    conversation_history.append({"role": "system", "content": mensaje_reporte})

    response_text = brain.ask_openai(conversation_history)

    # enviar el reporte ahora, antes de saltar a 207
    twilio.send_whatsapp_message(response_text, sender_number, None)

    # guardar el reporte en el historial
    conversation_history.append({"role": "assistant", "content": response_text})
    variables["conversation_history"] = conversation_history
    variables["conversation_str"] = json.dumps(conversation_history)

    return {
        "nodo_destino": 207,
        "subsiguiente": 0,  # (igual que antes) continuar a 207 en el mismo ciclo
        "conversation_str": variables["conversation_str"],
        "response_text": "",  # ✅ NUEVO: vacío para que el handler no lo pise/duplique
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }

def nodo_203(variables):
    """
    Nodo "Sherlock": hace preguntas activas al paciente usando GPT para completar el triage.
    """
    import json
    import app.services.brain as brain
    import app.services.twilio_service as twilio
    import builtins

    tx = variables["tx"]
    ctt = variables["ctt"]
    msj = variables["msj"]
    ev = variables["ev"]
    numero_limpio = variables["numero_limpio"]

    sender_number = "whatsapp:+" + numero_limpio
    contacto = ctt.get_by_phone(numero_limpio)
    #print(variables["conversation_str"])
    conversation_str = variables["conversation_str"]
    conversation_history = json.loads(conversation_str) if conversation_str else []

    event_id = ctt.get_event_id_by_phone(numero_limpio)
    question_id = msj.get_penultimate_question_id_by_phone(numero_limpio)
    question_id = question_id + 1 if question_id is not None else 1

    max_preguntas = builtins.int(ev.get_cant_preguntas_by_event_id(event_id))
    max_preguntas_str = builtins.str(max_preguntas)
    question_id_str = builtins.str(question_id)

    if question_id_str == "1":
        mensaje_intro = "Por los sintomas que planteas voy a necesitar hacerte " + max_preguntas_str + " preguntas para entender mejor que te anda pasando ."
        twilio.send_whatsapp_message(mensaje_intro, sender_number, None)

    if question_id > max_preguntas:
        return {
            "nodo_destino": 202,
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

    '''
    conversation_history.append({
        "role": "assistant",
        "content": mensaje_def_triage
    })
    '''
    result = brain.ask_openai(mensaje_def_triage)
    response_text = question_id_str + "/" + max_preguntas_str + " - " + result

    return {
        "nodo_destino": 203,
        "subsiguiente": 1,
        "conversation_str": json.dumps(conversation_history),
        "response_text": response_text,
        "group_id": None,
        "question_id": question_id,
        "result": "Abierta"
    }


# ========================= =========================
# NODOS POST TRIAGE: OOSS PREPAGA PARTICULAR
# ========================= =========================



# =========================
# Mensajes centralizados
# =========================
MESSAGES = {
    # 207
    "ASK_CREDENTIAL": (
        "Para continuar, enviá una *foto o PDF de la credencial* de tu obra social o prepaga.\n"
        "Si no tenés, escribí: *Particular*."
    ),
    "RETRY_CREDENTIAL": (
        "No pude validar tu cobertura. Probemos de nuevo: enviá una *captura o PDF* de la credencial.\n"
        "Si no tenés, escribí: *Particular*."
    ),
    "COVERAGE_FAIL": "No pudimos validar tu cobertura. Acercate a admisión para recibir ayuda.",

    # 208 confirmación
    "CONFIRM_HEADER": "Revisá y confirmá tus datos:\n\n",
    "CONFIRM_TPL": (
        "Nombre: {nombre} {apellido}\n"
        "Cobertura: {obra}\n"
        "Plan: {plan}\n"
        "Afiliado: {afiliado}\n"
        "Token: {token}\n\n"
        "{footer}\n\n"
        "¿Los datos son correctos? SI/NO"
    ),
    "CONFIRM_FOOTER_COPAY": "Copago a abonar: ${monto} 💵",
    "CONFIRM_FOOTER_NO_COPAY": "No hay copago.",
    "CONFIRM_FOOTER_NO_COVERAGE" : "Esta cobertura no se encuentra dentro de las obras sociales o prepagas con convenio.",



    # 209 pagos (3 mensajes separados)
    "PAYMENT_1": (
        "Total a abonar: ${monto} 💵\n\n"
        "Para continuar, podés pagar por *transferencia* y enviarnos el comprobante.\n"
        "Si preferís otro medio de pago, escribí “Otros”."
    ),
    "PAYMENT_2": "Nuestro alias es:",
    "PAYMENT_3": "PACIENTEX.CLINICA.GUARDIA",
    "PAYMENT_RETRY": "*No pude validar tu elección.* Probemos de nuevo:\n"
                     "enviá la *captura o PDF* del comprobante o escribí *Otros*.",
    "PAYMENT_FAIL": "*No pudimos validar el medio de pago elegido.*",
    "PAYMENT_OTHERS_ACK": "Preferís pagar con otros medios de pago. Acercate a admisión para recibir ayuda.",




    # 210 comprobante / otros medios
    "RECEIPT_OK": "✅ Recibimos tu comprobante.",
    "RECEIPT_RETRY": "*No pude validar tu comprobante.* Probemos de nuevo: enviá una *captura o PDF*. "
                     "Si preferís otro medio de pago, escribí *Otros*.",
    "RECEIPT_FAIL": "No pudimos validar tu comprobante. Acercate a admisión para recibir ayuda.",
    
    "OTHERS_MENU": (
        "💵 Para abonar con efectivo, escribí “Efectivo”.\n"  #ahora no se usa
        "💳 Para abonar con tarjeta, escribí “Tarjeta”."
    ),

    # 211 espera
    "WAITING": "✅ Ya registramos tus datos. Quedate en la sala de espera y aguardá a que te llamen.\n\n"
    "Si tus síntomas empeoran, avisá en admisión de inmediato.",

    #212 Admisión
    "TO_HUMAN": "Acercate a admisión para recibir ayuda.",

    }


def nodo_207(variables):
    """
    207 - Pide credencial de OOSS/prepaga o detecta 'particular'.
      - Acepta imagen **o** PDF (ambos válidos); otros adjuntos (audio/docs) = inválidos.
      - Extrae: nombre, apellido, obra, plan, afiliado, token (token opcional).
      - Requiere: obra + afiliado para avanzar por OOSS/prepaga.
      - 'particular' → salta a 208 (autoconfirma en 208) sin consumir intento.
      - Máx 2 reintentos; al agotar → 212 (admisión).
      - NO toca transactions; solo setea variables["coverage_draft"].
    """
    import json, re
    import app.services.brain as brain
    from app.flows.workflows_utils import (
        norm_text,
        # historial
        hist_load, hist_save, hist_truncate,
        hist_recent_since, hist_user_msgs, hist_last_user_content,
        hist_count_meta, hist_add_meta,
        # adjuntos
        attach_is_line, attach_kind,
    )

    ASK = MESSAGES["ASK_CREDENTIAL"]        # "Enviá una foto o PDF..."
    RETRY = MESSAGES["RETRY_CREDENTIAL"]    # "No pude tomar bien los datos..."
    TO_HUMAN = MESSAGES["TO_HUMAN"]         # "Acercate a admisión."
    MAX_RETRIES = 2
    META_FLAG = "[CRED_ATTEMPT]"            # contador por nodo 207
    FAIL = MESSAGES["COVERAGE_FAIL"]
    PROMPTS = {ASK, RETRY}

    # ---------------- Cargar historial y mensaje ----------------
    history = hist_load(variables.get("conversation_str") or "")
    body_raw = (variables.get("body") or "").strip()
    body_norm = norm_text(body_raw)

    # ---------------- Primera vez → ASK ----------------
    asked_once = any(isinstance(m, dict) and m.get("role") == "assistant" and m.get("content") == ASK for m in history)
    if not asked_once:
        history.append({"role": "assistant", "content": ASK})
        new_cs = hist_save(hist_truncate(history))
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": ASK,
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # ---------------- Trabajar sobre mensajes recientes (desde último ASK/RETRY) ----------------
    recent = hist_recent_since(history, PROMPTS)

    # Si aún no hay respuesta del usuario tras el último ASK/RETRY → no enviar nada (esperamos)
    if not hist_user_msgs(recent):
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # ---------------- Detectar "particular" (NO consume intento) ----------------
    if re.search(r"\bparticular\b", body_norm):
        variables["coverage_draft"] = {
            "nombre": "",
            "apellido": "",
            "obra": "PARTICULAR",
            "plan": "UNICO",
            "afiliado": "",
            "token": "",
        }
        return {
            "nodo_destino": 208,
            "subsiguiente": 0,  # 208 autoconfirma internamente para particular
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # ---------------- Analizar último user (texto o adjunto formateado por message_p) ----------------
    last_user = hist_last_user_content(recent)
    is_attach = attach_is_line(last_user)
    kind = attach_kind(last_user) if is_attach else ""
    is_image = (kind == "image") or kind.startswith("image/")
    is_pdf = (kind == "application/pdf")

    # Adjuntos inválidos (audio u otros) → cuenta intento
    if is_attach and not (is_image or is_pdf):
        attempts = hist_count_meta(history, META_FLAG)
        if attempts + 1 >= MAX_RETRIES:
            history.append({"role": "assistant", "content": FAIL})
            new_cs = hist_save(hist_truncate(history))
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": FAIL,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }
        hist_add_meta(history, META_FLAG)
        history.append({"role": "assistant", "content": RETRY})
        new_cs = hist_save(hist_truncate(history))
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": RETRY,
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # Fuente para extracción: si hubo adjunto válido (imagen/pdf), usamos esa línea (incluye resumen); si no, el body tipeado.
    extract_input = last_user if (is_image or is_pdf) else (body_raw or last_user)

    extract_prompt = [
        {
            "role": "system",
            "content": (
                "De la entrada del paciente (texto u OCR de la credencial), extraé SIEMPRE y SOLO:\n"
                "- nombre\n- apellido\n- obra (obra social o prepaga)\n- plan\n- afiliado (número)\n- token (si existe)\n\n"
                "Respondé SOLO JSON exacto con claves: nombre, apellido, obra, plan, afiliado, token.\n"
                "Si un dato no está, dejá cadena vacía."
            ),
        },
        {"role": "user", "content": extract_input},
    ]

    try:
        raw = brain.ask_openai(extract_prompt)
    except Exception as e:
        print(f"[207] Error LLM: {e}")
        raw = '{"nombre":"","apellido":"","obra":"","plan":"","afiliado":"","token":""}'

    try:
        data = json.loads(raw)
    except Exception:
        data = {"nombre": "", "apellido": "", "obra": "", "plan": "", "afiliado": "", "token": ""}

    nombre = (data.get("nombre") or "").strip()
    apellido = (data.get("apellido") or "").strip()
    obra = (data.get("obra") or "").strip()
    plan = (data.get("plan") or "").strip()
    afiliado = (data.get("afiliado") or "").strip()
    token = (data.get("token") or "").strip()

    # Validación mínima para avanzar por OOSS/prepaga (tu regla: si falta afiliado, cuenta reintento)
    if not obra or not afiliado:
        attempts = hist_count_meta(history, META_FLAG)
        if attempts + 1 >= MAX_RETRIES:
            history.append({"role": "assistant", "content": TO_HUMAN})
            new_cs = hist_save(hist_truncate(history))
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }
        hist_add_meta(history, META_FLAG)
        history.append({"role": "assistant", "content": RETRY})
        new_cs = hist_save(hist_truncate(history))
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": RETRY,
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # OK → guardamos draft y pasamos a 208 (allí se confirma y fija monto/estado)
    variables["coverage_draft"] = {
        "nombre": nombre,
        "apellido": apellido,
        "obra": obra,
        "plan": (plan or "UNICO"),
        "afiliado": afiliado,
        "token": token,
    }
    return {
        "nodo_destino": 208,
        "subsiguiente": 0,  # ejecutar 208 ahora
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": "",
        "group_id": None,
        "question_id": None,
        "result": "Abierta",
    }



def nodo_208(variables):
    """
    208 - Confirmación de cobertura y copago.
      - Chequea SI/NO primero (parseando la última confirmación del historial).
      - Trata como 'PARTICULAR' solo si:
          * el mensaje actual contiene 'particular' (norm_text), o
          * la última confirmación del historial tiene 'Cobertura: Particular'.
      - Persiste en contacts y fija TX (amount/status) en un solo lugar.
    """
    import json, re
    import app.Model.enums as enums


    from app.flows.workflows_utils import (
        norm_text, plan_norm, fmt_amount, calc_amount,
        hist_load, hist_save, hist_truncate,
        hist_count_meta, hist_add_meta,
        is_yes, is_no,
    )

    TO_HUMAN       = MESSAGES["TO_HUMAN"]
    ASK_CREDENTIAL = MESSAGES["ASK_CREDENTIAL"]

    CONFIRM_HEADER = MESSAGES["CONFIRM_HEADER"]
    CONFIRM_TPL    = MESSAGES["CONFIRM_TPL"]
    FOOT_NO_COVER  = MESSAGES["CONFIRM_FOOTER_NO_COVERAGE"]
    FOOT_NO_COPAY  = MESSAGES["CONFIRM_FOOTER_NO_COPAY"]
    FOOT_COPAY     = MESSAGES["CONFIRM_FOOTER_COPAY"]

    MAX_RETRIES = 2
    META_FLAG   = "[CONFIRM_ATTEMPT]"

    # ---------- helpers ----------
    def _save(nodo_destino, subsiguiente, history_list, response_text, abierta=True):
        new_cs = hist_save(hist_truncate(history_list))
        return {
            "nodo_destino": nodo_destino,
            "subsiguiente": subsiguiente,
            "conversation_str": new_cs,
            "response_text": response_text,
            "group_id": None,
            "question_id": None,
            "result": "Abierta" if abierta else "Cerrada",
        }

    def _parse_last_confirmation(history_list):
        # Busca el último bloque de confirmación que imprimimos
        for m in reversed(history_list):
            if isinstance(m, dict) and m.get("role") == "assistant":
                txt = (m.get("content") or "")
                if txt.startswith(CONFIRM_HEADER):
                    import re as _re
                    def _val(label):
                        rx = rf"^{_re.escape(label)}\s*(.*)$"
                        mo = _re.search(rx, txt, flags=_re.MULTILINE)
                        return (mo.group(1).strip() if mo else "")
                    return {
                        "full_name": _val("Nombre:"),
                        "obra":      _val("Cobertura:"),
                        "plan":      _val("Plan:"),
                        "afiliado":  _val("Afiliado:"),
                        "token":     _val("Token:"),
                    }
        return None

    # ---------- contexto ----------
    history  = hist_load(variables.get("conversation_str") or "")
    body_raw = (variables.get("body") or "").strip()
    body_norm = norm_text(body_raw)

    ctt      = variables.get("ctt")
    contacto = variables.get("contacto")
    tx       = variables.get("tx")

    draft    = variables.get("coverage_draft") or {}
    nombre   = (draft.get("nombre") or "").strip()
    apellido = (draft.get("apellido") or "").strip()
    obra_d   = (draft.get("obra") or "").strip()          # ojo: SIN default a "Particular"
    plan_d   = (draft.get("plan") or "").strip()
    afiliado = (draft.get("afiliado") or "").strip()
    token    = (draft.get("token") or "").strip()

    parsed_confirm = _parse_last_confirmation(history)
    obra_from_confirm = (parsed_confirm.get("obra") or "").strip() if parsed_confirm else ""
    plan_from_confirm = (parsed_confirm.get("plan") or "").strip() if parsed_confirm else ""

    user_said_particular = bool(re.search(r"\bparticular\b", body_norm))
    history_was_particular = (obra_from_confirm.upper() == "PARTICULAR")

    # =====================================================================
    # 1) SI / NO — SIEMPRE antes que cualquier otra cosa
    # =====================================================================
    if is_yes(body_raw) or is_no(body_raw):
        if not parsed_confirm:
            # No hay confirmación previa para interpretar el SI/NO -> humano
            return _save(212, 1, history, TO_HUMAN, abierta=False)

        full_name = (parsed_confirm.get("full_name") or "").strip()
        obra_txt  = (obra_from_confirm or obra_d or "Particular").strip()
        plan_txt  = (plan_from_confirm or plan_d or "UNICO").strip()
        plan_n    = plan_norm(plan_txt)
        amount    = calc_amount(obra_txt, plan_n)

        if is_yes(body_raw):
            # contacts
            try:
                if ctt and contacto:
                    if full_name:
                        try:
                            ctt.set_name(contact_id=contacto.contact_id, name=full_name)
                        except Exception as e:
                            print(f"[208] set_name error: {e}")
                    try:
                        ctt.set_coverage(
                            contact_id=contacto.contact_id,
                            coverage=obra_txt, plan=plan_n,
                            member_id=(afiliado or None), token=None
                        )
                    except Exception as e:
                        print(f"[208] set_coverage error: {e}")
            except Exception as e:
                print(f"[208] Persist contacts error: {e}")

            if amount is None:
                return _save(212, 1, history, TO_HUMAN, abierta=False)

            try:
                if tx and contacto:
                    if float(amount) <= 0:
                        ok = tx.safe_update(
                            contacto.contact_id,
                            amount=0.0, currency="ARS",
                            status=enums.TxStatus.NO_COPAY.value
                        )
                        print(f"[208] TX no_copay ok={ok}")
                        return _save(211, 0, history, "")  # a lista de espera
                    else:
                        ok = tx.safe_update(
                            contacto.contact_id,
                            amount=float(amount), currency="ARS",
                            status=enums.TxStatus.PENDING.value
                        )
                        print(f"[208] TX pending ok={ok} amount={amount}")
            except Exception as e:
                print(f"[208] TX update error: {e}")

            variables["payment_info"] = {
                "obra": obra_txt, "plan": plan_n, "amount": float(amount)
            }
            return {
                "nodo_destino": 209,
                "subsiguiente": 0,
                "conversation_str": variables.get("conversation_str", ""),
                "response_text": "",
                "group_id": None,
                "question_id": None,
                "result": "Abierta",
            }

        # NO → reintentos cruzados 207/208
        attempts = hist_count_meta(history, META_FLAG)
        if attempts + 1 >= MAX_RETRIES:
            return _save(212, 1, history, TO_HUMAN, abierta=False)
        hist_add_meta(history, META_FLAG)
        history.append({"role": "assistant", "content": ASK_CREDENTIAL})
        return _save(207, 1, history, ASK_CREDENTIAL)

    # =====================================================================
    # 2) “Particular” mensaje actual o confirmación previa)
    # =====================================================================
    if user_said_particular or history_was_particular:
        obra_txt = "PARTICULAR"
        plan_n = "UNICO"
        amount = calc_amount(obra_txt, plan_n)

        # contacts
        try:
            if ctt and contacto:
                full = " ".join([nombre, apellido]).strip()
                if full:
                    try:
                        ctt.set_name(contact_id=contacto.contact_id, name=full)
                    except Exception as e:
                        print(f"[208] set_name (Particular) error: {e}")
                try:
                    ctt.set_coverage(contact_id=contacto.contact_id,
                                     coverage=obra_txt, plan=plan_n,
                                     member_id=None, token=None)
                except Exception as e:
                    print(f"[208] set_coverage (Particular) error: {e}")
        except Exception as e:
            print(f"[208] Persist contacts (Particular) error: {e}")

        if amount is None:
            return _save(212, 1, history, TO_HUMAN, abierta=False)

        try:
            if tx and contacto:
                ok = tx.safe_update(contacto.contact_id,
                                    amount=float(amount),
                                    currency="ARS",
                                    status=enums.TxStatus.PENDING.value)
                print(f"[208] TX pending (Particular) ok={ok} amount={amount}")
        except Exception as e:
            print(f"[208] TX update (Particular) error: {e}")

        variables["payment_info"] = {"obra": obra_txt, "plan": plan_n, "amount": float(amount)}
        return {
            "nodo_destino": 209,
            "subsiguiente": 0,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # =====================================================================
    # 3) Generar (o regenerar) confirmación para OOSS/Prepaga
    # =====================================================================
    obra_txt = (obra_d or "Particular").strip()
    plan_txt = (plan_d or "UNICO").strip()
    plan_n   = plan_norm(plan_txt)
    amount   = calc_amount(obra_txt, plan_n)

    if amount is None:
        footer = FOOT_NO_COVER
    elif float(amount) <= 0:
        footer = FOOT_NO_COPAY
    else:
        footer = FOOT_COPAY.format(monto=fmt_amount(amount))

    confirm_text = (
        CONFIRM_HEADER +
        CONFIRM_TPL.format(
            nombre=nombre or "",
            apellido=apellido or "",
            obra=obra_txt,
            plan=plan_n,
            afiliado=afiliado,
            token=token or "",
            footer=footer,
        )
    )
    history.append({"role": "assistant", "content": confirm_text})
    return _save(208, 1, history, confirm_text)



def nodo_209(variables):
    """
    209 - Pago: envía instrucciones (una sola vez), recibe comprobante o comandos de medios.
      - En la primera entrada al nodo: envía PAYMENT_1/2/3 (con alias/CBU, etc.).
      - Si recibe adjunto image/pdf => 210 (análisis de comprobante).
      - Comandos:
         * "otros" => status=to_collect, method=None => 212 (admisión)
         * "efectivo" => status=to_collect, method=cash => 212
         * "tarjeta" => status=to_collect, method=card => 212
      - Input inválido (texto/audio/otros adjuntos):
         * Cuenta reintento (máx 2) y responde PLEASE_IMG (pidiendo foto/pdf o elegir método).
         * Al 3º inválido => 212 (admisión).
    """
    

    import json, re
    import app.services.twilio_service as twilio
    import app.Model.enums as enums
    from app.flows.workflows_utils import (
        norm_text, fmt_amount,
        # historial
        hist_load, hist_save, hist_truncate,
        hist_recent_since, hist_user_msgs, hist_last_user_content,
        hist_count_meta, hist_add_meta,
        # adjuntos
        attach_is_line, attach_kind,
    )
    print("[209] DEBUG keys:", list(MESSAGES.keys())[:5], "...")  # confirma que MESSAGES existe
    print("[209] DEBUG enums:", hasattr(enums.TxStatus, "PENDING"), hasattr(enums.TxMethod, "TRANSFER"))
    print("[209] DEBUG payment_info:", variables.get("payment_info"))

    # --- mensajes del flujo ---
    PAY1 = MESSAGES["PAYMENT_1"]   # .format(monto=...)
    PAY2 = MESSAGES["PAYMENT_2"]
    PAY3 = MESSAGES["PAYMENT_3"]
    PAYMENT_RETRY = MESSAGES["PAYMENT_RETRY"]
    PAYMENT_FAIL  = MESSAGES["PAYMENT_FAIL"]
    TO_HUMAN = MESSAGES["TO_HUMAN"]
    OTHERS_ACK = MESSAGES["PAYMENT_OTHERS_ACK"]

    # --- const ---
    META_SENT = "[PAYMENT_MSG_SENT]"
    META_ATTEMPT = "[PAYMENT_INPUT_ATTEMPT]"
    MAX_RETRIES = 2

    # --- contexto ---
    history = hist_load(variables.get("conversation_str") or "")
    body_raw = (variables.get("body") or "").strip()
    body_norm = norm_text(body_raw)

    numero_limpio = variables.get("numero_limpio")
    sender_number = "whatsapp:+" + numero_limpio if numero_limpio else None

    tx = variables.get("tx")
    contacto = variables.get("contacto")
    info = variables.get("payment_info") or {}

    # Robustez: asegurarnos de tener amount para el copy del mensaje.
    amount = info.get("amount")
    if amount is None and tx and contacto:
        try:
            # fallback por si 208 no dejó payment_info (no debería pasar)
            amount = tx.get_expected_amount(contacto.contact_id)
        except Exception as e:
            print(f"[209] get_expected_amount error: {e}")

    # Si no tenemos monto, no podemos dar instrucciones coherentes
    if amount is None:
        return {
            "nodo_destino": 212,
            "subsiguiente": 1,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Cerrada",
        }

    # ========== 1) Enviar mensajes de pago SOLO la primera vez ==========
    
    already_sent = any(
        isinstance(m, dict) and m.get("role") == "meta" and m.get("content") == META_SENT
        for m in history
    )


    if not already_sent:
        # Twilio salientes (si hay número)
        if sender_number:
            try:
                twilio.send_whatsapp_message(PAY1.format(monto=fmt_amount(amount)), sender_number, None)
                twilio.send_whatsapp_message(PAY2, sender_number, None)
                twilio.send_whatsapp_message(PAY3, sender_number, None)
            except Exception as e:
                print(f"[209] Twilio send error: {e}")

        # Guardar en historial y marcar meta
        history.extend([
            {"role": "assistant", "content": PAY1.format(monto=fmt_amount(amount))},
            {"role": "assistant", "content": PAY2},
            {"role": "assistant", "content": PAY3},
        ])
        hist_add_meta(history, META_SENT)

        new_cs = hist_save(hist_truncate(history))
        variables["conversation_history"] = history
        variables["conversation_str"] = new_cs
        return {
            "nodo_destino": 209,
            "subsiguiente": 1,  # quedamos esperando comprobante o comando
            "conversation_str": new_cs,
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # ========== 2) Procesar entrada del usuario ==========
    # Consideramos mensajes desde el último envío (ya no usamos prompts aquí; basta con el último user)
    recent = hist_recent_since(history, set())  # todo lo reciente
    last_user = hist_last_user_content(recent)

    # 2.a) Comandos por texto
    if body_raw:
        # "otros"
        if re.search(r"\both?ros\b|\botros\b", body_norm):
            try:
                if tx and contacto:
                    ok = tx.safe_update(contacto.contact_id, status=enums.TxStatus.TO_COLLECT.value)
                    print(f"[209] to_collect (otros) ok={ok}")
            except Exception as e:
                print(f"[209] TX to_collect (otros) error: {e}")

            history.append({"role": "assistant", "content": OTHERS_ACK})
            new_cs = hist_save(hist_truncate(history))
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": OTHERS_ACK,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }

        # "efectivo" (incluimos sinónimos más comunes)
        if re.search(r"\befec(ti|)vo\b|\bcash\b", body_norm):
            try:
                if tx and contacto:
                    ok = tx.safe_update(
                        contacto.contact_id,
                        status=enums.TxStatus.TO_COLLECT.value,
                        method=enums.TxMethod.CASH.value,
                    )
                    print(f"[209] to_collect cash ok={ok}")
            except Exception as e:
                print(f"[209] TX to_collect cash error: {e}")

            history.append({"role": "assistant", "content": OTHERS_ACK})
            new_cs = hist_save(hist_truncate(history))
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": OTHERS_ACK,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }

        # "tarjeta" (crédito/débito)
        if re.search(r"\btarjeta\b|\bcredito\b|\bcr[eé]dito\b|\bdebito\b|\bd[ée]bito\b", body_norm):
            try:
                if tx and contacto:
                    ok = tx.safe_update(
                        contacto.contact_id,
                        status=enums.TxStatus.TO_COLLECT.value,
                        method=enums.TxMethod.CARD.value,
                    )
                    print(f"[209] to_collect card ok={ok}")
            except Exception as e:
                print(f"[209] TX to_collect card error: {e}")

            history.append({"role": "assistant", "content": TO_HUMAN})
            new_cs = hist_save(hist_truncate(history))
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }

    # 2.b) Adjuntos analizados desde el history
    if attach_is_line(last_user):
        kind = attach_kind(last_user)
        kind_l = (kind or "").lower()
        is_image = (kind_l == "image") or kind_l.startswith("image/")
        is_pdf = (kind_l == "application/pdf")

        if is_image or is_pdf:
            # comprobante válido para analizar
            return {
                "nodo_destino": 210,   # análisis de comprobante
                "subsiguiente": 0,
                "conversation_str": variables.get("conversation_str", ""),
                "response_text": "",
                "group_id": None,
                "question_id": None,
                "result": "Abierta",
            }

    # 2.c) Input inválido => reintento (máx 2) con PLEASE_IMG
    attempts = hist_count_meta(history, META_ATTEMPT)
    if attempts + 1 >= MAX_RETRIES:
        history.append({"role": "assistant", "content": PAYMENT_FAIL})
        new_cs = hist_save(hist_truncate(history))
        return {
            "nodo_destino": 212,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": PAYMENT_FAIL,
            "group_id": None,
            "question_id": None,
            "result": "Cerrada",
        }

    hist_add_meta(history, META_ATTEMPT)
    history.append({"role": "assistant", "content": PAYMENT_RETRY})
    new_cs = hist_save(hist_truncate(history))
    return {
        "nodo_destino": 209,
        "subsiguiente": 1,  # seguir esperando
        "conversation_str": new_cs,
        "response_text":  PAYMENT_RETRY,
        "group_id": None,
        "question_id": None,
        "result": "Abierta",
    }

def nodo_210(variables):
    """
    210 - Análisis de comprobante.
      - Toma el ÚLTIMO adjunto válido (image/pdf) del history y extrae: dia (YYYY-MM-DD), hora (HH:MM 24h), destinatario, monto.
      - Validación TOLERANTE:
          * destinatario: acepta "Nombre Apellido" / "Apellido Nombre" y variantes (ignora tildes, may/min, orden).
          * fecha: mismo día (zona BA) que data_created de la transacción abierta (DB en UTC).
          * monto: igualdad a 2 decimales (redondeo).
      - OK -> TX paid(method=transfer, paid_at UTC) y deriva a 211 (lista de espera).
      - Inválido -> suma intento; máx 2 -> 212. Si no agotó, envía PLEASE_IMG y vuelve a 209.
    """
    import json
    from datetime import timezone
    import app.services.brain as brain
    import app.Model.enums as enums
    from app.flows.workflows_utils import (
        # texto / montos
        norm_text, parse_amount_ars, receipt_datetime_ba, amounts_equal_2dec,
        # historial
        hist_load, hist_save, hist_truncate, hist_count_meta, hist_add_meta,
        find_last_valid_attachment,
        # fechas / matching
        parse_dt_utc, names_match_flexible, BA_TZ,
    )

    OK         = MESSAGES["RECEIPT_OK"]
    RECEIPT_RETRY = MESSAGES["RECEIPT_RETRY"]
    RECEIPT_FAIL  = MESSAGES["RECEIPT_FAIL"]    
    TO_HUMAN   = MESSAGES["TO_HUMAN"]

    META_FLAG   = "[RECEIPT_CHECK_ATTEMPT]"
    MAX_RETRIES = 2
    EXPECTED_RECIPIENT = "Fernandez Bettelli, Luciana "

    # -------- helpers --------
    def _save(nodo_destino, subsiguiente, history_list, response_text, abierta=True):
        new_cs = hist_save(hist_truncate(history_list))
        return {
            "nodo_destino": nodo_destino,
            "subsiguiente": subsiguiente,
            "conversation_str": new_cs,
            "response_text": response_text,
            "group_id": None,
            "question_id": None,
            "result": "Abierta" if abierta else "Cerrada",
        }

    # -------- contexto --------
    history  = hist_load(variables.get("conversation_str") or "")
    body_raw = (variables.get("body") or "").strip()  # no usamos texto libre acá; validamos adjunto
    _ = norm_text(body_raw)  # por consistencia, aunque no lo usamos

    tx       = variables.get("tx")
    contacto = variables.get("contacto")
    if not (tx and contacto):
        return _save(212, 1, history, TO_HUMAN, abierta=False)

    # 1) Localizar el último comprobante válido (image/pdf)
    attach_line = find_last_valid_attachment(history)
    if not attach_line:
        attempts = hist_count_meta(history, META_FLAG)
        if attempts + 1 >= MAX_RETRIES:
            history.append({"role": "assistant", "content": RECEIPT_FAIL})
            return _save(212, 1, history, RECEIPT_FAIL, abierta=False)
        hist_add_meta(history, META_FLAG)
        history.append({"role": "assistant", "content": RECEIPT_RETRY})
        return _save(209, 1, history, RECEIPT_RETRY)

    # 2) LLM: extraer campos
    extract_prompt = [
        {
            "role": "system",
            "content": (
                "De la entrada del paciente (texto OCR/resumen de un comprobante bancario), extraé SIEMPRE y SOLO:\n"
                "- dia: YYYY-MM-DD\n"
                "- hora: HH:MM (24h)\n"
                "- destinatario: string\n"
                "- monto: número en ARS (usa punto decimal, sin símbolos ni separadores de miles)\n"
                "Respondé SOLO JSON exacto con claves: dia, hora, destinatario, monto. "
                "Si algún dato no está, dejá clave vacía."
            ),
        },
        {"role": "user", "content": attach_line},
    ]

    try:
        raw = brain.ask_openai(extract_prompt)
    except Exception as e:
        print(f"[210] Error LLM: {e}")
        raw = '{"dia":"","hora":"","destinatario":"","monto":""}'

    try:
        data = json.loads(raw)
    except Exception:
        data = {"dia": "", "hora": "", "destinatario": "", "monto": ""}

    dia   = (data.get("dia") or "").strip()
    hora  = (data.get("hora") or "").strip()
    dest  = (data.get("destinatario") or "").strip()
    m_raw = data.get("monto")
    comp_amount = parse_amount_ars(m_raw)
    comp_local  = receipt_datetime_ba(dia, hora)  # aware BA
    try:
        print("[210] extracted", {"dia": dia, "hora": hora, "dest": dest, "m_raw": m_raw, "comp_amount": comp_amount, "comp_local": str(comp_local)})
    except Exception as e:
        print(f"[210] debug error al loguear extracted: {e}")
    
    
    # 3) Datos esperados: monto + fecha creación de la TX abierta
    tx_row = tx.get_open_row(contacto.contact_id)
    if not tx_row:
        return _save(212, 1, history, TO_HUMAN, abierta=False)

    # DEBUG: TX abierta recuperada
    try:
        print(
            "[210] open_tx",
            "id=", getattr(tx_row, "id", None),
            "amount=", getattr(tx_row, "amount", None),
            "type(amount)=", type(getattr(tx_row, "amount", None)).__name__,
            "status=", getattr(tx_row, "status", None),
            "data_created=", getattr(tx_row, "data_created", None),
        )
    except Exception as e:
        print(f"[210] debug error al loguear tx_row: {e}, tx_row={tx_row}")




    try:
        expected_amount = float(getattr(tx_row, "amount", None)) if getattr(tx_row, "amount", None) is not None else None
    except Exception:
        expected_amount = None

    tx_created_utc = parse_dt_utc(getattr(tx_row, "data_created", None))
    if not tx_created_utc:
        return _save(212, 1, history, TO_HUMAN, abierta=False)

    tx_created_ba_date = tx_created_utc.astimezone(BA_TZ).date()

    # DEBUG: comparación de montos (+ tipos)
    try:
        print(
            "[210] amounts",
            {
                "comp_amount": comp_amount,
                "type(comp_amount)": type(comp_amount).__name__,
                "expected_amount": expected_amount,
                "type(expected_amount)": type(expected_amount).__name__,
                "eq2dec": amounts_equal_2dec(comp_amount, expected_amount),
            }
        )
    except Exception as e:
        print(f"[210] debug error al loguear amounts: {e}")

    # 4) Validaciones
    ok = True

    # 4.a) Monto
    if not amounts_equal_2dec(comp_amount, expected_amount):
        ok = False

    # 4.b) Destinatario (flexible)
    if ok and not names_match_flexible(EXPECTED_RECIPIENT, dest):
        ok = False

    # 4.c) Fecha = mismo día que tx.data_created (en BA)
    if ok:
        if not comp_local:
            ok = False
        else:
            if comp_local.date() != tx_created_ba_date:
                ok = False

    # 5) Ruteo
    if not ok:
        attempts = hist_count_meta(history, META_FLAG)
        if attempts + 1 >= MAX_RETRIES:
            history.append({"role": "assistant", "content": RECEIPT_FAIL})
            return _save(212, 1, history, RECEIPT_FAIL, abierta=False)
        hist_add_meta(history, META_FLAG)
        history.append({"role": "assistant", "content": RECEIPT_RETRY})
        return _save(209, 1, history, RECEIPT_RETRY)

    # OK → paid (UTC)
    history.append({"role": "assistant", "content": OK})
    try:
        paid_utc_str = comp_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        tx.safe_update(contacto.contact_id,
                       status=enums.TxStatus.PAID.value,
                       method=enums.TxMethod.TRANSFER.value,
                       paid_at=paid_utc_str)
    except Exception as e:
        print(f"[210] Error actualizando TX a paid: {e}")

    return _save(211, 0, history, OK)


def nodo_211(variables):
    """
    211 - Lista de espera.
      - Se usa cuando:
        * OOSS/Prepaga con copago = 0 (seteado como NO_COPAY en 208), o
        * Comprobante validado y marcado como PAID en 210.
      - Solo informa al paciente que quedó en espera y cierra la conversación.
      - No toca transactions (el estado ya quedó fijado antes).
    """
    from app.flows.workflows_utils import hist_load, hist_save, hist_truncate

    WAITING = MESSAGES["WAITING"]  # ej: "Perfecto, te dejamos en lista de espera..."
    history = hist_load(variables.get("conversation_str") or "")
    history.append({"role": "assistant", "content": WAITING})
    new_cs = hist_save(hist_truncate(history))

    return {
        "nodo_destino": 211,
        "subsiguiente": 1,          # no hay pasos siguientes automáticos
        "conversation_str": new_cs,
        "response_text": WAITING,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada",        # cerramos la conversación
    }

def nodo_212(variables):
    """
    212 - Derivación a admisión (humano).
      - Se usa cuando:
        * Se agotaron reintentos o hay inconsistencia que requiere intervención.
      - Solo informa y cierra.
      - No toca transactions aquí.
    """
    from app.flows.workflows_utils import hist_load, hist_save, hist_truncate

    TO_HUMAN = MESSAGES["TO_HUMAN"]  # ej: "Acercate a admisión."
    history = hist_load(variables.get("conversation_str") or "")
    history.append({"role": "assistant", "content": TO_HUMAN})
    new_cs = hist_save(hist_truncate(history))

    return {
        "nodo_destino": 212,
        "subsiguiente": 1,          # no hay pasos siguientes automáticos
        "conversation_str": new_cs,
        "response_text": TO_HUMAN,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada",        # cerramos la conversación
    }


