import json
import app.services.brain as brain
from typing import Optional
from datetime import datetime, timezone, timedelta
from dateutil.parser import isoparse  # ✅ NUEVO

def limpiar_numero(to):
    return to.replace("whatsapp:", "").replace("+", "")

def calcular_diferencia_en_minutos(transacciones, numero_limpio: str) -> Optional[float]:
    data = transacciones.get_last_timestamp_by_phone(numero_limpio)
    if not data:
        return None

    timestamp_str = data["timestamp"]

    try:
        t1 = isoparse(timestamp_str)
    except Exception as e:
        print(f"❌ Error al parsear timestamp: {timestamp_str} - {e}")
        return None

    if t1.tzinfo is None:
        t1 = t1.replace(tzinfo=timezone(timedelta(hours=5)))  # asume UTC+5 si no hay zona

    t1 = t1 + timedelta(hours=3)  # ajuste adicional
    t2 = datetime.now(timezone.utc)

    diferencia = (t2 - t1).total_seconds() / 60
    return diferencia - 120

def calcular_diferencia_desde_info(info) -> Optional[float]:
    """
    Misma lógica que calcular_diferencia_en_minutos, pero usando un dict
    ya leído de DB: {"id": ..., "name": ..., "timestamp": <iso str>}
    """
    if not info or not info.get("timestamp"):
        return None

    from dateutil.parser import isoparse
    from datetime import datetime, timezone, timedelta

    timestamp_str = str(info["timestamp"])
    try:
        t1 = isoparse(timestamp_str)
    except Exception as e:
        print(f"[TTL] parse error (info): {timestamp_str} - {e}")
        return None

    if t1.tzinfo is None:
        t1 = t1.replace(tzinfo=timezone(timedelta(hours=5)))  # igual que antes

    t1 = t1 + timedelta(hours=3)  # ajuste adicional (igual que antes)
    t2 = datetime.now(timezone.utc)
    diferencia = (t2 - t1).total_seconds() / 60
    return diferencia - 120  # mismo offset que tu función original


def ejecutar_codigo_guardado(codigo_crudo: str, variables: dict):
    try:
        if "\\n" in codigo_crudo:
            codigo_crudo = codigo_crudo.replace("\\n", "\n")
        
        contexto = {
            "__builtins__": {
                "print": print,
                "len": len,
                "range": range,
                "__import__": __import__
            },
            "next_node_fofoca_sin_logica": next_node_fofoca_sin_logica
        }
        
        contexto.update(variables)
        exec(codigo_crudo, contexto)

        if "result" not in contexto:
            contexto["result"] = "[Sin resultado definido]"
        if "nodo_destino" not in contexto:
            contexto["nodo_destino"] = 0
        return contexto

    except Exception as e:
        print("\u274c Error ejecutando código:", e)
        variables["result"] = "[Error en el motor de ejecución]"
        variables["nodo_destino"] = 0
        return variables
    

def next_node_fofoca_sin_logica(numero_limpio, body, conversation_str, ctt, tx, msj, contexto, max_tokens=80, nodo_destino=30):
    """
    Genera una respuesta GPT tipo 'fofoca', orientada al siguiente nodo del flujo,
    y actualiza la conversación en la base de datos.
    """

    # 2) Buscar mensajes anteriores
    ultimo_mensaje = msj.get_latest_by_phone(numero_limpio)
    msg_key = ultimo_mensaje.msg_key
    pen_ultimo_mensaje = msj.get_penultimate_by_phone(numero_limpio)
    pen_ultimo_mensaje = pen_ultimo_mensaje.text

    # 3) Armar prompt
    next_node_question = "¿Tenes una cuenta bancaria?¿Es de comercio exterior?"
    prompt = (
        f"{contexto} "
        f"Teniendo en cuenta este historial y manteniendo un diálogo fluido: {conversation_str} "
        f"Ante esta pregunta: {pen_ultimo_mensaje} "
        f"el usuario contestó: {body} "
        f"Razonamiento: Podrías darle al usuario un breve consejo de no más de {max_tokens} tokens, "
        f"con foco en el potencial de importar y el valor que le podés aportar como despachante de aduana, "
        f"sin usar lugares comunes como 'Como despachante de aduana'. "
        f"Adicionalmente, hacé que la narrativa tienda a la siguiente pregunta: {next_node_question}"
    )

    aux_question_fofoca = [{"role": "assistant", "content": prompt}]

    # 4) GPT
    result = brain.ask_openai(aux_question_fofoca, temperature=0, model="gpt-4")
    print(result)

    return result


'''
import json
import app.services.brain as brain
from typing import Optional
from datetime import datetime, timezone, timedelta

def limpiar_numero(to):
    return to.replace("whatsapp:", "").replace("+", "")

def calcular_diferencia_en_minutos(transacciones, numero_limpio: str) -> Optional[float]:
    data = transacciones.get_last_timestamp_by_phone(numero_limpio)
    if not data:
        return None
    timestamp_str = data["timestamp"]
    utc_plus_5 = timezone(timedelta(hours=5))
    utc_0 = timezone.utc
    t1 = datetime.fromisoformat(timestamp_str)
    if t1.tzinfo is None:
        t1 = t1.replace(tzinfo=utc_plus_5)
    t1 = t1 + timedelta(hours=3)
    t2 = datetime.now(utc_0)
    diferencia = (t2 - t1).total_seconds() / 60
    return diferencia - 120

def ejecutar_codigo_guardado(codigo_crudo: str, variables: dict):
    try:
        if "\\n" in codigo_crudo:
            codigo_crudo = codigo_crudo.replace("\\n", "\n")
        
        contexto = {
            "__builtins__": {
                "print": print,
                "len": len,
                "range": range,
                "__import__": __import__
            },
            "next_node_fofoca_sin_logica": next_node_fofoca_sin_logica  # ✅ Coma agregada
        }
        
        contexto.update(variables)
        exec(codigo_crudo, contexto)

        if "result" not in contexto:
            contexto["result"] = "[Sin resultado definido]"
        if "nodo_destino" not in contexto:
            contexto["nodo_destino"] = 0
        return contexto

    except Exception as e:
        print("\u274c Error ejecutando código:", e)
        variables["result"] = "[Error en el motor de ejecución]"
        variables["nodo_destino"] = 0
        return variables
    

def next_node_fofoca_sin_logica(numero_limpio, body, conversation_str, ctt, tx, msj, contexto, max_tokens=80, nodo_destino=30):
    """
    Genera una respuesta GPT tipo 'fofoca', orientada al siguiente nodo del flujo,
    y actualiza la conversación en la base de datos.

    Args:
        numero_limpio (str): Número del usuario sin símbolos.
        body (str): Mensaje del usuario.
        ctt: Instancia de Contacts.
        tx: Instancia de Transactions.
        msj: Instancia de Messages.
        contexto (str): Texto introductorio para el prompt.
        max_tokens (int): Máximo de tokens para la respuesta GPT.
        nodo_destino (int): Nodo destino al que se dirige el flujo (por ahora no se usa).

    Returns:
        str: Texto generado por GPT.
    """

    # 2) Buscar mensajes anteriores
    ultimo_mensaje = msj.get_latest_by_phone(numero_limpio)
    msg_key = ultimo_mensaje.msg_key
    pen_ultimo_mensaje = msj.get_penultimate_by_phone(numero_limpio)
    pen_ultimo_mensaje = pen_ultimo_mensaje.text

    # 3) Armar prompt
    next_node_question = "¿Tenes una cuenta bancaria?¿Es de comercio exterior?"
    prompt = (
        f"{contexto} "
        f"Teniendo en cuenta este historial y manteniendo un diálogo fluido: {conversation_str} "
        f"Ante esta pregunta: {pen_ultimo_mensaje} "
        f"el usuario contestó: {body} "
        f"Razonamiento: Podrías darle al usuario un breve consejo de no más de {max_tokens} tokens, "
        f"con foco en el potencial de importar y el valor que le podés aportar como despachante de aduana, "
        f"sin usar lugares comunes como 'Como despachante de aduana'. "
        f"Adicionalmente, hacé que la narrativa tienda a la siguiente pregunta: {next_node_question}"
    )

    aux_question_fofoca = [{"role": "assistant", "content": prompt}]

    # 4) GPT
    result = brain.ask_openai(aux_question_fofoca, temperature=0, model="gpt-4")
    print(result)

    return result




####### Next Node
body = "Yendo al proximo nodo"
nodo_destino = 3


####### Open AI - 2 answer question
import app.services.brain as brain

conversation_history.append({
    "role": "assistant",
    "content": "Mensaje:" + body + "; Question: Busca el el mensaje numero que tenga 7 u 8 dígitos. Si lo encontras responde únicamente con el número sin puntos, si no, responde con 0"
})

print(conversation_history)

result = brain.ask_openai(conversation_history, model="gpt-4", temperature=0)

print(result)


if result == "0":
    body = "Volve a ingresar tu DNI"
    nodo_destino = 3
else:
    body = result
    nodo_destino = 5


####### Open AI - n answer question
import app.services.brain as brain

'''