from dataclasses import dataclass
from typing import Any
from app.Model.enums import DataType

@dataclass
class Field:
    value: Any
    data_type: DataType
    optional: bool
    unique: bool