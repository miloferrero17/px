import os
import base64
import pdfplumber
import logging
import warnings

from dotenv import load_dotenv
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import app.services.twilio_service as twilio
from openai import OpenAI

# Cargar variables de entorno
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Capturar warnings silenciosos de librerías como pdfplumber
warnings.filterwarnings("always")
logging.captureWarnings(True)

def encode_image(image_path):
    """
    Convierte una imagen en base64 para enviarla a la API de OpenAI.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"❌ Imagen no encontrada en: {image_path}")

    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def describe_image(image_path):
    """
    Describe el contenido de una imagen usando la Responses API (GPT-4 Vision).
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"❌ Imagen no encontrada en: {image_path}")

    # Codificar la imagen a Base64 (para usar data URI)
    base64_image = encode_image(image_path)

    try:
        response = client.responses.create(
            model="gpt-4o",
            input=[
                {
                    "role": "user",
                    "content": "Por favor, continua la conversación pensando que quien aparece en la foto es el usuario, y resume los temas críticos de la imagen en no más de 1000 caracteres para que se entienda fácilmente. Por favor, NO HAGAS PREGUNTAS NI SALUDOS. En caso de ser una credencial o un comprobante extrae la información clave"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{base64_image}",
                        }
                    ]
                }
            ]
        )

        content = response.output_text.strip()
        if not content:
            print("❌ El contenido devuelto está vacío:", response)
            return "❌ No se obtuvo descripción de la imagen."

        print("🧠 Descripción generada:", content)
        return content

    except Exception as e:
        print("❌ Error en describe_image:", str(e))
        return f"❌ Error procesando imagen: {str(e)}"


import os
from openai import OpenAI

def resumir_texto_largo(texto_original):
    """
    Usa OpenAI GPT (Responses API) para resumir un texto largo en ~1000 caracteres.

    Parámetros:
        texto_original (str): El texto que se quiere resumir.

    Retorna:
        str: Resumen generado por el modelo, o un mensaje de error si ocurre algún problema.
    """
    # Validar que haya texto
    if not texto_original or texto_original.strip() == "":
        return "❌ No se encontró texto para resumir."

    # Obtener la clave de API desde la variable de entorno
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("API key no encontrada. Configura la variable de entorno OPENAI_API_KEY.")

    # Inicializar el cliente de OpenAI
    client = OpenAI(api_key=api_key)

    try:
        # Construir el prompt como un único string, igual que antes
        prompt = (
            "Por favor continua la conversación con un usuario pensando "
            "que el archivo pdf es de él y resúmele los temas críticos del documento "
            "en 1000 caracteres para que se entienda fácilmente. Por favor, NO HAGAS PREGUNTAS NI SALUDES.\n\n"
            f"{texto_original}"
        )

        # Llamada al Responses API
        response = client.responses.create(
            model="gpt-4o",      # Aquí puedes usar "gpt-4o", "gpt-4o-mini", "o4-mini", etc.
            input=prompt,
            temperature=0       # Mantenemos temperatura 0 para máxima determinismo
        )

        # Extraer el texto generado. `output_text` contiene el resumen completo.
        if hasattr(response, "output_text"):
            return response.output_text.strip()
        else:
            return "❌ No se pudo generar el resumen. Intenta de nuevo."

    except Exception as e:
        return f"❌ Error al resumir el texto: {str(e)}"




def extract_text_from_pdf(pdf_path, max_chars=1000):
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