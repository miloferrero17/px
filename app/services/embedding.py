import openai
import os
from pinecone import Pinecone, ServerlessSpec
from datetime import datetime

# Cargar API keys
openai.api_key = os.getenv("OPENAI_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")

# Inicializar Pinecone
pc = Pinecone(api_key=pinecone_api_key)
index = pc.Index("test")  # Asegurate de que el índice exista

# Función para crear embeddings
def create_embedding(text):
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response['data'][0]['embedding']


'''
def generar_reporte_importacion(texto_articulo: str, top_k: int = 3) -> str:
    # Historial de conversación inicial
    conversation_history = [{
        "role": "assistant",
        "content": (
            "Sos un despachante de aduana experto en la legislación Argentina; tu libro principal es el "
            "NOMENCLATURA COMÚN DEL MERCOSUR (NCM) Y ARANCEL EXTERNO COMÚN (AEC) 2017. "
            "Siempre das la posición arancelaria más probable, sin rodeos."
        )
    }]

    # Pregunta original del usuario
    conversation_history.append({
        "role": "user",
        "content": f"Pregunta: {texto_articulo} Por favor respondeme únicamente con el código arancelario de Mercosur más probable. Sin texto."
    })

    # Generar embedding de la pregunta
    query_vector = create_embedding(texto_articulo)

    # Consultar Pinecone
    result = index.query(vector=query_vector, top_k=top_k, include_metadata=True)

    # Guardar IDs de archivos relevantes
    file_ids = set(match['id'].rsplit('_', 1)[0] for match in result["matches"])
    conversation_history.append({"role": "user", "content": "Books with higher correlation:"})
    for file_id in file_ids:
        conversation_history.append({"role": "user", "content": f"- {file_id}"})

    # Agregar contenido de las páginas encontradas
    for match in result["matches"]:
        if 'metadata' in match and 'text' in match['metadata']:
            conversation_history.append({
                "role": "user",
                "content": f"Answer:\n{match['metadata']['text']}\n"
            })

    # Pedido de respuesta inteligente basada solo en fuentes encontradas
    conversation_history.append({
        "role": "user",
        "content": "Could you please answer longly and intelligently the user question using only the sources you found?"
    })

    # Primera respuesta: código arancelario más probable
    codigo_arancelario = openai.ChatCompletion.create(
        model="gpt-4",
        messages=conversation_history,
        temperature=0
    ).choices[0].message.content

    # Agregar la respuesta como parte del historial
    conversation_history.append({
        "role": "assistant",
        "content": codigo_arancelario
    })

    # Segunda pregunta: el reporte completo
    conversation_history.append({
        "role": "user",
        "content": (
            "Podrías hacer un reporte que el despachante de aduana pueda darle al cliente. "
            "Incluyendo: 1) Código arancelario de Mercosur más probable. "
            "2) Costo del producto puesto en Buenos Aires. "
            "3) Entidades y trámites a realizar. "
            "4) Otros."
        )
    })

    # Pregunta final al modelo
    respuesta_final = openai.ChatCompletion.create(
        model="gpt-4",
        messages=conversation_history,
        temperature=0
    ).choices[0].message.content

    return respuesta_final
'''