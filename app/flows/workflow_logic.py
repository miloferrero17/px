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
    "TO_HUMAN": "Acercate a admisión.",

    # 210 confirmación
    "CONFIRM_HEADER": "Revisá y confirmá tus datos:\n\n",
    "CONFIRM_TPL": (
        "Nombre: {nombre} {apellido}\n"
        "Cobertura: {obra}\n"
        "Plan: {plan}\n"
        "Afiliado: {afiliado}\n"
        "Token: {token}\n\n"
        "{footer}\n"
        "¿Está bien? SI/NO"
    ),
    "CONFIRM_FOOTER_COPAY": "Copago a abonar: ${monto} 💵",
    "CONFIRM_FOOTER_NO_COPAY": "No hay copago.",

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
    "WAITING": "✅ Tus datos fueron registrados.\nPor favor, aguardá en la sala de espera. Te vamos a llamar.",
}


def nodo_207(variables):
    """
    207 - Pedir credencial O detectar 'particular'.
      - Detecta cualquier mensaje que contenga "particular".
      - Extrae: nombre, apellido, obra, plan, afiliado, token (token opcional).
      - Requiere: obra + afiliado.
      - Si OK → guarda draft y deriva a 210 (confirmación con monto).
    """
    import json, re, unicodedata
    import app.services.brain as brain

    ASK = MESSAGES["ASK_CREDENTIAL"]
    RETRY = MESSAGES["RETRY_CREDENTIAL"]
    TO_HUMAN = MESSAGES["TO_HUMAN"]

    MAX_CRED_ATTEMPTS = 2  # tope acumulado 207/210

    def _cred_attempts_count(hist):
        return sum( 1 for m in hist if isinstance(m, dict) and m.get("role") == "meta" and m.get("content") == "[CRED_ATTEMPT]")

    def _cred_attempts_add(hist):
        hist.append({"role": "meta", "content": "[CRED_ATTEMPT]"})

    # Helpers
    def norm(s: str) -> str:
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = s.lower().strip()
        s = re.sub(r"\s+", " ", s)
        return s

    def count(hist, text):
        return sum(1 for m in hist if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content") == text)
    
    # Historial seguro
    conversation_str = variables.get("conversation_str", "")
    try:
        history = json.loads(conversation_str) if conversation_str else []
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []



    user_msg = (variables.get("body") or "").strip()
    user_norm = norm(user_msg)

    # 1) 'particular' en cualquier frase → ir a 210 con draft mínima
    if re.search(r"\bparticular\b", user_norm):
        # Saltar confirmación: ir directo a pagos con PART/UNICO
        from app.Model.coverages import Coverages

        obra_txt = "Particular"
        plan_norm = "UNICO"

        # Calcular monto de "Particular"
        cv = Coverages()
        amount = None
        try:
            amount = cv.get_amount_by_name_and_plan("PARTICULAR", "UNICO")
            if amount is None:
                amount = cv.get_amount_by_name("PARTICULAR")
        except Exception as e:
            print(f"[207] Error Coverages (Particular): {e}")
            amount = None

        # Persistir cobertura en contacts (sin token)
        try:
            ctt = variables.get("ctt")
            contacto = variables.get("contacto")
            if ctt and contacto:
                try:
                    # name no cambia acá; sólo coverage/plan/member_id/token=None
                    ctt.set_coverage(
                        contact_id=contacto.contact_id,
                        coverage=obra_txt,
                        plan=plan_norm,
                        member_id=None,
                        token=None,    # <- no guardamos token
                    )
                except Exception as e:
                    print(f"[207] set_coverage no disponible (Particular): {e}")
        except Exception as e:
            print(f"[207] Error persistiendo en contacts (Particular): {e}")

        # Actualizar transacción y enrutar
        try:
            tx = variables.get("tx")
            contacto = variables.get("contacto")
            open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id) if (tx and contacto) else None
            if open_tx_id and amount is not None:
                if float(amount) > 0:
                    tx.update(id=open_tx_id, amount=float(amount), currency="ARS", status="pending")
                else:
                    tx.update(id=open_tx_id, amount=0.0, currency="ARS", status="no_copay")
        except Exception as e:
            print(f"[207] Error actualizando tx (Particular): {e}")

        # Routing según monto
        if amount is None:
            # No pudimos determinar monto → a admisión
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": variables.get("conversation_str", ""),
                "response_text": MESSAGES["TO_HUMAN"],
                "group_id": None,
                "question_id": None,
                "result": "Cerrada",
            }

        if float(amount) <= 0:
            # No hay copago (raro en Particular, pero contemplado)
            return {
                "nodo_destino": 213,
                "subsiguiente": 1,
                "conversation_str": variables.get("conversation_str", ""),
                "response_text": MESSAGES["WAITING"],
                "group_id": None,
                "question_id": None,
                "result": "Abierta",
            }

        # Monto válido → ir a medios de pago
        variables["payment_info"] = {"obra": obra_txt, "plan": plan_norm, "amount": float(amount)}
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
    asked_once = any(isinstance(m, dict) and m.get("role") == "assistant" and m.get("content") == ASK for m in history)
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

    # Si todavía no hay ningún mensaje del paciente después del último ASK/RETRY, no intentes extraer
    has_new_user_after_prompt = any(isinstance(m, dict) and m.get("role") == "user" for m in recent)
    if not has_new_user_after_prompt:
        # no mandamos otro ASK para no spamear; esperamos nuevo input
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # 3) Intentar extraer datos del historial
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
        "content": json.dumps(recent)  # <<--- antes usaba variables.get("conversation_str", "")
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

    # Regla: obra + afiliado obligatorios (token/plan opcionales)
    # Regla: obra + afiliado obligatorios (token/plan opcionales).
    # Usa contador cruzado con 210 (tope 2 intentos en total).
    if not obra or not afiliado:
        attempts = _cred_attempts_count(history)
        if attempts >= (MAX_CRED_ATTEMPTS - 1):
            # alcanzó el tope acumulado → admisión
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

        # aún puede reintentar: marcamos intento y pedimos reintento
        _cred_attempts_add(history)
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


    # OK → guardar draft y pasar a 210
    variables["coverage_draft"] = {
        "nombre": nombre,
        "apellido": apellido,
        "obra": obra,
        "plan": plan,
        "afiliado": afiliado,
        "token": token,
    }
    return {
        "nodo_destino": 210,
        "subsiguiente": 0,
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

    numero_limpio = variables.get("numero_limpio")
    sender_number = "whatsapp:+" + numero_limpio if numero_limpio else None

    info = variables.get("payment_info") or {}
    amount = info.get("amount")

    def fmt_amt(a):
        try:
            return f"{float(a):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "-"

    if sender_number:
        twilio.send_whatsapp_message(MESSAGES["PAYMENT_1"].format(monto=fmt_amt(amount)), sender_number, None)
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
        {"role": "assistant", "content": MESSAGES["PAYMENT_1"].format(monto=fmt_amt(amount))},
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
    import json, re, unicodedata
    from app.Model.coverages import Coverages

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

    # Normaliza obra: quita tildes, colapsa espacios y pasa a MAYÚSCULAS
    def _deaccent_upper(s: str) -> str:
        s = ''.join(c for c in unicodedata.normalize('NFD', s or "") if unicodedata.category(c) != 'Mn')
        s = re.sub(r"\s+", " ", s).strip().upper()
        return s

    def _plan_norm(s: str) -> str:
        return re.sub(r"\s+", "", (s or "").strip()).upper() or "UNICO"

    def _fmt_amt(a):
        try:
            return f"{float(a):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "-"

    def _calc_amount(obra_norm: str, plan_norm: str):
        cv = Coverages()
        amt = None
        try:
            if obra_norm == "PARTICULAR":
                amt = cv.get_amount_by_name_and_plan("PARTICULAR", "UNICO")
                if amt is None:
                    amt = cv.get_amount_by_name("PARTICULAR")
            else:
                amt = cv.get_amount_by_name_and_plan(obra_norm, plan_norm)
                if amt is None:
                    amt = cv.get_amount_by_name(obra_norm)
        except Exception as e:
            print(f"[210] Error Coverages: {e}")
            amt = None
        return amt

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

    # Normalizador de input del usuario
    def norm(s: str) -> str:
        s = ''.join(c for c in unicodedata.normalize('NFD', s or "") if unicodedata.category(c) != 'Mn')
        s = s.lower().strip()
        s = re.sub(r"\s+", " ", s)
        return s

    user_msg = (variables.get("body") or "").strip()
    user_norm = norm(user_msg)
    is_yes = bool(re.search(r"\bsi\b|\bsí\b", user_norm))
    is_no  = bool(re.search(r"\bno\b", user_norm))

    # --- 1) SI/NO: procesar ANTES de generar confirmación para evitar loop ---
    if is_yes or is_no:
        parsed = _parse_last_confirmation(history)
        if not parsed:
            # No hay confirmación previa para leer → mandamos a admisión para evitar loops
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

        obra_norm = _deaccent_upper(obra_txt)
        plan_norm = _plan_norm(plan_txt)
        amount    = _calc_amount(obra_norm, plan_norm)

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
                            plan=(plan_norm or None),
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
                        pass
                    elif float(amount) <= 0:
                        tx.update(id=open_tx_id, amount=0.0, currency=currency, status="no_copay")
                    else:
                        tx.update(id=open_tx_id, amount=float(amount), currency=currency, status="pending")
            except Exception as e:
                print(f"[210] Error actualizando pago (SI): {e}")

            if amount is None:
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
                return {
                    "nodo_destino": 213,
                    "subsiguiente": 1,
                    "conversation_str": variables.get("conversation_str", ""),
                    "response_text": MESSAGES["WAITING"],
                    "group_id": None,
                    "question_id": None,
                    "result": "Abierta",
                }

            variables["payment_info"] = {"obra": obra_txt, "plan": plan_norm, "amount": float(amount)}
            # No usamos _210_cache; limpiamos por si quedó de versiones anteriores
            variables.pop("_210_cache", None)
            return {
                "nodo_destino": 208,
                "subsiguiente": 0,
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
            "subsiguiente": 1,
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

    obra_norm = _deaccent_upper(obra_txt)
    plan_norm = _plan_norm(plan_txt)
    amount    = _calc_amount(obra_norm, plan_norm)

    footer = (
        MESSAGES["CONFIRM_FOOTER_NO_COPAY"]
        if (amount is None or float(amount) <= 0)
        else MESSAGES["CONFIRM_FOOTER_COPAY"].format(monto=_fmt_amt(amount))
    )

    confirm_text = (
        MESSAGES["CONFIRM_HEADER"] +
        MESSAGES["CONFIRM_TPL"].format(
            nombre=nombre or "",
            apellido=apellido or "",
            obra=obra_txt,
            plan=plan_norm,
            afiliado=afiliado,
            token=token or "",
            footer=footer,
        )
    )

    history.append({"role": "assistant", "content": confirm_text})
    new_cs = json.dumps(history)

    return {
        "nodo_destino": 210,
        "subsiguiente": 1,
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
    import json, re, unicodedata

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

    # Normalizador
    def norm(s: str) -> str:
        s = ''.join(c for c in unicodedata.normalize('NFD', s or "") if unicodedata.category(c) != 'Mn')
        s = s.lower().strip()
        s = re.sub(r"\s+", " ", s)
        return s

    # >>> NUEVO: comandos solo desde BODY
    body_raw = (variables.get("body") or "")
    cmd_text = norm(body_raw)
    print(f"[211] DEBUG Body raw='{body_raw}' | norm='{cmd_text}'")  # << debug

    def retries_count():
        return sum(
            1 for m in history
            if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content") == PLEASE_IMG
        )

    def extract_kind(s: str) -> str:
        # Soporta "[Adjunto image]" o "[Adjunto image/jpeg]" o "[Adjunto application/pdf]"
        m = re.match(r"^\[Adjunto ([^\]]+)\]", s or "")
        kind = (m.group(1).strip() if m else "")
        return kind

    # --- 1) COMANDOS (solo por BODY) ---
    if cmd_text:
        if re.search(r"\both?ros\b|\botros\b", cmd_text):
            history.append({"role": "assistant", "content": OTHERS_MENU})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 211,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": OTHERS_MENU,
                "group_id": None,
                "question_id": None,
                "result": "Abierta",
            }

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

        if re.search(r"\btarjeta\b", cmd_text):
            # Para tarjeta mostramos "Acercate a admisión."
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
            history.append({"role": "assistant", "content": OK})
            new_cs = json.dumps(history)

            # pago por transferencia confirmado
            from datetime import datetime, timezone
            try:
                tx = variables.get("tx")
                contacto = variables.get("contacto")
                open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id) if (tx and contacto) else None
                paid_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
                if open_tx_id:
                    tx.update(
                        id=open_tx_id,
                        status="paid",
                        method="transfer",
                        paid_at=paid_now
                    )
            except Exception as e:
                print(f"[211] Error actualizando tx (paid/transfer): {e}")

            return {
                "nodo_destino": 213,
                "subsiguiente": 1,
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
            "subsiguiente": 1,
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
        "subsiguiente": 1,
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
        "result": "Abierta",
    }
