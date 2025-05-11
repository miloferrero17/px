from dataclasses import dataclass

from app.Model.enums import Role, MessageType, GuestAttendanceStatus, UserConfirmationStatus

@dataclass
class UsersRegister:
    user_id: int
    name: str
    phone: str
    email: str
    role: Role

@dataclass
class EventsRegister:
    event_id: int
    user_id: int
    name: str
    start_timestamp: str
    end_timestamp: str
    location: str
    description: str

@dataclass
class ContactsRegister:
    contact_id: int
    event_id: int
    name: str
    phone: str

@dataclass
class GuestsRegister:
    guest_id: int
    contact_id: int
    name: str
    food_restriction: str
    guest_attendance_status: GuestAttendanceStatus
    user_confirmation_status: UserConfirmationStatus
    timestamp: str

@dataclass
class FoodRestrictionsRegister:
    food_restriction_id: int
    name: str

@dataclass
class LogMessagesRegister:
    message_id: int
    contact_id: int
    message_type: MessageType
    content: str
    timestamp: str
    whatsapp_message_id: str

    def __str__(self) -> str:
        return f"Mensaje enviado {'al' if self.message_type.name == 'SENT' else 'por el'} contacto con ID {self.contact_id} el {self.timestamp}: {self.content}"

@dataclass
class MessagesRegister:
    message_id: int
    msg_key: str
    text: str

@dataclass
class FaqsRegister:
    faqs_id: int
    event_id: int
    question: str
    answer: str