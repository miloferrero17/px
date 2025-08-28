from typing import Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field
from app.Model.exceptions import DatabaseError

class PxHceReport(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            # PK / FKs
            "id":                    Field(None, DataType.INTEGER, False, True),
            "contact_id":            Field(None, DataType.INTEGER, False, False),
            "tx_id":                 Field(None, DataType.INTEGER, False, False),

            # Paciente
            "patient_dni":           Field(None, DataType.STRING,  True,  False),
            "birth_date":            Field(None, DataType.DATE,    True,  False),
            "genero":                Field(None, DataType.STRING,  True,  False),

            # Encuentro
            "encounter_class":       Field("emergency", DataType.STRING, False, False),
            "encounter_started_at":  Field(None, DataType.TIMESTAMP, True,  False),
            "encounter_ended_at":    Field(None, DataType.TIMESTAMP, True,  False),

            # Profesional
            "clinician_name":        Field(None, DataType.STRING,  True,  False),
            "clinician_license":     Field(None, DataType.STRING,  True,  False),

            # Núcleo clínico
            "chief_complaint":       Field(None, DataType.TEXT,    True,  False),
            "main_symptom":          Field(None, DataType.TEXT,    True,  False),
            "associated_symptoms":   Field(None, DataType.JSON,    True,  False),  # ← JSON
            "trigger_factor":        Field(None, DataType.TEXT,    True,  False),
            "onset_text":            Field(None, DataType.TEXT,    True,  False),
            "evolucion":             Field(None, DataType.TEXT,    True,  False),
            "meds_taken_prior":      Field(None, DataType.TEXT,    True,  False),
            "pain_scale":            Field(None, DataType.INTEGER, True,  False),
            "pain_text":             Field(None, DataType.TEXT,    True,  False),
            "vitals":                Field(None, DataType.JSON,    True,  False),  # ← JSON
            "triage_text":           Field(None, DataType.TEXT,    True,  False),
            "physical_exam":         Field(None, DataType.TEXT,    True,  False),

            # Antecedentes
            "personal_history":      Field(None, DataType.TEXT,    True,  False),
            "family_history":        Field(None, DataType.TEXT,    True,  False),
            "surgeries":             Field(None, DataType.TEXT,    True,  False),
            "allergies":             Field(None, DataType.TEXT,    True,  False),
            "current_medication":    Field(None, DataType.TEXT,    True,  False),
            "pregnancy_status":      Field(None, DataType.STRING,  True,  False),
            "immunizations_summary": Field(None, DataType.TEXT,    True,  False),

            # Snapshot + integridad
            "final_summary":         Field(None, DataType.JSON,    False, False),  # ← JSON
            "content_sha256":        Field(None, DataType.STRING,  False, False),

            # Timestamps
            "created_at":            Field(None, DataType.TIMESTAMP, True, False),
            "updated_at":            Field(None, DataType.TIMESTAMP, True, False),
        }
        super().__init__("px_hce_report", self.__data)

    def upsert_by_tx(self, row: Dict) -> Dict:
        try:
            return self.upsert(row, on_conflict="tx_id")
        except Exception as e:
            raise DatabaseError(f"Error en upsert_by_tx: {e}")
