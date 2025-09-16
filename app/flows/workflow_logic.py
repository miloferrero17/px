def ejecutar_nodo(nodo_id, variables):
    NODOS = {
        201: nodo_201,
        202: nodo_202,
        203: nodo_203,
        204: nodo_204,
        205: nodo_205,
        206: nodo_206,
        207: nodo_207,   # credencial / particular / extracción
        208: nodo_208,   # medios de pago (envía 3 mensajes) → 211
        210: nodo_210,   # confirmación con monto + persistencia + routing
        211: nodo_211,   # comprobante / “Otros” / efectivo/tarjeta
        212: nodo_212,   # admisión (humano)
        213: nodo_213,   # “espera”
    }
    return NODOS[nodo_id](variables)



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
    response_text = "¿Qué te trae a la guardia?"
    
    
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
        "Para continuar, enviá una foto o captura de la credencial de tu obra social o prepaga.\n"
        "Si no tenés, escribí: Particular."
    ),
    "RETRY_CREDENTIAL": (
        "No pude tomar bien los datos. Reintentemos: enviá de nuevo la credencial o escribí Particular."
    ),
    "TO_HUMAN": "Acercate a admisión para recibir ayuda.",

    # 210 confirmación
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


    # 208 pagos (3 mensajes separados)
    "PAYMENT_1": (
        "El monto a abonar es de ${monto} 💵\n"
        "Para continuar, podés pagar por transferencia y enviar acá la foto del comprobante.\n"
        "Si preferís otro medio de pago, escribí “Otros”."
    ),
    "PAYMENT_2": "Nuestro alias es:",
    "PAYMENT_3": "PACIENTEX.CLINICA.GUARDIA",

    # 211 comprobante / otros medios
    "RECEIPT_OK": "✅ Recibimos tu comprobante.",
    "PLEASE_IMG": "Por favor, reenviá el comprobante como imagen o PDF.",
    "OTHERS_MENU": (
        "💵 Para abonar con efectivo, escribí “Efectivo”.\n"
        "💳 Para abonar con tarjeta, escribí “Tarjeta”."
    ),
    "CASH_MSG": "Perfecto, abonás en efectivo. Acercate a admisión.",

    # 213 espera
    "WAITING": "✅ Ya registramos tu consulta. Quedate en la sala de espera y aguardá a que te llamen.\n\n"
    "Si tus síntomas empeoran, avisá en admisión de inmediato.",


    }


def nodo_207(variables):
    """
    207 - Pedir credencial O detectar 'particular'.
      - Detecta cualquier mensaje que contenga "particular".
      - Acepta credencial por adjunto **solo imagen** (PDF no).
      - Extrae: nombre, apellido, obra, plan, afiliado, token (token opcional).
      - Requiere: obra + afiliado.
      - Si OK → guarda draft y deriva a 210 (confirmación con monto).
      - Al agotar intentos / 2º error consecutivo → 212 (humano) para evitar loops.
    """
    import json, re
    import app.services.brain as brain
    from app.flows.workflows_utils import norm_text, calc_amount

    ASK = MESSAGES["ASK_CREDENTIAL"]
    RETRY = MESSAGES["RETRY_CREDENTIAL"]
    TO_HUMAN = MESSAGES["TO_HUMAN"]


    # Helpers de adjuntos (compatibles con 211)
    def _last_user(msgs):
        for m in reversed(msgs):
            if isinstance(m, dict) and m.get("role") == "user":
                return (m.get("content") or "").strip()
        return ""

    def _attachment_kind(s: str) -> str:
        # Soporta "[Adjunto image]" | "[Adjunto image/jpeg]" | "[Adjunto application/pdf]"
        m = re.match(r"^\[Adjunto ([^\]]+)\]", s or "")
        return (m.group(1).strip().lower() if m else "")

    # Historial seguro
    conversation_str = variables.get("conversation_str", "")
    try:
        history = json.loads(conversation_str) if conversation_str else []
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    user_msg = (variables.get("body") or "").strip()
    user_norm = norm_text(user_msg)

    # 1) 'particular' en cualquier frase → ir directo a pago (PARTICULAR/UNICO)
    if re.search(r"\bparticular\b", user_norm):
        obra_txt = "Particular"
        plan_txt = "UNICO"

        amount = calc_amount("PARTICULAR", "UNICO")
        if amount is None or float(amount) <= 0:
            # Evitar loop si la tabla de montos está mal
            return {
                "nodo_destino": 212,
                "subsiguiente": 0,
                "conversation_str": variables.get("conversation_str", ""),
                "response_text": "",
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }

        # Persistencia mínima ,guardo la info
        try:
            ctt = variables.get("ctt")
            contacto = variables.get("contacto")
            if ctt and contacto:
                try:
                    ctt.set_coverage(
                        contact_id=contacto.contact_id,
                        coverage=obra_txt,
                        plan=plan_txt,
                        member_id=None,
                        token=None,
                    )
                except Exception as e:
                    print(f"[207] set_coverage no disponible (Particular): {e}")
        except Exception as e:
            print(f"[207] Error persistiendo en contacts (Particular): {e}")

        try:
            tx = variables.get("tx")
            contacto = variables.get("contacto")
            open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id) if (tx and contacto) else None
            if open_tx_id:
                tx.update(id=open_tx_id, amount=float(amount), currency="ARS", status="pending")
        except Exception as e:
            print(f"[207] Error actualizando tx (Particular): {e}")

        variables["payment_info"] = {"obra": obra_txt, "plan": plan_txt, "amount": float(amount)}
        return {
            "nodo_destino": 208,
            "subsiguiente": 0,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # 2) Primera vez → pedir credencial
    asked_once = any(
        isinstance(m, dict) and m.get("role") == "assistant" and m.get("content") == ASK
        for m in history
    )
    if not asked_once:
        history.append({"role": "assistant", "content": ASK})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": ASK,
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # === Tomar sólo los mensajes posteriores al último ASK/RETRY ===
    last_prompt_idx = -1
    for i in range(len(history) - 1, -1, -1):
        m = history[i]
        if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content") in (ASK, RETRY):
            last_prompt_idx = i
            break
    recent = history[last_prompt_idx + 1:] if last_prompt_idx >= 0 else history
    last_prompt_content = (history[last_prompt_idx]["content"]
                           if last_prompt_idx >= 0 and isinstance(history[last_prompt_idx], dict)
                           else None)
    last_prompt_was_retry = (last_prompt_content == RETRY)
    
    # Anti-bucle: ¿cuántos RETRY ya mande desde el último prompt?
    

    # Si no hay mensaje del paciente después del ASK/RETRY → no reenvio
    has_new_user_after_prompt = any(isinstance(m, dict) and m.get("role") == "user" for m in recent)
    if not has_new_user_after_prompt:
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # --- Adjuntos: validar tipo (solo imagen; PDF NO) ---
    last_user_msg = _last_user(recent)
    if last_user_msg.startswith("[Adjunto "):
        kind = _attachment_kind(last_user_msg)
        is_image = (kind == "image") or kind.startswith("image/")
        is_pdf = (kind == "application/pdf")

        if is_pdf:
            # 2º error consecutivo → 212 aunque no se haya persistido el meta
            if last_prompt_was_retry:
                history.append({"role": "assistant", "content": TO_HUMAN})
                new_cs = json.dumps(history)
                return {
                    "nodo_destino": 212,
                    "subsiguiente": 1,
                    "conversation_str": new_cs,
                    "response_text": TO_HUMAN,
                    "group_id": None,
                    "question_id": None,
                    "result": "Cerrada",
                }

            # Intento contable normal
            history.append({"role": "assistant", "content": RETRY})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 207,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": RETRY,
                "group_id": None,
                "question_id": None,
                "result": "Abierta",
            }
        if not is_image:
            # Adjuntos neutrales (audio/docs) → reenviar ASK (no cuenta como inválido)
            history.append({"role": "assistant", "content": ASK})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 207,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": ASK,
                "group_id": None,
                "question_id": None,
                "result": "Abierta",
            }

        # Si es imagen, seguimos al extractor.

    # 3) Intentar extraer datos del historial (desde 'recent')
    extract_prompt = [{
        "role": "system",
        "content": (
            "De la conversación del paciente (incluyendo posibles capturas/OCR), extraé si es posible:\n"
            "- Nombre\n"
            "- Apellido\n"
            "- Cobertura (obra social o prepaga)\n"
            "- Plan\n"
            "- Número de afiliado\n"
            "- Token/código adicional (si existe)\n\n"
            "Respondé SOLO JSON exacto con claves: nombre, apellido, obra, plan, afiliado, token.\n"
            "Ejemplo: {\"nombre\":\"Juan\",\"apellido\":\"Pérez\",\"obra\":\"OSDE\",\"plan\":\"210\",\"afiliado\":\"123\",\"token\":\"ABC\"}"
        )
    }, {
        "role": "user",
        "content": json.dumps(recent)
    }]

    try:
        raw = brain.ask_openai(extract_prompt)
    except Exception as e:
        raw = '{"nombre":"","apellido":"","obra":"","plan":"","afiliado":"","token":""}'
        print(f"[207] Error LLM: {e}")

    try:
        data = json.loads(raw)
    except Exception:
        data = {"nombre": "", "apellido": "", "obra": "", "plan": "", "afiliado": "", "token": ""}

    nombre = (data.get("nombre") or "").strip()
    apellido = (data.get("apellido") or "").strip()
    obra = (data.get("obra") or "").strip()
    plan = re.sub(r"\s+", "", (data.get("plan") or "").strip()).upper()
    afiliado = (data.get("afiliado") or "").strip()
    token = (data.get("token") or "").strip()

        # Regla: obra + afiliado obligatorios
    if not obra or not afiliado:
        # 2º error consecutivo → 212 (anti-bucle aun si meta no persiste)
        if last_prompt_was_retry:
            history.append({"role": "assistant", "content": TO_HUMAN})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }

        # 1º inválido → RETRY y quedarse en 207 esperando
        history.append({"role": "assistant", "content": RETRY})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": RETRY,
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # ===== ÉXITO: obra+afiliado presentes → guardar draft, setear pending y derivar a 210 =====
    variables["coverage_draft"] = {
        "nombre": nombre,
        "apellido": apellido,
        "obra": obra,
        "plan": plan,
        "afiliado": afiliado,
        "token": token,
    }

    # Setear amount/currency/status='pending' en la tx abierta (para que 211 pueda validar)
    try:
        tx = variables.get("tx")
        contacto = variables.get("contacto")
        amt = calc_amount(obra, plan)

        open_tx_id = None
        if tx and contacto:
            if hasattr(tx, "get_open_transaction_id_by_contact_id"):
                open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id)
            if not open_tx_id and hasattr(tx, "get_by_contact_id"):
                rows = tx.get_by_contact_id(contacto.contact_id) or []
                if rows:
                    open_tx_id = rows[-1].id

        print(f"[207] TX open_tx_id={open_tx_id} | amt={amt}")
        if open_tx_id and (amt is not None):
            tx.update(id=open_tx_id, amount=float(amt), currency="ARS", status="pending")
        else:
            print(f"[207] No se pudo setear pending (open_tx_id={open_tx_id}, amt={amt})")
    except Exception as e:
        print(f"[207] Error configurando tx pending: {e}")

    print(f"[207] RETURN nodo_destino=210 subsiguiente=0 draft={variables.get('coverage_draft')}")
    return {
        "nodo_destino": 210,
        "subsiguiente": 0,  # ejecutar 210 ya
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": "",
        "group_id": None,
        "question_id": None,
        "result": "Abierta",
    }





def nodo_208(variables):
    """
    Pago (particular o copago). Envía 3 mensajes y deriva a 211.
    Requiere variables['payment_info'] = {'obra','plan','amount'} (set en 210).
    """
    import json
    import app.services.twilio_service as twilio
    from app.flows.workflows_utils import fmt_amount

    numero_limpio = variables.get("numero_limpio")
    sender_number = "whatsapp:+" + numero_limpio if numero_limpio else None

    info = variables.get("payment_info") or {}
    amount = info.get("amount")

    # Asegurar que la tx quede en 'pending' con el monto
    try:
        tx = variables.get("tx")
        contacto = variables.get("contacto")
        open_tx_id = None

        if tx and contacto:
            # 1) Método estándar
            if hasattr(tx, "get_open_transaction_id_by_contact_id"):
                open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id)

            # 2) Fallback: última tx del contacto
            if not open_tx_id and hasattr(tx, "get_by_contact_id"):
                rows = tx.get_by_contact_id(contacto.contact_id) or []
                if rows:
                    open_tx_id = rows[-1].id

        if open_tx_id and amount is not None:
            tx.update(id=open_tx_id, amount=float(amount), currency="ARS", status="pending")
            print(f"[208] TX {open_tx_id} seteada a pending | amount={amount}, currency=ARS")
        else:
            print(f"[208] No se pudo actualizar TX (open_tx_id={open_tx_id}, amount={amount})")

    except Exception as e:
        print(f"[208] Error seteando tx pending: {e}")

    # Enviar mensajes al paciente
    if sender_number:
        twilio.send_whatsapp_message(MESSAGES["PAYMENT_1"].format(monto=fmt_amount(amount)), sender_number, None)
        twilio.send_whatsapp_message(MESSAGES["PAYMENT_2"], sender_number, None)
        twilio.send_whatsapp_message(MESSAGES["PAYMENT_3"], sender_number, None)

    # Guardar en historial y pasar a 211
    try:
        history = json.loads(variables.get("conversation_str") or "[]")
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    history.extend([
        {"role": "assistant", "content": MESSAGES["PAYMENT_1"].format(monto=fmt_amount(amount))},
        {"role": "assistant", "content": MESSAGES["PAYMENT_2"]},
        {"role": "assistant", "content": MESSAGES["PAYMENT_3"]},
    ])
    new_cs = json.dumps(history)

    return {
        "nodo_destino": 211,
        "subsiguiente": 1,
        "conversation_str": new_cs,
        "response_text": "",
        "group_id": None,
        "question_id": None,
        "result": "Abierta",
    }



def nodo_210(variables):
    """
    210 - Confirmación con cálculo de copago y enrutamiento.
      - Genera mensaje de confirmación (con copago) a partir del draft de 207.
      - Si el paciente responde SI/NO, PARSEA la última confirmación del historial (no depende de _210_cache)
        y actúa en consecuencia:
          * SI  → persiste datos; monto > 0 → 208; monto = 0 → 213; monto None → 212
          * NO  → contabiliza intento cruzado (con 207); si alcanzó tope → 212; sino vuelve a 207 (ASK)
    """
    import json, re
    from app.flows.workflows_utils import ( norm_text,plan_norm as plan_norm_helper,fmt_amount,calc_amount,)

    TO_HUMAN = MESSAGES["TO_HUMAN"]
    ASK = MESSAGES["ASK_CREDENTIAL"]

    # === Helpers de reintentos (cross-nodo) ===
    MAX_CRED_ATTEMPTS = 2  # tope acumulado 207/210

    def _cred_attempts_count(history):
        return sum(
            1 for m in history
            if isinstance(m, dict) and m.get("role") == "meta" and m.get("content") == "[CRED_ATTEMPT]"
        )

    def _cred_attempts_add(history):
        history.append({"role": "meta", "content": "[CRED_ATTEMPT]"})

    def _parse_last_confirmation(history):
        # Busca el último mensaje de confirmación enviado por el bot
        for m in reversed(history):
            if isinstance(m, dict) and m.get("role") == "assistant":
                txt = (m.get("content") or "")
                if txt.startswith(MESSAGES["CONFIRM_HEADER"]):
                    def _val(label):
                        rx = rf"^{re.escape(label)}\s*(.*)$"
                        mo = re.search(rx, txt, flags=re.MULTILINE)
                        return (mo.group(1).strip() if mo else "")
                    full_name = _val("Nombre:")
                    obra      = _val("Cobertura:")
                    plan      = _val("Plan:")
                    afiliado  = _val("Afiliado:")
                    token     = _val("Token:")
                    return {
                        "full_name": full_name,
                        "obra": obra,
                        "plan": plan,
                        "afiliado": afiliado,
                        "token": token,
                    }
        return None

    # Historial
    try:
        history = json.loads(variables.get("conversation_str") or "[]")
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []
    
    draft = variables.get("coverage_draft") or {}
    print(f"[210] draft_in={draft}")

    # Normalizador de input del usuario
    user_msg = (variables.get("body") or "").strip()
    user_norm = norm_text(user_msg)
    is_yes = bool(re.search(r"\bsi\b|\bsí\b", user_norm))
    is_no  = bool(re.search(r"\bno\b", user_norm))
    print(f"[210] user_norm={user_norm!r} is_yes={is_yes} is_no={is_no}")
    # --- 1) SI/NO: procesar ANTES de generar confirmación para evitar loop ---
    if is_yes or is_no:
        parsed = _parse_last_confirmation(history)
        print(f"[210] parsed_from_history={parsed}")
        if not parsed:
            # No hay confirmación previa para leer → mandamos a admisión para evitar loops
            print("[210] No hay confirmación previa -> TO_HUMAN")
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": variables.get("conversation_str", ""),
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }

        full_name = (parsed.get("full_name") or "").strip()
        obra_txt  = (parsed.get("obra") or "").strip() or "Particular"
        plan_txt  = (parsed.get("plan") or "").strip() or "UNICO"
        afiliado  = (parsed.get("afiliado") or "").strip()
        token     = (parsed.get("token") or "").strip()

        # Normalizaciones y cálculo con helpers
        plan_n   = plan_norm_helper(plan_txt)
        amount   = calc_amount(obra_txt, plan_txt)  # calc_amount normaliza internamente
        print(f"[210] YES/NO flow -> obra={obra_txt} plan={plan_txt} amount={amount}")

        if is_yes:
            # Persistencia mínima
            try:
                ctt = variables.get("ctt")
                contacto = variables.get("contacto")
                if ctt and contacto:
                    if full_name:
                        try:
                            ctt.set_name(contact_id=contacto.contact_id, name=full_name)
                        except Exception as e:
                            print(f"[210] set_name no disponible: {e}")
                    try:
                        ctt.set_coverage(
                            contact_id=contacto.contact_id,
                            coverage=(obra_txt or None),
                            plan=(plan_n or None),
                            member_id=(afiliado or None),
                            token=(None),
                        )
                    except Exception as e:
                        print(f"[210] set_coverage no disponible: {e}")
            except Exception as e:
                print(f"[210] Error persistiendo en contacts (SI): {e}")

            # Transactions + routing
            try:
                tx = variables.get("tx")
                contacto = variables.get("contacto")
                open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id) if (tx and contacto) else None
                if open_tx_id:
                    currency = "ARS"
                    if amount is None:
                        # no tocamos la tx; ruteamos a 212 abajo
                        pass
                    elif float(amount) <= 0:
                        tx.update(id=open_tx_id, amount=0.0, currency=currency, status="no_copay")
                    else:
                        tx.update(id=open_tx_id, amount=float(amount), currency=currency, status="pending")
            except Exception as e:
                print(f"[210] Error actualizando pago (SI): {e}")

            # Routing según monto
            if amount is None:
                print("[210] amount= None -> TO_HUMAN")
                return {
                    "nodo_destino": 212,
                    "subsiguiente": 1,
                    "conversation_str": variables.get("conversation_str", ""),
                    "response_text": TO_HUMAN,
                    "group_id": None,
                    "question_id": None,
                    "result": "Cerrada",
                }
            if float(amount) <= 0:
                print("[210] amount<=0 -> 213")
                return {
                    "nodo_destino": 213,
                    "subsiguiente": 0,
                    "conversation_str": variables.get("conversation_str", ""),
                    "response_text": "",
                    "group_id": None,
                    "question_id": None,
                    "result": "Abierta",
                }
            print("[210] amount>0 -> 208")

            # Monto válido → a pago inmediato
            variables["payment_info"] = {"obra": obra_txt, "plan": plan_n, "amount": float(amount)}
            variables.pop("_210_cache", None)
            return {
                "nodo_destino": 208,
                "subsiguiente": 0,  # ejecutar 208 ahora
                "conversation_str": variables.get("conversation_str", ""),
                "response_text": "",
                "group_id": None,
                "question_id": None,
                "result": "Abierta",
            }

        # is_no → contar intento y decidir
        attempts = _cred_attempts_count(history)
        if attempts >= (MAX_CRED_ATTEMPTS - 1):
            variables.pop("_210_cache", None)
            variables.pop("coverage_draft", None)
            history.append({"role": "assistant", "content": TO_HUMAN})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }

        _cred_attempts_add(history)
        variables.pop("_210_cache", None)
        variables.pop("coverage_draft", None)
        history.append({"role": "assistant", "content": ASK})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,   # volver a pedir credencial y esperar
            "conversation_str": new_cs,
            "response_text": ASK,
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # --- 2) No es SI/NO: generar (o regenerar) confirmación desde el draft ---
    draft = variables.get("coverage_draft") or {}
    nombre = (draft.get("nombre") or "").strip()
    apellido = (draft.get("apellido") or "").strip()
    obra_txt = (draft.get("obra") or "").strip() or "Particular"
    plan_txt = (draft.get("plan") or "").strip() or "UNICO"
    afiliado = (draft.get("afiliado") or "").strip()
    token    = (draft.get("token") or "").strip()

    # Cálculo del monto para mostrar en la confirmación
    amount = calc_amount(obra_txt, plan_txt)
    print(f"[210] confirm flow -> obra={obra_txt} plan={plan_txt} amount={amount}")


    if amount is None:
        # Cobertura no encontrada en la lista de convenios
        footer = MESSAGES["CONFIRM_FOOTER_NO_COVERAGE"]
    elif float(amount) <= 0:
        footer = MESSAGES["CONFIRM_FOOTER_NO_COPAY"]
    else:
        footer = MESSAGES["CONFIRM_FOOTER_COPAY"].format(monto=fmt_amount(amount))


    confirm_text = (
        MESSAGES["CONFIRM_HEADER"] +
        MESSAGES["CONFIRM_TPL"].format(
            nombre=nombre or "",
            apellido=apellido or "",
            obra=obra_txt,
            plan=plan_norm_helper(plan_txt),
            afiliado=afiliado,
            token=token or "",
            footer=footer,
        )
    )
    print(f"[210] Saliendo con confirm_text (subsiguiente=1)")


    history.append({"role": "assistant", "content": confirm_text})
    new_cs = json.dumps(history)

    return {
        "nodo_destino": 210,
        "subsiguiente": 1,  # << esperar la respuesta SI/NO del paciente
        "conversation_str": new_cs,
        "response_text": confirm_text,
        "group_id": None,
        "question_id": None,
        "result": "Abierta",
    }


def nodo_211(variables):
    """
    Recibe comprobante de pago y comandos de medios:
      - Válidos: image/* o application/pdf → OK y 213 (espera)
      - 'Otros' → menú (efectivo/tarjeta)
      - 'Efectivo' o 'Tarjeta' → 212 (admisión) y cerrar
      - Inválidos → pedir reenviar (máx 2), luego 212
    """
    import json, re
    from app.flows.workflows_utils import (norm_text,parse_amount_ars,names_match,receipt_datetime_ba,is_today_not_future,amounts_equal_2dec,)
    import app.services.brain as brain
    from datetime import datetime, timezone
    import app.services.brain as brain
    from zoneinfo import ZoneInfo
    import unicodedata


    OK = MESSAGES["RECEIPT_OK"]
    PLEASE_IMG = MESSAGES["PLEASE_IMG"]
    TO_HUMAN = MESSAGES["TO_HUMAN"]
    CASH_MSG = MESSAGES["CASH_MSG"]
    OTHERS_MENU = MESSAGES["OTHERS_MENU"]
    MAX_RETRIES = 2

    # Historial
    try:
        history = json.loads(variables.get("conversation_str") or "[]")
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    # Último user del historial (para adjuntos)
    last_user = ""
    for m in reversed(history):
        if isinstance(m, dict) and m.get("role") == "user":
            last_user = (m.get("content") or "").strip()
            break

    def retries_count():
        # Cuenta cuántas veces ya pedimos "PLEASE_IMG"
        return sum(
            1 for m in history
            if isinstance(m, dict)
            and m.get("role") == "assistant"
            and m.get("content") == PLEASE_IMG
        )

    def extract_kind(s: str) -> str:
        # Soporta "[Adjunto image]" | "[Adjunto image/jpeg]" | "[Adjunto application/pdf]"
        m = re.match(r"^\[Adjunto ([^\]]+)\]", s or "")
        return (m.group(1).strip() if m else "")

    body_raw = (variables.get("body") or "")
    cmd_text = norm_text(body_raw)
    print(f"[211] DEBUG Body raw='{body_raw}' | norm='{cmd_text}'")  # << debug

    # --- 1) COMANDOS (solo por BODY) ---
    if cmd_text:
        # Menú de otros medios
        if re.search(r"\both?ros\b|\botros\b", cmd_text):
            history.append({"role": "assistant", "content": OTHERS_MENU})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,   # esperar elección (efectivo/tarjeta)
                "conversation_str": new_cs,
                "response_text": "",
                "group_id": None,
                "question_id": None,
                "result": "Abierta",
            }

        # Efectivo
        if re.search(r"\befectivo\b", cmd_text):
            history.append({"role": "assistant", "content": CASH_MSG})
            new_cs = json.dumps(history)

            # marcar a cobrar en efectivo
            try:
                tx = variables.get("tx")
                contacto = variables.get("contacto")
                open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id) if (tx and contacto) else None
                if open_tx_id:
                    tx.update(id=open_tx_id, status="to_collect", method="cash")
            except Exception as e:
                print(f"[211] Error actualizando tx (cash): {e}")

            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": CASH_MSG,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }

        # Tarjeta
        if re.search(r"\btarjeta\b", cmd_text):
            history.append({"role": "assistant", "content": TO_HUMAN})
            new_cs = json.dumps(history)

            # marcar a cobrar con tarjeta
            try:
                tx = variables.get("tx")
                contacto = variables.get("contacto")
                open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id) if (tx and contacto) else None
                if open_tx_id:
                    tx.update(id=open_tx_id, status="to_collect", method="card")
            except Exception as e:
                print(f"[211] Error actualizando tx (card): {e}")

            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }



    # --- 2) ADJUNTOS (solo por historial: last_user) ---
    if last_user.startswith("[Adjunto "):
        kind = extract_kind(last_user).lower()  # "image", "image/jpeg", "application/pdf", etc.
        is_image = (kind == "image") or kind.startswith("image/")
        is_pdf = (kind == "application/pdf")

        if is_image or is_pdf:
            # 1) Extraer campos del comprobante con OpenAI usando el último user (incluye OCR/summary)
            extract_prompt = [{
                "role": "system",
                "content": (
                    "Del siguiente comprobante de transferencia (texto OCR o resumen), extraé SIEMPRE y SOLO:\n"
                    "  - dia: en formato YYYY-MM-DD\n"
                    "  - hora: en formato HH:MM (24 horas)\n"
                    "  - destinatario: string\n"
                    "  - monto: número en ARS (usa punto decimal, sin símbolos ni separadores de miles)\n"
                    "Respondé SOLO JSON exacto con claves: dia, hora, destinatario, monto. "
                    "Si algún dato no está, dejá cadena vacía."
                )
            }, {
                "role": "user",
                "content": last_user
            }]

            try:
                raw = brain.ask_openai(extract_prompt)
                print(f"[211] LLM RAW: {raw}")

            except Exception as e:
                raw = '{"dia":"","hora":"","destinatario":"","monto":""}'
                print(f"[211] Error LLM: {e}")

            try:
                data = json.loads(raw)
            except Exception:
                data = {"dia": "", "hora": "", "destinatario": "", "monto": ""}

            dia = (data.get("dia") or "").strip()
            hora = (data.get("hora") or "").strip()
            dest = (data.get("destinatario") or "").strip()
            monto_raw = data.get("monto")  # puede venir como int/float o string
            comp_amount = parse_amount_ars(monto_raw)

            # 2) Traer monto esperado
            expected_amount = None
            tx_row = None
            try:
                tx = variables.get("tx")
                contacto = variables.get("contacto")
                if tx and contacto:
                    # Preferencia: pending/to_collect/no_copay en la conversación Abierta
                    if hasattr(tx, "get_open_pending_transaction_by_contact_id"):
                        tx_row = tx.get_open_pending_transaction_by_contact_id(contacto.contact_id)

                    # Fallback: última 'Abierta' (por si status no se guardó aún)
                    if not tx_row and hasattr(tx, "get_last_abierta_by_contact_id"):
                        tx_row = tx.get_last_abierta_by_contact_id(contacto.contact_id)

                    if tx_row:
                        expected_amount = float(getattr(tx_row, "amount", None) or 0.0)
                        print(f"[211] TX encontrada -> id={tx_row.id} name={getattr(tx_row,'name',None)} "
                            f"status={getattr(tx_row,'status',None)} amount={expected_amount} currency={getattr(tx_row,'currency',None)}")
                    else:
                        print("[211] No se encontró TX Abierta para este contacto.")
            except Exception as e:
                print(f"[211] Error obteniendo tx: {e}")


            # 3) Validaciones
            ok = True

            # 3.a) Monto (igualdad a 2 decimales)
            print(f"[211] Comparo montos: comp={comp_amount} vs expected={expected_amount}")
            if not amounts_equal_2dec(comp_amount, expected_amount):
                ok = False

            # 3.b) Destinatario
            if ok and not names_match("Luciana Fernandez Bettelli", dest):
                ok = False

            # 3.c) Fecha/hora (hoy y no futura en Buenos Aires)
            comp_local = receipt_datetime_ba(dia, hora)
            if ok and not is_today_not_future(comp_local):
                ok = False

            # 4) Ruteo según validación
            if not ok or (tx_row is None):
                history.append({"role": "assistant", "content": TO_HUMAN})
                new_cs = json.dumps(history)
                return {
                    "nodo_destino": 212,
                    "subsiguiente": 1,
                    "conversation_str": new_cs,
                    "response_text": TO_HUMAN,
                    "group_id": None,
                    "question_id": None,
                    "result": "Cerrada",
                }

            # 5) OK → marcar pagado con fecha/hora del comprobante (UTC)
            history.append({"role": "assistant", "content": OK})
            new_cs = json.dumps(history)
            try:
                paid_utc = comp_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
                variables.get("tx").update(
                    id=tx_row.id,
                    status="paid",
                    method="transfer",
                    paid_at=paid_utc
                )
                print(f"[211] TX {tx_row.id} actualizada a paid@{paid_utc}")
            except Exception as e:
                print(f"[211] Error actualizando tx (paid/transfer con comprobante): {e}")

            return {
                "nodo_destino": 213,
                "subsiguiente": 0,
                "conversation_str": new_cs,
                "response_text": OK,   
                "group_id": None,
                "question_id": None,
                "result": "Abierta",
            }



        # Adjuntos inválidos
        if retries_count() >= MAX_RETRIES:
            history.append({"role": "assistant", "content": TO_HUMAN})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }

        history.append({"role": "assistant", "content": PLEASE_IMG})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 211,
            "subsiguiente": 1,   # esperar que envíe la imagen/pdf válida
            "conversation_str": new_cs,
            "response_text": PLEASE_IMG,
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # --- 3) Texto sin adjunto ni comando → pedir imagen/pdf con límite ---
    if retries_count() >= MAX_RETRIES:
        history.append({"role": "assistant", "content": TO_HUMAN})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 211,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": TO_HUMAN,
            "group_id": None,
            "question_id": None,
            "result": "Cerrada",
        }

    history.append({"role": "assistant", "content": PLEASE_IMG})
    new_cs = json.dumps(history)
    return {
        "nodo_destino": 211,
        "subsiguiente": 1,  # esperar el adjunto del paciente
        "conversation_str": new_cs,
        "response_text": PLEASE_IMG,
        "group_id": None,
        "question_id": None,
        "result": "Abierta",
    }


def nodo_212(variables):
    """
    212 - Derivación a humano (admisión).
    """
    msg = MESSAGES["TO_HUMAN"]  # "Acercate a admisión."
    return {
        "nodo_destino": 212,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": msg,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada",
    }


def nodo_213(variables):
    return {
        "nodo_destino": 213,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": MESSAGES["WAITING"],
        "group_id": None,
        "question_id": None,
        "result": "Cerrada",
    }
