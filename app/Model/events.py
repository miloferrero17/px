from typing import Optional, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field

class Events(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "event_id":        Field(None, DataType.INTEGER,   False, True),
            "user_id":         Field(None, DataType.INTEGER,   False, False),
            "name":            Field(None, DataType.STRING,    False, False),
            "start_timestamp": Field(None, DataType.TIMESTAMP, True,  False),
            "end_timestamp":   Field(None, DataType.TIMESTAMP, True,  False),
            "reporte":         Field(None, DataType.TEXT,       True,  False),
            "description":     Field(None, DataType.TEXT,       True,  False),
            "nodo_inicio":     Field(None, DataType.INTEGER,   True,  False),
            "cant_preguntas":  Field(None, DataType.INTEGER,   True,  False),
            "tiempo_sesion":   Field(None, DataType.INTEGER,   True,  False),
            "assistant":       Field(None, DataType.TEXT,       True,  False),  # Nuevo campo
        }
        super().__init__("events", self.__data)

    def add(
        self,
        user_id: int,
        name: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        reporte: Optional[str] = None,
        description: Optional[str] = None,
        nodo_inicio: Optional[int] = None,
        cant_preguntas: Optional[int] = None,
        tiempo_sesion: Optional[int] = None,
        assistant: Optional[str] = None
    ) -> int:
        self.__data["event_id"].value        = None
        self.__data["user_id"].value         = user_id
        self.__data["name"].value            = name
        self.__data["start_timestamp"].value = start_timestamp
        self.__data["end_timestamp"].value   = end_timestamp
        self.__data["reporte"].value         = reporte
        self.__data["description"].value     = description
        self.__data["nodo_inicio"].value     = nodo_inicio
        self.__data["cant_preguntas"].value  = cant_preguntas
        self.__data["tiempo_sesion"].value   = tiempo_sesion
        self.__data["assistant"].value       = assistant
        return super().add()

    def get_by_user(self, user_id: int):
        return super().get("user_id", user_id)

    def get_by_id(self, event_id: int):
        result = super().get("event_id", event_id)
        return result[0] if result else None

    def update(
        self,
        event_id: int,
        name: Optional[str] = None,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        reporte: Optional[str] = None,
        description: Optional[str] = None,
        nodo_inicio: Optional[int] = None,
        cant_preguntas: Optional[int] = None,
        tiempo_sesion: Optional[int] = None,
        assistant: Optional[str] = None
    ) -> None:
        self.__data["event_id"].value = event_id
        if name is not None:
            self.__data["name"].value = name
        if start_timestamp is not None:
            self.__data["start_timestamp"].value = start_timestamp
        if end_timestamp is not None:
            self.__data["end_timestamp"].value = end_timestamp
        if reporte is not None:
            self.__data["reporte"].value = reporte
        if description is not None:
            self.__data["description"].value = description
        if nodo_inicio is not None:
            self.__data["nodo_inicio"].value = nodo_inicio
        if cant_preguntas is not None:
            self.__data["cant_preguntas"].value = cant_preguntas
        if tiempo_sesion is not None:
            self.__data["tiempo_sesion"].value = tiempo_sesion
        if assistant is not None:
            self.__data["assistant"].value = assistant
        super().update("event_id", event_id)

    def delete(self, event_id: int) -> None:
        super().delete("event_id", event_id)

    def get_reporte_by_event_id(self, event_id: int) -> Optional[str]:
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "reporte"):
            return result[0].reporte
        return None

    def get_description_by_event_id(self, event_id: int) -> Optional[str]:
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "description"):
            return result[0].description
        return None

    def get_nodo_inicio_by_event_id(self, event_id: int) -> Optional[int]:
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "nodo_inicio"):
            return result[0].nodo_inicio
        return None

    def get_cant_preguntas_by_event_id(self, event_id: int) -> Optional[int]:
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "cant_preguntas"):
            return result[0].cant_preguntas
        return None

    def get_time_by_event_id(self, event_id: int) -> Optional[int]:
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "tiempo_sesion"):
            return result[0].tiempo_sesion
        return None

    def get_assistant_by_event_id(self, event_id: int) -> Optional[str]:
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "assistant"):
            return result[0].assistant
        return None
'''
from typing import Optional, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field

class Events(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "event_id":        Field(None, DataType.INTEGER,   False, True),
            "user_id":         Field(None, DataType.INTEGER,   False, False),
            "name":            Field(None, DataType.STRING,    False, False),
            "start_timestamp": Field(None, DataType.TIMESTAMP, True,  False),
            "end_timestamp":   Field(None, DataType.TIMESTAMP, True,  False),
            "reporte":         Field(None, DataType.TEXT,       True,  False),
            "description":     Field(None, DataType.TEXT,       True,  False),
            "nodo_inicio":     Field(None, DataType.INTEGER,   True,  False),
            "cant_preguntas":  Field(None, DataType.INTEGER,   True,  False),
            "tiempo_sesion":   Field(None, DataType.INTEGER,   True,  False),  # Nuevo campo int2
        }
        super().__init__("events", self.__data)

    def add(
        self,
        user_id: int,
        name: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        reporte: Optional[str] = None,
        description: Optional[str] = None,
        nodo_inicio: Optional[int] = None,
        cant_preguntas: Optional[int] = None,
        tiempo_sesion: Optional[int] = None  # Nuevo parámetro
    ) -> int:
        self.__data["event_id"].value        = None
        self.__data["user_id"].value         = user_id
        self.__data["name"].value            = name
        self.__data["start_timestamp"].value = start_timestamp
        self.__data["end_timestamp"].value   = end_timestamp
        self.__data["reporte"].value         = reporte
        self.__data["description"].value     = description
        self.__data["nodo_inicio"].value     = nodo_inicio
        self.__data["cant_preguntas"].value  = cant_preguntas
        self.__data["tiempo_sesion"].value   = tiempo_sesion
        return super().add()

    def get_by_user(self, user_id: int):
        return super().get("user_id", user_id)

    def get_by_id(self, event_id: int):
        result = super().get("event_id", event_id)
        return result[0] if result else None

    def update(
        self,
        event_id: int,
        name: Optional[str] = None,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        reporte: Optional[str] = None,
        description: Optional[str] = None,
        nodo_inicio: Optional[int] = None,
        cant_preguntas: Optional[int] = None,
        tiempo_sesion: Optional[int] = None  # Nuevo parámetro
    ) -> None:
        self.__data["event_id"].value = event_id
        if name is not None:
            self.__data["name"].value = name
        if start_timestamp is not None:
            self.__data["start_timestamp"].value = start_timestamp
        if end_timestamp is not None:
            self.__data["end_timestamp"].value = end_timestamp
        if reporte is not None:
            self.__data["reporte"].value = reporte
        if description is not None:
            self.__data["description"].value = description
        if nodo_inicio is not None:
            self.__data["nodo_inicio"].value = nodo_inicio
        if cant_preguntas is not None:
            self.__data["cant_preguntas"].value = cant_preguntas
        if tiempo_sesion is not None:
            self.__data["tiempo_sesion"].value = tiempo_sesion
        super().update("event_id", event_id)

    def delete(self, event_id: int) -> None:
        super().delete("event_id", event_id)

    def get_reporte_by_event_id(self, event_id: int) -> Optional[str]:
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "reporte"):
            return result[0].reporte
        return None

    def get_description_by_event_id(self, event_id: int) -> Optional[str]:
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "description"):
            return result[0].description
        return None

    def get_nodo_inicio_by_event_id(self, event_id: int) -> Optional[int]:
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "nodo_inicio"):
            return result[0].nodo_inicio
        return None

    def get_cant_preguntas_by_event_id(self, event_id: int) -> Optional[int]:
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "cant_preguntas"):
            return result[0].cant_preguntas
        return None

    def get_time_by_event_id(self, event_id: int) -> Optional[int]:
        """
        Retorna el tiempo de sesión (tiempo_sesion) del evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "tiempo_sesion"):
            return result[0].tiempo_sesion
        return None



from typing import Optional, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field

class Events(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "event_id":         Field(None, DataType.INTEGER,   False, True),
            "user_id":          Field(None, DataType.INTEGER,   False, False),
            "name":             Field(None, DataType.STRING,    False, False),
            "start_timestamp":  Field(None, DataType.TIMESTAMP, True,  False),
            "end_timestamp":    Field(None, DataType.TIMESTAMP, True,  False),
            "reporte":          Field(None, DataType.TEXT,       True,  False),
            "description":      Field(None, DataType.TEXT,       True,  False),
            "nodo_inicio":      Field(None, DataType.INTEGER,   True,  False),
            "cant_preguntas":   Field(None, DataType.INTEGER,   True,  False),  # ✅ agregado
        }
        super().__init__("events", self.__data)

    def add(
        self,
        user_id: int,
        name: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        reporte: Optional[str] = None,
        description: Optional[str] = None,
        nodo_inicio: Optional[int] = None,
        cant_preguntas: Optional[int] = None   # ✅ agregado
    ) -> int:
        self.__data["event_id"].value         = None
        self.__data["user_id"].value          = user_id
        self.__data["name"].value             = name
        self.__data["start_timestamp"].value  = start_timestamp
        self.__data["end_timestamp"].value    = end_timestamp
        self.__data["reporte"].value          = reporte
        self.__data["description"].value      = description
        self.__data["nodo_inicio"].value      = nodo_inicio
        self.__data["cant_preguntas"].value   = cant_preguntas   # ✅ agregado
        return super().add()

    def get_by_user(self, user_id: int):
        return super().get("user_id", user_id)

    def get_by_id(self, event_id: int):
        result = super().get("event_id", event_id)
        return result[0] if result else None

    def update(
        self,
        event_id: int,
        name: Optional[str] = None,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        reporte: Optional[str] = None,
        description: Optional[str] = None,
        nodo_inicio: Optional[int] = None,
        cant_preguntas: Optional[int] = None   # ✅ agregado
    ) -> None:
        self.__data["event_id"].value = event_id
        if name is not None:
            self.__data["name"].value = name
        if start_timestamp is not None:
            self.__data["start_timestamp"].value = start_timestamp
        if end_timestamp is not None:
            self.__data["end_timestamp"].value = end_timestamp
        if reporte is not None:
            self.__data["reporte"].value = reporte
        if description is not None:
            self.__data["description"].value = description
        if nodo_inicio is not None:
            self.__data["nodo_inicio"].value = nodo_inicio
        if cant_preguntas is not None:
            self.__data["cant_preguntas"].value = cant_preguntas   # ✅ agregado
        super().update("event_id", event_id)

    def delete(self, event_id: int) -> None:
        super().delete("event_id", event_id)

    def get_reporte_by_event_id(self, event_id: int) -> Optional[str]:
        """
        Retorna el reporte del evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "reporte"):
            return result[0].reporte
        return None

    def get_description_by_event_id(self, event_id: int) -> Optional[str]:
        """
        Retorna la descripción del evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "description"):
            return result[0].description
        return None

    def get_nodo_inicio_by_event_id(self, event_id: int) -> Optional[int]:
        """
        Retorna el valor de nodo_inicio para el evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "nodo_inicio"):
            return result[0].nodo_inicio
        return None

    def get_cant_preguntas_by_event_id(self, event_id: int) -> Optional[int]:
        """
        Retorna la cantidad de preguntas (cant_preguntas) del evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "cant_preguntas"):
            return result[0].cant_preguntas
        return None



ev = Events()

nodo_inicio = ev.get_cant_preguntas_by_event_id(2)
print(nodo_inicio)



from typing import Optional, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field

class Events(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "event_id":         Field(None, DataType.INTEGER,   False, True),
            "user_id":          Field(None, DataType.INTEGER,   False, False),
            "name":             Field(None, DataType.STRING,    False, False),
            "start_timestamp":  Field(None, DataType.TIMESTAMP, True,  False),
            "end_timestamp":    Field(None, DataType.TIMESTAMP, True,  False),
            "reporte":          Field(None, DataType.TEXT,       True,  False),
            "description":      Field(None, DataType.TEXT,       True,  False),
            "nodo_inicio":      Field(None, DataType.INTEGER,   True,  False),
        }
        super().__init__("events", self.__data)

    def add(
        self,
        user_id: int,
        name: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        reporte: Optional[str] = None,
        description: Optional[str] = None,
        nodo_inicio: Optional[int] = None
    ) -> int:
        self.__data["event_id"].value         = None
        self.__data["user_id"].value          = user_id
        self.__data["name"].value             = name
        self.__data["start_timestamp"].value  = start_timestamp
        self.__data["end_timestamp"].value    = end_timestamp
        self.__data["reporte"].value          = reporte
        self.__data["description"].value      = description
        self.__data["nodo_inicio"].value      = nodo_inicio
        return super().add()

    def get_by_user(self, user_id: int):
        return super().get("user_id", user_id)

    def get_by_id(self, event_id: int):
        result = super().get("event_id", event_id)
        return result[0] if result else None

    def update(
        self,
        event_id: int,
        name: Optional[str] = None,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        reporte: Optional[str] = None,
        description: Optional[str] = None,
        nodo_inicio: Optional[int] = None
    ) -> None:
        self.__data["event_id"].value = event_id
        if name is not None:
            self.__data["name"].value = name
        if start_timestamp is not None:
            self.__data["start_timestamp"].value = start_timestamp
        if end_timestamp is not None:
            self.__data["end_timestamp"].value = end_timestamp
        if reporte is not None:
            self.__data["reporte"].value = reporte
        if description is not None:
            self.__data["description"].value = description
        if nodo_inicio is not None:
            self.__data["nodo_inicio"].value = nodo_inicio
        super().update("event_id", event_id)

    def delete(self, event_id: int) -> None:
        super().delete("event_id", event_id)

    def get_reporte_by_event_id(self, event_id: int) -> Optional[str]:
        """
        Retorna el reporte del evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "reporte"):
            return result[0].reporte
        return None

    def get_description_by_event_id(self, event_id: int) -> Optional[str]:
        """
        Retorna la descripción del evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "description"):
            return result[0].description
        return None

    def get_nodo_inicio_by_event_id(self, event_id: int) -> Optional[int]:
        """
        Retorna el valor de nodo_inicio para el evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "nodo_inicio"):
            return result[0].nodo_inicio
        return None

ev = Events()

nodo_inicio = ev.get_reporte_by_event_id(2)
print(nodo_inicio)

from typing import Optional, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field

class Events(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "event_id":         Field(None, DataType.INTEGER,   False, True),
            "user_id":          Field(None, DataType.INTEGER,   False, False),
            "name":             Field(None, DataType.STRING,    False, False),
            "start_timestamp":  Field(None, DataType.TIMESTAMP, True,  False),
            "end_timestamp":    Field(None, DataType.TIMESTAMP, True,  False),
            "location":         Field(None, DataType.STRING,    True,  False),
            "description":      Field(None, DataType.TEXT,      True,  False),
            "nodo_inicio":      Field(None, DataType.INTEGER,   True,  False),
        }
        super().__init__("events", self.__data)

    def add(
        self,
        user_id: int,
        name: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        nodo_inicio: Optional[int] = None
    ) -> int:
        self.__data["event_id"].value         = None
        self.__data["user_id"].value          = user_id
        self.__data["name"].value             = name
        self.__data["start_timestamp"].value  = start_timestamp
        self.__data["end_timestamp"].value    = end_timestamp
        self.__data["location"].value         = location
        self.__data["description"].value      = description
        self.__data["nodo_inicio"].value      = nodo_inicio
        return super().add()

    def get_by_user(self, user_id: int):
        return super().get("user_id", user_id)

    def get_by_id(self, event_id: int):
        result = super().get("event_id", event_id)
        return result[0] if result else None

    def update(
        self,
        event_id: int,
        name: Optional[str] = None,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        nodo_inicio: Optional[int] = None
    ) -> None:
        self.__data["event_id"].value = event_id
        if name is not None:
            self.__data["name"].value = name
        if start_timestamp is not None:
            self.__data["start_timestamp"].value = start_timestamp
        if end_timestamp is not None:
            self.__data["end_timestamp"].value = end_timestamp
        if location is not None:
            self.__data["location"].value = location
        if description is not None:
            self.__data["description"].value = description
        if nodo_inicio is not None:
            self.__data["nodo_inicio"].value = nodo_inicio
        super().update("event_id", event_id)

    def delete(self, event_id: int) -> None:
        super().delete("event_id", event_id)

    def get_description_by_event_id(self, event_id: int) -> Optional[str]:
        """
        Retorna la descripción del evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "description"):
            return result[0].description
        return None

    def get_nodo_inicio_by_event_id(self, event_id: int) -> Optional[int]:
        """
        Retorna el valor de nodo_inicio para el evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "nodo_inicio"):
            return result[0].nodo_inicio
        return None




from typing import Optional, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field

class Events(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "event_id":         Field(None, DataType.INTEGER, False, True),
            "user_id":          Field(None, DataType.INTEGER, False, False),
            "name":             Field(None, DataType.STRING,  False, False),
            "start_timestamp":  Field(None, DataType.TIMESTAMP, True,  False),
            "end_timestamp":    Field(None, DataType.TIMESTAMP, True,  False),
            "location":         Field(None, DataType.STRING,  True,  False),
            "description":      Field(None, DataType.TEXT,    True,  False)
        }
        super().__init__("events", self.__data)

    def add(
        self,
        user_id: int,
        name: str,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None
    ) -> int:
        self.__data["event_id"].value         = None
        self.__data["user_id"].value          = user_id
        self.__data["name"].value             = name
        self.__data["start_timestamp"].value  = start_timestamp
        self.__data["end_timestamp"].value    = end_timestamp
        self.__data["location"].value         = location
        self.__data["description"].value      = description
        return super().add()

    def get_by_user(self, user_id: int):
        return super().get("user_id", user_id)

    def get_by_id(self, event_id: int):
        result = super().get("event_id", event_id)
        return result[0] if result else None

    def update(
        self,
        event_id: int,
        name: Optional[str] = None,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None
    ) -> None:
        self.__data["event_id"].value = event_id
        if name is not None:
            self.__data["name"].value = name
        if start_timestamp is not None:
            self.__data["start_timestamp"].value = start_timestamp
        if end_timestamp is not None:
            self.__data["end_timestamp"].value = end_timestamp
        if location is not None:
            self.__data["location"].value = location
        if description is not None:
            self.__data["description"].value = description
        super().update("event_id", event_id)

    def delete(self, event_id: int) -> None:
        super().delete("event_id", event_id)


    def get_description_by_event_id(self, event_id: int) -> Optional[str]:
        """
        Retorna la descripción del evento identificado por event_id.
        """
        result = super().get("event_id", event_id)
        if result and hasattr(result[0], "description"):
            return result[0].description
        return None
    
'''