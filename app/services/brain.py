import os
import time
from dotenv import load_dotenv
from openai import OpenAI
# Cargar variables de entorno y crear cliente
load_dotenv()  # ← ¡Esto es clave!
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)



#############################
# RESPONSE MODE
#############################
import os
from openai import OpenAI

def ask_openai(messages, temperature=0, model="gpt-4.1"):
    """
    Realiza una consulta a la API de OpenAI (Responses API) con los parámetros dados.

    Parámetros:
        messages (list o str):
            - Si es lista: historial de la conversación en formato [{'role':'user','content':'...'}, ...].
            - Si es string: prompt sencillo para el modelo.
        temperature (float): Configuración de temperatura para la creatividad de las respuestas.
        model (str): Nombre del modelo de OpenAI a utilizar (ej. "gpt-4o", "gpt-4o-mini", "o4-mini").

    Retorna:
        str: Respuesta generada por el modelo o un mensaje predeterminado en caso de error.
    """
    # Obtener la clave de API desde las variables de entorno
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("API key no encontrada. Configura la variable de entorno OPENAI_API_KEY.")

    # Inicializar el cliente de OpenAI
    client = OpenAI(api_key=api_key)

    try:
        # Llamada al Responses API
        response = client.responses.create(
            model=model,
            input=messages,
            temperature=temperature
        )

        # Retorna el texto generado (output_text)
        if hasattr(response, "output_text"):
            return response.output_text
        else:
            return "No se pudo generar una respuesta. Intenta de nuevo."
    except Exception as e:
        # Captura errores de la API
        raise RuntimeError(f"Error en la API de OpenAI (Responses API): {e}")



'''
def ask_openai(messages, temperature=0, model="gpt-4.1"):
    """
    Realiza una consulta a la API de OpenAI con los parámetros dados.

    Parámetros:
        messages (list): Lista de diccionarios que representan el historial de la conversación.
        temperature (float): Configuración de temperatura para la creatividad de las respuestas.
        model (str): Nombre del modelo de OpenAI a utilizar.

    Retorna:
        str: Respuesta generada por el modelo o un mensaje predeterminado en caso de error.
    """
    # Obtener la clave de API desde las variables de entorno
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("API key no encontrada. Configura la variable de entorno OPENAI_API_KEY.")

    # Configurar la clave de API para OpenAI
    openai.api_key = api_key

    try:
        # Llamada a la API de OpenAI
        completion = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature
        )

        # Retorna el contenido del mensaje de la primera elección
        if completion.choices and completion.choices[0].message:
            return completion.choices[0].message.content
        else:
            return "No se pudo generar una respuesta. Intenta de nuevo."
    except openai.error.OpenAIError as e:
        raise RuntimeError(f"Error en la API de OpenAI: {e}")

'''



#############################
# ASSISTANT MODE
#############################

# 1. Crear Assistant
def create_assistant(client):
    assistant = client.beta.assistants.create(
        name="MiloBot",
        instructions="Sos un experto en salud. Respondé preguntas médicas de forma clara y empática.",
        tools=[{"type": "code_interpreter"}],
        model="gpt-4o"
    )
    return assistant.id

# 2. Crear Thread
def create_thread(client):
    thread = client.beta.threads.create()
    return thread.id

# 3. Enviar mensaje, ejecutar run y obtener respuesta
def send_message_and_get_response(client, assistant_id, thread_id, message_text):
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=message_text
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )

    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        if run_status.status in ["completed", "failed", "cancelled", "expired"]:
            break
        time.sleep(1)

    messages = client.beta.threads.messages.list(thread_id=thread_id)
    for m in reversed(messages.data):
        if m.role == "assistant":
            return m.content[0].text.value

    return "❌ No se encontró respuesta del assistant."

'''
if __name__ == "__main__":

    message = "[{'role': 'system', 'content': 'Sos Huni, agente virtual de Hunitro, empresa especializada en mover mercaderia por el mundo. Tenes 40 años y sos un tipo techy. Su sueño es ayudar a sus clientes exporten e importen lo mas rapido y lo menos costoso posible.'}, {'role': 'user', 'content': 'no'}, {'role': 'assistant', 'content': 'Arranca en Etapa 1: Producto\n\nIniciá con una presentación breve y cálida utilizando 2 emojis. Luego, guiá la conversación con preguntas claras, una por una utilizando 2 emojis. Asegurate de entender: 1. ¿Sabes que queres importar? (Si no sabe que importar imprimi lo siguiente: Coordina una reunion de asesoría con Ignacio y da por cerrada la charla) 2. ¿Tenes la hoja de producto y/o proforma? ¿Me la podrías enviar? 3. Si no está detallado previamete ¿Me podrías describir con el mayor grado de detalle posible la función principal del producto? 4. Si no está detallado previamete ¿Cuanto pesa? 5. Si no está detallado previamete ¿Que dimensiones tiene? 6. Si no está detallado previamete ¿De que material esta hecho? Si el usuario no entiende, explicá con ejemplos concretos y simples. Si responde con dudas o contradicciones, pedí aclaración con amabilidad. Las cosas preguntalas de a una (i.e peso por un lado y dimensiones en otra pregunta).No pases a la siguiente pregunta sin entender bien la anterior. HACE LAS PREGUNTAS DE A UNA! Como output MANDATORIAMENTE necesito un string con 2 valores separados por una punto y coma (;), el primer valor la respuesta completa (sin ;) y el segundo un valor que refleje si las preguntas se terminaron o no. 0 si tenes que seguir haciendo preguntas o 1 si ya tenes toda la data recolectada (i.e.: ¿Sabes que queres importar?; 0\n\nEtapa 2: Planificación\nDale la bienvenida a la etapa del proceso y guiá la conversación con preguntas claras, una por una utilizando 2 emojis. Asegurate de entender:\n1. ¿Tenes la cantidad definida?\n2. ¿Tenes fecha para traer el producto?\n3. ¿Donde se entrega?\n'}, {'role': 'assistant', 'content': '¡Hola! 👋🚀 Soy Huni, tu agente virtual de Hunitro. Estoy acá para ayudarte a importar o exportar tu mercadería de la forma más rápida y económica posible.\n\nPara empezar, ¿sabés qué producto querés importar o exportar? 😊📦\n\n¿Sabes que queres importar?'}, {'role': 'user', 'content': 'hol'}, {'role': 'assistant', 'content': 'Arranca en Etapa 1: Producto\n\nIniciá con una presentación breve y cálida utilizando 2 emojis. Luego, guiá la conversación con preguntas claras, una por una utilizando 2 emojis. Asegurate de entender: 1. ¿Sabes que queres importar? (Si no sabe que importar imprimi lo siguiente: Coordina una reunion de asesoría con Ignacio y da por cerrada la charla) 2. ¿Tenes la hoja de producto y/o proforma? ¿Me la podrías enviar? 3. Si no está detallado previamete ¿Me podrías describir con el mayor grado de detalle posible la función principal del producto? 4. Si no está detallado previamete ¿Cuanto pesa? 5. Si no está detallado previamete ¿Que dimensiones tiene? 6. Si no está detallado previamete ¿De que material esta hecho? Si el usuario no entiende, explicá con ejemplos concretos y simples. Si responde con dudas o contradicciones, pedí aclaración con amabilidad. Las cosas preguntalas de a una (i.e peso por un lado y dimensiones en otra pregunta).No pases a la siguiente pregunta sin entender bien la anterior. HACE LAS PREGUNTAS DE A UNA! Como output MANDATORIAMENTE necesito un string con 2 valores separados por una punto y coma (;), el primer valor la respuesta completa (sin ;) y el segundo un valor que refleje si las preguntas se terminaron o no. 0 si tenes que seguir haciendo preguntas o 1 si ya tenes toda la data recolectada (i.e.: ¿Sabes que queres importar?; 0\n\nEtapa 2: Planificación\nDale la bienvenida a la etapa del proceso y guiá la conversación con preguntas claras, una por una utilizando 2 emojis. Asegurate de entender:\n1. ¿Tenes la cantidad definida?\n2. ¿Tenes fecha para traer el producto?\n3. ¿Donde se entrega?\n'}]"
    result = ask_openai(message)
    print(result)
'''

################
# File Vector
################

# 2. Create a new vector store named "Financial Statements"
''' assistant_id = create_assistant(client)
    vector_store = client.vector_stores.create(name="Scheme Enablers")

    # 3. List the file paths. If goog-10k.pdf and brka-10k.txt are in the same folder as this script,
    #    just use their filenames directly. Otherwise, include the relative path (e.g. "edgar/goog-10k.pdf").
    file_paths = [
        "app/services/Authorization Manual.pdf"
    ]


    # 4. Open each file in binary mode
    file_streams = [open(path, "rb") for path in file_paths]

    # 5. Upload them to the vector store and wait for the batch to finish
    file_batch = client.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id,
        files=file_streams
    )

    # 6. Close all file handles now that they’ve been uploaded
    for f in file_streams:
        f.close()

    # 7. Print status and counts to verify everything worked
    print("Batch status:", file_batch.status)
    print("Number of files added:", file_batch.file_counts)
    print(vector_store)
    
    assistant = client.beta.assistants.update(
        assistant_id=assistant_id,
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        )
    thread_id = create_thread(client)
    respuesta = send_message_and_get_response(client, assistant_id, thread_id, "¿Cuáles son las obligaciones del adquirente con respecto al almacenamiento y manejo de los datos de la tarjeta?")
    print("💬", respuesta)

    assistant_id = create_assistant(client)
    thread_id = create_thread(client)
    respuesta = send_message_and_get_response(client, assistant_id, thread_id, "¿Qué puedo tomar si tengo dolor de culo?")
    print("💬", respuesta)

'''
