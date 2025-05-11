import os
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

class DatabaseManager:
    def __init__(self):
        # Base URL para la REST API de Supabase (PostgREST)
        self.base_url = f"{SUPABASE_URL}/rest/v1"
        self.headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json",
            # Con "return=representation" se devuelve el registro creado/actualizado
            "Prefer": "return=representation"
        }

    def fetch_one(self, table: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        """
        Ejecuta una consulta GET a la tabla y retorna una sola fila.
        :param table: Nombre de la tabla.
        :param params: Diccionario de filtros (ej: {"email": "user@mail.com"}).
        :return: Un diccionario con los datos de una fila o None si no hay resultados.
        """
        url = f"{self.base_url}/{table}?select=*"
        if params:
            filters = [f"{key}=eq.{value}" for key, value in params.items()]
            url += "&" + "&".join(filters)
        r = requests.get(url, headers=self.headers)
        if r.status_code >= 400:
            raise Exception(f"Error en fetch_one: {r.status_code}, {r.text}")
        data = r.json()
        if data:
            return data[0]
        return None

    def fetch_all(self, table: str, params: Optional[Dict[str, str]] = None) -> Optional[List[Dict]]:
        """
        Ejecuta una consulta GET a la tabla y retorna todas las filas.
        :param table: Nombre de la tabla.
        :param params: Diccionario de filtros (opcional).
        :return: Una lista de diccionarios con los datos o None si no hay resultados.
        """
        url = f"{self.base_url}/{table}?select=*"
        if params:
            filters = [f"{key}=eq.{value}" for key, value in params.items()]
            url += "&" + "&".join(filters)
        r = requests.get(url, headers=self.headers)
        if r.status_code >= 400:
            raise Exception(f"Error en fetch_all: {r.status_code}, {r.text}")
        data = r.json()
        if data:
            return data
        return None

    def execute_command(self, table: str, method: str, payload: Optional[Dict] = None, params: Optional[Dict[str, str]] = None) -> Optional[List[Dict]]:
        """
        Ejecuta un comando (INSERT, UPDATE, DELETE) en la tabla especificada.
        :param table: Nombre de la tabla.
        :param method: "POST" para insertar, "PATCH" para actualizar, "DELETE" para eliminar.
        :param payload: Diccionario con los datos a insertar o actualizar (opcional).
        :param params: Diccionario con filtros para operaciones de actualización o eliminación (opcional).
        :return: La respuesta de la API (usualmente el registro o registros afectados) o None.
        """
        url = f"{self.base_url}/{table}"
        if params:
            filters = [f"{key}=eq.{value}" for key, value in params.items()]
            url += "?" + "&".join(filters)
        method = method.upper()
        if method == "POST":
            r = requests.post(url, headers=self.headers, json=payload)
        elif method == "PATCH":
            r = requests.patch(url, headers=self.headers, json=payload)
        elif method == "DELETE":
            r = requests.delete(url, headers=self.headers)
        else:
            raise ValueError("Método no soportado, use POST, PATCH o DELETE.")
        if r.status_code >= 400:
            raise Exception(f"Error en execute_command: {r.status_code}, {r.text}")
        return r.json() if r.text else None

    def close_connection(self):
        """
        No es necesario cerrar conexión en una API REST.
        """
        pass
