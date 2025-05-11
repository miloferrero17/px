# Módulos Build-in
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+
from typing import Optional
import json
from dateutil.parser import isoparse
import requests
import builtins
import sys

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


import app.services.brain as brain
import app.services.decisions as decs
import app.services.embedding as vector
from app.services.decisions import next_node_fofoca_sin_logica, limpiar_numero, calcular_diferencia_en_minutos,ejecutar_codigo_guardado
import app.services.brain as brain

numero_limpio = "5491133585362"
ctt=Contacts()
contacto = ctt.get_by_phone(numero_limpio)
event_id = ctt.get_event_id_by_phone(numero_limpio)

print(event_id)

sender_number = "whatsapp:+" + numero_limpio
twilio.send_whatsapp_message("Estoy pensando, dame unos segundos...", sender_number, None)    

# 1) Cargo conversation_history
tx=Transactions()
conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)
conversation_history = json.loads(conversation_str) if conversation_str else []
print("Reporte final")    
ev = Events()
mensaje_reporte = ev.get_reporte_by_event_id(event_id)
print(mensaje_reporte)


conversation_history.append({
            "role": "assistant",
            "content": mensaje_reporte
        })


result1 = brain.ask_openai(conversation_history)

print(result1)
response_text = result1
nodo_destino = 3
result = "Cerrada"
subsiguiente = 1

twilio.send_whatsapp_message(response_text, sender_number, None)    
