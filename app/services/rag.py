import os
import openai
from pinecone import Pinecone
from typing import List

# Setup APIs
openai.api_key = os.getenv("OPENAI_API_KEY")
pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

def generar_reporte_desde_vector_search(
    prompt: str,
    cantidad_paginas: int,
    index_name: str,
    contexto: str,
    system_prompt: str = "Genera un reporte claro y detallado en base al contenido recuperado."
) -> str:
    # 1. Obtener embedding del prompt
    embedding_response = openai.Embedding.create(
        input=prompt,
        model="text-embedding-3-small"
    )
    prompt_vector = embedding_response['data'][0]['embedding']

    # 2. Buscar en Pinecone
    index = pinecone.Index(index_name)
    resultados = index.query(vector=prompt_vector, top_k=cantidad_paginas, include_metadata=True)

    # 3. Extraer textos relevantes
    textos = [match['metadata']['text'] for match in resultados['matches']]
    contenido = "\n\n".join(textos)

    # 4. Generar prompt final para OpenAI
    full_prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Contexto: {contexto}\n\nContenido:\n{contenido}\n\nInstrucción: {prompt}"}
    ]

    # 5. Llamar a OpenAI
    completion = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=full_prompt,
        temperature=0.2
    )

    return completion['choices'][0]['message']['content']

reporte = generar_reporte_desde_vector_search(
    prompt="Maquina de galletitas de arroz de 1000 USD FOB China",
    cantidad_paginas=3,
    index_name="test",
    contexto="Cuales son las 2 posiciones arrancelarias mas probables?"
)
print(reporte)