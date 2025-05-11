# Modulos Build-in
from datetime import datetime
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
from typing import Optional

# Modulos de 3eros
import app.services.twilio_service as twilio
from twilio.twiml.messaging_response import MessagingResponse


# Modulos propios
from app.Model.users import Users   
from app.Model.enums import Role
from app.Model.contacts import Contacts
from app.Model.engine import Engine
from app.Model.messages import Messages
from app.Model.transactions import Transactions
import app.services.brain as brain
import app.services.decisions as decs
import app.services.embedding as vector



def handle_incoming_message(body, to, media_url):
    nodo_destino = 0
    ultimo_mensaje = ""
    msg_key = 0
    registro = 0

    ctt = Contacts()
    eng = Engine()
    msj = Messages()
    tx = Transactions()
    numero_limpio = limpiar_numero(to)

    if body == "x":
        msj.add(
            msg_key=2,
            text="Reset",
            phone=numero_limpio
        )
        return "Ok"

    conversation_history = [{
        "role": "system",
        "content": "Sos un asistente virtual que te ayudara a resolver cualquier duda que tengas en comercio exterior"
    }]
    conversation_str = json.dumps(conversation_history)

    variables = {
        "body": body,
        "to": to,
        "media_url": media_url,
        "nodo_destino": nodo_destino,
        "numero_limpio": numero_limpio,
        "msg_key": msg_key,
        "ctt": ctt,
        "msj": msj,
        "eng": eng,
        "conversation_history": conversation_history
    }

    contacto = ctt.get_by_phone(numero_limpio)

    if contacto is None:
        ctt.add(
            event_id=100,
            name="Juan",
            phone=numero_limpio
        )
        contacto = ctt.get_by_phone(numero_limpio)
        msg_key = 2
        msj.add(
            msg_key=msg_key,
            text="Inicio de la conversación",
            phone=numero_limpio
        )
        tx.add(
            contact_id=contacto.contact_id,
            phone=numero_limpio,
            name="Abierta",
            conversation=conversation_str,
        )

    else:
        diferencia = calcular_diferencia_en_minutos(tx, numero_limpio)
        if diferencia is not None and diferencia > 3:
            print("⏱️ Sesión terminada")
            ultima_tx = tx.get_last_timestamp_by_phone(numero_limpio)

            if ultima_tx:
                tx_id = ultima_tx["id"]
                timestamp_ahora = datetime.now().isoformat()
                tx.update(
                    _id=tx_id,
                    contact_id=contacto,
                    phone=numero_limpio,
                    name="Cerrada",
                    timestamp=timestamp_ahora
                )

            tx.add(
                contact_id=contacto.contact_id,
                phone=numero_limpio,
                name="Abierta",
                conversation=conversation_str,
            )
            msg_key = 2
            msj.add(
                msg_key=msg_key,
                text=body,
                phone=numero_limpio
            )
        else:
            print("✅ Sesión vigente")

    ultimo_mensaje = msj.get_latest_by_phone(numero_limpio)
    msg_key = ultimo_mensaje.msg_key
    registro = eng.get_by_id(msg_key)
    codigo_crudo = registro.Python_Code

    contexto = {
        "__builtins__": {
            "print": print,
            "__import__": __import__
        }
    }
    contexto.update(variables)

    contexto_actualizado = ejecutar_codigo_guardado(codigo_crudo, variables)

    nodo_destino = contexto_actualizado.get("nodo_destino")
    print(f"🚀 Nodo destino: {nodo_destino}")
    twilio.send_whatsapp_message(contexto_actualizado.get("body", "Sorry"), to, None)

    msj.add(
        msg_key=nodo_destino,
        text=body,
        phone=numero_limpio
    )

    return "Ok"

'''
# Modulos Build-in
from datetime import datetime
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
from typing import Optional

# Modulos de 3eros
import app.services.twilio_service as twilio
from twilio.twiml.messaging_response import MessagingResponse


# Modulos propios
from app.Model.users import Users   
from app.Model.enums import Role
from app.Model.contacts import Contacts
from app.Model.engine import Engine
from app.Model.messages import Messages
from app.Model.transactions import Transactions
import app.services.brain as brain
import app.services.decisions as decs
import app.services.embedding as vector


def handle_incoming_message(body, to, media_url):
    nodo_destino = 0
    ultimo_mensaje = ""
    msg_key=0
    registro=0
    ctt = Contacts()
    eng = Engine()
    msj = Messages()
    tx = Transactions()
    numero_limpio = limpiar_numero(to)
    
    if body == "x":
        msj.add(
            msg_key=2,
            text="Reset",
            phone=numero_limpio
        )
        return "Ok"
    
    conversation_history = [{
        "role": "system",
        "content":"Sos un asistente virtual que te ayudara a resolver cualquier duda que tengas en comercio exterior"
    }]
    conversation_str = json.dumps(conversation_history)
    
   
    variables = {
        "body": body,
        "to": to,
        "media_url": media_url,
        "nodo_destino": nodo_destino,
        "numero_limpio": numero_limpio,
        "msg_key": msg_key,
        "ctt": ctt,
        "msj": msj,
        "eng": eng,
        "conversation_history": conversation_history
    }
    
    # Chequeo si el contacto existe
    contacto = ctt.get_by_phone(numero_limpio)
    
    if contacto is None:
        ctt.add(
            event_id=100,
            name="Juan",
            phone=numero_limpio
        )
        contacto = ctt.get_by_phone(numero_limpio)
        msg_key = 2 # Inicia en 2 porque el primer stage del engine es 2
        msj.add(
            msg_key=msg_key,
            text="Inicio de la conversación",
            phone=numero_limpio
        )
        ###Add transaction

        tx.add(
            contact_id=contacto.contact_id,  # ✅ ahora sí
            phone=numero_limpio,
            name="Abierta",
            conversation=conversation_str,
        )

    else:
        ### La sesion esta vivia???
        if calcular_diferencia_en_minutos(tx, numero_limpio) > 3:
            contacto = ctt.get_by_phone(numero_limpio)
            ### Termino la tx
            print("Sesión terminada")
            ultima_tx = tx.get_last_timestamp_by_phone(numero_limpio)

            if ultima_tx:
                tx_id = ultima_tx["id"]
                timestamp_ahora = datetime.now().isoformat()
                tx.update(
                    _id=tx_id,
                    contact_id=contacto,
                    phone=numero_limpio,
                    name="Cerrada",
                    timestamp= timestamp_ahora
                )
                
            ### Creo una nueva tx
            tx.add(
                contact_id=contacto.contact_id,  # ✅ ahora sí
                phone=numero_limpio,
                name="Abierta",
                conversation=conversation_str,
            )
            msg_key = 2 # Inicia en 2 porque el primer stage del engine es 2
            msj.add(
                msg_key=msg_key,
                text=body,
                phone=numero_limpio
            )
        else:
            print("Sesión vigente")

    ultimo_mensaje = msj.get_latest_by_phone(numero_limpio)
    #print(ultimo_mensaje)
    msg_key = ultimo_mensaje.msg_key
    registro = eng.get_by_id((msg_key))
    codigo_crudo = registro.Python_Code
    contexto = {"__builtins__": {}, "print": print}
    contexto.update(variables)

    contexto_actualizado = ejecutar_codigo_guardado(codigo_crudo, variables)
    
    nodo_destino = contexto_actualizado.get("nodo_destino")  
    print(nodo_destino)
    twilio.send_whatsapp_message(contexto_actualizado.get("body", "Sorry"), to, None)

    msj.add(
        msg_key=nodo_destino,
        text=body,
        phone=numero_limpio
    )
    return "Ok"









def calcular_diferencia_en_minutos(transacciones, numero_limpio: str) -> Optional[float]:
    """
    Devuelve la diferencia en minutos entre la última transacción y ahora (UTC),
    ajustando el timestamp a UTC+5 y sumando 3 horas, luego restando 120 minutos.
    """
    data = transacciones.get_last_timestamp_by_phone(numero_limpio)
    if not data:
        return None  # No hay datos

    timestamp_str = data["timestamp"]

    # Zonas horarias
    utc_plus_5 = timezone(timedelta(hours=5))
    utc_0 = timezone.utc

    # Convertir string a datetime
    t1 = datetime.fromisoformat(timestamp_str)

    # Asegurar que tenga zona horaria
    if t1.tzinfo is None:
        t1 = t1.replace(tzinfo=utc_plus_5)

    # Sumar 3 horas
    t1 = t1 + timedelta(hours=3)

    # Tiempo actual en UTC
    t2 = datetime.now(utc_0)

    # Calcular diferencia
    diferencia = (t2 - t1).total_seconds() / 60  # en minutos
    diferencia_ajustada = diferencia - 120

    return diferencia_ajustada


def ejecutar_codigo_guardado(codigo_crudo: str, variables: dict):
    try:
        if "\\n" in codigo_crudo:
            codigo_crudo = codigo_crudo.replace("\\n", "\n")

        #contexto = {"__builtins__": {}, "print": print}
        contexto = {
            "__builtins__": {
                "print": print,
                "__import__": __import__  # 👈 Esto habilita los imports
            }
        }

        contexto.update(variables)

        exec(codigo_crudo, contexto)
        return contexto  # ← devolvemos el contexto con los cambios

    except Exception as e:
        print("Error ejecutando código:", e)
        return variables  # devolvemos lo que tengamos, aunque sea el original

def limpiar_numero(to):
    return to.replace("whatsapp:", "").replace("+", "")

handle_incoming_message("Hola", "whatsapp:+5491133585362", "")


# Modulos Build-in
from datetime import datetime
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
from typing import Optional

# Modulos de 3eros
import app.services.twilio_service as twilio
from twilio.twiml.messaging_response import MessagingResponse


# Modulos propios
from app.Model.users import Users   
from app.Model.enums import Role
from app.Model.contacts import Contacts
from app.Model.engine import Engine
from app.Model.messages import Messages
from app.Model.transactions import Transactions
import app.services.brain as brain
import app.services.decisions as decs
import app.services.embedding as vector

print("Gato Negro")


def handle_incoming_message(body, to, media_url):
    #print("Exito gatito")
    nodo_destino = 0
    ultimo_mensaje = ""
    msg_key=0
    registro=0
    ctt = Contacts()
    eng = Engine()
    msj = Messages()
    tx = Transactions()
    numero_limpio = limpiar_numero(to)
    #diferencia = calcular_diferencia_en_minutos(tx, numero_limpio)
    #print(diferencia)

    
    if body == "x":
        msj.add(
            msg_key=2,
            text="Reset",
            phone=numero_limpio
        )
        return "Ok"
    
    conversation_history = [{
        "role": "system",
        "content":"Sos un asistente virtual que te ayudara a resolver cualquier duda que tengas en comercio exterior"
    }]
    conversation_str = json.dumps(conversation_history)
    
   
    variables = {
        "body": body,
        "to": to,
        "media_url": media_url,
        "nodo_destino": nodo_destino,
        "numero_limpio": numero_limpio,
        "msg_key": msg_key,
        "ctt": ctt,
        "msj": msj,
        "eng": eng,
        "conversation_history": conversation_history
    }
    
    # Chequeo si el contacto existe
    contacto = ctt.get_by_phone(numero_limpio)
    
    if contacto is None:
        ctt.add(
            event_id=100,
            name="Juan",
            phone=numero_limpio
        )
        contacto = ctt.get_by_phone(numero_limpio)
        msg_key = 2 # Inicia en 2 porque el primer stage del engine es 2
        msj.add(
            msg_key=msg_key,
            text="Inicio de la conversación",
            phone=numero_limpio
        )
        ###Add transaction
        tx.add(
            contact_id=contacto.contact_id,  # ✅ ahora sí
            phone=numero_limpio,
            name="Abierta",
            conversation=conversation_str,
        )

    else:
        ### La sesion esta vivia???
        if calcular_diferencia_en_minutos(tx, numero_limpio) > 3:
            contacto = ctt.get_by_phone(numero_limpio)
            ### Termino la tx
            print("Sesión terminada")
            ultima_tx = tx.get_last_timestamp_by_phone(numero_limpio)

            if ultima_tx:
                tx_id = ultima_tx["id"]
                timestamp_ahora = datetime.now().isoformat()
                tx.update(
                    _id=tx_id,
                    contact_id=contacto,
                    phone=numero_limpio,
                    name="Cerrada",
                    timestamp= timestamp_ahora
                )
                
            ### Creo una nueva tx
            tx.add(
                contact_id=contacto.contact_id,  # ✅ ahora sí
                phone=numero_limpio,
                name="Abierta",
                conversation=conversation_str,
            )
            msg_key = 2 # Inicia en 2 porque el primer stage del engine es 2
            msj.add(
                msg_key=msg_key,
                text=body,
                phone=numero_limpio
            )
        else:
            print("Sesión vigente")

    ultimo_mensaje = msj.get_latest_by_phone(numero_limpio)
    #print(ultimo_mensaje)
    msg_key = ultimo_mensaje.msg_key
    registro = eng.get_by_id((msg_key))
    codigo_crudo = registro.Python_Code
    contexto = {"__builtins__": {}, "print": print}
    contexto.update(variables)

    contexto_actualizado = ejecutar_codigo_guardado(codigo_crudo, variables)
    
    nodo_destino = contexto_actualizado.get("nodo_destino")  
    print(nodo_destino)
    twilio.send_whatsapp_message(contexto_actualizado.get("body", "Sorry"), to, None)

    msj.add(
        msg_key=nodo_destino,
        text=body,
        phone=numero_limpio
    )

    return "Ok"








def calcular_diferencia_en_minutos(transacciones, numero_limpio: str) -> Optional[float]:
    """
    Devuelve la diferencia en minutos entre la última transacción y ahora (UTC),
    ajustando el timestamp a UTC+5 y sumando 3 horas, luego restando 120 minutos.
    """
    data = transacciones.get_last_timestamp_by_phone(numero_limpio)
    if not data:
        return None  # No hay datos

    timestamp_str = data["timestamp"]

    # Zonas horarias
    utc_plus_5 = timezone(timedelta(hours=5))
    utc_0 = timezone.utc

    # Convertir string a datetime
    t1 = datetime.fromisoformat(timestamp_str)

    # Asegurar que tenga zona horaria
    if t1.tzinfo is None:
        t1 = t1.replace(tzinfo=utc_plus_5)

    # Sumar 3 horas
    t1 = t1 + timedelta(hours=3)

    # Tiempo actual en UTC
    t2 = datetime.now(utc_0)

    # Calcular diferencia
    diferencia = (t2 - t1).total_seconds() / 60  # en minutos
    diferencia_ajustada = diferencia - 120

    return diferencia_ajustada


def ejecutar_codigo_guardado(codigo_crudo: str, variables: dict):
    try:
        if "\\n" in codigo_crudo:
            codigo_crudo = codigo_crudo.replace("\\n", "\n")

        #contexto = {"__builtins__": {}, "print": print}
        contexto = {
            "__builtins__": {
                "print": print,
                "__import__": __import__  # 👈 Esto habilita los imports
            }
        }

        contexto.update(variables)

        exec(codigo_crudo, contexto)
        return contexto  # ← devolvemos el contexto con los cambios

    except Exception as e:
        print("Error ejecutando código:", e)
        return variables  # devolvemos lo que tengamos, aunque sea el original

def limpiar_numero(to):
    return to.replace("whatsapp:", "").replace("+", "")
'''
