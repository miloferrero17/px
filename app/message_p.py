# message_p.py actualizado

# Módulos Build-in
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
from typing import Optional
import json
from dateutil.parser import isoparse
import requests
import time
import os


# Módulos de 3eros
import app.services.twilio_service as twilio
from twilio.twiml.messaging_response import MessagingResponse

# Módulos propios
from app.Model.users import Users   
from app.Model.enums import Role
from app.Model.contacts import Contacts
from app.Model.engine import Engine
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
from app.services.decisions import next_node_fofoca_sin_logica, limpiar_numero, calcular_diferencia_en_minutos,ejecutar_codigo_guardado
import app.services.brain as brain
entorno = os.getenv("ENV", "undefined")



def handle_incoming_message(body, to, tiene_adjunto, media_type, file_path, transcription, description, pdf_text):
    numero_limpio = limpiar_numero(to)

    # 1) Manejo de adjuntos (si devuelve True ya respondió y no sigue el flujo)
    if procesar_adjuntos(tiene_adjunto, media_type, description, pdf_text, to):
        return "Ok"

    # 2) Obtener o crear contacto
    contacto, event_id = obtener_o_crear_contacto(numero_limpio)

    # 3) Gestionar sesión y registrar mensaje
    msg_key, conversation_str, conversation_history = gestionar_sesion_y_mensaje(contacto, event_id, body, numero_limpio)

    # 4) Ejecutar workflow
    variables = inicializar_variables(body, numero_limpio, contacto, event_id, msg_key, conversation_str, conversation_history)
    variables = ejecutar_workflow(variables)

    # 5) Enviar respuesta y actualizar transacción
    enviar_respuesta_y_actualizar(variables, contacto, event_id, to)

    return "Ok"

def procesar_adjuntos(tiene_adjunto, media_type, description, pdf_text, to):
    if tiene_adjunto == 1:
        if media_type.startswith("image"):
            twilio.send_whatsapp_message(description, to, None)
            return True
        if media_type == "application/pdf":
            twilio.send_whatsapp_message(pdf_text, to, None)
            return True
    return False

def obtener_o_crear_contacto(numero_limpio):
    ctt = Contacts()
    ev = Events()
    msj = Messages()

    contacto = ctt.get_by_phone(numero_limpio)
    event_id = 1  


    if contacto is None:
        event_id = 1  # default
        contact_id = ctt.add(event_id=event_id, name="Juan", phone=numero_limpio)
        msg_key = ev.get_nodo_inicio_by_event_id(event_id)
        msj.add(msg_key=msg_key, text="Nuevo contacto", phone=numero_limpio, event_id=event_id, question_id=0)
        print("Contacto creado")
        contacto = ctt.get_by_phone(numero_limpio)
    else:
        #  trae el event_id que ya tiene asignado el contacto
        event_id = ctt.get_event_id_by_phone(numero_limpio) or 1
        print("Contacto ya exstente")

    return contacto, event_id


def gestionar_sesion_y_mensaje(contacto, event_id, body, numero_limpio):
    tx, msj, ev = Transactions(), Messages(), Events()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    # Nodo inicial del evento (no asumir 200)
    nodo_inicio = ev.get_nodo_inicio_by_event_id(event_id) or 200

    # Contexto del agente para SEMBRAR la sesión (sin historial previo)
    contexto_agente = ev.get_description_by_event_id(event_id) or ""
    base_context = json.dumps([{"role": "system", "content": contexto_agente}])

    # Última transacción del contacto
    ultima_tx = tx.get_last_timestamp_by_phone(numero_limpio)

    # --- Caso 1: primera vez que escribe (no hay TX previa) ---
    if ultima_tx is None:
        print("[NUEVA] Primer mensaje, creo transacción con CONTEXTO")
        tx.add(
            contact_id=contacto.contact_id,
            phone=numero_limpio,
            name="Abierta",
            event_id=event_id,
            conversation=base_context,   # <-- sembrar contexto del evento
            timestamp=now_utc,
            data_created=now_utc
        )
        msg_key = nodo_inicio
        msj.add(msg_key=msg_key, text=body, phone=numero_limpio, event_id=event_id)

    # --- Caso 2: última sesión estaba CERRADA ---
    elif tx.is_last_transaction_closed(numero_limpio) == 1:
        print("[CERRADA] Nueva sesión con CONTEXTO y nodo inicio")
        tx.add(
            contact_id=contacto.contact_id,
            phone=numero_limpio,
            name="Abierta",
            event_id=event_id,
            conversation=base_context,   # <-- sembrar contexto del evento
            timestamp=now_utc,
            data_created=now_utc
        )
        msg_key = nodo_inicio
        msj.add(msg_key=msg_key, text=body, phone=numero_limpio, event_id=event_id)

    # --- Caso 3: la sesión VENCIDA por tiempo ---
    elif calcular_diferencia_en_minutos(tx, numero_limpio) > ev.get_time_by_event_id(event_id):
        print("[VENCIDA] Cierro anterior y creo nueva con CONTEXTO; reinicio en nodo inicio")
        tx.update(
            id=ultima_tx["id"],
            contact_id=contacto.contact_id,
            phone=numero_limpio,
            name="Cerrada",
            timestamp=now_utc,
            event_id=event_id
        )
        tx.add(
            contact_id=contacto.contact_id,
            phone=numero_limpio,
            name="Abierta",
            event_id=event_id,
            conversation=base_context,   # <-- sembrar contexto del evento
            timestamp=now_utc,
            data_created=now_utc
        )
        msg_key = nodo_inicio
        msj.add(msg_key=msg_key, text=body, phone=numero_limpio, event_id=event_id)

    # --- Caso 4: sesión VIGENTE ---
    else:
        print("[VIGENTE] Uso la sesión abierta ")
        ultimo_mensaje = msj.get_latest_by_phone(numero_limpio)
        msg_key = ultimo_mensaje.msg_key if ultimo_mensaje else nodo_inicio
        msj.add(msg_key=msg_key, text=body, phone=numero_limpio, event_id=event_id)

    # Cargar historial ACTUAL de la TX ABIERTA (per-sesión) y agregar el usuario
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id) or base_context
    conversation_history = json.loads(conversation_str)
    conversation_history.append({"role": "user", "content": body})
    conversation_str = json.dumps(conversation_history)

    return msg_key, conversation_str, conversation_history

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

def ejecutar_workflow(variables):
    while True:
        print(f"Ejecutando nodo {variables['nodo_destino']}")
        contexto_actualizado = ejecutar_nodo(variables["nodo_destino"], variables)
        if contexto_actualizado:
            variables.update(contexto_actualizado)
        if variables.get("subsiguiente") == 1:
            break
    return variables

def enviar_respuesta_y_actualizar(variables, contacto, event_id, to):
    import json
    tx, now_utc = Transactions(), datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    # Enviar respuesta
    mensaje_a_enviar = variables.get("response_text") or "Hubo un problema interno. Intenta más tarde."
    twilio.send_whatsapp_message(mensaje_a_enviar, to, variables.get("url"))

    # 🔑 AÑADIR respuesta del asistente al historial ANTES de persistir
    ch = variables.get("conversation_history", [])
    ch.append({"role": "assistant", "content": variables.get("response_text", "")})
    variables["conversation_history"] = ch
    variables["conversation_str"] = json.dumps(ch)

    # Persistir conversación completa
    open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id)
    estado = "Cerrada" if variables.get("result") == "Cerrada" else "Abierta"

    tx.update(
        id=open_tx_id,
        contact_id=contacto.contact_id,
        phone=variables["numero_limpio"],
        name=estado,
        conversation=variables["conversation_str"],
        timestamp=now_utc,
        event_id=event_id
    )

    if estado == "Cerrada":
        twilio.send_whatsapp_message("Gracias!", to, None)

    # Guardar última pregunta / salida del bot (como hacías antes)
    Messages().add(
        msg_key=variables.get("nodo_destino"),
        text=variables.get("response_text"),
        phone=variables["numero_limpio"],
        group_id=variables.get("group_id", 0),
        question_id=variables.get("question_id", 0),
        event_id=event_id
    )



'''''
def handle_incoming_message1(body, to,  tiene_adjunto, media_type, file_path, transcription, description,pdf_text):
    print(body)
    #twilio.enviar_mensaje_si_no("+5491133585362")

    print(media_type)
    if tiene_adjunto == 1:
        if media_type.startswith("image"):
            twilio.send_whatsapp_message(description, to, None)    
        if( media_type == "application/pdf"):
            twilio.send_whatsapp_message(pdf_text, to, None)    
    
    msj = Messages()
    tx = Transactions()
    ev = Events()
    numero_limpio = limpiar_numero(to)
    ctt = Contacts()    

    # Obtener el timestamp actual en UTC
    now_utc = datetime.now(timezone.utc)
    formatted_now = now_utc.strftime("%Y-%m-%d %H:%M:%S.%f")

    ### 1) Inicializo las variables
    event_id = 1
    msg_key = 0
    nodo_destino = 0
    ultimo_mensaje = ""
    response_text = ""
    next_node_question = ""
    registro = 0
    max_preguntas= 0
    contexto = ""
    eng = Engine()
    aux = Messages()
    qs = Questions()
    last_assistant_question = Messages()
    group_id = 0
    question_id = 0
    question_name =""
    contacto = ""
    result = ""
    url = ""
    subsiguiente = 0
    conversation_str = ""
    conversation_history = [{"role": "system", "content": ""}]
    aux_question_fofoca = [{"role": "system", "content": ""}]


    contacto = ctt.get_by_phone(numero_limpio)

    
    #### 1) Reseteo
    if body in ("R6"):
        event_id = int(body[1:])    # toma desde el índice 1 hasta el final
        print(event_id)
        msg_key = ev.get_nodo_inicio_by_event_id(event_id)
        print(msg_key)

        try: 
            if contacto is None:
                # creás el contacto y recuperás sólo el ID
                _new_id = ctt.add(
                    event_id=event_id,
                    name="Juan",
                     phone=numero_limpio
                )
                # ahora sí traés el objeto completo con su contact_id, nombre, etc.
                contacto = ctt.get_by_phone(numero_limpio)
                print("1.1) Contacto creado")
            else:
                ctt.update(
                    contact_id=contacto.contact_id,
                    event_id=event_id
                )

        except Exception as e:
            print(f"Ocurrió un error: {e}")
        
            
        msj.add(
            msg_key=msg_key,
            text="Cambio a " + body,
            phone=numero_limpio,
            event_id=event_id
        )
        
        try:
            ultima_tx = tx.get_last_timestamp_by_phone(numero_limpio)
            #print(ultima_tx)
            
            if ultima_tx is not None:
                # Cierro la transacción anterior
                tx.update(
                    id=ultima_tx["id"],
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    name="Cerrada",
                    timestamp=formatted_now,
                    event_id=event_id

                )
                print("2.1.) Cierro la tx vieja")                
                
                # Abro la nueva transacción
                #print(event_id)
                contexto_agente = ev.get_description_by_event_id(event_id)
                conversation_history = [{
                        "role": "system",
                        "content":contexto_agente
                    }]
                #print(conversation_history)
                conversation_str = json.dumps(conversation_history)                
                
                
                tx.add(
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    event_id=event_id,
                    name="Abierta",
                    conversation = conversation_str,
                    timestamp=formatted_now,
                    data_created=formatted_now
                )
                print(tx)

                print("2.2.) Creo la tx")                

            else:
                # No había transacción previa: abro la primera
                contexto_agente = ev.get_description_by_event_id(event_id)
                conversation_history = [{
                    "role": "system",
                    "content":contexto_agente
                }]
                #print(conversation_history)
                conversation_str = json.dumps(conversation_history)                
                #print(conversation_str)
                tx.add(
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    name="Abierta",
                    event_id=event_id,
                    conversation = conversation_str,
                    timestamp=formatted_now,
                    data_created=formatted_now
                )

                print("2.3.) Creo la tx")                

        except (TypeError, KeyError) as e:
            print(f"❌ Error manejando transacciones: {e}")
            # acá podrías decidir si vuelves a lanzar la excepción o manejarla de otro modo

        
        except Exception as e:
            print(f"Ocurrió un error: {e}")

        eventos = ev.get_by_id(event_id)
        print(eventos.name)
        twilio.send_whatsapp_message("Cambio de proyecto con éxito: "+eventos.name, to, None)    
        return "Ok"        




    
    #### 2) Alta de contacto   
    if contacto is None:        
        event_id = 1   
        ctt.add(
            event_id=event_id, 
            name="Juan",
            phone=numero_limpio
        )
        msg_key = ev.get_nodo_inicio_by_event_id(event_id)
        msj.add(
            msg_key=msg_key,
            text="Nuevo contacto",
            phone=numero_limpio,
            event_id=event_id,
            question_id=0
        )
        
        print("1) Contacto creado")
    

    contacto = ctt.get_by_phone(numero_limpio)
    











    #### 3) Gestión de sesiones   
    if contacto is not None:        
        
        event_id = ctt.get_event_id_by_phone(numero_limpio)
        if event_id == 0:    ### Primera sesion de todas
            twilio.send_whatsapp_message("Por favor contesta un numero para comenzar.", to, None)   
            print("Por favor contesta un numero para comenzar.")
            return "Ok"        
        

        contexto_agente = ev.get_description_by_event_id(event_id)
        conversation_history = [{
            "role": "system",
            "content":contexto_agente
        }]
        #print(conversation_history)
        conversation_str = json.dumps(conversation_history)


        #print(conversation_str)   
        try: #### Creacion y update de sesiones
            ultima_tx = tx.get_last_timestamp_by_phone(numero_limpio)
            if ultima_tx is None:
                tx.add(
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    name="Abierta",
                    event_id=event_id,
                    conversation = conversation_str,
                    timestamp=formatted_now,
                    data_created=formatted_now
                )
                print("2.4) Creo la tx")
            
            
            elif tx.is_last_transaction_closed(numero_limpio) == 1: ### Esta cerrada
                print("2.8) Sesion cerrada sin hacer nada")
                tx.add(
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    name="Abierta",
                    event_id=event_id,
                    conversation = conversation_str,
                    timestamp=formatted_now,
                    data_created=formatted_now
                )
                
                msg_key = ev.get_nodo_inicio_by_event_id(event_id)
                msj.add(
                    msg_key=msg_key, 
                    text=body, 
                    phone=numero_limpio,
                    event_id=event_id
                )    
                print("2.6) Sesion nueva")
                    
            elif calcular_diferencia_en_minutos(tx, numero_limpio) > ev.get_time_by_event_id(event_id):
                                
                tx.update(
                    id=ultima_tx["id"],
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    name="Cerrada",
                    timestamp=formatted_now,
                    event_id=event_id
                )
                #print(tx)
                print("2.5) Sesion vencida")
            
                tx.add(
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    name="Abierta",
                    event_id=event_id,
                    conversation = conversation_str,
                    timestamp=formatted_now,
                    data_created=formatted_now
                )

                msg_key = ev.get_nodo_inicio_by_event_id(event_id)
                msj.add(
                    msg_key=msg_key, 
                    text=body, 
                    phone=numero_limpio,
                    event_id=event_id
                )    
                print("2.6) Sesion nueva")
            
            else:
                ### 3) Trabajo sobre la sesión vigente/recien creada 
                print("2.7) Sesion vigente") 
        
            
            ultimo_mensaje = msj.get_latest_by_phone(numero_limpio)
            if ultimo_mensaje:
                msg_key = ultimo_mensaje.msg_key
                #print(ultimo_mensaje)
                #print(msg_key)
                msj.add(
                    msg_key=msg_key, 
                    text=body, 
                    phone=numero_limpio,
                    event_id=event_id
                )


            # Bloque de update de sesión
            conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)
            #print(conversation_str)
            #print(conversation_str)
            conversation_history = json.loads(conversation_str) if conversation_str else []
            conversation_history.append({
                "role": "user",
                "content": body
            })
            conversation_str = json.dumps(conversation_history)

            #print(conversation_str)
            nodo_destino = msg_key
            #print(nodo_destino)

            variables = {
                    "body": body,
                    "max_preguntas":max_preguntas,
                    "nodo_destino": nodo_destino,
                    "numero_limpio": numero_limpio,
                    "msg_key": msg_key,
                    "ctt": ctt,
                    "msj": msj,
                    "qs":qs,
                    "last_assistant_question": last_assistant_question,
                    "eng": eng,
                    "tx": tx,
                    "ev":ev,
                    "response_text": response_text,
                    "conversation_str": conversation_str,
                    "aux_question_fofoca": aux_question_fofoca,
                    "ultimo_mensaje": ultimo_mensaje,
                    "next_node_question": next_node_question,
                    "aux": aux,
                    "contacto": contacto,
                    "result": result,
                    "conversation_history": conversation_history,
                    "question_name": question_name,
                    "question_id": question_id,
                    "group_id":group_id,
                    "event_id":event_id,
                    "url":url
                }

            while True:
                print("Usted está entrando a:", nodo_destino)
                contexto_actualizado = ejecutar_nodo(nodo_destino, variables)
                variables.update(contexto_actualizado)
                #print(variables)
                # Salida del loop
                #print(variables.get("conversation_str"))
                nodo_destino = variables.get("nodo_destino")
                if variables.get("subsiguiente") == 1:
                    break
            print(variables.get("result"))
            

            conversation_history.append({
                "role": "assistant",
                "content":variables.get("response_text")
            })
            conversation_str = json.dumps(conversation_history)
            #print(conversation_str)
            
            #print(variables.get("response_text"))
            #mensaje = msj.get_latest_by_phone(numero_limpio)
            mensaje_a_enviar = variables.get("response_text") or "Hubo un problema interno. Por favor intentá más tarde."
            twilio.send_whatsapp_message(mensaje_a_enviar, to, variables.get("url"))

            open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id)
            #print(open_tx_id)
            if variables.get("result") == "Cerrada": 
                tx.update(
                    id=open_tx_id,
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    name="Cerrada",
                    conversation=conversation_str,
                    timestamp=formatted_now,
                    event_id=event_id
                )
                time.sleep(2)
                twilio.send_whatsapp_message("Gracias!", to, None)
            else:
                tx.update(
                    id=open_tx_id,
                    contact_id=contacto.contact_id,
                    phone=numero_limpio,
                    name="Abierta",
                    conversation=conversation_str,
                    timestamp=formatted_now,
                    event_id=event_id

                )
            print()
            print(variables.get("response_text"))
            
            # Cargo la ultima pregunta
            last_assistant_question.add(
                msg_key=variables.get("nodo_destino"),
                text=variables.get("response_text"),
                phone=numero_limpio,
                group_id=variables.get("group_id"),
                question_id=variables.get("question_id"),
                event_id=event_id         
            )
            return "Ok"

        except (TypeError, KeyError) as e:
            print(f"❌ Error accediendo a 'name': {e}")

            '''''