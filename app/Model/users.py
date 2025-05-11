from typing import Optional, List, Dict
from app.Model.enums import Role, DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field
from app.Model.connection import DatabaseManager
from app.Model.registers import UsersRegister

# Se asume que existe una clase UsersRegister (o similar) en globals() para convertir los registros.
# Si no la tenés definida, podés definirla de forma sencilla, por ejemplo:
class UsersRegister:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return f"UsersRegister({self.__dict__})"


class Users(BaseModel):
  def __init__(self):
      # Definición de la estructura de la tabla "users".
      # Los valores se inicializan en None; se usarán para validación y construcción de filtros o payloads.
      self.__data: Dict[str, Field] = {
          "user_id": Field(None, DataType.INTEGER, False, True),
          "name": Field(None, DataType.STRING, False, False),
          "phone": Field(None, DataType.PHONE, False, True),
          "email": Field(None, DataType.EMAIL, True, True),
          "role": Field(None, DataType.ROLE, False, False),
      }
      # Llamamos a BaseModel pasando el nombre exacto de la tabla (en Supabase suele estar en minúsculas, por ejemplo, "users")
      super().__init__("users", self.__data)

  def add(self, name: str, phone: str, email: Optional[str] = None, role: Role = Role.HOST) -> int:
    """
    Inserta un nuevo usuario y retorna su ID.

    :raises UniqueConstraintError: Si se viola la restricción de unicidad.
    :raises ValidationError: Si la validación de algún campo falla.
    :raises DatabaseError: Si ocurre algún error al interactuar con la base de datos.
    """
    # Configuramos los valores a insertar
    self.__data["user_id"].value = None
    self.__data["name"].value = name
    self.__data["phone"].value = phone
    self.__data["email"].value = email
    self.__data["role"].value = role.name

    return super().add()


  def get_by_id(self, user_id: int) -> Optional[UsersRegister]:
    """
    Retorna una instancia de UsersRegister con los datos del usuario identificado por user_id.
    """
    result = super().get("user_id", user_id)
    return result[0] if result else None

  def get_by_name(self, name: str) -> Optional[List[UsersRegister]]:
    """
    Retorna una lista de instancias de UsersRegister que coincidan con el nombre dado.
    """
    return super().get("name", name)

  def get_by_email(self, email: str) -> Optional[UsersRegister]:
    """
    Retorna una instancia de UsersRegister con los datos del usuario identificado por email.
    """
    result = super().get("email", email)
    return result[0] if result else None

  def get_by_phone(self, phone: str) -> Optional[UsersRegister]:
    """
    Retorna una instancia de UsersRegister con los datos del usuario identificado por phone.
    """
    result = super().get("phone", phone)
    return result[0] if result else None

  def get_by_role(self, role: Role) -> Optional[List[UsersRegister]]:
    """
    Retorna una lista de instancias de UsersRegister con los datos de los usuarios que tengan el rol especificado.
    """
    return super().get("role", role)

  def update(self, user_id: int, name: Optional[str] = None, email: Optional[str] = None, 
     phone: Optional[str] = None, role: Optional[Role] = None) -> None:
    """
    Actualiza los datos de un usuario identificado por user_id.
    Solo se actualizan los campos cuyo valor no sea None.
  
    :raises UniqueConstraintError, ValidationError, MissingUniqueFieldError, RecordNotFoundError, DatabaseError
    """
    # Asignamos el user_id para identificar el registro
    self.__data["user_id"].value = user_id
    # Asignamos los nuevos valores a actualizar
    self.__data["name"].value = name
    self.__data["email"].value = email
    self.__data["phone"].value = phone
    # Convertimos el enum a cadena, si se proporciona
    if role is not None:
      self.__data["role"].value = role.name
    else:
      self.__data["role"].value = None
  
    # Llamamos al método update de la clase base
    super().update("user_id", user_id)
  
  
  def delete(self, user_id: int) -> None:
    """
    Elimina el usuario identificado por user_id.

    :raises ValidationError, RecordNotFoundError, DatabaseError
    """
    super().delete("user_id", user_id)



