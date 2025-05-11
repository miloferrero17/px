from typing import Optional, List, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel, MessagesRegister
from app.Model.field import Field


class Log(BaseModel):
    def __init__(self):
        # Definición de la estructura de la tabla "Log_messages"
        self.__data: Dict[str, Field] = {
            "message_id": Field(None, DataType.INTEGER, False, True),
            "contact_id": Field(None, DataType.INTEGER, False, False),
            "message_type": Field(None, DataType.STRING, False, False),
            "content": Field(None, DataType.STRING, False, False),
            "timestamp": Field(None, DataType.TIMESTAMP, False, False),
            "whatsapp_message_id": Field(None, DataType.STRING, True, False)
        }
        # Se llama a BaseModel pasando el nombre de la tabla y la estructura de datos
        super().__init__("log", self.__data)



    def add(self, contact_id: int, message_type: str, content: str, whatsapp_message_id: Optional[str] = None) -> int:
        """
        Inserta un nuevo registro en Log_messages y retorna su ID.
        """
        self.__data["message_id"].value = None
        self.__data["contact_id"].value = contact_id
        self.__data["message_type"].value = message_type
        self.__data["content"].value = content
        # Se deja en None para que la base de datos asigne el CURRENT_TIMESTAMP por defecto
        self.__data["timestamp"].value = None
        self.__data["whatsapp_message_id"].value = whatsapp_message_id
        return super().add()


    def get_by_id(self, message_id: int) -> Optional[MessagesRegister]:
        """
        Retorna una instancia de MessagesRegister con los datos del registro identificado por message_id.
        """
        result = super().get("message_id", message_id)
        return result[0] if result else None

    def get_by_contact_id(self, contact_id: int) -> Optional[List[MessagesRegister]]:
        """
        Retorna una lista de instancias de MessagesRegister con los registros asociados al contact_id proporcionado.
        """
        return super().get("contact_id", contact_id)
    
    def update(
        self,
        message_id: int,
        contact_id: Optional[int] = None,
        message_type: Optional[str] = None,
        content: Optional[str] = None,
        whatsapp_message_id: Optional[str] = None
    ) -> None:
        """
        Actualiza los datos de un registro identificado por message_id.
        Solo se actualizan los campos cuyo valor no sea None.
        """
        self.__data["message_id"].value = message_id
        if contact_id is not None:
            self.__data["contact_id"].value = contact_id
        if message_type is not None:
            self.__data["message_type"].value = message_type
        if content is not None:
            self.__data["content"].value = content
        if whatsapp_message_id is not None:
            self.__data["whatsapp_message_id"].value = whatsapp_message_id
        super().update("message_id", message_id)


    def delete(self, message_id: int) -> None:
        """
        Elimina el registro identificado por message_id.
        """
        super().delete("message_id", message_id)