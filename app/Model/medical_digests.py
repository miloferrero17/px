# app/Model/medical_digests.py
from typing import Any, Dict
from app.Model.base_model import BaseModel, Field, DataType  # <- mismo casing que tu estructura

class MedicalDigests(BaseModel):
    def __init__(self):
        data = {
            "id":           Field(None, DataType.INTEGER,  False, True),   # PK autoincremental
            "contact_id":   Field(None, DataType.INTEGER,  False, False),
            "tx_id":        Field(None, DataType.INTEGER,  False, True),   # UNIQUE para idempotencia
            "digest_text":  Field(None, DataType.STRING,   False, False),
            "digest_json":  Field(None, DataType.STRING,   False, False),  # json serializado como texto
            "created_at":   Field(None, DataType.TIMESTAMP, True,  False),
        }
        super().__init__("medical_digests", data)
        # acceso directo a los campos si lo necesitás (como en otros modelos)
        self.data = self._BaseModel__data

    def add_row(self, *, contact_id: int, tx_id: int, digest_text: str, digest_json: str) -> Dict[str, Any]:
        """
        Inserta (o actualiza si ya existe tx_id) una fila de digest.
        Usa upsert por 'tx_id' para garantizar idempotencia.
        """
        row = {
            "contact_id":  contact_id,
            "tx_id":       tx_id,
            "digest_text": digest_text,
            "digest_json": digest_json,
        }
        return self.upsert(row, on_conflict="tx_id")


# (Opcional) Registrar una clase Register para compatibilidad con BaseModel.get, si alguna vez la usás
class MedicalDigestsRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"MedicalDigestsRegister({self.__dict__})"

globals()["MedicalDigestsRegister"] = MedicalDigestsRegister
