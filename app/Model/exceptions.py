from typing import Any

class BaseModelError(Exception):
    """
    Excepción base para errores en el modelo.
    """
    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value

class ValidationError(BaseModelError):
    """
    Excepción para errores de validación.
    Se lanza cuando un valor no cumple con los criterios de validación.
    """
    def __init__(self, message: str, field: str, value: Any):
        super().__init__(message, field, value)

class DatabaseError(BaseModelError):
    """
    Excepción para errores de base de datos.
    Se lanza cuando ocurre un error al interactuar con la base de datos.
    """
    pass

class UniqueConstraintError(BaseModelError):
    """
    Excepción para errores que sean debido a UNIQUE.
    Se lanza cuando se intenta insertar un valor que debe ser único pero ya existe en la base de datos.
    """
    def __init__(self, message: str, field: str, value: Any):
        super().__init__(message, field, value)

class MissingUniqueFieldError(BaseModelError):
    """
    Excepción para errores de campo UNIQUE faltante.
    Se lanza cuando no se encuentra un campo UNIQUE en los datos y por lo tanto no se puede crear o modificar un campo.
    """
    pass

class RecordNotFoundError(BaseModelError):
    """
    Excepción para errores de registro no encontrado.
    Se lanza cuando no se encuentra un registro en la base de datos.
    """
    def __init__(self, message: str, field: str, value: Any):
        super().__init__(message, field, value)