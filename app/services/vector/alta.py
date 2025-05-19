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
def fix_hyphenation(text: str) -> str:
    """
    Junta palabras cortadas con guión al final de línea.
    """
    return re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)


def extract_text(pdf_path: str) -> list[str]:
    """
    Extrae el texto de cada página del PDF.
    Devuelve una lista de strings, una por página.
    """
    with pdfplumber.open(pdf_path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def identify_noise_lines(pages: list[str], hf_lines: int = 2, freq: float = 0.6) -> tuple[set[str], set[str]]:
    """
    Identifica líneas frecuentes al inicio (header) y fin (footer).
    Devuelve dos sets: header_noise, footer_noise.
    """
    total = len(pages)
    hdr = Counter()
    ftr = Counter()
    for text in pages:
        lines = text.split("\n")
        hdr.update(lines[:hf_lines])
        ftr.update(lines[-hf_lines:])

    header_noise = {l for l, c in hdr.items() if c / total >= freq}
    footer_noise = {l for l, c in ftr.items() if c / total >= freq}
    return header_noise, footer_noise


def clean_pages(pages: list[str], header_noise: set[str], footer_noise: set[str]) -> list[str]:
    """
    Limpia cada página: quita headers, footers, numeración aislada y líneas de guiones.
    También aplica fix_hyphenation.
    """
    cleaned = []
    for text in pages:
        text = fix_hyphenation(text)
        lines = text.split("\n")
        filtered = [line for line in lines
                    if line not in header_noise
                    and line not in footer_noise
                    and not re.match(r'^\s*\d+\s*$', line)
                    and not re.match(r'^[-_]{2,}\s*$', line)]
        cleaned.append("\n".join(filtered))
    return cleaned


def normalize_text(text: str) -> str:
    """
    Normaliza texto: elimina URLs, e-mails, convierte a minúsculas, limpia caracteres extraños.
    """
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\S+@\S+', '', text)
    text = fix_hyphenation(text)
    text = text.lower()
    text = text.replace('“', '"').replace('”', '"').replace("’", "'")
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n{2,}', '\n\n', text)
    text = re.sub(r'[^\x20-\x7EáéíóúñüÁÉÍÓÚÑÜ]+', '', text)
    return text.strip()


def recortar_pdf(input_path: str, output_path: str, n: int = 1) -> None:
    """
    Genera un PDF con las primeras n páginas del PDF de entrada.
    """
    with pdfplumber.open(input_path) as pdf:
        total = len(pdf.pages)
        to_cut = min(n, total)

    with pikepdf.Pdf.open(input_path) as src:
        dst = pikepdf.Pdf.new()
        for i in range(to_cut):
            dst.pages.append(src.pages[i])
        dst.save(output_path)

    print(f"Recortado: {to_cut}/{total} páginas en '{output_path}'")

def is_index_page(text: str) -> bool:
    """
    Usa OpenAI para determinar si un bloque de texto es parte de la Tabla de Contenidos.
    Responde True si la IA responde 'SI'.
    """
    prompt = (
        "¿Este texto corresponde a una página de índice o Tabla de Contenidos?"
        "Responde SOLO 'SI' o 'NO'.\n\n" + text[:2000]
    )
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    answer = resp.choices[0].message.content.strip().upper()
    return answer == "SI"


def find_toc_pages(pages: list[str]) -> tuple[int, int] | tuple[None, None]:
    """
    Encuentra las páginas de inicio y fin de la Tabla de Contenidos.
    Devuelve (inicio, fin) en base 1, o (None, None) si no se detecta.
    """
    start = None
    for idx, pg in enumerate(pages):
        if is_index_page(pg):
            start = idx + 1
            break
    if start is None:
        return None, None

    end = start
    for pg in pages[start:]:
        if is_index_page(pg):
            end += 1
        else:
            break
    return start, end


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_pdf = os.path.join(base_dir, "Visa Core Rules_100.pdf")
    recort_pdf_path = os.path.join(base_dir, "recortar_pdf.pdf")
    texto_limpio_txt = os.path.join(base_dir, "texto_limpio.txt")

    # Paso 1: recortar PDF y extraer texto
    recortar_pdf(input_pdf, recort_pdf_path, n=50)
    pages = extract_text(recort_pdf_path)

    # Paso 2: limpiar ruido y normalizar
    hdr_noise, ftr_noise = identify_noise_lines(pages)
    cleaned_pages = clean_pages(pages, hdr_noise, ftr_noise)
    with open(texto_limpio_txt, 'w', encoding='utf-8') as f:
        for pg in cleaned_pages:
            f.write(normalize_text(pg) + "\n\n")
    print(f"ETL terminado. Archivo creado: '{texto_limpio_txt}'")

    # 3) Detectar TOC
    toc_start, toc_end = find_toc_pages(cleaned_pages)
    if toc_start and toc_end:
        print(f"Tabla de Contenidos detectada desde la página {toc_start} hasta la {toc_end}.")
        print("\n-- Contenido de la Tabla de Contenidos --")
        for i in range(toc_start-1, toc_end):
            toc_text = normalize_text(cleaned_pages[i])
            print(f"\n==== Página {i+1} ====\n{toc_text}")
    else:
        print("No se detectó Tabla de Contenidos con IA.")

'''
if __name__ == "__main__":
    # Directorio base y paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_pdf = os.path.join(base_dir, "Visa Core Rules_100.pdf")
    recort_pdf_path = os.path.join(base_dir, "recortar_pdf.pdf")
    texto_limpio_txt = os.path.join(base_dir, "texto_limpio.txt")

    # Paso 1: recortar PDF
    recortar_pdf(input_pdf, recort_pdf_path, n=50)

    # Paso 2: extraer y limpiar texto
    pages = extract_text(recort_pdf_path)
    hdr_noise, ftr_noise = identify_noise_lines(pages)
    cleaned_pages = clean_pages(pages, hdr_noise, ftr_noise)

    # Paso 3: normalizar y volcar a TXT
    with open(texto_limpio_txt, 'w', encoding='utf-8') as f:
        for pg in cleaned_pages:
            f.write(normalize_text(pg) + "\n\n")

    print(f"ETL terminado. Archivo creado: '{texto_limpio_txt}'")
    
    brain.ask_openai()

    

def extract_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]

def identify_noise_lines(pages, hf_lines=2, freq=0.6):
    hdr, ftr = Counter(), Counter()
    total = len(pages)
    for text in pages:
        lines = text.split("\n")
        hdr.update(lines[:hf_lines])
        ftr.update(lines[-hf_lines:])
    header_noise = {l for l,c in hdr.items() if c/total >= freq}
    footer_noise = {l for l,c in ftr.items() if c/total >= freq}
    return header_noise, footer_noise

def clean_pages(pages, header_noise, footer_noise):
    cleaned = []
    for text in pages:
        # 1) corrige guiones, 2) split lines y filtra ruido
        text = fix_hyphenation(text)
        lines = text.split("\n")
        lines = [
            line for line in lines
            if line not in header_noise
            and line not in footer_noise
            and not re.match(r'^\s*\d+\s*$', line)
            and not re.match(r'^[-_]{2,}\s*$', line)
        ]
        cleaned.append("\n".join(lines))
    return cleaned

def normalize_text(text):
    # URLs y e-mails
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\S+@\S+', '', text)
    # espacios y líneas en blanco
    text = fix_hyphenation(text)
    text = text.lower()
    text = text.replace('“','"').replace('”','"').replace("’","'")
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n{2,}', '\n\n', text)
    text = re.sub(r'[^\x20-\x7EáéíóúñüÁÉÍÓÚÑÜ]+','', text)
    return text.strip()

def fix_hyphenation(text: str) -> str:
    """
    Junta palabras cortadas con guión al final de línea.
    """
    return re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)


##################################################
# --- Paso 2: Creo las obtener las páginas de TOC
##################################################
def recortar_pdf(input_path: str, output_path: str, n: int = 50):
    """
    Crea un PDF con las primeras n páginas del PDF de entrada,
    usando pdfplumber para contar/examinar y pikepdf para escribir.

    :param input_path: Ruta al PDF original.
    :param output_path: Ruta donde se guardará el PDF recortado.
    :param n: Número de páginas a incluir (por defecto 50).
    """
    # 1) Abrimos con pdfplumber solo para saber cuántas páginas tiene
    with pdfplumber.open(input_path) as pdf:
        total_paginas = len(pdf.pages)
        paginas_a_recortar = min(n, total_paginas)

    # 2) Abrimos con pikepdf para extraer y escribir
    with pikepdf.Pdf.open(input_path) as src:
        dst = pikepdf.Pdf.new()
        for i in range(paginas_a_recortar):
            dst.pages.append(src.pages[i])
        dst.save(output_path)

    print(f"Se han guardado {paginas_a_recortar} de {total_paginas} páginas en «{output_path}».")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_pdf = os.path.join(base_dir, "Visa Core Rules_100.pdf")    
    ouput_pdf = os.path.join(base_dir, "recortar_pdf.pdf")    
    recortar_pdf(input_pdf, ouput_pdf, n=50)
    pages = extract_text(ouput_pdf)
    hdr_noise, ftr_noise = identify_noise_lines(pages)
    cleaned = clean_pages(pages, hdr_noise, ftr_noise)
    with open(ouput_pdf,"w",encoding="utf-8") as f:
       for p in cleaned:
            f.write(normalize_text(p) + "\n\n")
    print("ETL Terminado")









import os
from typing import List, Callable
from app.services.brain import ask_openai

##################################################
# --- Paso 2: División de TOC y Contenido
##################################################

def is_index_page(text: str) -> bool:
    """
    Pregunta a OpenAI si este texto es un índice.
    Devuelve True solo si responde 'SI'.
    """
    prompt = (
        "¿Este texto parece ser un índice de contenidos? "
        "Responde SOLO 'SI' o 'NO'.\n\n"
        + text[:2000]
    )
    resp = ask_openai(messages=[{"role": "user", "content": prompt}])
    return resp.strip().upper() == "SI"


def find_content_start(
    pages: List[str],
    is_index_fn: Callable[[str], bool],
    max_checks: int = 50,
    consecutive_needed: int = 2
) -> int:
    """
    1) Encuentra la PRIMERA página que is_index_fn() clasifica como índice
    2) Desde ahí, busca cuándo terminan esas páginas de índice:
       tras `consecutive_needed` NO seguidos, devuelve la posición
       (0‐based) donde arranca el contenido.
    Si no hay índice en max_checks páginas, devuelve 0 (todo es contenido).
    """
    # 1) Buscar la primera página de índice
    first_index = None
    for i, text in enumerate(pages[:max_checks]):
        if is_index_fn(text):
            first_index = i
            break

    # Si nunca encontramos índice, el contenido arranca en la página 0
    if first_index is None:
        return 0

    # 2) A partir de first_index, detectar fin del índice
    non_index_count = 0
    for j in range(first_index, len(pages)):
        if not is_index_fn(pages[j]):
            non_index_count += 1
            if non_index_count >= consecutive_needed:
                # contenido inicia en la primera de esas NO consecutivas
                return j - (consecutive_needed - 1)
        else:
            non_index_count = 0

    # Si nunca hubo suficientes NO, entonces todo hasta el final fue índice
    return len(pages)


def split_index_content(
    pages: List[str],
    is_index_fn: Callable[[str], bool],
    max_checks: int = 50,
    consecutive_needed: int = 2
) -> (List[str], List[str]):
    """
    Devuelve dos listas:
      - index_pages: el bloque de páginas que is_index_fn clasifica como índice
      - content_pages: TODO lo demás (previo y posterior al índice)
    """
    # Encuentra dónde empieza el contenido
    start = find_content_start(pages, is_index_fn, max_checks, consecutive_needed)

    # Localiza la primera página de índice dentro de las primeras 'start' páginas
    idx_start = None
    for i, text in enumerate(pages[:start]):
        if is_index_fn(text):
            idx_start = i
            break

    # Si no había índice, todo es contenido
    if idx_start is None:
        return [], pages

    # El final del bloque de índice es start-1
    idx_end = start - 1

    # Cortes usando índices enteros
    index_pages = pages[idx_start : idx_end + 1]
    content_pages = pages[:idx_start] + pages[idx_end + 1 :]

    return index_pages, content_pages


def load_cleaned_pages(txt_path: str) -> List[str]:
    """
    Carga el TXT limpio y lo parte en páginas.
    Asume que cada página terminó con '\n\n' al guardar.
    """
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    # Cada página se separa con doble salto de línea:
    return text.split("\n\n")


def save_pages(pages: List[str], out_path: str):
    """
    Guarda una lista de páginas en un TXT, uniendo con '\n\n'.
    """
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(pages))


if __name__ == "__main__":
    # 1) Cargo las “páginas” del TXT limpio
    base_dir = os.path.dirname(os.path.abspath(__file__))
    clean_txt = os.path.join(base_dir, "txt_limpio.txt")
    pages = load_cleaned_pages(clean_txt)

    # 2) Divido en índice y contenido
    index_pages, content_pages = split_index_content(
        pages,
        is_index_page,       # función que llama a OpenAI
        max_checks=50,
        consecutive_needed=2
    )

    # 3) Guardo resultados
    save_pages(index_pages, os.path.join(base_dir, "texto_limpio_indice.txt"))
    save_pages(content_pages, os.path.join(base_dir, "texto_limpio_contenido.txt"))

    print(f"Detecté {len(index_pages)} páginas de índice y {len(content_pages)} de contenido.")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dirty_pdf = os.path.join(base_dir, "Visa Core Rules_100.pdf")
    clean_txt = os.path.join(base_dir, "txt_limpio.txt")
    pages = extract_text(dirty_pdf)
    hdr_noise, ftr_noise = identify_noise_lines(pages)
    cleaned = clean_pages(pages, hdr_noise, ftr_noise)
    with open(clean_txt,"w",encoding="utf-8") as f:
       for p in cleaned:
            f.write(normalize_text(p) + "\n\n")
    print("ETL Terminado")


def detect_index_pages_via_llm(pdf_path: str,
                               max_pages: int = 20,
                               chars_per_page: int = 2000) -> List[int]:
    """
    Lee las primeras max_pages del PDF, toma hasta chars_per_page caracteres de cada página,
    y pregunta al LLM: “¿Qué páginas parecen índice?”.
    Devuelve un listado de números de página (1-based).
    """
    # 1) Extraer texto resumido de las primeras max_pages páginas
    snippets = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages], start=1):
            txt = (page.extract_text() or "").replace("\n", " ")
            snippets.append(f"PÁGINA {i}: “{txt[:chars_per_page]}”")
    # 2) Construir prompt
    prompt = (
        "Tengo un documento cuyas primeras páginas son:\n\n"
        + "\n\n".join(snippets)
        + "\n\n¿Cuáles de estas páginas parecen corresponder a la tabla de contenidos "
          "o índice? Devuélveme SOLO un array JSON de números de página (1-based)."
    )
    # 3) Llamar al LLM
    resp = brain.ask_openai(messages=[{"role":"user","content":prompt}])
    
    # 4) Parsear la respuesta como JSON
    try:
        pages = json.loads(resp)
        if isinstance(pages, list) and all(isinstance(n, int) for n in pages):
            return pages
    except json.JSONDecodeError:
        pass
    # En caso de fallo, volvemos al método anterior
    return []

# Ejemplo de uso
if __name__ == "__main__":
    pdf_path = "app/services/vector/Visa Core Rules_100.pdf"
    index_pages = detect_index_pages_via_llm(pdf_path)
    print("Páginas de índice detectadas:", index_pages)




def es_indice(texto_pagina):
    """Devuelve True si el LLM considera que este texto es un índice."""
    prompt = (
        "¿Luce este texto como un índice de contenidos? "
        "Responde SOLO 'SI' o 'NO'.\n\n"
        + texto_pagina[:2000]  # limitar a los primeros 2000 caracteres
    )
    resp = brain.ask_openai(messages=[{"role":"user","content":prompt}])
    answer = resp.strip().upper()
    return answer == "SI"

def detectar_rango_toc(pdf_path, max_sins=2):
    rango = []
    sin_cont = 0
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            texto = page.extract_text() or ""
            if es_indice(texto):
                rango.append(i)        # índice basado en 0
                sin_cont = 0
            elif rango:
                # ya arrancó el índice y encontramos un NO
                sin_cont += 1
                if sin_cont >= max_sins:
                    break
    # Ajustamos al rango continuo desde el primer hasta el último índice detectado
    if not rango:
        return []
    return list(range(rango[0], rango[-1] + 1))




##################################################
# --- Paso 3: Embedding y upsert de TOC
##################################################

def extract_toc_entries(pdf_path: str, pages_toc: List[int]) -> List[dict]:
    """
    Extrae entradas de índice de las páginas detectadas.
    Cada entry: {'id','text','chapter','title','page'}.
    """
    entries = []
    pattern = re.compile(r'^(\d+(?:\.\d+){0,2})\s*(.+?)\s+(\d+)$')
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pages_toc:
            text = pdf.pages[pg].extract_text() or ""
            for line in text.split("\n"):
                m = pattern.match(line.strip())
                if m:
                    chapter, title, pno = m.group(1), m.group(2), int(m.group(3))
                    entries.append({
                        "id":      f"toc-{chapter}-{pno}",
                        "text":    f"{chapter} {title}",
                        "chapter": chapter,
                        "title":   title,
                        "page":    pno
                    })
    return entries


def embed_toc_entries(entries: List[dict], batch_size: int = 16) -> List[list]:
    """
    Genera embeddings batch y aplica L2‑normalización.
    """
    embeddings = []
    for i in range(0, len(entries), batch_size):
        batch = [e["text"] for e in entries[i:i + batch_size]]
        resp = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=batch
        )
        for item in resp["data"]:
            vec = np.array(item["embedding"])
            embeddings.append((vec / np.linalg.norm(vec)).tolist())
    return embeddings


def upsert_toc(entries: List[dict], embeddings: List[List[float]], namespace: str = "toc", upsert_batch_size: int = 50):
    """
    Sube vectores a Pinecone en batches para evitar payload demasiado grande.
    """
    all_vectors = []
    for entry, vec in zip(entries, embeddings):
        all_vectors.append((
            entry["id"],
            vec,
            {"chapter": entry["chapter"], "title": entry["title"], "page": entry["page"]}
        ))
    # Ejecutar upserts en lotes
    for i in range(0, len(all_vectors), upsert_batch_size):
        batch = all_vectors[i : i + upsert_batch_size]
        index.upsert(vectors=batch, namespace=namespace)





###################################################
# --- Paso 4: Chunking, embedding y upsert de CONTENIDO
##################################################

def chunk_text(cleaned_txt_path: str, pages_to_skip: List[int], chunk_chars: int = 4000, overlap_chars: int = 800) -> List[dict]:
    """
    Lee el TXT limpio, lo divide en chunks de ~chunk_chars con overlap de overlap_chars,
    excluyendo las páginas cuyo índice (0-based) esté en pages_to_skip.
    Devuelve lista de dicts con: id, text, page_start, page_end.
    """
    # Leer y separar páginas (doble salto indica cambio de página)
    with open(cleaned_txt_path, "r", encoding="utf-8") as f:
        pages = f.read().split("\n\n")
    entries = []
    for page_no, page_text in enumerate(pages, start=1):
        # Saltar páginas de TOC
        if (page_no - 1) in pages_to_skip:
            continue
        length = len(page_text)
        start = 0
        while start < length:
            end = start + chunk_chars
            chunk = page_text[start:end]
            entry_id = f"content-{page_no}-{start}"
            entries.append({
                "id":         entry_id,
                "text":       chunk,
                "page_start": page_no,
                "page_end":   page_no
            })
            # avanzar con overlap
            start += (chunk_chars - overlap_chars)
    return entries


def embed_content_entries(entries: List[dict],
                          batch_size: int = 16) -> List[List[float]]:
    """
    Genera embeddings batch y aplica L2-normalización.
    """
    embeddings = []
    for i in range(0, len(entries), batch_size):
        batch_texts = [e["text"] for e in entries[i:i+batch_size]]
        resp = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=batch_texts
        )
        for rec in resp["data"]:
            vec = np.array(rec["embedding"])
            embeddings.append((vec / np.linalg.norm(vec)).tolist())
    return embeddings


def upsert_content(entries: List[dict],
                   embeddings: List[List[float]],
                   namespace: str = "content",
                   upsert_batch_size: int = 50):
    """
    Sube vectores con metadata page_start/page_end a Pinecone en batches.
    """
    all_vecs = []
    for e, vec in zip(entries, embeddings):
        all_vecs.append((
            e["id"],
            vec,
            {"page_start": e["page_start"], "page_end": e["page_end"]}
        ))
    for i in range(0, len(all_vecs), upsert_batch_size):
        batch = all_vecs[i:i+upsert_batch_size]
        index.upsert(vectors=batch, namespace=namespace)




##################################################
# --- Ejecución completa del pipeline
##################################################
if __name__ == "__main__":
    pdf_path = "app/services/vector/Visa Core Rules_100.pdf"

    # Paso 2: Detección de páginas de TOC
    pages_toc = detectar_rango_toc(pdf_path)
    print(f"Páginas de TOC detectadas (1-based): {[p+1 for p in pages_toc]}")

    # Paso 3: Extracción y vectorización de TOC
    toc_entries = extract_toc_entries(pdf_path, pages_toc)
    print(f"Total entradas TOC: {len(toc_entries)}")
    toc_embeddings = embed_toc_entries(toc_entries)
    print("Embeddings de TOC generados.")
    upsert_toc(toc_entries, toc_embeddings)
    print("TOC embedded y upsert completado en namespace 'toc'.")

    # Paso 4: Procesar contenido limpiado excluyendo TOC
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cleaned_txt = os.path.join(base_dir, "cleaned_visa_manual.txt")
    content_entries = chunk_text(cleaned_txt, pages_to_skip=pages_toc)
    print(f"Total content chunks (sin TOC): {len(content_entries)}")
    content_embeddings = embed_content_entries(content_entries)
    print("Embeddings de contenido generados.")
    upsert_content(content_entries, content_embeddings)
    print("Contenido embebido y subido en namespace 'content'.")


if __name__ == "__main__":
    pdf_path = "app/services/vector/Visa Core Rules_100.pdf" 
    
    # 1) Extraer texto
    pages = extract_text(pdf_path)
    print(f"Extraído texto de {len(pages)} páginas.")
    
    # 2) Identificar encabezados/pies de página repetidos
    header_noise, footer_noise = identify_noise_lines(pages)
    print("Encabezados detectados como ruido:", header_noise)
    print("Pies de página detectados como ruido:", footer_noise)
    
    # 3) Limpiar páginas y normalizar
    cleaned_pages = clean_pages(pages, header_noise, footer_noise)
    normalized_pages = [normalize_text(p) for p in cleaned_pages]
    
    # ——— Punto de comprobación ———
    for i in range(min(3, len(pages))):
        print(f"\n=== Página {i+1} ORIGINAL ===")
        print(pages[i][:200], '…')                # primeros 200 chars de la página original
        print(f"\n=== Página {i+1} LIMPIADA ===")
        print(cleaned_pages[i][:200], '…')        # después de quitar encabezados/pies
        print(f"\n=== Página {i+1} NORMALIZADA ===")
        print(normalized_pages[i][:200], '…')     # además en minúsculas y sin ruido
        print("\n" + "-"*40)
    
    
    # 4) Guardar resultado
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_path_txt_full = os.path.join(base_dir, "cleaned_visa_manual.txt")
    with open(output_path_txt_full, "w", encoding="utf-8") as f:
        for page in normalized_pages:
            f.write(page + "\n\n")
    
    # Detección de páginas de TOC
    pages_toc = detectar_rango_toc(pdf_path)
    print(f"Páginas de TOC detectadas (1-based): {[p+1 for p in pages_toc]}")

    
    # Extracción de entradas
    toc_entries = extract_toc_entries(pdf_path, pages_toc)
    print(f"Total entradas TOC: {len(toc_entries)}")

    # Embedding batch
    toc_embeddings = embed_toc_entries(toc_entries)
    print("Embeddings generados.")

    # Upsert en Pinecone
    upsert_toc(toc_entries, toc_embeddings)
    print("Toc embedded y upsert completado en namespace 'toc'.")

'''