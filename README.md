# PacienteX (PX) - Motor Conversacional para Guardia Medica

Motor conversacional basado en GPT-4, que opera via WhatsApp para asistir a pacientes en la guardia medica. El sistema recolecta el motivo de consulta, hace preguntas de triage con IA y genera un resumen medico para el equipo clinico.

---

## Indice

- [Que hace el sistema](#que-hace-el-sistema)
- [Stack tecnologico](#stack-tecnologico)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Flujo de la conversacion](#flujo-de-la-conversacion)
- [Variables de entorno](#variables-de-entorno)
- [Como correr localmente](#como-correr-localmente)
- [Modelo de datos (Supabase)](#modelo-de-datos-supabase)
- [Agregar o modificar un nodo](#agregar-o-modificar-un-nodo)
- [Observabilidad y logs](#observabilidad-y-logs)
- [Proveedor de WhatsApp](#proveedor-de-whatsapp)

---

## Que hace el sistema

1. El paciente escribe a un numero de WhatsApp.
2. El sistema lo saluda, pide su DNI y verifica consentimiento LOPD (Ley 25.326).
3. Pregunta el motivo de consulta.
4. Un clasificador con GPT decide si es una emergencia urgente o si se pueden hacer mas preguntas.
5. Si es urgente: genera el reporte medico de inmediato (nodo 202).
6. Si no: "Sherlock" (nodo 203) hace hasta N preguntas de triage generadas por IA.
7. Al final, genera y ofrece un resumen medico al paciente.

---

## Stack tecnologico

| Componente         | Tecnologia                        |
|--------------------|-----------------------------------|
| Backend            | Python 3.11+ + Flask              |
| Despliegue         | AWS Lambda (serverless)           |
| Canal de mensajes  | WhatsApp via Twilio o Meta Cloud API |
| Base de datos      | Supabase (PostgreSQL via REST)    |
| LLM                | OpenAI GPT-4.1 (Responses API)    |
| Audio              | OpenAI Whisper                    |
| Vision             | OpenAI Vision (imagenes y PDFs)   |
| Observabilidad     | Logs JSON estructurados (stdout)  |

---

## Estructura del proyecto

```
px/
├── app/
│   ├── __init__.py          # Crea la app Flask y registra blueprints
│   ├── message_p.py         # Orquestador principal del flujo de un mensaje
│   ├── chat.py              # Script para pruebas locales rapidas
│   ├── chat_milo.py         # Variante del script de pruebas
│   │
│   ├── routes/
│   │   ├── __init__.py      # Define el Blueprint "routes"
│   │   ├── whatsapp.py      # Endpoints: webhook Twilio (/) y webhook Meta (/whatsapp/meta/webhook)
│   │   └── consulta.py      # Otros endpoints (consultas admin, etc.)
│   │
│   ├── flows/
│   │   ├── workflow_logic.py    # Definicion de cada NODO (201-206 y 210)
│   │   └── workflows_utils.py   # Utilidades compartidas entre nodos
│   │
│   ├── services/
│   │   ├── brain.py             # Wrapper de OpenAI (ask_openai)
│   │   ├── messaging.py         # Abstraccion del proveedor: Twilio o Meta
│   │   ├── twilio_service.py    # Envio de mensajes via Twilio
│   │   ├── meta_whatsapp_service.py  # Envio de mensajes via Meta Cloud API
│   │   ├── wisper.py            # Transcripcion de audio con Whisper
│   │   ├── vision.py            # Descripcion de imagenes y extraccion de PDFs
│   │   ├── decisions.py         # Helpers de logica de decision
│   │   ├── decs.py              # Helpers de decision (variante)
│   │   ├── reporting.py         # Armado del reporte medico
│   │   └── uploader.py          # Subida de archivos
│   │
│   ├── Model/
│   │   ├── base_model.py        # CRUD generico sobre Supabase REST API
│   │   ├── connection.py        # Configuracion de conexion a Supabase
│   │   ├── contacts.py          # Tabla: contacts (pacientes)
│   │   ├── transactions.py      # Tabla: transactions (sesiones de conversacion)
│   │   ├── messages.py          # Tabla: messages (historial de mensajes)
│   │   ├── events.py            # Tabla: events (configuracion por evento/cliente)
│   │   ├── medical_digests.py   # Tabla: medical_digests (resumenes medicos)
│   │   ├── privacy_consents.py  # Tabla: privacy_consents (LOPD)
│   │   ├── coverages.py         # Tabla: coverages (cobertura medica)
│   │   ├── registers.py         # Tabla: registers
│   │   ├── users.py             # Tabla: users
│   │   ├── log.py               # Tabla: log
│   │   ├── px_hce_report.py     # Reporte HCE
│   │   ├── questions.py         # Tabla: questions
│   │   ├── engine.py            # Tabla: engine (codigo Python dinamico)
│   │   ├── enums.py             # Tipos de datos y roles
│   │   ├── field.py             # Clase Field (descriptor de columna)
│   │   ├── validators.py        # Validadores de tipo
│   │   ├── exceptions.py        # Excepciones custom
│   │   └── tools.py             # Helpers internos del ORM
│   │
│   ├── obs/
│   │   └── logs.py              # Sistema de observabilidad: logs JSON estructurados
│   │
│   ├── Utils/
│   │   └── table_cleaner.py     # Limpieza de tablas (uso admin)
│   │
│   └── pdf_builder/
│       ├── generate_html.py     # Genera HTML del reporte medico
│       ├── generate_pdf.py      # Convierte HTML a PDF
│       └── models.py            # Modelos del PDF
```

---

## Flujo de la conversacion

El sistema usa una maquina de estados basada en **nodos numerados**. Cada mensaje entrante se procesa en `message_p.py` y luego se ejecuta el nodo correspondiente en `workflow_logic.py`.

```
Mensaje del paciente
        |
        v
[message_p.handle_incoming_message]
        |
        +-- Es primera vez o sesion expirada?
        |       YES --> Enviar WELCOME (pedir DNI) --> Nodo 206
        |       NO  --> Continuar sesion existente
        |
        v
[ejecutar_workflow] -- loop de nodos
        |
   Nodo 206: Validar DNI
        |-- DNI invalido --> pedir reintento (1 vez) o cerrar
        |-- DNI valido, sin consentimiento --> Nodo 204
        |-- DNI valido, con consentimiento --> Nodo 205
        |
   Nodo 204: Consentimiento (Ley 25.326)
        |-- "Si" --> Nodo 205
        |-- "No" --> Cerrar consulta
        |
   Nodo 205: Preguntar motivo de consulta
        |
        v
   Nodo 201: Clasificador (GPT)
        |-- No es motivo medico --> re-preguntar (1 vez) o cerrar
        |-- Urgente            --> Nodo 202 (reporte inmediato)
        |-- Necesita preguntas --> Nodo 203 (Sherlock)
        |
   Nodo 203: Sherlock - preguntas de triage (hasta N preguntas)
        |-- Respuesta off-topic --> avisar y repetir (1 vez) o cerrar
        |-- N preguntas completas --> Nodo 202
        |
   Nodo 202: Generar reporte medico (GPT)
        |-- Envia reporte al paciente
        |-- Envia disclaimer
        |-- Ofrece resumen medico --> Nodo 210
        |
   Nodo 210: Respuesta a la oferta del resumen
        |-- "Si" --> Envia digest + disclaimer --> Cerrar TX
        |-- "No" --> Mensaje de despedida --> Cerrar TX
```

---

## Variables de entorno

Crear un archivo `.env` en la raiz del proyecto:

```env
# OpenAI
OPENAI_API_KEY=sk-...

# Supabase
SUPABASE_URL=https://<tu-proyecto>.supabase.co
SUPABASE_API_KEY=<service-role-key>
SUPABASE_KEY=<service-role-key>   # alias legacy, aun leido en base_model.py

# Proveedor de WhatsApp: "twilio" o "meta"
WHATSAPP_PROVIDER=meta

# Meta WhatsApp Cloud API
META_WABA_TOKEN=<token-de-acceso>
META_WABA_PHONE_ID=<phone-number-id>
META_VERIFY_TOKEN=<tu-verify-token>
META_API_VERSION=v24.0

# Twilio (si WHATSAPP_PROVIDER=twilio)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Privacidad
PRIVACY_NOTICE_VERSION=v1.0

# Entorno
ENV=dev
PX_ENV=dev
PX_SERVICE=px-engine
PX_VERSION=v1
```

**Notas sobre el token de Meta:** `whatsapp.py` resuelve el token en cascada —
`META_WABA_TOKEN` → `META_ACCESS_TOKEN` → `META_WHATSAPP_TOKEN`. Alcanza con
definir uno; si no hay ninguno, el envio falla con `RuntimeError`.

`META_VERIFY_TOKEN` tiene un valor por defecto hardcodeado en el codigo. En
cualquier despliegue real hay que setear la variable para no quedarse con ese
default.

---

## Como correr localmente

```bash
# 1. Clonar el repo
git clone <repo-url>
cd px

# 2. Crear entorno virtual y activar
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
# (no hay .env.example en el repo: crear el .env a mano
#  con las variables de la seccion anterior)
touch .env

# 5. Correr localmente
python -m flask --app app run --port 5000

# 6. Prueba rapida sin WhatsApp (chat.py)
python app/chat.py
```

Para exponer el servidor local a internet (necesario para recibir webhooks):
```bash
ngrok http 5000
# Configurar la URL de ngrok en el panel de Twilio o Meta
```

---

## Modelo de datos (Supabase)

Todas las tablas viven en Supabase (PostgreSQL). El acceso se hace via REST API usando `BaseModel` en `app/Model/base_model.py`.

| Tabla               | Descripcion                                                   |
|---------------------|---------------------------------------------------------------|
| `contacts`          | Un registro por paciente (phone, national_id, event_id)       |
| `transactions`      | Una sesion de conversacion (contact_id, conversation JSON, estado Abierta/Cerrada) |
| `messages`          | Cada mensaje enviado/recibido (msg_key=nodo, text, phone)     |
| `events`            | Configuracion de cada cliente/evento (contexto del agente, nodo inicio, TTL, cant preguntas) |
| `privacy_consents`  | Registro de consentimiento LOPD por hash de DNI              |
| `medical_digests`   | Resumenes medicos generados por GPT, vinculados a una TX      |
| `engine`            | Codigo Python dinamico ejecutable (feature avanzada)          |
| `questions`         | Preguntas predefinidas (feature alternativa al GPT libre)     |

### Patron de acceso a datos

```python
# Cada modelo hereda de BaseModel
from app.Model.contacts import Contacts

ctt = Contacts()
contacto = ctt.get_by_phone("5491112345678")  # SELECT
ctt.add(event_id=1, name="Juan", phone="5491112345678")  # INSERT
ctt.update(...)  # UPDATE (via PATCH en Supabase)
```

---

## Agregar o modificar un nodo

Los nodos se definen en [app/flows/workflow_logic.py](app/flows/workflow_logic.py).

**Estructura de un nodo:**

```python
def nodo_XXX(variables):
    # Lee lo que necesita de variables
    body = variables.get("body")

    # Hace su logica...

    # Retorna un dict con el estado actualizado
    return {
        "nodo_destino": 201,   # proximo nodo a ejecutar
        "subsiguiente": 1,     # 1 = cortar ciclo y esperar nuevo mensaje
                               # 0 = seguir en el mismo ciclo (ejecutar nodo_destino)
        "conversation_str": variables.get("conversation_str"),
        "response_text": "Texto a enviar al paciente",
        "result": "Abierta",   # "Abierta" o "Cerrada" (cierra la TX si es "Cerrada")
        "group_id": None,
        "question_id": None,
    }
```

**Para registrar el nodo nuevo:**

```python
# En workflow_logic.py, agregar al dict NODOS dentro de ejecutar_nodo()
NODOS = {
    201: nodo_201,
    202: nodo_202,
    ...
    XXX: nodo_XXX,   # <- agregar aca
}
```

---

## Observabilidad y logs

El sistema emite logs JSON estructurados a stdout (capturados por CloudWatch en AWS).

```python
from app.obs.logs import op_log

op_log("supabase", "select_contact", "OK", t0=t0, extra={"contact_id": 42})
op_log("engine",   "welcome_guard",  "ERROR", error="mensaje de error")
```

Tipos de eventos de log:
- `ENGINE_STEP`: enter/exit de cada nodo (con latencia)
- `PROVIDER_CALL`: llamadas a Twilio/Meta/OpenAI (con latencia)
- `PROVIDER_RESULT`: referencia del proveedor (SID de Twilio, wamid de Meta)
- `OP_LOG`: logs operativos generales
- `FUNC_CALL`: latencia de funciones internas (via decorador `@log_latency`)

**Nota:** Los numeros de telefono NUNCA aparecen en los logs en claro. Se hashean con SHA-256 y se muestran los primeros 12 caracteres.

---

## Proveedor de WhatsApp

El sistema soporta dos proveedores, seleccionables via variable de entorno:

```env
WHATSAPP_PROVIDER=meta    # Meta Cloud API (produccion)
WHATSAPP_PROVIDER=twilio  # Twilio (sandbox de desarrollo)
```

La capa de abstraccion esta en [app/services/messaging.py](app/services/messaging.py). Tanto el webhook de Twilio (`/`) como el de Meta (`/whatsapp/meta/webhook`) terminan llamando al mismo engine (`message_p.handle_incoming_message`).

---

## Autor

Emilio Ferrero - [LinkedIn](https://www.linkedin.com/in/emilio-ferrero-87a64928/) - Consultor en AI y tecnologia para salud, pagos y comercio exterior.
