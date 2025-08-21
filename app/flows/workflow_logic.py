def ejecutar_nodo(nodo_id, variables):
    NODOS = {
        200: nodo_200,
        201: nodo_201,
        202: nodo_202,
        203: nodo_203,
        204: nodo_204,
        205: nodo_205,
        206: nodo_206,
    }
    return NODOS[nodo_id](variables)


#############################################################
# PX - WA B2B
#############################################################

def nodo_200(variables):
    """
    Nodo inicial de bienvenida en el flujo; Ley 25.326 
    """
    response_text = (
    "👋 Hola, soy el co-piloto de PX.\n"
    "Necesitamos tu consentimiento para tratar tus datos según la Ley 25.326.\nResponde 'Si', si aceptas. \n"

    "Más info: pacientex.com.ar/politica-privacidad")
    #print(response_text)    

    return {
        "nodo_destino": 204,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }

def nodo_204(variables):
    """
    - '1' => consentimiento afirmativo -> ir a 205
    - '0' => no/ambiguo => enviar mensajes por Twilio y cerrar
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
            "nodo_destino": 200,
            "subsiguiente": 1,
            "conversation_str": variables["conversation_str"],
            "response_text": cierre,
            "group_id": None,
            "question_id": None,
            "result": "Cerrada"
        }




def nodo_205(variables):
    """
    Nodo inicial de bienvenida en el flujo.
    """
    import app.services.brain as brain
    conversation_str = variables["conversation_str"]
    
    listen_and_speak = (
        "Podrias leer este historial y formular la pregunta en base al mismo: "+ conversation_str + "Pedile que te de mas detalle de su patologia. Por favor, no escribas nada antes ni despues de la respuesta e intentar ser breve"
    )
    
    messages = [{"role": "assistant", "content": listen_and_speak}]
    response_text = brain.ask_openai(messages)
    #print(response_text)
    

    return {
        "nodo_destino": 201,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }

def nodo_206(variables):
    """
    Pide DNI (7–8 dígitos). Normaliza, valida y controla reintentos.
    - Válido  -> salta a 205 
    - Inválido-> hasta 2 reintentos; luego informa y vuelve a 200
    """
    import re, json

    P1 = "Para continuar necesito tu DNI (solo números, sin puntos)."
    P2 = "El DNI debe tener 7 u 8 números. Probá de nuevo."
    PF = "No pude validar tu DNI. Volvamos a empezar."

    # 1) Validar
    body = (variables.get("body") or "").strip()
    dni = re.sub(r"\D+", "", body)  # normaliza: deja solo dígitos

    if dni and len(dni) in (7, 8):
        variables["dni"] = dni  # pra  guardarlo para nodos siguientes
        return {
            "nodo_destino": 205,
            "subsiguiente": 0,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta",
        }

    # 2) Cargar historial y contar cuántas veces ya pedimos/reintentamos
    try:
        history = json.loads(variables.get("conversation_str") or "[]")
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    attempts = 0
    for m in history:
        if (
            isinstance(m, dict)
            and m.get("role") == "assistant"
            and m.get("content") in (P1, P2)
        ):
            attempts += 1


    # 3) Elegir el próximo mensaje según intentos
    if attempts == 0:
        prompt = P1
        next_node = 206
        result = "Abierta"
    elif attempts == 1:
        prompt = P2
        next_node = 206
        result = "Abierta"
    else:
        prompt = PF
        next_node = 200
        result = "Cerrada"

    # 4) Guardar el prompt en el historial y responder
    history.append({"role": "assistant", "content": prompt})
    new_cs = json.dumps(history)

    return {
        "nodo_destino": next_node,
        "subsiguiente": 1,
        "conversation_str": new_cs,
        "response_text": prompt,
        "group_id": None,
        "question_id": None,
        "result": result,
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

    tx = variables["tx"]
    ctt = variables["ctt"]
    ev = variables["ev"]
    numero_limpio = variables["numero_limpio"]

    sender_number = "whatsapp:+" + numero_limpio
    twilio.send_whatsapp_message("Estoy pensando, dame unos segundos...", sender_number, None)

    conversation_history = variables["conversation_history"]
    #print(conversation_history)

    contacto = ctt.get_by_phone(numero_limpio)
    event_id = ctt.get_event_id_by_phone(numero_limpio)
    mensaje_reporte = ev.get_reporte_by_event_id(event_id)


    conversation_history.append({
        "role": "system",
        "content": mensaje_reporte
    })

    response_text = brain.ask_openai(conversation_history)

    return {
        "nodo_destino": 200,
        "subsiguiente": 1,
        "conversation_str": variables["conversation_str"],
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada"
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
        "Contestame UNICAMENTE con la pregunta; sin números y sin comillas. Utilizá 1 emoji para hacer más proxima la pregunta."
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