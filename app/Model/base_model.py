import os
import requests
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import sys

from app.Model.connection import DatabaseManager
from app.Model.field import Field
from app.Model.enums import *
from app.Model.exceptions import (
    DatabaseError, UniqueConstraintError, ValidationError,
    BaseModelError, MissingUniqueFieldError, RecordNotFoundError
)
from app.Model.tools import get_fields_and_params, snake_to_camel
from app.Model.validators import validate

import warnings
warnings.filterwarnings("ignore", message=".*found in sys.modules.*")

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")


class BaseModel:
    def __init__(self, table_name: str, data: Dict[str, Any]) -> None:
        self.table_name = table_name
        self.__data = data
        self.base_url = f"{SUPABASE_URL}/rest/v1/{self.table_name}"
        self.headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    def add(self) -> int:
        try:
            fields, params = get_fields_and_params(self.__data, for_update=False)
            if not fields:
                raise Exception("No hay datos para actualizar.")
            payload = {field: value for field, value in zip(fields, params)}
            r = requests.post(self.base_url, headers=self.headers, json=payload)
            if r.status_code >= 400:
                raise Exception(f"Error: {r.status_code}, {r.text}")
            response_data = r.json()
            if not response_data:
                raise Exception("No se devolvió registro creado.")
            new_record = response_data[0]
            return (new_record.get("contact_id")        # contacts
            or new_record.get("id")
            or new_record.get("user_id")
            or 0
            )
        except Exception as e:
            raise DatabaseError(f"Error al crear registro en {self.table_name}: {e}")

    def get(self, field: str, value: Any, order_field: str = None) -> Optional[List[Any]]:
        try:
            if field not in self.__data:
                raise ValidationError(f"El campo {field} no existe.", field=field, value=value)
            if not validate(value, self.__data[field].data_type, self.__data[field].optional):
                raise ValidationError(f"El {field} debe ser de tipo {self.__data[field].data_type}.",
                                      field=field, value=value)
            url = f"{self.base_url}?{field}=eq.{value}"
            if order_field:
                url += f"&order={order_field}"
            r = requests.get(url, headers=self.headers)
            if r.status_code >= 400:
                raise DatabaseError(f"Error al obtener registro por {field} en {self.table_name}: {r.status_code}, {r.text}")
            records = r.json()
            if not records:
                return None
            result_objects = []
            for record in records:
                class_name = f"{snake_to_camel(self.table_name.capitalize())}Register"
                if class_name in globals():
                    record_obj = globals()[class_name](**record)
                    result_objects.append(record_obj)
                else:
                    raise ValueError(f"Clase {class_name} no encontrada.")
            return result_objects
        except Exception as e:
            raise DatabaseError(f"Error al obtener registro por {field} en {self.table_name}: {e}")

    def get_all(self, order_field: str = None) -> List[Any]:
        try:
            url = f"{self.base_url}?select=*"
            if order_field:
                url += f"&order={order_field}"
            r = requests.get(url, headers=self.headers)
            if r.status_code >= 400:
                raise DatabaseError(f"Error al obtener todos los registros de {self.table_name}: {r.status_code}, {r.text}")
            records = r.json()
            if not records:
                return []
            result_objects = []
            for record in records:
                class_name = f"{snake_to_camel(self.table_name.capitalize())}Register"
                if class_name in globals():
                    record_obj = globals()[class_name](**record)
                    result_objects.append(record_obj)
                else:
                    raise ValueError(f"Clase {class_name} no encontrada.")
            return result_objects
        except Exception as e:
            raise DatabaseError(f"Error al obtener todos los registros de {self.table_name}: {e}")

    def get_with_multiple_fields(self, fields: Dict[str, Any], order_field: str = None) -> Optional[List[Any]]:
        try:
            filter_str = ""
            for field, value in fields.items():
                if field not in self.__data:
                    raise ValidationError(f"El campo {field} no existe.", field=field, value=value)
                if not validate(value, self.__data[field].data_type, self.__data[field].optional):
                    raise ValidationError(f"El {field} debe ser de tipo {self.__data[field].data_type}.",
                                          field=field, value=value)
                filter_str += f"{field}=eq.{value}&"
            if filter_str.endswith("&"):
                filter_str = filter_str[:-1]
            url = f"{self.base_url}?{filter_str}"
            if order_field:
                url += f"&order={order_field}"
            r = requests.get(url, headers=self.headers)
            if r.status_code >= 400:
                raise DatabaseError(f"Error al obtener registros en {self.table_name}: {r.status_code}, {r.text}")
            records = r.json()
            if not records:
                return None
            result_objects = []
            for record in records:
                class_name = f"{snake_to_camel(self.table_name.capitalize())}Register"
                if class_name in globals():
                    record_obj = globals()[class_name](**record)
                    result_objects.append(record_obj)
                else:
                    raise ValueError(f"Clase {class_name} no encontrada.")
            return result_objects
        except Exception as e:
            raise DatabaseError(f"Error al obtener registros con múltiples campos en {self.table_name}: {e}")

    def update(self, unique_field_name: str, unique_field_value: Any) -> None:
        try:
            fields, params = get_fields_and_params(self.__data, for_update=True)
            if not fields:
                raise ValidationError("No hay datos para actualizar.", field=None, value=None)
            actual_fields = [field.replace(" = %s", "") for field in fields]
            payload = {field: value for field, value in zip(actual_fields, params)}
            url = f"{self.base_url}?{unique_field_name}=eq.{unique_field_value}"
            r = requests.patch(url, headers=self.headers, json=payload)
            if r.status_code >= 400:
                error_text = r.text
                for field, field_obj in self.__data.items():
                    if field_obj.unique and str(field_obj.value) in error_text:
                        raise UniqueConstraintError(f"El {field} ya está en uso.", field=field, value=field_obj.value)
                raise DatabaseError(f"Error al actualizar registro en {self.table_name}: {r.status_code}, {r.text}")
            if not r.json():
                raise RecordNotFoundError(
                    f"No se encontró el registro con {unique_field_name}={unique_field_value} en {self.table_name}.",
                    field=unique_field_name,
                    value=unique_field_value
                )
        except Exception as e:
            raise DatabaseError(f"Error al actualizar registro en {self.table_name}: {e}")


    def _fetch_one(self, query: str) -> dict:
        url = os.environ.get("SUPABASE_URL") + f"/rest/v1/{self.table_name}?{query}"
        headers = {
            "apikey": os.environ.get("SUPABASE_API_KEY"),
            "Authorization": f"Bearer {os.environ.get('SUPABASE_API_KEY')}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        try:
            data = response.json()
            if isinstance(data, list):
                return data[0] if data else None
            else:
                raise ValueError(f"Respuesta inesperada: {data}")
        except Exception as e:
            raise ValueError(f"Error procesando respuesta JSON: {e}")

        def _fetch_one(self, query: str) -> dict:
            url = os.environ.get("SUPABASE_URL") + f"/rest/v1/{self.table_name}?{query}"
            headers = {
                "apikey": os.environ.get("SUPABASE_KEY"),
                "Authorization": f"Bearer {os.environ.get('SUPABASE_KEY')}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
            data = response.json()
            
            return data[0] if data else None

        

    def delete(self, field: str, value: Any) -> None:
        try:
            if field not in self.__data:
                raise ValidationError(f"El campo {field} no existe.", field=field, value=value)
            if not validate(value, self.__data[field].data_type, self.__data[field].optional):
                raise ValidationError(f"El {field} debe ser de tipo {self.__data[field].data_type}.",
                                      field=field, value=value)
            url = f"{self.base_url}?{field}=eq.{value}"
            r = requests.delete(url, headers=self.headers)
            if r.status_code >= 400:
                raise DatabaseError(f"Error al eliminar registro en {self.table_name}: {r.status_code}, {r.text}")
            if not r.json():
                raise DatabaseError(f"No se encontró registro con {field}={value} en {self.table_name}.")
        except Exception as e:
            raise DatabaseError(f"Error al eliminar registro en {self.table_name}: {e}")
    def upsert(self, row: Dict[str, Any], on_conflict: str) -> Dict[str, Any]:
        """
        Insert-or-Update usando índice único (p.ej. on_conflict='tx_id').
        Requiere que la tabla tenga ese índice único creado.
        insertar o, si hay duplicado por on_conflict, merge/actualizar y devolver la fila.
        """
        try:
            url = f"{self.base_url}?on_conflict={on_conflict}"
            headers = self.headers.copy()
            # Devolver representación + merge de duplicados (upsert real)
            prefer = headers.get("Prefer", "return=representation")
            if "resolution=merge-duplicates" not in prefer:
                prefer = f"{prefer},resolution=merge-duplicates"
            headers["Prefer"] = prefer

            r = requests.post(url, headers=headers, json=row, timeout=10)
            if r.status_code >= 400:
                raise DatabaseError(f"Upsert error {r.status_code}: {r.text}")
            data = r.json()
            return data[0] if isinstance(data, list) and data else data
        except Exception as e:
            raise DatabaseError(f"Error en upsert {self.table_name}: {e}")



# Definición de la clase UsersRegister para convertir registros de la tabla "users"
class UsersRegister:

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return f"UsersRegister({self.__dict__})"

globals()["UsersRegister"] = UsersRegister

# --- DEFINICIÓN DE LA CLASE ContactsRegister ---
class ContactsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"ContactsRegister({self.__dict__})"

# Registrar ContactsRegister en globals() para asegurar su disponibilidad global
globals()["ContactsRegister"] = ContactsRegister





class TransactionsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"TransactionsRegister({self.__dict__})"

# Register the class in globals() so that BaseModel can find it
globals()["TransactionsRegister"] = TransactionsRegister


class MessagesRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"MessagesRegister({self.__dict__})"

# Register the class in globals() so that BaseModel can find it
globals()["MessagesRegister"] = MessagesRegister

class LogRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"LogRegister({self.__dict__})"

# Register the class in globals() so that BaseModel can find it
globals()["LogRegister"] = LogRegister


class EngineRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"EngineRegister({self.__dict__})"

# Register the class in globals() so that BaseModel can find it
globals()["EngineRegister"] = EngineRegister

class QuestionsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"QuestionsRegister({self.__dict__})"
globals()["QuestionsRegister"] = QuestionsRegister


class EventsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"EventsRegister({self.__dict__})"

# Registrar en globals para que BaseModel la encuentre
globals()["EventsRegister"] = EventsRegister


class TransactionsRegister:
    def __init__(self, **kwargs):
        # Soporte retrocompatible con '_id'
        if "_id" in kwargs:
            kwargs["id"] = kwargs.pop("_id")
        self.__dict__.update(kwargs)

    def __repr__(self):
        return f"TransactionsRegister({self.__dict__})"
    

#  CoveragesRegister (para la tabla 'coverages')
class CoveragesRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"CoveragesRegister({self.__dict__})"
globals()["CoveragesRegister"] = CoveragesRegister


class PrivacyConsentsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return f"PrivacyConsentsRegister({self.__dict__})"

globals()["PrivacyConsentsRegister"] = PrivacyConsentsRegister

