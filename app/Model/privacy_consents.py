from typing import Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field
import os
PRIVACY_NOTICE_VERSION = os.getenv("PRIVACY_NOTICE_VERSION", "v1.0")


class PrivacyConsents(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "id":         Field(None, DataType.INTEGER, False, True),
            "contact_id": Field(None, DataType.INTEGER, False, False),
            "phone_hash": Field(None, DataType.STRING,  False, False),
            "dni_hash":   Field(None, DataType.STRING,  False, False),
            "privacy_notice_version": Field(None, DataType.STRING, False, False),
        }
        super().__init__("privacy_consents", self.__data)

    def add_row(
        self,
        contact_id: int,
        phone_hash: str = None,
        privacy_notice_version: str = "v1.0",
        dni_hash: str = None,
    ) -> int:
        """
        Inserta un registro de consentimiento.
        accepted_at / created_at se setean en la DB con DEFAULT NOW().
        """
        # ⚠ Normalizamos a string vacío para no mandar None a campos NOT NULL
        phone_hash = phone_hash or ""
        dni_hash = dni_hash or ""

        self.__data["id"].value = None
        self.__data["contact_id"].value = contact_id
        self.__data["phone_hash"].value = phone_hash
        self.__data["dni_hash"].value = dni_hash
        self.__data["privacy_notice_version"].value = privacy_notice_version
        return super().add()

    def has_consent(self, dni_hash: str = None) -> bool:
        if not dni_hash:
            return False
        try:
            rows = self.get("dni_hash", dni_hash)
            return bool(rows)
        except Exception as e:
            print(f"[CONSENT] error en has_consent: {e}")
            return False




