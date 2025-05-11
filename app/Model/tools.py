from typing import Dict, Tuple, Any, List
from enum import Enum

from app.Model.validators import validate
from app.Model.enums import DataType
from app.Model.field import Field
from app.Model.exceptions import ValidationError, MissingUniqueFieldError

def get_fields_and_params(data: Dict[str, Field], for_update: bool = False) -> Tuple[List[str], List[Any]]:
    """
    Extrae los campos y parámetros de un diccionario de datos.

    Valida cada campo y su valor, asegurándose de que cumplan con los criterios de validación.
    Si for_update es True, se formatean los campos como "campo = %s" (útil para la cláusula SET en UPDATE)
    y se requiere que al menos uno de los campos tenga la propiedad UNIQUE, o se lanza MissingUniqueFieldError.
    Si for_update es False, se retornan los nombres de campo tal cual (útiles para INSERT).

    :param data: Diccionario con los datos a insertar o actualizar. Las claves son nombres de campos y los valores son objetos Field.
    :param for_update: Indica si se requiere formateo para UPDATE y verificación de un campo UNIQUE.
                       Por defecto es False.
    :return: Una tupla con una lista de campos y una lista de parámetros.

    :raises ValidationError: Si algún campo no cumple con los criterios de validación o si no hay suficientes datos.
    :raises MissingUniqueFieldError: Si for_update es True y no se encuentra un campo UNIQUE en los datos.
    """
    fields: List[str] = []
    params: List[Any] = []
    has_unique_value = False

    for field, field_obj in data.items():
        # Verifica si el campo es válido o, si es opcional y no tiene valor
        if validate(field_obj.value, field_obj.data_type, field_obj.optional) or (field_obj.value is None and field_obj.optional):
            if for_update:
                fields.append(f"{field} = %s")
            else:
                fields.append(field)
            # Asegura que, si el valor es un Enum, se guarde su valor y no el objeto completo.
            params.append(field_obj.value.value if isinstance(field_obj.value, Enum) else field_obj.value)
            if not has_unique_value:
                has_unique_value = field_obj.unique

    if for_update and not has_unique_value:
        raise MissingUniqueFieldError("No se encontró un campo UNIQUE en los datos.")

    if not fields:
        raise ValidationError("No hay suficientes datos.")

    return fields, params

def snake_to_camel(snake_str: str) -> str:
    """
    Convierte un string en snake_case a CamelCase.
    """
    components = snake_str.split('_')
    return ''.join(x.capitalize() for x in components)

def list_to_string(lista: list) -> str:
    """
    Convierte una lista de strings a una cadena separada por comas,
    utilizando 'y' antes del último elemento.
    """
    if not lista:
        return ""
    if len(lista) == 1:
        return lista[0]
    return ", ".join(lista[:-1]) + " y " + lista[-1]
