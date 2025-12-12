from typing import Optional, List, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel, TransactionsRegister
from app.Model.field import Field
from datetime import datetime, timezone, timedelta
import hashlib

class Transactions(BaseModel):
    def __init__(self):
        # Definición de campos, incluyendo id como clave única y event_id tipo SMALLINT (int2)
        fields: Dict[str, Field] = {
            "id": Field(None, DataType.INTEGER, False, True),
            "event_id": Field(None, DataType.INTEGER, True, False),  # int2 / SMALLINT
            "contact_id": Field(None, DataType.INTEGER, False, False),
            "name": Field(None, DataType.STRING, False, False),
            "phone": Field(None, DataType.STRING, True, False),
            "conversation": Field(None, DataType.STRING, False, False),
            "timestamp": Field(None, DataType.TIMESTAMP, False, False),
            "puntuacion": Field(None, DataType.INTEGER, True, False),  # int2 / SMALLINT
            "comentario": Field(None, DataType.STRING, True, False),    # text
            "data_created": Field(None, DataType.TIMESTAMP, False, False),  # timestamp de creación



            "question_cursor": Field(None, DataType.INTEGER, False, False),     # contador de preguntas (por sesión)
            "last_question_fingerprint": Field(None, DataType.STRING, True, False),  # hash sha256 de la última pregunta
            "last_question_sent_at": Field(None, DataType.TIMESTAMP, True, False),   # timestamptz del último envío

        }
        super().__init__("transactions", fields)
        # Exponer los campos para facilitar su uso
        self.data = self._BaseModel__data

    def add(
        self,
        contact_id: int,
        phone: str,
        name: Optional[str] = None,
        conversation: str = "",
        timestamp: Optional[str] = None,
        event_id: Optional[int] = None,
        puntuacion: Optional[int] = None,
        comentario: Optional[str] = None,
        data_created: Optional[str] = None,


    ) -> int:
        # Inicializa el id en None para auto-incrementar
        self.data["id"].value = None
        self.data["event_id"].value = event_id
        self.data["contact_id"].value = contact_id
        self.data["phone"].value = phone
        self.data["name"].value = name
        self.data["conversation"].value = conversation
        self.data["timestamp"].value = timestamp
        self.data["puntuacion"].value = puntuacion
        self.data["comentario"].value = comentario
        self.data["data_created"].value = data_created



        return super().add()

    def get_by_id(self, id: int) -> Optional[TransactionsRegister]:
        results = super().get("id", id, order_field="timestamp")
        return results[0] if results else None

    def get_last_timestamp_by_phone(self, phone: str) -> Optional[Dict[str, str]]:
        results = super().get("phone", phone, order_field="timestamp")
        if not results:
            return None
        last = results[-1]
        return {
            "id": last.id,
            "timestamp": last.timestamp,
            "name": last.name
        }

    def get_by_contact_id(self, contact_id: int) -> List[TransactionsRegister]:
        return super().get("contact_id", contact_id, order_field="timestamp")

    def get_by_name(self, name: str) -> List[TransactionsRegister]:
        return super().get("name", name, order_field="timestamp")

    def get_open_conversation_by_contact_id(self, contact_id: int) -> str:
        transactions = self.get_by_contact_id(contact_id)
        for tx in transactions:
            if tx.name == "Abierta":
                return tx.conversation or ""
        return ""

    def get_open_transaction_id_by_contact_id(self, contact_id: int) -> Optional[int]:
        transactions = self.get_by_contact_id(contact_id)
        abiertas = [tx for tx in transactions if tx.name == "Abierta"]
        return abiertas[-1].id if abiertas else None

    def get_event_id_by_tx_id(self, tx_id: int) -> Optional[int]:
        """
        Retorna el event_id asociado a una transacción dada su id.
        """
        tx = self.get_by_id(tx_id)
        return tx.event_id if tx and tx.event_id is not None else None

    def update(
        self,
        id: int,
        contact_id: Optional[int] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        conversation: Optional[str] = None,
        timestamp: Optional[str] = None,
        event_id: Optional[int] = None,
        puntuacion: Optional[int] = None,
        comentario: Optional[str] = None,
    ) -> None:
        # Establecer id para la clave única
        self.data["id"].value = id

        # Actualiza solo los campos proporcionados
        if event_id is not None:
            self.data["event_id"].value = event_id
        if contact_id is not None:
            self.data["contact_id"].value = contact_id
        if phone is not None:
            self.data["phone"].value = phone
        if name is not None:
            self.data["name"].value = name
        if conversation is not None:
            self.data["conversation"].value = conversation
        if timestamp is not None:
            self.data["timestamp"].value = timestamp
        if puntuacion is not None:
            self.data["puntuacion"].value = puntuacion
        if comentario is not None:
            self.data["comentario"].value = comentario

        # Llama a la actualización usando 'id' como clave única
        super().update("id", id)


    def delete(self, id: int) -> None:
        super().delete("id", id)

 # --------- Estado “abierta” (sin cobranzas) ----------

    def get_last_transaction_by_event_and_phone(
        self, event_id: int, phone: str
    ) -> Optional[TransactionsRegister]:
        """
        Retorna la última transacción asociada a un event_id y un teléfono dado,
        o None si no existe.
        """
        # Primero traemos todas las txs de ese teléfono ordenadas por timestamp
        txs_por_telf = super().get("phone", phone, order_field="timestamp")
        # Filtramos sólo las que tengan el event_id buscado
        txs_filtradas = [tx for tx in txs_por_telf if tx.event_id == event_id]
        # Devolvemos la última (más reciente) o None
        return txs_filtradas[-1] if txs_filtradas else None

    def get_conversation_by_id(self, tx_id) -> str:
        """
        Devuelve el JSON de `conversation` de la transacción con id = tx_id,
        o cadena vacía si no existe o está vacío.
        Acepta `tx_id` int o str.
        """
        try:
            tx_id_int = int(tx_id)
        except (ValueError, TypeError):
            return ""

        tx = self.get_by_id(tx_id_int)
        return tx.conversation or ""
    
    def is_last_transaction_closed(self, phone: str) -> int:
        """
        Retorna 1 si la última transacción del teléfono tiene name == "Cerrada", 0 en caso contrario.
        """
        txs = super().get("phone", phone, order_field="timestamp")
        if not txs:
            return 0
        ultima_tx = txs[-1]
        return 1 if ultima_tx.name == "Cerrada" else 0
    


    def get_last_abierta_by_contact_id(self, contact_id: int):
        """
        #Fallback: trae la última fila con name='Abierta' (sin importar status).
        """
        txs = self.get_by_contact_id(contact_id)
        if not txs:
            return None
        abiertas = [tx for tx in txs if getattr(tx, "name", None) == "Abierta"]
        return abiertas[-1] if abiertas else None
    


    def get_open_row(self, contact_id: int) -> Optional[TransactionsRegister]:
        """
        Devuelve la transacción 'activa' del contacto: última con name='Abierta'.
        """
        return self.get_last_abierta_by_contact_id(contact_id)

    def get_open_tx_id(self, contact_id: int) -> Optional[int]:
        """
        Id de la TX activa (ver get_open_row).
        """
        row = self.get_open_row(contact_id)
        return row.id if row else None
    
    # === Preguntas / Sherlock state ===
    def get_question_state(self, contact_id: int):
        """
        Devuelve (cursor:int, last_fp:str|None, last_sent_at:str|None) de la TX abierta del contacto.
        Si no hay TX abierta, retorna (0, None, None).
        """
        row = self.get_open_row(contact_id)
        if not row:
            return 0, None, None
        cursor = int(getattr(row, "question_cursor", 0) or 0)
        last_fp = getattr(row, "last_question_fingerprint", None)
        last_sent_at = getattr(row, "last_question_sent_at", None)
        return cursor, last_fp, last_sent_at

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

    @staticmethod
    def _now_iso_utc() -> str:
        # ISO con microsegundos compatible con tu update actual
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    def register_question_attempt_by_contact(
        self,
        contact_id: int,
        *,
        fingerprint: str,
        debounce_seconds: int = 90
    ):
        """
        Idempotencia + debounce por TX ABIERA del contact_id.
        Retorna (status, cursor):
          - status: "new" | "resend" | "skip" | "no_tx"
          - cursor: valor final de question_cursor tras la operación
        Reglas:
          • Si fingerprint != último → incrementa cursor, set fp y sent_at → "new"
          • Si fingerprint == último:
               - si pasaron >= debounce → solo actualiza sent_at → "resend"
               - si no → no hace nada → "skip"
          • Si no hay TX abierta → "no_tx", 0
        """
        row = self.get_open_row(contact_id)
        if not row:
            return "no_tx", 0

        current_cursor = int(getattr(row, "question_cursor", 0) or 0)
        last_fp = getattr(row, "last_question_fingerprint", None)
        last_sent_at = getattr(row, "last_question_sent_at", None)
        now_iso = self._now_iso_utc()

        # Caso: pregunta nueva
        if (last_fp or "") != (fingerprint or ""):
            new_cursor = current_cursor + 1
            try:
                self.update(
                    id=row.id,
                    contact_id=row.contact_id,
                    phone=row.phone,
                    name=getattr(row, "name", "Abierta"),
                    event_id=getattr(row, "event_id", None),
                    # solo los 3 campos + timestamp
                    # (tu update es parcial: solo setea lo que no es None)
                )
                # Ahora setear nuestros 3 campos
                self.data["question_cursor"].value = new_cursor
                self.data["last_question_fingerprint"].value = fingerprint
                self.data["last_question_sent_at"].value = now_iso
                self.data["timestamp"].value = now_iso
                super().update("id", row.id)
            except Exception as e:
                print(f"[Transactions.register_question_attempt_by_contact] error NEW en TX {row.id}: {e}")
            return "new", new_cursor

        # Caso: mismo fingerprint → posible retry
        # parse last_sent_at (puede venir None)
        last_dt = None
        if last_sent_at:
            try:
                last_dt = datetime.fromisoformat(str(last_sent_at).replace("Z", "+00:00"))
            except Exception:
                last_dt = None

        should_resend = True
        if last_dt:
            should_resend = (datetime.now(timezone.utc) - last_dt) >= timedelta(seconds=debounce_seconds)

        if should_resend:
            # Política nueva: no reenviar ni tocar DB ante duplicados.
            return "skip", current_cursor

        return "skip", current_cursor

    def set_question_zero(
        self,
        contact_id: int,
        *,
        fingerprint: str
    ):
        """
        Registra la 'pregunta 0' SIN incrementar question_cursor.
        Reglas:
          • Si no hay TX abierta → ("no_tx", cursor_actual)
          • Si fingerprint == último → ("skip0", cursor_actual)  [no toca DB]
          • Si fingerprint != último → set fp y sent_at → ("new0", cursor_actual)
        """
        row = self.get_open_row(contact_id)
        if not row:
            return "no_tx", 0

        current_cursor = int(getattr(row, "question_cursor", 0) or 0)
        last_fp = getattr(row, "last_question_fingerprint", None)

        # Si es el mismo fingerprint, no re-enviamos ni tocamos sent_at
        if (last_fp or "") == (fingerprint or ""):
            return "skip0", current_cursor

        now_iso = self._now_iso_utc()
        try:
            # update parcial para no pisar otros campos
            self.update(
                id=row.id,
                contact_id=row.contact_id,
                phone=row.phone,
                name=getattr(row, "name", "Abierta"),
                event_id=getattr(row, "event_id", None),
            )
            # setear SOLO fp y sent_at (sin mover cursor)
            self.data["last_question_fingerprint"].value = fingerprint
            self.data["last_question_sent_at"].value = now_iso
            self.data["timestamp"].value = now_iso
            super().update("id", row.id)
        except Exception as e:
            print(f"[Transactions.set_question_zero] error TX {row.id}: {e}")

        return "new0", current_cursor
    def get_last_tx_info_by_phone(self, phone: str):
        """
        Devuelve info mínima de la última TX para ese teléfono en UNA SOLA lectura:
        {
        "id": int,
        "name": str,
        "timestamp": <iso str>,
        "event_id": int | None,
        "conversation": str | None,

        }
        Retorna None si no hay transacciones.
        """
        txs = super().get("phone", phone, order_field="timestamp.asc,id.asc")
        if not txs:
            return None

        last = txs[-1]

        if isinstance(last, dict):
            return {
                "id": last.get("id"),
                "name": last.get("name"),
                "timestamp": last.get("timestamp"),
                "event_id": last.get("event_id"),
                "conversation": last.get("conversation"),

            }

        # TransactionsRegister (lo más común)
        return {
            "id": getattr(last, "id", None),
            "name": getattr(last, "name", None),
            "timestamp": getattr(last, "timestamp", None),
            "event_id": getattr(last, "event_id", None),
            "conversation": getattr(last, "conversation", None),

        }


    
""""
    def get_last_tx_info_by_phone(self, phone: str):

        txs = super().get("phone", phone, order_field="timestamp")
        if not txs:
            return None
        last = txs[-1]
        # last puede ser dataclass/objeto o dict según tu BaseModel
        if isinstance(last, dict):
            return {"id": last.get("id"), "name": last.get("name"), "timestamp": last.get("timestamp")}
        return {"id": getattr(last, "id", None),
                "name": getattr(last, "name", None),
                "timestamp": getattr(last, "timestamp", None)}
"""




