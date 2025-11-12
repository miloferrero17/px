# app/Model/redsom_digest.py
from typing import Any, Dict
from app.Model.base_model import BaseModel, Field, DataType  # mismo casing que el resto

class RedsomDigest(BaseModel):
    def __init__(self):
        data = {
            "id":                   Field(None, DataType.INTEGER,   False, True),   # PK autoincremental
            "tx_id":                Field(None, DataType.INTEGER,   False, True),   # UNIQUE para idempotencia
            "contact_id":           Field(None, DataType.INTEGER,   False, False),
            "event_id":             Field(2,    DataType.INTEGER,   False, False),  # por defecto 2 en este flujo
            "decision":             Field(None, DataType.STRING,    False, False),  # 'GUARDIA' | 'TELECONSULTA'
            "reason":               Field(None, DataType.STRING,    False, False),  # explicación breve
            "conversation_summary": Field(None, DataType.STRING,    False, False),  # resumen compacto
            "created_at":           Field(None, DataType.TIMESTAMP, True,  False),  # lo completa la DB
        }
        super().__init__("redsom_digest", data)
        self.data = self._BaseModel__data  # acceso similar a otros modelos

    def add_row(
        self, *, contact_id: int, tx_id: int, event_id: int,
        decision: str, reason: str, conversation_summary: str
    ) -> Dict[str, Any]:
        """
        Inserta (o actualiza si ya existe tx_id) una fila del digest de Redsom.
        Usa upsert por 'tx_id' para asegurar idempotencia.
        """
        row = {
            "contact_id":           contact_id,
            "tx_id":                tx_id,
            "event_id":             event_id,
            "decision":             decision,
            "reason":               reason,
            "conversation_summary": conversation_summary,
        }
        return self.upsert(row, on_conflict="tx_id")


# (Opcional) Clase Register para compatibilidad con BaseModel.get, si la usás
class RedsomDigestRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        return f"RedsomDigestRegister({self.__dict__})"

globals()["RedsomDigestRegister"] = RedsomDigestRegister
