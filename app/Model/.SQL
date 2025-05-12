class Contacts(BaseModel):
    def __init__(self):
        data: Dict[str, Field] = {
            "contact_id": Field(None, DataType.INTEGER, False, True),  # ✅ nueva PK
            "event_id": Field(None, DataType.INTEGER, False, False),
            "name": Field(None, DataType.STRING, False, False),
            "phone": Field(None, DataType.PHONE, False, False)
        }
        super().__init__("contacts", data)
        self.__data = data  # opcional, por si necesitás usarlo luego

class Events(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "event_id":        Field(None, DataType.INTEGER,   False, True),
            "user_id":         Field(None, DataType.INTEGER,   False, False),
            "name":            Field(None, DataType.STRING,    False, False),
            "start_timestamp": Field(None, DataType.TIMESTAMP, True,  False),
            "end_timestamp":   Field(None, DataType.TIMESTAMP, True,  False),
            "reporte":         Field(None, DataType.TEXT,       True,  False),
            "description":     Field(None, DataType.TEXT,       True,  False),
            "nodo_inicio":     Field(None, DataType.INTEGER,   True,  False),
            "cant_preguntas":  Field(None, DataType.INTEGER,   True,  False),
            "tiempo_sesion":   Field(None, DataType.INTEGER,   True,  False),  # Nuevo campo int2
        }
        super().__init__("events", self.__data)


class Log(BaseModel):
    def __init__(self):
        # Definición de la estructura de la tabla "Log_messages"
        self.__data: Dict[str, Field] = {
            "message_id": Field(None, DataType.INTEGER, False, True),
            "contact_id": Field(None, DataType.INTEGER, False, False),
            "message_type": Field(None, DataType.STRING, False, False),
            "content": Field(None, DataType.STRING, False, False),
            "timestamp": Field(None, DataType.TIMESTAMP, False, False),
            "whatsapp_message_id": Field(None, DataType.STRING, True, False)
        }
        # Se llama a BaseModel pasando el nombre de la tabla y la estructura de datos
        super().__init__("log", self.__data)


class Messages(BaseModel):
    def __init__(self):
        self.__data: Dict[str, Field] = {
            "message_id":    Field(None, DataType.INTEGER, False, True),
            "msg_key":       Field(None, DataType.INTEGER, False, False),
            "text":          Field(None, DataType.STRING,  False, False),
            "phone":         Field(None, DataType.STRING,  True,  False),  # opcional
            "question_id":   Field(None, DataType.INTEGER, True,  False),  # FK opcional
            "group_id":      Field(None, DataType.INTEGER, True,  False),  # FK opcional
            "question_name": Field(None, DataType.STRING,  True,  False),  # opcional
            "event_id":      Field(None, DataType.INTEGER, True,  False)   # Nuevo campo event_id opcional
        }
        super().__init__("messages", self.__data)


class Questions(BaseModel):
    def __init__(self):
        self._data: Dict[str, Field] = {
            "question_id": Field(None, DataType.INTEGER, False, True),
            "event_id": Field(None, DataType.INTEGER, False, False),
            "group_id": Field(None, DataType.INTEGER, False, False),
            "group_name": Field(None, DataType.STRING, False, False),
            "question_name": Field(None, DataType.STRING, False, False)
        }
        super().__init__("questions", self._data)
        

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
            "data_created": Field(None, DataType.TIMESTAMP, False, False)  # timestamp de creación
        }
        super().__init__("transactions", fields)
        # Exponer los campos para facilitar su uso
        self.data = self._BaseModel__data



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
