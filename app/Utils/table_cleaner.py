from app.Model.messages import Messages
from app.Model.users import Users
from app.Model.transactions import Transactions

class TableCleaner:
    def __init__(self):
        self.models = {
            "messages": (Messages(), "message_id"),
            "users": (Users(), "user_id"),
            "transactions": (Transactions(), "id"),
        }

    def delete_all(self):
        for name, (model, id_field) in self.models.items():
            print(f"🧹 Cleaning table: {name}")
            all_records = model.get_all()
            for record in all_records:
                model.delete(id_field, getattr(record, id_field))
            print(f"✅ {name} cleaned. Deleted {len(all_records)} rows.")
