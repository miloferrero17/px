''' Codificacion de diagramas de flujo:
0XX - PX - WA
1XX - Hunitro
2XX - PX - WA V2
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
        40: nodo_40,
        100: nodo_100,
        #101: nodo_101,
        #102: nodo_102,
        103: nodo_103,
        104: nodo_104,
        200: nodo_200,
        #201: nodo_201,
        203: nodo_203
    }
    return NODOS[nodo_id](variables)











#############################################################
# PX - WA
#############################################################

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
        "Podrias escuchar este mensaje: "+ variables["body"] + "y responder con esta intencion de: - Saludarlo brevemente de una forma empatica, -presentarte como /el co-piloto del PX/ y - pedirle que te cuente más de su patologia"
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
        "nodo_destino": 40,
        "subsiguiente": 1,
        "conversation_str": json.dumps(conversation_history),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"
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
        mensaje_intro = "Te voy a hacer " + max_preguntas_str + " preguntas para entender mejor que te anda pasando ."
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

'''
def nodo_40(variables):
    """
    Nodo que genera un listado de estudios médicos sugeridos para el paciente
    basándose en el historial de conversación. Envía el listado por WhatsApp    
    """
    import app.services.brain as brain
    import app.services.twilio_service as twilio
    import json

    tx = variables["tx"]
    ctt = variables["ctt"]
    numero_limpio = variables["numero_limpio"]
    sender_number = "whatsapp:+" + numero_limpio

    twilio.send_whatsapp_message("Un momento, estoy revisando qué estudios podrías necesitar...", sender_number, None)

    conversation_history = variables["conversation_history"]

    # Agrego una instrucción específica para que el modelo proponga estudios
    conversation_history.append({
        "role": "system",
        "content": "Por favor, generá una lista de estudios médicos mandatorios que el paciente debería realizar antes de ver al médico, en base al historial anterior. Hay dos posibles respuestas: 1) Listado de estudios separado por enter y comennzando con - sin introduccion ni desenlace listos para ser escritos en una receta o 2) el numero 0 si no hace falta que se haga ningun estudio antes de ver al medico."
    })

    result3 = brain.ask_openai(conversation_history, model="gpt-4.1-2025-04-14")
    
    return {
        "nodo_destino": 32,
        "subsiguiente": 1,
        "conversation_str": json.dumps(conversation_history),
        "response_text": result3,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada"
    }

'''


def nodo_40(variables):
    """
    Nodo que genera un listado de estudios médicos sugeridos para el paciente,
    y si corresponde, genera un PDF de receta médica con esos estudios.
    """
    import app.services.brain as brain
    import app.services.twilio_service as twilio
    import json
    from datetime import datetime
    from app.pdf_builder.generate_pdf import generate_recipe_pdf_from_data  # ✅ Usamos solo esta función
    import app.services.uploader as uploader
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


    tx = variables["tx"]
    ctt = variables["ctt"]
    numero_limpio = variables["numero_limpio"]
    sender_number = "whatsapp:+" + numero_limpio

    twilio.send_whatsapp_message("Un momento, estoy escribiendo el detalle de mi analisis para que lo puedas leer ...", sender_number, None)

    conversation_history = variables["conversation_history"]

    conversation_history.append({
        "role": "assistant",
        "content": ("Por favor genera un reporte pormenorizado para que el usuario pueda ver con mayor detalle el analisis que hizo el medico con la logica de los posibles diagnosticos, la lógica que te hizo llegar a ellos y un detalle pormenorizado de que sigue. Hacelo de 1 carilla y media A4"
        )
    })

    estudios_raw = brain.ask_openai(conversation_history, model="gpt-4.1-2025-04-14")


    if estudios_raw.strip() == "0":
        return {
            "nodo_destino": 32,
            "subsiguiente": 1,
            "conversation_str": json.dumps(conversation_history),
            "response_text": "Chau",
            "group_id": None,
            "question_id": None,
            "result": "Cerrada"
        }

    estudios_list = [line.strip("- ").strip() for line in estudios_raw.strip().split("\n") if line.strip()]

    doctor = {
        "nombre": "AGUSTIN FERNANDEZ VIÑA",
        "especialidad": "MÉDICO ESPECIALISTA EN DIAGNÓSTICO",
        "matricula": "140.100",
        "email": "agustinfvinadxi@gmail.com",
        "logo_url": "https://web.innovamed.com.ar/hubfs/LOGO%20A%20COLOR%20SOLO-2.png"
    }
    paciente = {
        "nombre": "Julian Patricio Ferrero",
        "dni": "601.904.816",
        "sexo": "M",
        "fecha_nac": "09/06/1979",
        "obra_social": "Vida Cámara",
        "plan": "AAA",
        "credencial": "601.904.816"
    }

    diagnostico = "Se solicita realización de los estudios indicados para evaluación médica."
    fecha = datetime.now().strftime("%d/%m/%Y")
    output_pdf = f"/tmp/receta_estudios_{numero_limpio}_{timestamp}.pdf"

    generate_recipe_pdf_from_data(
        doctor=doctor,
        paciente=paciente,
        rp=estudios_list,
        diagnostico=diagnostico,
        fecha=fecha,
        output_pdf=output_pdf
    )


    url = uploader.subir_a_s3(archivo_local=output_pdf, nombre_en_s3=f"recetas/receta_estudios_{numero_limpio}_{timestamp}.pdf")
    #twilio.send_whatsapp_message("Tus recetas:", sender_number, url)


    return {
        "nodo_destino": 32,
        "subsiguiente": 1,
        "conversation_str": json.dumps(conversation_history),
        "response_text": "Mi criterio médico",
        "pdf_path": output_pdf,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada",
        "url": url
    }


















#############################################################
# HUNITRO
#############################################################

#############################################################
# Hunitro - Flujo de Relevamiento de Producto
# Codificación: 1XX
#############################################################

def nodo_100(variables):
    """
    Nodo de preguntas de Etapa 1: Producto.
    """
    import app.services.brain as brain
    tx = variables["tx"]
    ctt = variables["ctt"]
    ev = variables["ev"]
    numero_limpio = variables["numero_limpio"]
    contacto = ctt.get_by_phone(numero_limpio)    
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)
    conversation_history = variables["conversation_history"]

    assistant_text = ev.get_assistant_by_event_id(1)

    if not assistant_text:
        raise ValueError("El texto del asistente es None. Verificá ev.get_assistant_by_event_id(2).")

    conversation_history.append({
        "role": "assistant",
        "content": assistant_text
    })

    print(conversation_history)
    response_text = brain.ask_openai(conversation_history)
    print(response_text)
    # Separar por el punto y coma
    partes = response_text.split(';')

    if len(partes) != 2:
        print(f"⚠️ Respuesta inválida: {response_text}")
        response_text = response_text.strip()
        valor = 0  # seguir preguntando
    else:
        response_text = partes[0].strip()
        valor = int(partes[1].strip())
    # Mostrar resultados

    print("Pregunta:", response_text)
    print("Valor:", valor)
    
    if valor == 0:
        return {
            "nodo_destino": 100,
            "subsiguiente": 1,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": response_text,
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }
    else:
        return {
            "nodo_destino": 103,
            "subsiguiente": 0,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }
def nodo_103(variables):
    """
    Nodo de generación de reporte de producto.
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
        "content": "Hace unicamente el Reporte 1 - Producto: " + mensaje_reporte
    })

    response_text = brain.ask_openai(conversation_history)

    return {
        "nodo_destino": 104,
        "subsiguiente": 1,
        "conversation_str": json.dumps(conversation_history),
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada"
    }


def nodo_104(variables):
    """
    Nodo de preguntas de Etapa 2: Planificación.
    """
    import app.services.brain as brain
    tx = variables["tx"]
    ctt = variables["ctt"]
    ev = variables["ev"]
    numero_limpio = variables["numero_limpio"]
    contacto = ctt.get_by_phone(numero_limpio)    
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)
    conversation_history = variables["conversation_history"]

    assistant_text = "Encara la Etapa 2" + ev.get_assistant_by_event_id(1)
    print(assistant_text)

    conversation_history.append({
        "role": "assistant",
        "content": assistant_text
    })

    print(conversation_history)
    response_text = brain.ask_openai(conversation_history)
    print(response_text)
    # Separar por el punto y coma
    partes = response_text.split(';')

    if len(partes) != 2:
        print(f"⚠️ Respuesta inválida: {response_text}")
        response_text = response_text.strip()
        valor = 0  # seguir preguntando
    else:
        response_text = partes[0].strip()
        valor = int(partes[1].strip())
    # Mostrar resultados

    print("Pregunta:", response_text)
    print("Valor:", valor)
    
    if valor == 0:
        return {
            "nodo_destino": 100,
            "subsiguiente": 1,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": response_text,
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }
    else:
        return {
            "nodo_destino": 103,
            "subsiguiente": 0,
            "conversation_str": variables.get("conversation_str", ""),
            "response_text": "",
            "group_id": None,
            "question_id": None,
            "result": "Abierta"
        }

'''
def nodo_102(variables):
    """
    Nodo que le pide la hoja de producto.
    """
    import app.services.brain as brain
    import json
    import app.services.brain as brain
    tx = variables["tx"]
    ctt = variables["ctt"]
    numero_limpio = variables["numero_limpio"]
    contacto = ctt.get_by_phone(numero_limpio)    
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)


    listen_and_speak = ("Podrias escuchar este mensaje: "+ variables["body"] + "y teniendo en cuenta este historial" + conversation_str + "hacerle la mejor proxima pregunta ")
    messages = [{"role": "user", "content": listen_and_speak}]
    sabe_que_importar = brain.ask_openai(messages)
    print(sabe_que_importar)
    
    nodo_destino = 104
         
    
    print(nodo_destino)
    return {
        "nodo_destino": nodo_destino,
        "subsiguiente": 0,
        "conversation_str": conversation_str,
        "response_text": sabe_que_importar,
        "group_id": None,
        "question_id": None,
        "result": "Abierta"

    }


def nodo_104(variables):
    """
    Nodo que decide si el usuario compartio una hoja de producto.
    """
    import app.services.brain as brain
    import json
    import app.services.brain as brain
    tx = variables["tx"]
    ctt = variables["ctt"]
    numero_limpio = variables["numero_limpio"]
    contacto = ctt.get_by_phone(numero_limpio)    
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)


    listen_and_speak = ("Podrias escuchar este mensaje: "+ variables["body"] + "y teniendo en cuenta este historial" + conversation_str + "ver si el historial contiene una hoja de producto o similar; en caso positivo responder 1 y en caso negativo 0")
    messages = [{"role": "user", "content": listen_and_speak}]
    attach = brain.ask_openai(messages)
    print(attach)
    
    if attach == "1":
        response_text = "Attached"

    else:
        response_text = "Non Attached"    

    nodo_destino = 100
    
    #   chequear si todas las preguntas en question_id estan contestadas, caso contrario comenzar a preguntar en orden
    # else
    #   comentario positicvo + preguntar en orden sien 

    print(nodo_destino)
    return {
        "nodo_destino": nodo_destino,
        "subsiguiente": 1,
        "conversation_str": conversation_str,
        "response_text": response_text,
        "group_id": None,
        "question_id": None,
        "result": "Cerrada"

    }

def nodo_101(variables):
    """
    Nodo que decide si el usuario sabe que importar.
    """
    import app.services.brain as brain
    import json
    import app.services.brain as brain
    tx = variables["tx"]
    ctt = variables["ctt"]
    numero_limpio = variables["numero_limpio"]
    contacto = ctt.get_by_phone(numero_limpio)    
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)
    conversation_history = variables["conversation_history"]

    conversation_history.append({
        "role": "system",
        "content": ("En caso que estes seguro que no sepa que importar responde 0 y en cualquier otro caso 1"
        )
    })

    sabe_que_importar = brain.ask_openai(conversation_history)
    print(sabe_que_importar)
    
    if sabe_que_importar == "1":
        nodo_destino = 102
         
    else:
        nodo_destino = 104

    
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


def nodo_102(variables):
    """
    Nodo "Sherlock": hace preguntas activas al cliente usando GPT para completar la busqueda de la posicion arancelaria.
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
        mensaje_intro = "Te voy a hacer " + max_preguntas_str + " preguntas para entender mejor que producto queres importar."
        twilio.send_whatsapp_message(mensaje_intro, sender_number, None)

    if question_id > max_preguntas:
        return {
            "nodo_destino": 103,
            "subsiguiente": 0,
            "conversation_str": conversation_str,
            "response_text": "Fin de las preguntas.",
            "group_id": None,
            "question_id": question_id,
            "result": "Abierta"
        }

    mensaje_def_triage = (
        "Vas a hacerle " + max_preguntas_str + " preguntas que estés seguro que te entienda a un cliente "
        "con el objetivo de conocer que posicion arancelaria tiene el producto que quiere importar. En todos los casos vas a hacer primero un comentario sobre la ultima respuesta del usuario y una pregunta cubriendo lo siguiente: 1) La hoja de producto; 2)Un detalle de la función principal; 3) El peso; 4) Las dimensiones ; y a partir de aca las preguntas que mas ayuden a definir la posicion arancelaria de un bien.\n"
        "En cada iteración debes tomar como historico esto : " + conversation_str + ",\n"
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
        "nodo_destino": 102,
        "subsiguiente": 1,
        "conversation_str": json.dumps(conversation_history),
        "response_text": response_text,
        "group_id": None,
        "question_id": question_id,
        "result": "Abierta"
    }
    
    
    
'''






