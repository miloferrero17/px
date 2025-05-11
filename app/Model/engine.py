# engine.py

from typing import Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel, MessagesRegister
from app.Model.field import Field
from datetime import datetime


class Engine(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "status_id": Field(None, DataType.INTEGER, False, True),
            "created_at": Field(None, DataType.TIMESTAMP, False, False),
            "Python_Code": Field(None, DataType.STRING, False, False),
            "event_id": Field(None, DataType.INTEGER, False, False)

        }

        super().__init__("engine", self.__data)


    def add(self, status_id: int, created_at, message_text: str, python_code: str, event_id: int) -> int:
        self.__data["status_id"].value = status_id
        self.__data["created_at"].value = created_at.strftime("%Y-%m-%d %H:%M:%S")  # 👈 conversión a string
        self.__data["Python_Code"].value = python_code
        self.__data["event_id"].value = event_id
        return super().add()

    def get_by_id(self, status_id: int) -> MessagesRegister:
        result = super().get("status_id", status_id)
        return result[0] if result else None


 
    def get_by_status(self, event_id: int):
        return super().get("event_id", event_id)


    def update(self, status_id: int, created_at, message_text: str, python_code: str, event_id: int) -> None:
        self.__data["status_id"].value = status_id
        self.__data["created_at"].value = created_at
        self.__data["Python_Code"].value = python_code
        self.__data["event_id"].value = event_id
        super().update("status_id", status_id)


    def delete(self, status_id: int) -> None:
        super().delete("status_id", status_id)