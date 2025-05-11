from typing import Dict, Tuple, Any, Optional, Callable

from app.Model.enums import Role, DataType

def validate(value: Any, data_type: DataType, optional: bool) -> bool:
    """
    Valida un campo de datos según su tipo especificado.

    :param value: Valor a validar.
    :param data_type: Tipo de dato esperado.
    :return: True si el valor es válido, False de lo contrario.

    :ValueError: Un error si no se encuentra una función de validación para el tipo de dato especificado.
    """
    if value is None:
        return optional

    validator_name = f"is_{data_type.name.lower()}"

    # Busca dinámicamente la función de validación basada en el nombre ("is_<tipo>") dentro del módulo o espacio de nombres global (este mismo archivo).
    validator: Optional[Callable[[Any], bool]] = globals().get(validator_name)
    if not callable(validator):
        raise ValueError(f"No se encontró un validador para el tipo de dato: {data_type}")
    return validator(value)

def is_string(value: Any) -> bool:
    """Valida si el valor es una cadena de texto."""
    return isinstance(value, str)

def is_varchar(value) -> bool:
    """
    Valida que el valor sea una cadena (string).
    """
    return isinstance(value, str)

def is_integer(value: Any) -> bool:
    """Valida si el valor es un número entero."""
    return isinstance(value, int)

def is_float(value: Any) -> bool:
    """Valida si el valor es un número de punto flotante."""
    return isinstance(value, float)

def is_boolean(value: Any) -> bool:
    """Valida si el valor es un booleano."""
    return True

def is_role(value: Any) -> bool:
    """Valida si el valor es un rol válido."""
    try:
        return Role(value) in Role
    except ValueError:
        return False

def is_email(value: Any) -> bool:
    """Valida si el valor es un correo electrónico válido."""
    #TODO: Hacer que se fije si el mail existe
    return isinstance(value, str) and '@' in value

def is_phone(value: Any) -> bool:
    """Valida si el valor es un número de teléfono válido."""
    #TODO: Hacer que se fije si el número existe
    return True

def is_timestamp(value: Any) -> bool:
    """Valida si el valor es una fecha y hora válida."""
    #TODO: Aparte de esta funcion abria que verificar si la start_timestamp y la end_timestamp tienen sentido por los horarios
    return True

def is_message_type(value: Any) -> bool:
    """Valida si el valor es un tipo de mensaje válido."""
    return True

def is_attendance_status(value: Any) -> bool:
    """Valida si el valor es un attendance status valido."""
    return True

def is_text(value: Any) -> bool:
    """Valida si el valor es un texto largo."""
    return isinstance(value, str)