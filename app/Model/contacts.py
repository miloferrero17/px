from typing import Optional, List, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel, ContactsRegister
from app.Model.field import Field
from app.Model.exceptions import DatabaseError


class Contacts(BaseModel):
    def __init__(self):
        data: Dict[str, Field] = {
            "contact_id": Field(None, DataType.INTEGER, False, True),  # ✅ nueva PK
            "event_id": Field(None, DataType.INTEGER, False, False),
            "name": Field(None, DataType.STRING, False, False),
            "phone": Field(None, DataType.PHONE, False, False)
        }
        super().__init__("contacts", data)
        self.__data = data  # opcional, por si necesitás usarlo luego

    def add(self, event_id: int, name: str, phone: str) -> int:
        """
        Inserta un nuevo contacto y retorna su ID.
        """
        self.__data["contact_id"].value = None  # para autoincrementar
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        return super().add()

    def get_by_event_id(self, event_id: int) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos que coinciden con event_id.
        """
        try:
            result = super().get("event_id", event_id, order_field="name")
            if not result:
                return None
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_event_id: {e}")

    def get_by_name(self, name: str) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos que coinciden con el nombre dado.
        """
        try:
            result = super().get("name", name, order_field="name")
            if not result:
                return None
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_name: {e}")

    def get_by_id(self, contact_id: int) -> Optional[ContactsRegister]:
        """
        Retorna un contacto por ID.
        """
        try:
            result = super().get("contact_id", contact_id)
            if not result:
                return None
            return ContactsRegister(**result[0]) if isinstance(result[0], dict) else result[0]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_id: {e}")

    def get_by_phone(self, phone: str) -> Optional[ContactsRegister]:
        """
        Retorna un contacto por teléfono.
        """
        try:
            result = super().get("phone", phone)
            if not result:
                return None
            return ContactsRegister(**result[0]) if isinstance(result[0], dict) else result[0]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_phone: {e}")

    def update(self, contact_id: int, event_id: Optional[int] = None, name: Optional[str] = None, phone: Optional[str] = None) -> None:
        """
        Actualiza un contacto por contact_id.
        """
        self.__data["contact_id"].value = contact_id
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        try:
            super().update("contact_id", contact_id)
        except Exception as e:
            raise DatabaseError(f"Error en update: {e}")

    def delete(self, contact_id: int) -> None:
        """
        Elimina un contacto por contact_id.
        """
        try:
            super().delete("contact_id", contact_id)
        except Exception as e:
            raise DatabaseError(f"Error en delete: {e}")

    def delete_all(self) -> None:
        """
        Elimina todos los contactos de la tabla.
        """
        try:
            self._db.table(self._table_name).delete().execute()
        except Exception as e:
            raise DatabaseError(f"Error en delete_all: {e}")

    def get_event_id_by_phone(self, phone: str) -> Optional[int]:
        """
        Retorna el event_id asociado a un número de teléfono.
        """
        try:
            result = super().get("phone", phone)
            if not result:
                return None
            registro = result[0]
            return registro["event_id"] if isinstance(registro, dict) else registro.event_id
        except Exception as e:
            raise DatabaseError(f"Error en get_event_id_by_phone: {e}")

'''
ctt = Contacts()
event_id = ctt.get_event_id_by_phone("5491133585362")
print(event_id)



# contacts.py

import os
import requests
from typing import Dict, Optional, List, Any

from app.Model.field import Field
from app.Model.enums import DataType
from app.Model.exceptions import (
    DatabaseError,
    UniqueConstraintError,
    ValidationError,
    RecordNotFoundError,
    MissingUniqueFieldError
)
from app.Model.tools import get_fields_and_params, snake_to_camel
from app.Model.validators import validate
from app.Model.base_model import BaseModel
from app.Model.connection import DatabaseManager


# --- DEFINICIÓN DE CLASES DE REGISTRO (usadas como output de consultas) ---

class TransactionsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"TransactionsRegister({self.__dict__})"

globals()["TransactionsRegister"] = TransactionsRegister


class MessagesRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"MessagesRegister({self.__dict__})"

globals()["MessagesRegister"] = MessagesRegister


class ContactsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"ContactsRegister({self.__dict__})"

globals()["ContactsRegister"] = ContactsRegister


# --- CLASE PRINCIPAL CONTACTS ---
from typing import Optional, List, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel, ContactsRegister
from app.Model.field import Field
from app.Model.exceptions import DatabaseError


class Contacts(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "contact_id": Field(None, DataType.INTEGER, False, True),  # ✅ nueva PK
            "event_id": Field(None, DataType.INTEGER, False, False),
            "name": Field(None, DataType.STRING, False, False),
            "phone": Field(None, DataType.PHONE, False, False)  # Podés agregar unique=True si lo necesitás
        }
        super().__init__("contacts", self.__data)

    def add(self, event_id: int, name: str, phone: str) -> int:
        """
        Inserta un nuevo contacto y retorna su ID.
        """
        self.__data["contact_id"].value = None  # para autoincrementar
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        return super().add()

    def get_by_event_id(self, event_id: int) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos que coinciden con event_id.
        """
        try:
            result = super().get("event_id", event_id, order_field="name")
            if not result:
                return None
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_event_id: {e}")

    def get_by_name(self, name: str) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos que coinciden con el nombre dado.
        """
        try:
            result = super().get("name", name, order_field="name")
            if not result:
                return None
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_name: {e}")

    def get_by_id(self, contact_id: int) -> Optional[ContactsRegister]:
        """
        Retorna un contacto por ID.
        """
        try:
            result = super().get("contact_id", contact_id)
            if not result:
                return None
            return ContactsRegister(**result[0]) if isinstance(result[0], dict) else result[0]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_id: {e}")

    def get_by_phone(self, phone: str) -> Optional[ContactsRegister]:
        """
        Retorna un contacto por teléfono.
        """
        try:
            result = super().get("phone", phone)
            if not result:
                return None
            return ContactsRegister(**result[0]) if isinstance(result[0], dict) else result[0]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_phone: {e}")

    def update(self, contact_id: int, event_id: Optional[int] = None, name: Optional[str] = None, phone: Optional[str] = None) -> None:
        """
        Actualiza un contacto por contact_id.
        """
        self.__data["contact_id"].value = contact_id
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        try:
            super().update("contact_id", contact_id)
        except Exception as e:
            raise DatabaseError(f"Error en update: {e}")

    def delete(self, contact_id: int) -> None:
        """
        Elimina un contacto por contact_id.
        """
        try:
            super().delete("contact_id", contact_id)
        except Exception as e:
            raise DatabaseError(f"Error en delete: {e}")
    
 

class Contacts(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "event_id": Field(None, DataType.INTEGER, False, True),
            "name": Field(None, DataType.STRING, False, False),
            "phone": Field(None, DataType.PHONE, False, True),  # phone es ahora la clave primaria
        }
        super().__init__("contacts", self.__data)

    def add(self, event_id: int, name: str, phone: str) -> int:
        """
        Inserta un nuevo contacto y retorna su identificador.
        En este caso, phone es la clave primaria.
        """
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        return super().add()

    def get_by_event_id(self, event_id: int) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos (ContactsRegister) que coinciden con event_id,
        o None si no se encuentran registros.
        """
        try:
            result = super().get("event_id", event_id, order_field="name")
            if not result:
                return None
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_event_id: {e}")


    def get_by_name(self, name: str) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos que coinciden con el nombre dado.
        """
        try:
            result = super().get("name", name, order_field="name")
            if not result:
                return None
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_name: {e}")

    def get_by_phone(self, phone: str) -> Optional[ContactsRegister]:
        """
        Retorna una instancia de ContactsRegister con los datos del contacto que tenga el phone especificado,
        o None si no se encuentra el registro.
        """
        try:
            result = super().get("phone", phone)
            if not result:
                return None
            return ContactsRegister(**result[0]) if isinstance(result[0], dict) else result[0]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_phone: {e}")

    def update(self, phone: str, event_id: Optional[int] = None, name: Optional[str] = None) -> None:
        """
        Actualiza los datos de un contacto identificado por phone.
        Se actualizan los campos cuyos valores no sean None.
        """
        self.__data["phone"].value = phone
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        try:
            super().update("phone", phone)
        except Exception as e:
            raise DatabaseError(f"Error en update: {e}")

    def delete(self, phone: str) -> None:
        """
        Elimina un contacto identificado por phone.
        """
        try:
            super().delete("phone", phone)
        except Exception as e:
            raise DatabaseError(f"Error en delete: {e}")
'''
'''


# contacts.py

import os
import requests
from typing import Dict, Optional, List, Any

from app.Model.field import Field
from app.Model.enums import DataType
from app.Model.exceptions import (
    DatabaseError,
    UniqueConstraintError,
    ValidationError,
    RecordNotFoundError,
    MissingUniqueFieldError
)
from app.Model.tools import get_fields_and_params, snake_to_camel
from app.Model.validators import validate
from app.Model.base_model import BaseModel
from app.Model.connection import DatabaseManager

class TransactionsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"TransactionsRegister({self.__dict__})"

# Register the class in globals() so that BaseModel can find it
globals()["TransactionsRegister"] = TransactionsRegister


# Definición de MessagesRegister en el módulo para que esté en el namespace global
class MessagesRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return f"MessagesRegister({self.__dict__})"
# Aseguramos que la clase se encuentre en el namespace global
globals()["MessagesRegister"] = MessagesRegister


# --- DEFINICIÓN DE LA CLASE ContactsRegister ---
class ContactsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"ContactsRegister({self.__dict__})"

# Registrar ContactsRegister en globals() para asegurar su disponibilidad global
globals()["ContactsRegister"] = ContactsRegister

# --- CLASE CONTACTS ---
class Contacts(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "contact_id": Field(None, DataType.INTEGER, False, True),
            "event_id": Field(None, DataType.INTEGER, False, True),
            "name": Field(None, DataType.STRING, False, False),
            "phone": Field(None, DataType.PHONE, False, True),
        }
        # Se asume que la tabla en Supabase se llama "contacts" (en minúsculas)
        super().__init__("contacts", self.__data)

    def add(self, event_id: int, name: str, phone: str) -> int:
        """
        Inserta un nuevo contacto y retorna su ID.
        """
        self.__data["contact_id"].value = None
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        return super().add()


    def get_by_id(self, message_id: int) -> Optional[MessagesRegister]:
        """
        Retorna una instancia de MessagesRegister con los datos del mensaje identificado por message_id.
        """
        result = super().get("message_id", message_id)
        return result[0] if result else None


    def get_by_event_id(self, event_id: int) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos (ContactsRegister) que coinciden con event_id o None si no se encuentran registros.
        """
        try:
            result = super().get("event_id", event_id, order_field="name")
            if not result:
                return None
            # Convertir cada registro a una instancia de ContactsRegister usando globals()
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_event_id: {e}")

    def get_by_name(self, name: str) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos que coinciden con el nombre dado.
        """
        try:
            result = super().get("name", name, order_field="name")
            if not result:
                return None
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_name: {e}")

    def get_by_phone(self, phone: str) -> Optional[ContactsRegister]:
        """
        Retorna una instancia de ContactsRegister con los datos del contacto que tenga el phone especificado, o None.
        """
        try:
            result = super().get("phone", phone)
            if not result:
                return None
            return ContactsRegister(**result[0]) if isinstance(result[0], dict) else result[0]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_phone: {e}")

    def update(self, contact_id: int, event_id: Optional[int] = None, name: Optional[str] = None, phone: Optional[str] = None) -> None:
        """
        Actualiza los datos de un contacto identificado por contact_id. Se actualizan los campos cuyos valores no sean None.
        """
        self.__data["contact_id"].value = contact_id
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        try:
            super().update("contact_id", contact_id)
        except Exception as e:
            raise DatabaseError(f"Error en update: {e}")

    def delete(self, contact_id: int) -> None:
        """
        Elimina un contacto identificado por contact_id.
        """
        try:
            super().delete("contact_id", contact_id)
        except Exception as e:
            raise DatabaseError(f"Error en delete: {e}")




# contacts.py

import os
import requests
from typing import Dict, Optional, List, Any

from app.Model.field import Field
from app.Model.enums import DataType
from app.Model.exceptions import (
    DatabaseError,
    UniqueConstraintError,
    ValidationError,
    RecordNotFoundError,
    MissingUniqueFieldError
)
from app.Model.tools import get_fields_and_params, snake_to_camel
from app.Model.validators import validate
from app.Model.base_model import BaseModel
from app.Model.connection import DatabaseManager

# --- DEFINICIÓN DE LA CLASE ContactsRegister ---
class ContactsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"ContactsRegister({self.__dict__})"

# Registrar ContactsRegister en globals() para que esté disponible globalmente.
globals()["ContactsRegister"] = ContactsRegister

# --- CLASE CONTACTS ---
class Contacts(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "contact_id": Field(None, DataType.INTEGER, False, True),
            "event_id": Field(None, DataType.INTEGER, False, True),
            "name": Field(None, DataType.STRING, False, False),
            "phone": Field(None, DataType.PHONE, False, True),
        }
        # Se asume que la tabla en Supabase se llama "contacts" (en minúsculas)
        super().__init__("contacts", self.__data)

    def add(self, event_id: int, name: str, phone: str) -> int:
        self.__data["contact_id"].value = None
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        return super().add()

    def get_by_id(self, contact_id: int) -> Optional[ContactsRegister]:
        try:
            url = f"{self.base_url}?contact_id=eq.{contact_id}"
            print("Consultando URL:", url)
            r = requests.get(url, headers=self.headers)
            if r.status_code >= 400:
                raise DatabaseError(f"Error al obtener registro por contact_id en {self.table_name}: {r.status_code}, {r.text}")
            records = r.json()
            print("Respuesta de la API:", records)
            if not records:
                return None
            return globals()["ContactsRegister"](**records[0])
        except Exception as e:
            raise DatabaseError(f"Error en get_by_id: {e}")


    def get_by_event_id(self, event_id: int) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos (ContactsRegister) que coinciden con event_id o None si no se encuentran registros.
        """
        try:
            result = super().get("event_id", event_id, order_field="name")
            if not result:
                return None
            # Convertir cada registro a una instancia de ContactsRegister usando globals()
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_event_id: {e}")
    def get_by_name(self, name: str) -> Optional[List[ContactsRegister]]:
        try:
            result = super().get("name", name, order_field="name")
            if not result:
                return None
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_name: {e}")

    def get_by_phone(self, phone: str) -> Optional[ContactsRegister]:
        try:
            result = super().get("phone", phone)
            if not result:
                return None
            return ContactsRegister(**result[0]) if isinstance(result[0], dict) else result[0]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_phone: {e}")

    def update(self, contact_id: int, event_id: Optional[int] = None, name: Optional[str] = None, phone: Optional[str] = None) -> None:
        self.__data["contact_id"].value = contact_id
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        try:
            super().update("contact_id", contact_id)
        except Exception as e:
            raise DatabaseError(f"Error en update: {e}")

    def delete(self, contact_id: int) -> None:
        try:
            super().delete("contact_id", contact_id)
        except Exception as e:
            raise DatabaseError(f"Error en delete: {e}")


# --- EJEMPLOS DE USO ---
if __name__ == '__main__':
    contacts_model = Contacts()


    # Ejemplo de get_by_event_id:
    
    try:
        contacts_list = contacts_model.get_by_event_id(100)
        print("Contactos obtenidos por event_id:", contacts_list)
    except Exception as e:
        print("Error en get_by_event_id:", e)
    
    
    # Ejemplo de get_by_name:
    try:
        contacts_by_name = contacts_model.get_by_name("Alice")
        print("Contactos obtenidos por name:", contacts_by_name)
    except Exception as e:
        print("Error en get_by_name:", e)

    # Ejemplo de get_by_phone:
    try:
        contact_by_phone = contacts_model.get_by_phone("1234567890")
        print("Contacto obtenido por phone:", contact_by_phone)
    except Exception as e:
        print("Error en get_by_phone:", e)

    # Ejemplo de update:
    try:
        contacts_model.update(new_contact_id, name="Alice Updated")
        updated_contact = contacts_model.get_by_id(new_contact_id)
        print("Contacto actualizado:", updated_contact)
    except Exception as e:
        print("Error en update:", e)

    # Ejemplo de delete:
    try:
        contacts_model.delete(new_contact_id)
        deleted_contact = contacts_model.get_by_id(new_contact_id)
        print("Contacto después de eliminar (debe ser None):", deleted_contact)
    except Exception as e:
        print("Error en delete:", e)

# contacts.py

import os
import requests
from typing import Dict, Optional, List, Any

from app.Model.field import Field
from app.Model.enums import DataType
from app.Model.exceptions import (
    DatabaseError,
    UniqueConstraintError,
    ValidationError,
    RecordNotFoundError,
    MissingUniqueFieldError
)
from app.Model.tools import get_fields_and_params, snake_to_camel
from app.Model.validators import validate
from app.Model.base_model import BaseModel
from app.Model.connection import DatabaseManager

# --- DEFINICIÓN DE LA CLASE ContactsRegister ---
class ContactsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"ContactsRegister({self.__dict__})"

# Registrar ContactsRegister en globals() para asegurar su disponibilidad (aunque para get_by_event_id lo evitaremos)
globals()["ContactsRegister"] = ContactsRegister

# --- CLASE Contacts ---
class Contacts(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "contact_id": Field(None, DataType.INTEGER, False, True),
            "event_id": Field(None, DataType.INTEGER, False, True),
            "name": Field(None, DataType.STRING, False, False),
            "phone": Field(None, DataType.PHONE, False, True),
        }
        # Se asume que la tabla en Supabase se llama "contacts" en minúsculas.
        super().__init__("contacts", self.__data)

    def add(self, event_id: int, name: str, phone: str) -> int:
        """
        Inserta un nuevo contacto y retorna su ID.
        """
        self.__data["contact_id"].value = None
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        return super().add()

    def get_by_id(self, contact_id: int) -> Optional[ContactsRegister]:
        """
        Retorna una instancia de ContactsRegister con los datos del contacto o None si no se encuentra.
        Se consulta por "contact_id".
        """
        try:
            url = f"{self.base_url}?contact_id=eq.{contact_id}"
            print("Consultando URL:", url)
            r = requests.get(url, headers=self.headers)
            if r.status_code >= 400:
                raise DatabaseError(f"Error al obtener registro por contact_id en {self.table_name}: {r.status_code}, {r.text}")
            records = r.json()
            print("Respuesta de la API:", records)
            if not records:
                return None
            return globals()["ContactsRegister"](**records[0])
        except Exception as e:
            raise DatabaseError(f"Error en get_by_id: {e}")

    def get_by_event_id(self, event_id: int) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos (ContactsRegister) que coinciden con event_id,
        o None si no se encuentran registros.
        Se instancia directamente la clase ContactsRegister.
        """
        try:
            # Llamamos al método get de BaseModel que devuelve una lista de diccionarios
            result = super().get("event_id", event_id, order_field="name")
            if not result:
                return None
            # Convertir cada registro a una instancia de ContactsRegister sin depender de globals()
            contacts_list = [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
            return contacts_list
        except Exception as e:
            raise DatabaseError(f"Error en get_by_event_id: {e}")

    def get_by_name(self, name: str) -> Optional[List[ContactsRegister]]:
        """
        Retorna una lista de contactos que coinciden con el nombre dado.
        """
        try:
            result = super().get("name", name, order_field="name")
            if not result:
                return None
            return [ContactsRegister(**record) if isinstance(record, dict) else record for record in result]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_name: {e}")

    def get_by_phone(self, phone: str) -> Optional[ContactsRegister]:
        """
        Retorna una instancia de ContactsRegister con los datos del contacto que tenga el phone especificado, o None.
        """
        try:
            result = super().get("phone", phone)
            if not result:
                return None
            # Convertir el primer registro a ContactsRegister
            return ContactsRegister(**result[0]) if isinstance(result[0], dict) else result[0]
        except Exception as e:
            raise DatabaseError(f"Error en get_by_phone: {e}")

    def update(self, contact_id: int, event_id: Optional[int] = None, name: Optional[str] = None, phone: Optional[str] = None) -> None:
        """
        Actualiza los datos de un contacto identificado por contact_id.
        Se actualizan los campos cuyos valores no sean None.
        """
        self.__data["contact_id"].value = contact_id
        self.__data["event_id"].value = event_id
        self.__data["name"].value = name
        self.__data["phone"].value = phone
        try:
            super().update("contact_id", contact_id)
        except Exception as e:
            raise DatabaseError(f"Error en update: {e}")

    def delete(self, contact_id: int) -> None:
        """
        Elimina un contacto identificado por contact_id.
        """
        try:
            super().delete("contact_id", contact_id)
        except Exception as e:
            raise DatabaseError(f"Error en delete: {e}")


# --- EJEMPLOS DE USO ---
if __name__ == '__main__':
    contacts_model = Contacts()


    try:
        contacts_list = contacts_model.get_by_event_id(100)
        print("Contactos obtenidos por event_id:", contacts_list)
    except Exception as e:
        print("Error en get_by_event_id:", e)

    
    # Ejemplo de get_by_name:
    try:
        contacts_by_name = contacts_model.get_by_name("Alice")
        print("Contactos obtenidos por name:", contacts_by_name)
    except Exception as e:
        print("Error en get_by_name:", e)

    # Ejemplo de get_by_phone:
    try:
        contact_by_phone = contacts_model.get_by_phone("1234567890")
        print("Contacto obtenido por phone:", contact_by_phone)
    except Exception as e:
        print("Error en get_by_phone:", e)

'''