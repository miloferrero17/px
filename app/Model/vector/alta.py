import warnings

# ignore just that CropBox warning
warnings.filterwarnings(
    "ignore",
    message=r"CropBox missing from /Page, defaulting to MediaBox"
)
import logging

# silence pdfminer entirely (or change 'DEBUG' to 'WARNING' if you only want errors)
logging.getLogger("pdfminer").setLevel(logging.ERROR)

import pdfplumber
import re
import time
from collections import Counter
import os
import openai
from pinecone import Pinecone
from typing import List, Callable
import re
import numpy as np
import app.services.brain as brain
import json
import pikepdf
import csv
import tiktoken
from dataclasses import dataclass
from pathlib import Path


##################################################
# --- Paso 0: Set-up del enviroment
##################################################

#OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")


#Pinecode
pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
INDEX_NAME = "test"
#INDEX_NAME = input("Por favor ingrese el nombre del indice de la base de datos vectorial: ")
DIMENSION = 1536  # dims de text-embedding-ada-002
NAMESPACE = "chapters"  # <-- define aquí tu namespace


# Conectar al índice existente (crea si no existe)

if INDEX_NAME not in pinecone.list_indexes().names():
    pinecone.create_index(
        name=INDEX_NAME,
        dimension=DIMENSION,
        metric="cosine"
    )
index = pinecone.Index(INDEX_NAME)




##################################################
# --- Paso 1: Creo las funciones para convertir pdf -> txt_limpio
##################################################
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# aquí copias fix_hyphenation, extract_text, identify_noise_lines, clean_pages, normalize_text

def fix_hyphenation(text: str) -> str:
    return re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

def extract_text(pdf_path: str) -> list[str]:
    pages_out = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(
                x_tolerance=2,
                y_tolerance=1,
                keep_blank_chars=False,
                use_text_flow=True   # <-- en lugar de layout=True
            )
            lines: dict[float, list[dict]] = {}
            for w in words:
                y = round(w["top"], 1)
                lines.setdefault(y, []).append(w)
            page_lines = []
            for y in sorted(lines):
                row = sorted(lines[y], key=lambda w: w["x0"])
                page_lines.append(" ".join(w["text"] for w in row))
            pages_out.append("\n".join(page_lines))
    return pages_out


def identify_noise_lines(pages: list[str], hf_lines: int = 2, freq: float = 0.6):
    total = len(pages)
    hdr, ftr = Counter(), Counter()
    for text in pages:
        lines = text.split("\n")
        hdr.update(lines[:hf_lines])
        ftr.update(lines[-hf_lines:])
    header_noise = {l for l,c in hdr.items() if c/total >= freq}
    footer_noise = {l for l,c in ftr.items() if c/total >= freq}
    return header_noise, footer_noise

def clean_pages(pages: list[str], header_noise: set[str], footer_noise: set[str]):
    cleaned = []
    for text in pages:
        text = fix_hyphenation(text)
        kept = []
        for line in text.split("\n"):
            if (line in header_noise or
                line in footer_noise or
                re.match(r'^\s*\d+\s*$', line) or
                re.match(r'^[-_]{2,}\s*$', line)):
                continue
            kept.append(line)
        cleaned.append("\n".join(kept))
    return cleaned

def normalize_text(text: str) -> str:
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\S+@\S+', '', text)
    text = fix_hyphenation(text)
    text = text.replace('“','"').replace('”','"').replace("’","'")
    text = re.sub(r'[ ]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

import csv, time, re, tiktoken, openai
from dataclasses import dataclass
from typing import List
from tenacity import retry, stop_after_attempt, wait_random_exponential  # Retry con backoff exponencial para API calls

# Inicializa el tokenizer para el modelo de embeddings de OpenAI
ENC = tiktoken.get_encoding("cl100k_base")
MAX_TOKENS = 8191  # Límite de tokens para el modelo text-embedding-ada-002
NAMESPACE = "default"  # Espacio de nombres para Pinecone

def procesar_pdfs_en_carpeta(carpeta_path: str):
    carpeta = Path(carpeta_path)
    pdfs = list(carpeta.glob("*.pdf"))

    for pdf_file in pdfs:
        try:
            print(f"🧹 Procesando {pdf_file.name}...")

            # Paso 1: extraer texto
            raw_pages = extract_text(str(pdf_file))
            
            # Paso 2: identificar líneas de encabezado/pie ruidosas
            header_noise, footer_noise = identify_noise_lines(raw_pages)
            
            # Paso 3: limpiar
            cleaned_pages = clean_pages(raw_pages, header_noise, footer_noise)
            full_text = "\n\n".join(cleaned_pages)

            # Paso 4: normalizar
            texto_limpio = normalize_text(full_text)

            # Paso 5: guardar como .txt
            txt_path = pdf_file.with_suffix(".txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(texto_limpio)

            # Paso 6: eliminar el PDF
            pdf_file.unlink()
            print(f"✅ Guardado como {txt_path.name} y eliminado el PDF original.")
        
        except Exception as e:
            print(f"❌ Error procesando {pdf_file.name}: {e}")

procesar_pdfs_en_carpeta("app/Model/vector/Manuales Clara IA")


'''
# ------------------------------
# 2.1) UTILIDADES DE CHUNKING
# ------------------------------

def clean_text(text: str) -> str:
    """
    Normaliza el texto eliminando caracteres invisibles y espacios redundantes.
    Ayuda a reducir tokens innecesarios en el embedding.
    """
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def chunk_text(text: str, max_tokens: int = 300, overlap: int = 75) -> List[str]:
    """
    Divide un texto largo en varios "chunks" (bloques) de hasta `max_tokens` tokens,
    con un solape (`overlap`) para que la continuidad semántica no se pierda.
    El corte intenta respetar los párrafos y ajusta si un párrafo es muy largo.
    """
    paragraphs = [clean_text(p) for p in text.split("\n\n") if p.strip()]  # limpieza y eliminación de vacíos
    chunks = []
    current_tokens: List[int] = []

    for para in paragraphs:
        para_tokens = ENC.encode(para)

        # Si el párrafo es más largo que un chunk, se fragmenta
        if len(para_tokens) > max_tokens:
            if current_tokens:
                chunks.append(ENC.decode(current_tokens))
                current_tokens = []
            start = 0
            while start < len(para_tokens):
                end = min(start + max_tokens, len(para_tokens))
                chunk = para_tokens[start:end]
                chunks.append(ENC.decode(chunk))
                start += max_tokens - overlap
        else:
            # Si entra en el bloque actual, se agrega
            if len(current_tokens) + len(para_tokens) <= max_tokens:
                current_tokens += para_tokens
            else:
                # Si no entra, se cierra el bloque actual y se comienza uno nuevo con solape
                if current_tokens:
                    chunks.append(ENC.decode(current_tokens))
                current_tokens = para_tokens[-overlap:] if overlap < len(para_tokens) else para_tokens

    if current_tokens:
        chunks.append(ENC.decode(current_tokens))  # último bloque

    return chunks

# ------------------------------
# 2.2) LEER ÍNDICE CSV
# ------------------------------

def load_toc(csv_path: str) -> List[dict]:
    """
    Carga un CSV que tiene un índice con capítulos y páginas de inicio.
    Devuelve una lista ordenada de diccionarios con 'chapter' y 'start_page'.
    """
    toc = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            toc.append({
                "chapter": row["chapter"],
                "start_page": int(row["start_page"])
            })
    return sorted(toc, key=lambda x: x["start_page"])

def chapter_ranges(toc: List[dict], total_pages: int):
    """
    A partir del índice de capítulos (toc) y del total de páginas,
    genera tuplas con (nombre_capítulo, página_inicio, página_fin).
    """
    for i, ch in enumerate(toc):
        start = ch["start_page"]
        end = toc[i+1]["start_page"] - 1 if i+1 < len(toc) else total_pages
        yield ch["chapter"], start, end

# ------------------------------
# 2.3) DATACLASS PARA CADA CHUNK
# ------------------------------

@dataclass
class ChapterChunk:
    """
    Representa un bloque de texto (chunk) con su id único, texto y metadata asociada.
    """
    id: str
    text: str
    metadata: dict

# ------------------------------
# 2.4) CARGAR TEXTO PRE-PROCESADO
# ------------------------------

def load_cleaned_pages(path: str) -> List[str]:
    """
    Carga un archivo de texto preprocesado (uno que contiene las páginas ya limpias).
    Cada salto de dos líneas se considera una página.
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return content.split("\n\n")  # se asume que cada página está separada por doble salto de línea

# ------------------------------
# 2.5) EMBEDDINGS Y UPSERT EN PINECONE
# ------------------------------

@retry(stop=stop_after_attempt(5), wait=wait_random_exponential(min=1, max=10))
def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Llama a la API de OpenAI para obtener embeddings de una lista de textos.
    Se incluye lógica de retry inteligente ante errores temporales.
    """
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=texts
    )
    return [d["embedding"] for d in sorted(response["data"], key=lambda x: x["index"])]

def embed_and_upsert(chunks: List[ChapterChunk], batch_size: int = 50):
    """
    Embebe y sube los vectores a Pinecone en batches.
    Incluye limpieza del texto, retries, y pausa para evitar rate limiting.
    """
    batch_size = int(batch_size)
    for i in range(0, len(chunks), batch_size):
        #print(f"[DEBUG] batch_size type: {type(batch_size)} → {batch_size}")
        batch = chunks[i:i+batch_size]
        texts = [clean_text(c.text)[:3000] for c in batch]  # seguridad: truncado a 3000 caracteres por chunk
        ids   = [c.id for c in batch]

        try:
            vectors = get_embeddings(texts)
        except Exception as e:
            print(f"❌ Falló el batch {i // batch_size + 1}: {e}")
            continue  # saltea el batch con error

        to_upsert = [
            (ids[k], vectors[k], batch[k].metadata)
            for k in range(len(batch))
        ]

        index.upsert(vectors=to_upsert, namespace=NAMESPACE)
        print(f"✅ Upsert batch {i // batch_size + 1}/{(len(chunks) - 1) // batch_size + 1}")
        time.sleep(1.0)  # para evitar ser rate-limiteado por Pinecone o OpenAI
def vectorizar_documento(
    path_csv: str,
    path_txt: str,
    index,
    namespace: str = "default"
):
    """
    Flujo completo:
    1. Carga el índice y las páginas
    2. Chunkifica cada página dentro del rango del capítulo
    3. Embebe y sube a Pinecone
    """
    global NAMESPACE
    NAMESPACE = namespace

    toc = load_toc(path_csv)
    pages = load_cleaned_pages(path_txt)

    chunks = []
    for chapter, start, end in chapter_ranges(toc, len(pages)):
        for page_num in range(start, end + 1):
            page_text = pages[page_num - 1]
            chunk_list = chunk_text(page_text)
            for i, chunk in enumerate(chunk_list):
                chunks.append(ChapterChunk(
                    id=f"{chapter}_{page_num}_{i}",
                    text=chunk,
                    metadata={
                        "chapter": chapter,
                        "page": page_num,
                        "chunk_index": i,
                        "tokens": len(ENC.encode(chunk)),
                        "text": chunk
                    }
                ))

    embed_and_upsert(chunks, 50)

# ------------------------------
# USO
# ------------------------------


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(base_dir, "Visa Core Rules.pdf")
    
    # Paso 1: Extraer texto por página
    raw_pages = extract_text(pdf_path)

    # Paso 2: Identificar ruido (headers y footers comunes)
    header_noise, footer_noise = identify_noise_lines(raw_pages)

    # Paso 3: Limpiar páginas eliminando el ruido y líneas triviales
    cleaned_pages = clean_pages(raw_pages, header_noise, footer_noise)

    # Paso 4: Normalizar texto final
    full_text = "\n\n".join(cleaned_pages)
    final_text = normalize_text(full_text)

    # Paso 5: Guardar resultado en archivo de texto
    output_path = pdf_path.replace(".pdf", "_limpio.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_text)

    print(f"✅ Texto limpio guardado en: {output_path}")
    
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base_dir, "Visa Core Rules_limpio.txt")
    path_csv = os.path.join(base_dir, "indice.csv")
    vectorizar_documento(
        path_csv=path_csv,
        path_txt=output_path,
        index=index,
        namespace="VCR"  # o el namespace que uses
    )

# ------------------------------
# 2) VECTORIZACIÓN
# ------------------------------
# ------------------------------
# 2.1) UTILIDADES DE CHUNKING
# ------------------------------
ENC = tiktoken.get_encoding("cl100k_base")

def chunk_text(
    text: str,
    max_tokens: int = 300,
    overlap: int = 75
) -> List[str]:
    """
    Divide un texto en chunks de hasta max_tokens tokens,
    con overlap tokens de solape. Respeta saltos de párrafo.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_tokens: List[int] = []

    for para in paragraphs:
        para_tokens = ENC.encode(para)
        # Si el párrafo supera solo el límite:
        if len(para_tokens) > max_tokens:
            # Primero, vaciar bloque actual
            if current_tokens:
                chunks.append(ENC.decode(current_tokens))
                current_tokens = []
            # Luego fragmentar el párrafo largo
            start = 0
            while start < len(para_tokens):
                end = start + max_tokens
                chunk = para_tokens[start:end]
                chunks.append(ENC.decode(chunk))
                start += max_tokens - overlap
        else:
            # Si cabe en el bloque actual
            if len(current_tokens) + len(para_tokens) <= max_tokens:
                current_tokens += para_tokens
            else:
                # Cerrar bloque actual
                if current_tokens:
                    chunks.append(ENC.decode(current_tokens))
                # Iniciar nuevo bloque con solape
                current_tokens = para_tokens[-overlap:] if overlap < len(para_tokens) else para_tokens

    # Añadir el último bloque si quedó algo
    if current_tokens:
        chunks.append(ENC.decode(current_tokens))

    return chunks

# ------------------------------
# 2.2) LEER ÍNDICE CSV
# ------------------------------
def load_toc(csv_path: str) -> List[dict]:
    toc = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            toc.append({
                "chapter": row["chapter"],
                "start_page": int(row["start_page"])
            })
    return sorted(toc, key=lambda x: x["start_page"])

def chapter_ranges(toc: List[dict], total_pages: int):
    for i, ch in enumerate(toc):
        start = ch["start_page"]
        end = toc[i+1]["start_page"] - 1 if i+1 < len(toc) else total_pages
        yield ch["chapter"], start, end

# ------------------------------
# 2.3) DATACLASS PARA CADA CHUNK
# ------------------------------
@dataclass
class ChapterChunk:
    id: str
    text: str
    metadata: dict

# ------------------------------
# 2.4) CARGAR TEXTO PRE-PROCESADO
# ------------------------------
def load_cleaned_pages(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return content.split("\n\n")

# ------------------------------
# 2.5) EMBEDDINGS Y UPSERT EN PINECONE
# ------------------------------
def embed_and_upsert(
    chunks: List[ChapterChunk],
    batch_size: int = 50
):
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        texts = [c.text for c in batch]
        ids   = [c.id   for c in batch]
        resp  = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=texts
        )
        vectors = [d["embedding"] for d in resp["data"]]
        to_upsert = [
            (ids[k], vectors[k], batch[k].metadata)
            for k in range(len(batch))
        ]
        index.upsert(vectors=to_upsert, namespace=NAMESPACE)
        print(f"✅ Upsert batch {i//batch_size+1}/{(len(chunks)-1)//batch_size+1}")
        time.sleep(0.5)




def main():
    
    # 1) Cargar páginas limpias
    base_dir = os.path.dirname(os.path.abspath(__file__))
    texto_limpio = os.path.join(base_dir, "1_limpio.txt")
    pages = load_cleaned_pages(texto_limpio)
    total_pages = len(pages)
    print(f"📄 Total páginas detectadas: {total_pages}")
    
    # 2) Leer índice
    indice = os.path.join(base_dir, "indice.csv")

    toc = load_toc(indice)
    print("🔖 Capítulos detectados:")
    for ch in toc:
        print(f"  - {ch['chapter']} (página {ch['start_page']})")

    # 3) Generar chunks por capítulo
    all_chunks: List[ChapterChunk] = []
    for chap, start, end in chapter_ranges(toc, total_pages):
        text = "\n".join(pages[start-1 : end])
        for idx, chunk in enumerate(chunk_text(text), start=1):
            cid = f"{chap.replace(' ','_')}_chunk{idx:03d}"
            meta = {"chapter": chap, "start_page": start, "end_page": end}
            all_chunks.append(ChapterChunk(id=cid, text=chunk, metadata=meta))
    print(f"🔪 Total de chunks a procesar: {len(all_chunks)}")

    # 4) Embeddings y upsert
    embed_and_upsert(all_chunks)
    print("🎉 Vectorización por capítulos completada.")

if __name__ == "__main__":
    main()
'''


