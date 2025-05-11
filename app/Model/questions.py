from typing import Optional, List, Dict, Any
from app.Model.enums import DataType
from app.Model.base_model import BaseModel, QuestionsRegister
from app.Model.field import Field
import os

class Questions(BaseModel):
    def __init__(self):
        self._data: Dict[str, Field] = {
            "question_id": Field(None, DataType.INTEGER, False, True),
            "event_id": Field(None, DataType.INTEGER, False, False),
            "group_id": Field(None, DataType.INTEGER, False, False),
            "group_name": Field(None, DataType.STRING, False, False),
            "question_name": Field(None, DataType.STRING, False, False)
        }
        super().__init__("questions", self._data)
        

    def add(self, event_id: int, group_id: int, group_name: str, question_name: str) -> int:
        self._data["question_id"].value = None
        self._data["event_id"].value = event_id
        self._data["group_id"].value = group_id
        self._data["group_name"].value = group_name
        self._data["question_name"].value = question_name
        return super().add()

    def get_question_name_by_id(self, question_id: int) -> str:
        query = f"question_id=eq.{question_id}"
        res = self._fetch_one(query)
        return res['question_name'] if res else None

    def get_by_event_id(self, event_id: int) -> Optional[List[QuestionsRegister]]:
        return super().get("event_id", event_id)

    def get_by_id(self, question_id: int) -> Optional[QuestionsRegister]:
        """
        Retorna una instancia de QuestionsRegister con los datos de la pregunta identificada por question_id.
        """
        result = super().get("question_id", question_id)
        return result[0] if result else None

    def get_by_group_id(self, group_id: int) -> Optional[List[QuestionsRegister]]:
        return super().get("group_id", group_id)

    def get_by_question_id(self, question_id: int) -> Optional[QuestionsRegister]:
        result = super().get("question_id", question_id)
        return result[0] if result else None

    def get_groups_by_event_id(self, event_id: int) -> List[Dict[str, Any]]:
        """
        Devuelve una lista de grupos únicos (group_id, group_name) asociados a un evento.
        """
        resultados = self.get_by_event_id(event_id)
        if not resultados:
            return []

        grupos_vistos = set()
        grupos_unicos = []

        for r in resultados:
            clave = (r.group_id, r.group_name)
            if clave not in grupos_vistos:
                grupos_vistos.add(clave)
                grupos_unicos.append({
                    "group_id": r.group_id,
                    "group_name": r.group_name
                })

        return grupos_unicos

    def get_question_ids_by_group_id(self, group_id: int) -> List[int]:
        """
        Devuelve una lista con los IDs de las preguntas asociadas a un group_id.
        """
        resultados = self.get_by_group_id(group_id)
        if not resultados:
            return []

        return [r.question_id for r in resultados]

    def get_questions_by_group_id(self, group_id: int) -> List[str]:
        """
        Devuelve una lista con los nombres de las preguntas (question_name)
        asociadas a un group_id.
        """
        resultados = self.get_by_group_id(group_id)
        if not resultados:
            return []

        return [r.question_name for r in resultados]

    def get_next_question_id(self, current_question_id: int) -> Any:
        """
        Dado un question_id, devuelve el siguiente question_id dentro del mismo group_id.
        Si no hay uno siguiente, devuelve "No existe".
        """
        actual = self.get_by_question_id(current_question_id)
        if not actual:
            return "No existe"

        group_id = actual.group_id
        preguntas = self.get_question_ids_by_group_id(group_id)

        if current_question_id not in preguntas:
            return "No existe"

        preguntas.sort()  # ordenar por ID ascendente
        index = preguntas.index(current_question_id)

        if index + 1 < len(preguntas):
            return preguntas[index + 1]
        else:
            return "No existe"

    def delete(self, question_id: int) -> None:
        super().delete("question_id", question_id)

'''
if __name__ == "__main__":
    qs = Questions()
    siguiente = qs.get_next_question_id(10)  # por ejemplo, si 5 es un question_id
    print(siguiente)



from typing import Optional, List, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel, QuestionsRegister
from app.Model.field import Field

class Questions(BaseModel):
    def __init__(self):
        self._data: Dict[str, Field] = {
            "question_id": Field(None, DataType.INTEGER, False, True),
            "event_id": Field(None, DataType.INTEGER, False, False),
            "group_id": Field(None, DataType.INTEGER, False, False),
            "group_name": Field(None, DataType.STRING, False, False),
            "question_name": Field(None, DataType.STRING, False, False)
        }
        super().__init__("questions", self._data)

    def add(self, event_id: int, group_id: int, group_name: str, question_name: str) -> int:
        self._data["question_id"].value = None
        self._data["event_id"].value = event_id
        self._data["group_id"].value = group_id
        self._data["group_name"].value = group_name
        self._data["question_name"].value = question_name
        return super().add()

    def get_by_event_id(self, event_id: int) -> Optional[List[QuestionsRegister]]:
        return super().get("event_id", event_id)

    def get_by_group_id(self, group_id: int) -> Optional[List[QuestionsRegister]]:
        return super().get("group_id", group_id)

    def get_by_question_id(self, question_id: int) -> Optional[QuestionsRegister]:
        result = super().get("question_id", question_id)
        return result[0] if result else None



    def delete(self, question_id: int) -> None:
        super().delete("question_id", question_id)


'''
