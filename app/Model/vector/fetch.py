import os
import openai
from pinecone import Pinecone
import tiktoken

# Config
INDEX_NAME = "test"         # <-- Cambiar si tu índice tiene otro nombre
NAMESPACE = "VCR"           # <-- Cambiar según el namespace que usaste
TOP_K = 5                   # ← Cantidad de chunks más relevantes

# Inicialización
openai.api_key = os.getenv("OPENAI_API_KEY")
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(INDEX_NAME)

# Tokenizer (útil si querés medir tokens en el futuro)
ENC = tiktoken.get_encoding("cl100k_base")


def get_prompt_embedding(prompt: str) -> list[float]:
    """Genera el embedding para el prompt del usuario."""
    response = openai.Embedding.create(
        input=prompt,
        model="text-embedding-ada-002"
    )
    return response["data"][0]["embedding"]


def buscar_chunks(prompt: str, top_k: int = TOP_K):
    """Busca los chunks más relevantes en Pinecone y los imprime."""
    embedding = get_prompt_embedding(prompt)

    results = index.query(
        vector=embedding,
        top_k=top_k,
        namespace=NAMESPACE,
        include_metadata=True
    )

    print(f"\n🔎 Resultados para: \"{prompt}\"\n")

    for i, match in enumerate(results["matches"], 1):
        metadata = match["metadata"]
        texto = metadata.get("text", "[Sin texto]")
        capitulo = metadata.get("chapter", "[Desconocido]")
        pagina = metadata.get("page", "[Desconocida]")
        chunk_index = metadata.get("chunk_index", "[?]")

        print(f"🧩 Chunk {i}:")
        print(f"📘 Capítulo: {capitulo}")
        print(f"📄 Página: {pagina} | 🧷 Chunk Index: {chunk_index}")
        print(f"🧠 Similaridad: {match['score']:.4f}")
        print(f"--- Texto ---\n{texto[:800]}{'...' if len(texto) > 800 else ''}\n")
        print("-" * 60)


if __name__ == "__main__":
    prompt = input("📥 Ingresá tu consulta: ")
    buscar_chunks(prompt)
