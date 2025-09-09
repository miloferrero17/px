def ejecutar_nodo(nodo_id, variables):
    NODOS = {
        201: nodo_201,
        202: nodo_202,
        203: nodo_203,
        204: nodo_204,
        205: nodo_205,
        206: nodo_206,
        207: nodo_207,  # Pedir credencial o detectar "Particular"
        208: nodo_208,  # Pago unificado (copago o particular)
        209: nodo_209,  # Confirmar datos extraídos (SI/NO)
        211: nodo_211,  # Recibir comprobante
        212: nodo_212,  # Derivar a humano
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
    - Si es válido, guarda en contacts.dni y avanza a 205.
    """
    import re, json

    # Mensajes
    REASK = "El DNI debe tener 7 u 8 números. Por favor, volvé a ingresarlo."
    FAIL  = "No pude validar tu DNI. Cerramos la consulta por ahora."

    # 1) Normalizar y validar lo que escribió el usuario
    body = (variables.get("body") or "").strip()
    dni = re.sub(r"\D+", "", body)  # deja solo dígitos

    if dni and 7 <= len(dni) <= 8:
        # Éxito: guardamos para el siguiente nodo y persistimos en contacts.dni
        variables["dni"] = dni
        ctt = variables.get("ctt")            # Contacts()
        contacto = variables.get("contacto")  # registro de contacto actual

        try:
            # Actualiza SOLO el campo dni sin tocar name/phone/event_id
            ctt.set_dni(contact_id=contacto.contact_id, dni=dni)
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

def nodo_207(variables):
    """
    207 - Pedir credencial O detectar 'particular' y saltar a pago.
    Reglas:
      - Si el usuario escribe 'particular' (solo singular, case-insensitive): ir directo a 208.
      - Primera vez: enviar ASK y esperar.
      - Si llega adjunto/texto: intentar extraer {obra, afiliado, token}.
        * Si falta cualquiera de los 3 -> RETRY (reenvíe la captura).
        * Si están los 3 -> mostrar confirmación y pasar a 209.
      - Máx 2 RETRY. Al 3° -> 212 (humano).
    """
    import json, re, unicodedata
    import app.services.brain as brain

    ASK = "Enviá una foto o PDF de tu credencial de obra social o prepaga. Si no tenés, escribí: Particular."
    RETRY = "No pude tomar bien los datos. Reintentemos: enviá de nuevo la credencial o escribí Particular."
    CONFIRM_TPL = "Cobertura: {obra}\nAfiliado: {afiliado}\nToken: {token}\n\n¿Está bien? SI/NO"
    TO_HUMAN = "Acercate a admisión."

    # Historial seguro
    conversation_str = variables.get("conversation_str", "")
    try:
        history = json.loads(conversation_str) if conversation_str else []
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    # Helpers locales
    def norm(s: str) -> str:
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = s.lower().strip()
        s = re.sub(r"\s+", " ", s)
        return s

    def count_occurrences(hist, text):
        return sum(1 for m in hist if isinstance(m, dict) and m.get("role")=="assistant" and m.get("content")==text)

    # Mensaje actual (si vino vacío por adjunto puro, igual extraemos de conversation_str)
    user_msg = (variables.get("body") or "").strip()
    user_norm = norm(user_msg)

    # 1) Prioridad: 'particular' (solo singular)
    if re.search(r"\bparticular\b", user_norm):
        variables["coverage_data"] = {"obra": "Particular", "afiliado": "", "token": ""}
        return {
            "nodo_destino": 208,
            "subsiguiente": 0,
            "conversation_str": variables.get("conversation_str",""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }

    # 2) Primera vez → pedir credencial / Particular
    asked_once = any(isinstance(m, dict) and m.get("role")=="assistant" and m.get("content")==ASK for m in history)
    if not asked_once:
        history.append({"role":"assistant","content":ASK})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": ASK,
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }

    # 3) Intentar extraer {obra, afiliado, token} del historial completo
    extract_prompt = [{
        "role": "system",
        "content": (
            "De la conversación del paciente, extraé si es posible:\n"
            "- Cobertura (obra social o prepaga)\n"
            "- Número de afiliado\n"
            "- Token/código adicional (si existe)\n"
            "Respondé SOLO JSON con claves: obra, afiliado, token. Si no hay datos, usá \"\"."
        )
    }, {
        "role": "user",
        "content": variables.get("conversation_str", "")
    }]

    try:
        raw = brain.ask_openai(extract_prompt)
    except Exception as e:
        raw = '{"obra":"","afiliado":"","token":""}'
        print(f"[207] Error LLM: {e}")

    try:
        data = json.loads(raw)
    except Exception:
        data = {"obra":"", "afiliado":"", "token":""}

    extracted_obra = (data.get("obra") or "").strip()
    extracted_afiliado = (data.get("afiliado") or "").strip()
    extracted_token = (data.get("token") or "").strip()

    # 3.b) Regla estricta: si falta ALGUNO de los 3 campos -> RETRY (no corrección manual)
    if not extracted_obra or not extracted_afiliado or not extracted_token:
        retries = count_occurrences(history, RETRY)
        # limpiar draft viejo si lo hubiera, para evitar datos obsoletos
        if "coverage_draft" in variables:
            try:
                del variables["coverage_draft"]
            except Exception:
                pass
        if retries >= 2:
            history.append({"role":"assistant","content": TO_HUMAN})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada"
            }
        history.append({"role":"assistant","content": RETRY})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": RETRY,
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }

    # 4) Confirmación completa → pasar a 209
    confirm = CONFIRM_TPL.format(
        obra = extracted_obra,
        afiliado = extracted_afiliado,
        token = extracted_token
    )
    history.append({"role":"assistant","content": confirm})
    variables["coverage_draft"] = {
        "obra": extracted_obra,
        "afiliado": extracted_afiliado,
        "token": extracted_token
    }
    new_cs = json.dumps(history)

    return {
        "nodo_destino": 209,   # solo SI/NO
        "subsiguiente": 1,
        "conversation_str": new_cs,
        "response_text": confirm,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }


def nodo_209(variables):
    """
    209 - Confirmar cobertura extraída: SI/NO.
      - SI: setea variables['coverage_data'] y va a 208 (pago).
        (Solo si obra/afiliado/token están completos; si faltara algo, pedir reenviar captura.)
      - NO: reintenta (volviendo a 207) hasta 2 veces; luego 212.
      - Si escribe 'particular' (singular), va directo a 208.
      - Cualquier otra cosa: pedir SI/NO o 'Particular'.
    """
    import json, re, unicodedata

    RETRY = "No pude tomar bien los datos. Reintentemos: enviá de nuevo la credencial o escribí Particular."
    CONFIRM_HDR = "Cobertura:"
    TO_HUMAN = "Acercate a admisión."
    ASK_YN = "Por favor, respondé SI o NO, o escribí Particular."

    # Historial
    conversation_str = variables.get("conversation_str", "")
    try:
        history = json.loads(conversation_str) if conversation_str else []
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    # Helpers locales
    def norm(s: str) -> str:
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = s.lower().strip()
        s = re.sub(r"\s+", " ", s)
        return s

    def count_occurrences(hist, text):
        return sum(1 for m in hist if isinstance(m, dict) and m.get("role")=="assistant" and m.get("content")==text)

    user_msg = (variables.get("body") or "").strip()
    user_norm = norm(user_msg)

    # 0) Particular (solo singular) → pago
    if re.search(r"\bparticular\b", user_norm):
        variables["coverage_data"] = {"obra": "Particular", "afiliado": "", "token": ""}
        return {
            "nodo_destino": 208,
            "subsiguiente": 0,
            "conversation_str": variables.get("conversation_str",""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }

    # 1) NO → reintento o derivación
    if re.search(r"\bno\b", user_norm):
        retries = count_occurrences(history, RETRY)
        # limpiar draft para evitar confirmaciones viejas
        if "coverage_draft" in variables:
            try:
                del variables["coverage_draft"]
            except Exception:
                pass
        if retries >= 2:
            history.append({"role":"assistant","content": TO_HUMAN})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada"
            }
        history.append({"role":"assistant","content": RETRY})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 207,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": RETRY,
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }

    # 2) SI → tomar confirmación previa o draft
    if re.search(r"\bsi\b|\bsí\b", user_norm):
        obra = afiliado = token = ""
        for m in reversed(history):
            if isinstance(m, dict) and m.get("role")=="assistant":
                txt = (m.get("content") or "")
                if txt.startswith(CONFIRM_HDR) and "¿Está bien? SI/NO" in txt:
                    lines = txt.splitlines()
                    for ln in lines:
                        if ln.startswith("Cobertura:"):
                            obra = ln.split(":",1)[1].strip()
                        elif ln.startswith("Afiliado:"):
                            afiliado = ln.split(":",1)[1].strip()
                        elif ln.startswith("Token:"):
                            token = ln.split(":",1)[1].strip()
                    break

        if not (obra and afiliado and token):
            draft = variables.get("coverage_draft") or {}
            obra = obra or draft.get("obra","")
            afiliado = afiliado or draft.get("afiliado","")
            token = token or draft.get("token","")

        # Validación estricta: deben estar los 3 campos
        if not obra or not afiliado or not token:
            # no avanzamos a pago; pedimos reenviar captura
            retries = count_occurrences(history, RETRY)
            if "coverage_draft" in variables:
                try:
                    del variables["coverage_draft"]
                except Exception:
                    pass
            if retries >= 2:
                history.append({"role":"assistant","content": TO_HUMAN})
                new_cs = json.dumps(history)
                return {
                    "nodo_destino": 212,
                    "subsiguiente": 1,
                    "conversation_str": new_cs,
                    "response_text": TO_HUMAN,
                    "group_id": None,
                    "question_id": None,
                    "result": "Cerrada"
                }
            history.append({"role":"assistant","content": RETRY})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 207,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": RETRY,
                "group_id": None,
                "question_id": None,
                "result": "Abierta"
            }

        # OK: confirmar y avanzar a pago
        variables["coverage_data"] = {"obra": obra, "afiliado": afiliado, "token": token}
        return {
            "nodo_destino": 208,
            "subsiguiente": 0,
            "conversation_str": variables.get("conversation_str",""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }

    # 3) Otro texto → pedir formato correcto
    history.append({"role":"assistant","content": ASK_YN})
    new_cs = json.dumps(history)
    return {
        "nodo_destino": 209,
        "subsiguiente": 1,
        "conversation_str": new_cs,
        "response_text": ASK_YN,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }


def nodo_208(variables):
    """
    Pago unificado (particular o copago).
    Requiere variables['coverage_data'] = {'obra','afiliado','token'} desde 207.
    """
    from app.Model.coverages import Coverages
    import json

    ALIAS = "Pacientex.Emergencia"
    NO_COPAY = "Cobertura registrada: no hay copago."
    TO_HUMAN = "Acercate a admisión."
    ASK_RECEIPT = (
        "El monto es ARS {monto}.\n"
        "Alias: {alias}\n\n"
        "Cuando hagas la transferencia, enviá una captura del comprobante.\n"
        "Si vas a pagar en efectivo en admisión, escribí: Efectivo."
    )

    cov = variables.get("coverage_data") or {}
    obra = (cov.get("obra") or "").strip()
    afiliado = (cov.get("afiliado") or "").strip()
    token = (cov.get("token") or "").strip()

    cv = Coverages()

    # Monto a cobrar
    if obra.lower() == "particular":
        amount = cv.get_amount_by_name("Particular")
        if amount is None:
            # No tenemos el precio particular -> derivar
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": variables.get("conversation_str",""),
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada"
            }
    else:
        amount = cv.get_amount_by_name(obra)
        if amount is None:
            # Obra social desconocida -> derivar
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": variables.get("conversation_str",""),
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada"
            }
        if float(amount) == 0.0:
            # Sin copago
            return {
                "nodo_destino": 207,  # irrelevante, cerramos
                "subsiguiente": 1,
                "conversation_str": variables.get("conversation_str",""),
                "response_text": NO_COPAY,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada"
            }

    # Hay que cobrar (particular o copago > 0)
    msg = ASK_RECEIPT.format(monto=f"{float(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X","."), alias=ALIAS)

    # Añadimos el prompt al historial y pedimos comprobante
    try:
        history = json.loads(variables.get("conversation_str") or "[]")
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []
    history.append({"role": "assistant", "content": msg})
    new_cs = json.dumps(history)

    # Guardamos amount y obra por si 211 quiere mostrarlos
    variables["payment_info"] = {"obra": obra or "Particular", "amount": float(amount)}

    return {
        "nodo_destino": 211,   # recibir comprobante
        "subsiguiente": 1,
        "conversation_str": new_cs,
        "response_text": msg,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }
def nodo_211(variables):
    """
    Recibe comprobante de pago.
    Reglas:
      - Válidos: [Adjunto image] o [Adjunto application/pdf] -> OK y Cerrar.
      - Texto clave: si el usuario escribe 'efectivo'  -> derivar a admisión (212) y Cerrar.
      - Inválidos: audio, video, otros tipos, o texto sin adjunto ni 'efectivo' -> pedir reenviar (hasta MAX_RETRIES).
      - Al superar MAX_RETRIES -> Derivar a admisión (212) y Cerrar.
    """
    import json, re, unicodedata

    OK = "✅ Recibimos tu comprobante. "
    PLEASE_IMG = "Por favor, reenviá el comprobante como imagen o PDF."
    TO_HUMAN = "Acercate a admisión."
    CASH_MSG = "Perfecto, abonás en efectivo. Acercate a admisión."
    MAX_RETRIES = 2  # cantidad de reintentos permitidos

    # Historial seguro
    try:
        history = json.loads(variables.get("conversation_str") or "[]")
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    # Último mensaje del usuario (handler guarda adjuntos como "[Adjunto <tipo>] ...")
    last_user = ""
    for m in reversed(history):
        if isinstance(m, dict) and m.get("role") == "user":
            last_user = (m.get("content") or "").strip()
            break

    # Normalizador simple (para detectar 'efectivo')
    def norm(s: str) -> str:
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = s.lower().strip()
        s = re.sub(r"\s+", " ", s)
        return s

    # Mensaje textual actual (puede venir por variables['body'] o desde historial)
    text_current = (variables.get("body") or "").strip() or last_user
    text_norm = norm(text_current)

    # Contar reintentos previos (veces que ya pedimos PLEASE_IMG)
    def count_retries():
        return sum(
            1 for m in history
            if isinstance(m, dict)
            and m.get("role") == "assistant"
            and m.get("content") == PLEASE_IMG
        )

    # Extraer tipo de adjunto del formato "[Adjunto <tipo>]"
    def extract_kind(s: str) -> str:
        m = re.match(r"^\[Adjunto ([^\]]+)\]", s or "")
        return (m.group(1).strip() if m else "")

    # PRIORIDAD 1: si el usuario indica 'efectivo' en cualquier momento -> admisión
    if re.search(r"\befectivo\b", text_norm):
        history.append({"role": "assistant", "content": CASH_MSG})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 212,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": CASH_MSG,
            "group_id": None,
            "question_id": None,
            "result": "Cerrada"
        }

    # 1) Si vino adjunto, validar tipo
    if last_user.startswith("[Adjunto "):
        kind = extract_kind(last_user)  # "image", "application/pdf", "audio", "video", etc.

        if kind == "image" or kind == "application/pdf":
            # Válido -> OK y cerrar
            history.append({"role": "assistant", "content": OK})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 211,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": OK,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada"
            }

        # Adjuntos inválidos (audio, video, otros)
        retries = count_retries()
        if retries >= MAX_RETRIES:
            history.append({"role": "assistant", "content": TO_HUMAN})
            new_cs = json.dumps(history)
            return {
                "nodo_destino": 212,
                "subsiguiente": 1,
                "conversation_str": new_cs,
                "response_text": TO_HUMAN,
                "group_id": None,
                "question_id": None,
                "result": "Cerrada"
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
            "result": "Abierta"
        }

    # 2) No vino adjunto (texto, stickers, etc.) -> inválido (salvo 'efectivo' ya tratado)
    retries = count_retries()
    if retries >= MAX_RETRIES:
        history.append({"role": "assistant", "content": TO_HUMAN})
        new_cs = json.dumps(history)
        return {
            "nodo_destino": 212,
            "subsiguiente": 1,
            "conversation_str": new_cs,
            "response_text": TO_HUMAN,
            "group_id": None,
            "question_id": None,
            "result": "Cerrada"
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
        "result": "Abierta"
    }

def nodo_212(variables):
    """
    Derivación a humano.
    """
    msg = "Acercate a admisión."
    return {
        "nodo_destino": 212,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str",""),
        "response_text": msg,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada"
    }
