import os
import base64
import pdfplumber
import openai
import logging
import warnings
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Capturar warnings silenciosos de librerías como pdfplumber
warnings.filterwarnings("always")
logging.captureWarnings(True)


def encode_image(image_path):
    """
    Convierte una imagen en base64 para enviarla a la API de OpenAI.
    """
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


def describe_image(image_path):
    """
    Describe el contenido de una imagen usando GPT-4 Vision.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"❌ Imagen no encontrada en: {image_path}")

    base64_image = encode_image(image_path)

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Por favor continua la conversacion con un usuario pensando que el de la foto es el y resumile  los temas criticos de la foto en 500 caracteres para que se entienda fácilmente. Por favor, NO HAGAS PREGUNTAS NI SALUDES"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            #max_tokens=1000
        )

        if "choices" not in response or not response["choices"]:
            print("❌ La respuesta de OpenAI no contiene 'choices' válidos:", response)
            return "❌ No se pudo procesar la imagen. Intentalo de nuevo."

        content = response["choices"][0]["message"].get("content", "").strip()
        if not content:
            print("❌ El contenido devuelto está vacío:", response)
            return "❌ No se obtuvo descripción de la imagen."

        print("🧠 Descripción generada:", content)
        return content

    except Exception as e:
        print("❌ Error en describe_image:", str(e))
        return f"❌ Error procesando imagen: {str(e)}"


def resumir_texto_largo(texto_original, max_tokens=300):
    """
    Usa OpenAI GPT para resumir un texto largo.
    """
    if not texto_original or texto_original.strip() == "":
        return "❌ No se encontró texto para resumir."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"Por favor continua la conversacion con un usuario pensando que el archivo pdf es de el y resumile  los temas criticos del documento en NO MAS de 1000 caracteres para que se entienda fácilmente. Por favor, NO HAGAS PREGUNTAS NI SALUDES\n\n{texto_original}"
                }
            ],
            temperature=0
        )
        return response["choices"][0]["message"]["content"].strip()

    except Exception as e:
        return f"❌ Error al resumir el texto: {str(e)}"


def extract_text_from_pdf(pdf_path, max_chars=10000):
    """
    Extrae el texto de un PDF. Si es muy largo, lo resume automáticamente.
    """
    if not os.path.exists(pdf_path):
        return f"❌ No se encontró el archivo PDF: {pdf_path}"

    try:
        full_text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    text = page.extract_text() or ""
                    print(f"📄 Página {page_num + 1} — {len(text)} caracteres extraídos.")
                    full_text += text
                except Exception as e:
                    print(f"⚠️ Error al procesar página {page_num + 1}: {e}")

        if not full_text.strip():
            return "❌ El PDF no contiene texto legible."

        if len(full_text) > max_chars:
            return resumir_texto_largo(full_text)
        else:
            return full_text.strip()

    except Exception as e:
        return f"❌ Error al procesar el PDF: {str(e)}"