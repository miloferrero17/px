from enum import Enum

class Role(Enum):
    HOST = 1
    SUPER_USER = 2

class DataType(Enum):
    STRING = 1
    TIMESTAMP = 2
    ROLE = 3
    EMAIL = 4
    PHONE = 5
    ATTENDANCE_STATUS = 6
    MESSAGE_TYPE = 7
    INTEGER = 8
    BOOLEAN = 9
    MESSAGE_CATEGORY = 10
    VARCHAR = 11
    INT = 12
    TEXT = "text"
    JSON = "json"
    DATE = "date"  # permite marcar campos como JSON y validarlos/enviarlos como dict/list
    FLOAT = 13


class GuestAttendanceStatus(Enum):
    CONFIRMED = 1
    DECLINED = 2
    PENDING = 3

class UserConfirmationStatus(Enum):
    CONFIRMED = 1
    DECLINED = 2
    PENDING = 3

class MessageType(Enum):
    SENT = 1
    RECEIVED = 2


class TxStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    TO_COLLECT = "to_collect"
    NO_COPAY = "no_copay"
    FAILED = "failed"

class TxMethod(Enum):
    TRANSFER = "transfer"
    CASH = "cash"
    CARD = "card"
