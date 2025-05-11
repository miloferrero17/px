from typing import Callable, Optional
import json
import app.services.brain as brain



def next_node_fofoca_sin_logica(ctt, tx, msj, brain, numero_limpio, body, next_node_question):
    """
    Genera una sugerencia tipo 'fofoca' para continuar una conversación de comercio exterior,
    basada en el historial previo y sin lógica condicional compleja.

    Args:
        ctt: Instancia de Contacts (para obtener información del contacto).
        tx: Instancia de Transactions (para obtener historial de conversación).
        msj: Instancia de Messages (para obtener los mensajes anteriores).
        brain: Servicio de OpenAI para generar el texto.
        numero_limpio (str): Número del usuario (formato limpio).
        body (str): Último mensaje recibido del usuario.
        next_node_question (str): Próxima pregunta del flujo conversacional.

    Returns:
        str: Texto generado por OpenAI para continuar la conversación.
    """
    ctt = Contacts()
    eng = Engine()
    msj = Messages()
    aux = Messages()
    # 1) Cargo conversation_history
    contacto = ctt.get_by_phone(numero_limpio)
    conversation_str = tx.get_open_conversation_by_contact_id(contacto.contact_id)
    print("Historial de conversación:", conversation_str)

    # 2) Busco el penúltimo mensaje
    pen_ultimo_mensaje = msj.get_penultimate_by_phone(numero_limpio)
    pen_ultimo_mensaje_text = pen_ultimo_mensaje.text

    # 3) Armo prompt tipo assistant
    aux_question_fofoca = [{
        "role": "assistant",
        "content": (
            "Sos un experto en comercio exterior del Mercosur con foco en Argentina. "
            "Teniendo en cuenta este historial y manteniendo un dialogo fluido: " + conversation_str +
            "\nAnte esta pregunta: " + pen_ultimo_mensaje_text +
            "\nEl usuario contestó esto: " + body +
            "\nRazonamiento: Podrías darle al usuario un breve consejo de no más de 80 tokens con foco en el potencial de importar y el valor que le podés aportar como despachante de aduana, sin usar lugares comunes como \"Como despachante de aduana\". "
            "Adicionalmente, hacé que la narrativa tienda a la siguiente pregunta: " + next_node_question
        )
    }]

    # 4) Llamo a GPT
    result = brain.ask_openai(aux_question_fofoca, temperature=0, model="gpt-4")
    print("Respuesta generada:", result)

    return result

'''
print ("Bienvenido al nodo: "+str(msg_key))
print(numero_limpio)
print(body)
print(contexto)
ctt= Contacts()
tx = Transactions()
msj = Messages()

#Cargo conversation_history
conversation_history = [{
        "role": "system",
        "content":"Sos un asistente virtual que te ayudara a resolver cualquier duda que tengas en comercio exterior, especializado en Asia y en el Mercosur. Siempre contesta explicando."
    }]
conversation_history.append({
    "role": "user",
    "content": body
    })

response_text = "Bienvenido al co-piloto de importación de Hunitro, yo voy a acompañarte en todo el proceso de importación. Ahora estas en el primer paso Documentación y Proveedor, contesta estas preguntas podes hacer con texto, audio y adjuntando archivos. Arranquemos. ¿Sos monotributista o tenes una empresa?"

conversation_history.append({
    "role": "assistant",
    "content": response_text
    })

conversation_str = json.dumps(conversation_history)
print(conversation_str)




### Escribo conversation en tx
#Obtengo en numero de nodo en el que esta
ultimo_mensaje = msj.get_latest_by_phone(numero_limpio)
msg_key = ultimo_mensaje.msg_key
#print(msg_key)

#Obtengo contact_id
contacto = ctt.get_by_phone(numero_limpio)
#print(contacto)

open_tx_id = tx.get_open_transaction_id_by_contact_id(contacto.contact_id)
tx.update(
    id=open_tx_id,
    contact_id=contacto.contact_id,
    phone=numero_limpio,
    name="Abierta",
    conversation=conversation_str
)

# Cargo la ultima pregunta
last_assistant_question.add(
    msg_key=msg_key,
    text=response_text,
    phone=numero_limpio    
)


nodo_destino = 5
result = response_text
#print(result)
'''
