import os
import requests
import subprocess
import openai

def descargar_archivo(url, carpeta="temp_audio"):
    """ Descarga un archivo desde una URL, lo guarda y lo convierte a WAV si es necesario """
    os.makedirs(carpeta, exist_ok=True)  # Crea la carpeta si no existe
    nombre_original = os.path.join(carpeta, url.split("/")[-1])  # Extrae el nombre del archivo

    try:
        print(f"⬇️ Descargando archivo desde: {url}")
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(nombre_original, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"✅ Archivo guardado en: {nombre_original}")

            # Verificar si es un formato que necesita conversión
            if nombre_original.endswith((".ogg", ".oga", ".mpga")):
                nombre_convertido = nombre_original.rsplit(".", 1)[0] + ".wav"  # Cambia la extensión a .wav
                print(f"🔄 Convirtiendo {nombre_original} a {nombre_convertido}")

                try:
                    subprocess.run(["ffmpeg", "-i", nombre_original, nombre_convertido, "-y"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    print(f"✅ Conversión exitosa: {nombre_convertido}")
                    return nombre_convertido  # Retorna la nueva ruta del archivo convertido
                except subprocess.CalledProcessError as e:
                    print(f"⚠️ Error en la conversión: {e}")
                    return None

            return nombre_original  # Si no necesita conversión, devolver el original

        else:
            print(f"⚠️ Error descargando el archivo: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error en la descarga: {e}")
        return None

def transcribir_audio_cloud(ruta_archivo):
    """
    Transcribe un archivo de audio (ruta local) usando la API de Whisper de OpenAI.
    """
    try:
        with open(ruta_archivo, "rb") as audio_file:
            transcript = openai.Audio.transcribe(
                model="gpt-4o-audio-preview-2024-12-17",
                file=audio_file
            )
        return transcript["text"]
    except Exception as e:
        return f"Error en la transcripción: {str(e)}"

