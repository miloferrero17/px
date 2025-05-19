import fitz  # PyMuPDF
import openai
import numpy as np
import os
from pinecone import Pinecone, ServerlessSpec

# Configura tus claves de API
openai.api_key = os.getenv("OPENAI_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")

# Inicializar Pinecone
pc = Pinecone(api_key=pinecone_api_key)

# Nombre del índice

index_name = input("Por favor ingrese el index que quiere eliminar: ")

# Eliminar el índice completo
pc.delete_index(index_name)

# Opcional: Recrear el índice
pc.create_index(
    name=index_name,
    dimension=1536,  # Ajusta según la dimensión de tu modelo de embeddings
    metric="cosine",
    spec=ServerlessSpec(
        cloud="aws",
        region="us-east-1"
    )
)