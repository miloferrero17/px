''' Codificacion de diagramas de flujo:
0XX - PX - Chat
1XX - Hunitro
''' 

def ejecutar_nodo(nodo_id, variables):
    NODOS = {
        32: nodo_32,
        33: nodo_33,
        #34: nodo_34,
        #35: nodo_35,
        36: nodo_36,
        37: nodo_37,
        38: nodo_38,
        39: nodo_39,
        100: nodo_100,
        101: nodo_101,
        #102: nodo_102,
    }
    return NODOS[nodo_id](variables)



def nodo_32(variables):
    """
    Nodo que decide si el paciente necesita intervención médica urgente.
    Usa el historial de conversación para preguntarle a OpenAI.
    """
    import app.services.brain as brain
    import json

    #print(variables["conversation_str"])
    tx = variables["tx"]
    ctt = variables["ctt"]
    numero_limpio = variables["numero_limpio"]

    contacto = ctt.get_by_phone(numero_limpio)
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)
    conversation_history = json.loads(conversation_str) if conversation_str else []

    mensaje_urgencia = (
        "En base únicamente a la respuesta: " + variables["body"] +
        "¿El caso requiere intervencion medica humana urgente? "
        "Responde unicamente con los numeros: 1 si la requiere o 0 si necesitás hacer más preguntas para entender mejor la situacion"
    )

    mensaje_urgencia_dic = [{
        "role": "system",
        "content":mensaje_urgencia
    }]
    #print(mensaje_urgencia_dic)

    result1 = brain.ask_openai(mensaje_urgencia_dic)
    #print(result1)

    if result1.strip() == "1":
        nodo_destino = 37
    else:
        nodo_destino = 33

    print(nodo_destino)
    return {
        "nodo_destino": nodo_destino,
        "subsiguiente": 0,
        "conversation_str": conversation_str,
        "response_text": "",
        "group_id": None,
        "question_id": None,
        "result": "Abierta"

    }



def nodo_33(variables):
    """
    Nodo inicial de bienvenida en el flujo del Hospital Mater Dei.
    """
    import app.services.brain as brain
   
    listen_and_speak = (
        "Podrias escuchar este mensaje: "+ variables["body"] + "y responder con esta intencion de: - Saludarlo brevemente de una forma empatica, -presentarte como /el co-piloto del Hospital Mater Dei/ y - pedirle que te cuente más de su patologia"
    )
    
    messages = [{"role": "user", "content": listen_and_speak}]
    response_text = brain.ask_openai(messages)
    
    
    return {
        "nodo_destino": 36,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }

'''
def nodo_34(variables):
    """
    Nodo de pregunta abierta al paciente para que detalle su situación.
    """
    response_text = "¿Podrias profundizar un poco más?"
    return {
        "nodo_destino": 35,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }
'''

'''
def nodo_35(variables):
    """
    Nodo que decide si tiene sentido pedir una foto al paciente.
    Usa GPT para analizar el contexto de la conversación.
    """
    import app.services.brain as brain
    import builtins

    foto_prompt = (
        "Basado en esta conversacion: " + variables["conversation_str"] +
        " ¿Crees que una foto de la zona afectada o un pdf medico complementaria el diagnostico?"
        "Respondeme con numeros. 0 por si o 1 por no"
    )
    print(foto_prompt)

    messages = [{"role": "system", "content": foto_prompt}]
    result_str = brain.ask_openai(messages)
    print(result_str)


    if result_str == "0":
        response_text = ""
        nodo_destino = 38
        subsiguiente = 0
    else:
        print("else")
        response_text = ""
        nodo_destino = 36
        subsiguiente = 0

    return {
        "nodo_destino": nodo_destino,
        "subsiguiente": variables.get(subsiguiente),
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }
'''

def nodo_36(variables):
    """
    Nodo que decide si el paciente necesita intervención médica urgente.
    Usa el historial de conversación para preguntarle a OpenAI.
    """
    import app.services.brain as brain
    import json

    tx = variables["tx"]
    ctt = variables["ctt"]
    numero_limpio = variables["numero_limpio"]

    contacto = ctt.get_by_phone(numero_limpio)
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)
    conversation_history = json.loads(conversation_str) if conversation_str else []

    mensaje_urgencia = (
        "En base únicamente a la respuesta: " + variables["body"] +
        "¿El caso requiere intervencion medica humana urgente? "
        "Responde solo con: 1 si la requiere o 0 si necesitás hacer más preguntas para entender mejor la situacion"
    )

    mensaje_urgencia_dic = [{
        "role": "system",
        "content":mensaje_urgencia
    }]
    print(mensaje_urgencia_dic)

    result1 = brain.ask_openai(mensaje_urgencia_dic)
    print(result1)

    if result1.strip() == "1":
        nodo_destino = 37
    else:
        nodo_destino = 39

    return {
        "nodo_destino": nodo_destino,
        "subsiguiente": 0,
        "conversation_str": conversation_str,
        "response_text": "",
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }



def nodo_37(variables):
    """
    Nodo de generación de reporte médico final usando el historial de conversación.
    Marca la sesión como 'Cerrada' y redirige al nodo de reinicio (33).
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

    response_text = brain.ask_openai(conversation_history, model="gpt-4.1-2025-04-14")

    return {
        "nodo_destino": 32,
        "subsiguiente": 1,
        "conversation_str": json.dumps(conversation_history),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada"
    }


def nodo_38(variables):
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
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)
    conversation_history = json.loads(conversation_str) if conversation_str else []

    event_id = ctt.get_event_id_by_phone(numero_limpio)
    question_id = msj.get_penultimate_question_id_by_phone(numero_limpio)
    question_id = question_id + 1 if question_id is not None else 1

    max_preguntas = builtins.int(ev.get_cant_preguntas_by_event_id(event_id))
    max_preguntas_str = builtins.str(max_preguntas)
    question_id_str = builtins.str(question_id)

    if question_id == 1:
        mensaje_intro = "Te voy a hacer " + max_preguntas_str + " preguntas."
        twilio.send_whatsapp_message(mensaje_intro, sender_number, None)

    if question_id > max_preguntas:
        return {
            "nodo_destino": 37,
            "subsiguiente": 0,
            "conversation_str": conversation_str,
            "response_text": "Fin de las preguntas.",
            "group_id": None,
            "question_id": question_id,
            "result": "Abierta"
        }

    mensaje_def_triage = (
        "Vas a hacerle " + max_preguntas_str + " preguntas que estés seguro que te entienda a un paciente "
        "con el objetivo de diagnosticarlo y darle un consejo sobre qué hacer.\n"
        "En cada iteración debes tomar como historico esto : " + conversation_str + ",\n"
        "y en base a eso, debes por un lado dar un comentario sobre la última pregunta contestada y por otro lado  diseñar la mejor próxima pregunta utilizando emojis.\n"
        "Contestame UNICAMENTE con la pregunta; sin números y sin comillas."
    )
    print(mensaje_def_triage)


    conversation_history.append({
        "role": "assistant",
        "content": mensaje_def_triage
    })

    result = brain.ask_openai(conversation_history)
    response_text = question_id_str + "/" + max_preguntas_str + " - " + result

    return {
        "nodo_destino": 38,
        "subsiguiente": 1,
        "conversation_str": json.dumps(conversation_history),
        "response_text": response_text,
        "group_id": None,
        "question_id": question_id,
        "result": "Abierta"
    }

def nodo_39(variables):
    """
    Nodo de pregunta de la foto
    """
    response_text = "¿Me compartirias si lo crees necesario un documento o una foto que me ayuden a mejorar mi diagnostico?"
    return {
        "nodo_destino": 38,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
    }



def nodo_100(variables):
    """
    Nodo inicial de bienvenida en el flujo del Hospital Mater Dei.
    """
    import app.services.brain as brain
   
    listen_and_speak = (
        "Podrias escuchar este mensaje: "+ variables["body"] + "darle la bienvenida al usuario a  Hunitro IA y preguntarle la siguiente pregunta: ¿Sos monotributista o tenes una sociedad?"
    )
    
    messages = [{"role": "assistant", "content": listen_and_speak}]
    
    response_text = brain.ask_openai(messages)
    print(response_text)
    group_id = 12
    return {
        "nodo_destino": 101,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": response_text,
        "group_id": group_id,
        "question_id": None,
        "result": "Abierta"
    }


def nodo_101(variables):
    """
    Nodo "Sherlock" para Hunitro: hace un interrogatorio según el grupo de preguntas.
    """
    import app.services.twilio_service as twilio
    from app.Model.questions import Questions
    from app.Model.messages import Messages

    qs = Questions()
    msj = Messages()
    numero = variables["numero_limpio"]
    ultimo = msj.get_penultimate_by_phone(numero)
    print(ultimo)


    # Obtener ids de preguntas del grupo
    question_ids = qs.get_question_ids_by_group_id(ultimo.group_id)
    #print(question_ids)
    # Obtener el último mensaje del usuario
    #ultimo = msj.get_penultimate_by_phone(numero)
    last_qid = ultimo.question_id if ultimo else 0
    print(last_qid)

    if last_qid is None:
        # Primera pregunta
        next_qid = question_ids[0]
    else:
        # Siguiente pregunta o fin
        nxt = qs.get_next_question_id(last_qid)
        if nxt == "No existe":
            # Fin del interrogatorio
            return {
                "nodo_destino": 103,
                "subsiguiente": 0,
                "conversation_str": variables.get("conversation_str", ""),
                "response_text": "Fin del interrogatorio.",
                "group_id": variables["group_id"],
                "question_id": None,
                "result": "Abierta"
            }
        next_qid = nxt

    # Obtener texto de la pregunta
    pregunta = qs.get_question_name_by_id(next_qid)
    sender = "whatsapp:+" + numero
    # Enviar la pregunta
    #twilio.send_whatsapp_message(pregunta, sender, None)

    return {
        "nodo_destino": 101,
        "subsiguiente": 1,
        "conversation_str": variables.get("conversation_str", ""),
        "response_text": pregunta,
        "group_id": variables["group_id"],
        "question_id": next_qid,
        "result": "Abierta"
    }
