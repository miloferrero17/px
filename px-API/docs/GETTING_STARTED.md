# PX API — Getting Started

## Base
- **Prod:** `https://api.pacientex.com.ar`
- **Sandbox:** `https://api.sandbox.pacientex.com.ar`
- **Versión:** `/v1`
- **Formato:** JSON · **HTTPS obligatorio**

### Headers comunes
- `Content-Type: application/json`
- `Accept: application/json`
- `X-API-Key: <token>` (**requerido**)
- (Respuesta) `X-Request-Id` (correlación)


## Credenciales
- **Auth:** `X-API-Key: <token>`
- **Prod:** además **allowlist de IPs**
- **Rotación:** hasta 2 keys activas por 7 días (revocación inmediata posible)

## Endpoint inicial
**POST** `/v1/triage:fetch-latest`  
**Body:**
```json
{ "national_id": "12345678" }
```
## Respuesta (200)
```json
{
  "national_id": "12345678",
  "triage_timestamp": "2025-09-23T12:34:56Z",
  "medical_digest": "… (<=1200 chars, puede venir vacío)",
  "conversation": [
    { "role": "user", "content": "…enmascarado…", "timestamp": "2025-09-23T12:33:10Z" }
  ],
  "conversation_truncated": false,
  "request_id": "pxe-abc123"
}
```

## Errores (JSON)
```json
{ "error": { "code": "NOT_FOUND", "message": "No triage in last 8h for national_id", "request_id": "pxe-abc123" } }

```


### Códigos y `error.code`
- `400 BAD_REQUEST_national_id` — national_id **ausente**.
- `401 UNAUTHORIZED` — falta o es incorrecta la `X-API-Key`.
- `403 FORBIDDEN_IP` — IP no permitida (prod) o key revocada.
- `404 NOT_FOUND` — no hay triage en la ventana de **8 h**.
- `409 DATA_CONFLICT` — múltiples contactos para el mismo national_id.
- `429 RATE_LIMITED` — superó el límite (respetar `Retry-After`).
- `500 INTERNAL_ERROR` — error interno de PX.
- `503 DEPENDENCY_ERROR` — falla de dependencia (DB/proveedor).

## Ventana, empates y límites
- **Ventana (8 h, UTC):** se considera solo el “último triage” dentro de las últimas 8 horas. Si no hay → **404 NOT_FOUND**.
- **Empates:** si hay **>1 sesión** en 8 h, se devuelve **la más reciente** (200).
- **Truncado por cantidad:** se conservan **los últimos 100** mensajes.
- **Tamaño máximo de respuesta:** **512 KB UTF-8**. Si se excede, se recorta desde el inicio (queda lo más reciente) y `conversation_truncated=true`.

## Notas de implementación actual (Supabase)
**Fuentes de datos**
- `contacts`: búsqueda por `national_id = <valor>` → `contact_id`.
- `transactions`: últimas en **8 h** para ese `contact_id`, `order=timestamp.desc`, `limit=2`.

**Construcción de respuesta**
- `medical_digest`: puede venir **vacío** (máx. 1200 chars).
- `conversation`: si la DB trae texto plano, se **normaliza** a un array con un único mensaje `"assistant"`.
- Se aplica truncado: **100** últimos mensajes y tope **512 KB**.

## Ejemplo de request
```bash
curl -sS -X POST "https://api.sandbox.pacientex.com.ar/v1/triage:fetch-latest"   -H "Content-Type: application/json"   -H "X-API-Key: <token-sandbox>"   -H "X-Request-Id: pxe-doc-001"   --data '{"national_id":"45038826"}'
```

**Respuesta típica (headers)**
- `X-Request-Id: pxe-doc-001`  

## Respuestas esperadas

- **200 OK** — devuelve:
  - `national_id` (string), `triage_timestamp` (ISO-8601 UTC),
  - `medical_digest` (string; puede venir vacío, máx. 1200 chars),
  - `conversation` (array de mensajes; si la DB tenía texto plano, se normaliza a un único mensaje `"assistant"`),
  - `conversation_truncated` (bool),
  - `request_id` (string).
- **400 BAD_REQUEST_national_id** — national_id ausente.
- **401 UNAUTHORIZED** — falta o es incorrecta la `X-API-Key`.
- **403 FORBIDDEN_IP** — IP no permitida (en prod) o key revocada.
- **404 NOT_FOUND** — no hay sesiones en las últimas 8 h.
- **409 DATA_CONFLICT** — múltiples contactos para el mismo national_id.
- **503 DEPENDENCY_ERROR** — error al consultar Supabase.
- **500 INTERNAL_ERROR** — error interno de PX.


