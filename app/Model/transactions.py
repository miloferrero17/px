from typing import Optional, List, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel, TransactionsRegister
from app.Model.field import Field

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


            "amount": Field(None, DataType.FLOAT, True, False),              # double precision
            "currency": Field(None, DataType.STRING, True, False),           # ej. "ARS"
            "status": Field(None, DataType.STRING, True, False),             # pending | paid | to_collect | no_copay | failed
            "method": Field(None, DataType.STRING, True, False),             # transfer | cash | card
            "receipt_url": Field(None, DataType.STRING, True, False),        # por ahora NULL
            "paid_at": Field(None, DataType.TIMESTAMP, True, False),         # timestamptz
            "payment_reference": Field(None, DataType.STRING, True, True),
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

        amount: Optional[float] = None,
        currency: Optional[str] = None,
        status: Optional[str] = None,
        method: Optional[str] = None,
        receipt_url: Optional[str] = None,
        paid_at: Optional[str] = None,
        payment_reference: Optional[str] = None,
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


        self.data["amount"].value = amount
        self.data["currency"].value = currency
        self.data["status"].value = status
        self.data["method"].value = method
        self.data["receipt_url"].value = receipt_url
        self.data["paid_at"].value = paid_at
        self.data["payment_reference"].value = payment_reference

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

        amount: Optional[float] = None,
        currency: Optional[str] = None,
        status: Optional[str] = None,
        method: Optional[str] = None,
        receipt_url: Optional[str] = None,
        paid_at: Optional[str] = None,
        payment_reference: Optional[str] = None


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

        
        if amount is not None:
            self.data["amount"].value = amount
        if currency is not None:
            self.data["currency"].value = currency
        if status is not None:
            self.data["status"].value = status
        if method is not None:
            self.data["method"].value = method
        if receipt_url is not None:
            self.data["receipt_url"].value = receipt_url
        if paid_at is not None:
            self.data["paid_at"].value = paid_at
        if payment_reference is not None:
            self.data["payment_reference"].value = payment_reference

        # Llama a la actualización usando 'id' como clave única
        super().update("id", id)

    def delete(self, id: int) -> None:
        super().delete("id", id)

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
    def get_open_pending_transaction_by_contact_id(self, contact_id: int):
        """
        Devuelve la última transacción del contacto que está Abierta (name='Abierta')
        y con status de cobro ('pending', 'to_collect', 'no_copay').
        """
        txs = self.get_by_contact_id(contact_id)
        if not txs:
            return None
        candidatas = [
            tx for tx in txs
            if getattr(tx, "name", None) == "Abierta"
            and getattr(tx, "status", None) in ("pending", "to_collect", "no_copay")
        ]
        return candidatas[-1] if candidatas else None


   