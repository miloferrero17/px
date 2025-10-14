import json

# handler.py
import os
from uuid import uuid4
from datetime import datetime, timezone
import hmac, hashlib, base64, time


# ---- Config básica ----

SEC_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
}
# Límites informativos (pueden variar por entorno)
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
BURST_LIMIT_PER_SEC = int(os.getenv("BURST_LIMIT_PER_SEC", "10"))



# ---- Utilidades ----
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def get_req_id(event) -> str:
    # Intenta propagar el que venga del cliente
    headers = (event.get("headers") or {})
    rid = headers.get("X-Request-Id") or headers.get("x-request-id")
    return rid or f"pxe-{uuid4()}"

def _sign_headers(method: str, path: str, body_json: str) -> dict:
    """
    Devuelve cabeceras X-PXE-* con HMAC-SHA256 si PX_SIGNING_SECRET está seteado.
    Canonical string: method + "\\n" + path + "\\n" + ts + "\\n" + body_sha256
    """
    secret = os.getenv("PX_SIGNING_SECRET") or ""
    if not secret or not method or not path:
        return {}

    ts = str(int(time.time()))
    body_sha = hashlib.sha256(body_json.encode("utf-8")).hexdigest()
    to_sign = f"{method}\n{path}\n{ts}\n{body_sha}"
    sig = base64.b64encode(hmac.new(secret.encode("utf-8"), to_sign.encode("utf-8"), hashlib.sha256).digest()).decode()

    return {
        "X-PXE-Timestamp": ts,         # epoch seconds
        "X-PXE-Body-SHA256": body_sha, # hex
        "X-PXE-Signature": sig,        # base64(HMAC-SHA256)
    }



def response(status: int, body: dict, req_id: str, extra_headers: dict | None = None, *, method: str = "", path: str = ""):
    # Serializamos primero para firmar sobre el JSON final
    body_json = json.dumps(body, ensure_ascii=False)

    headers = dict(SEC_HEADERS)
    headers["X-Request-Id"] = req_id

    # Headers informativos de rate limit (enforcement en API Gateway)
    headers["X-RateLimit-Limit-Minute"] = str(RATE_LIMIT_PER_MIN)
    headers["X-RateLimit-Limit-Second"] = str(BURST_LIMIT_PER_SEC)

    # Firma opcional
    headers.update(_sign_headers(method, path, body_json))

    if extra_headers:
        headers.update(extra_headers)
    return {
        "statusCode": status,
        "headers": headers,
        "body": body_json,
    }

def error(status: int, code: str, message: str, req_id: str, *, method: str = "", path: str = ""):
    body = {"error": {"code": code, "message": message, "request_id": req_id}}
    return response(status, body, req_id, method=method, path=path)

def parse_json_body(event):
    body = event.get("body")
    if body is None:
        return None

    # Si ya viene dict, devolver directo
    if isinstance(body, dict):
        return body

    def _parse_str(s: str):
        # 1) intento normal
        try:
            data = json.loads(s)
            if isinstance(data, dict):
                return data
            # si parsea a string (JSON doblemente serializado), reintentar
            if isinstance(data, str):
                try:
                    data2 = json.loads(data)
                    if isinstance(data2, dict):
                        return data2
                except Exception:
                    pass
        except Exception:
            pass

        # 2) fallback: tomar el JSON entre la primera '{' y la última '}' y parsear eso
        try:
            i, j = s.find("{"), s.rfind("}")
            if i != -1 and j > i:
                inner = s[i:j+1]
                data3 = json.loads(inner)
                if isinstance(data3, dict):
                    return data3
        except Exception:
            pass

        return None

    # Texto/bytes
    if isinstance(body, (bytes, str)):
        s = body if isinstance(body, str) else body.decode("utf-8", errors="ignore")
        parsed = _parse_str(s)
        if parsed is not None:
            return parsed

    # Marcado como base64 por API Gateway
    if event.get("isBase64Encoded"):
        try:
            import base64
            s = base64.b64decode(body).decode("utf-8", errors="ignore")
            parsed = _parse_str(s)
            if parsed is not None:
                return parsed
        except Exception:
            return None

    return None





# ---- Supabase (REST) opcional ----
from urllib import request as _urlreq
from urllib.parse import quote as _q


def _sb_env():
    return {
        "use": (os.getenv("USE_SUPABASE") or "false").lower() == "true",
        "url": os.getenv("SUPABASE_URL") or "",
        "key": os.getenv("SUPABASE_KEY") or "",
        "table_contacts": os.getenv("SUPABASE_CONTACTS_TABLE") or "contacts",
        "table_tx": os.getenv("SUPABASE_TX_TABLE") or "transactions",
    }

def _sb_get(url: str, key: str, timeout: int = 8):
    req = _urlreq.Request(url)
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Accept", "application/json")
    with _urlreq.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):  # por si el server responde un objeto
            data = [data]
        return data

def sb_find_contact_by_national_id(base_url: str, key: str, table_contacts: str, national_id: str):
    # contacts?national_id=eq.<national_id>&select=contact_id,national_id&limit=2
    qs = f"national_id=eq.{_q(national_id)}&select=contact_id,national_id&limit=2"
    url = f"{base_url.rstrip('/')}/rest/v1/{table_contacts}?{qs}"
    rows = _sb_get(url, key)
    return rows  # 0/1/N

def sb_find_txs_for_contact(base_url: str, key: str, table_tx: str, contact_id: int, hours_window: int = 8, limit: int = 2):
    from datetime import datetime, timezone, timedelta
    from_ts = (datetime.now(timezone.utc) - timedelta(hours=hours_window)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # transactions?contact_id=eq.<id>&timestamp=gte.<iso>&order=timestamp.desc&select=id,contact_id,timestamp,conversation&limit=2
    qs = (
        f"contact_id=eq.{_q(str(contact_id))}"
        f"&timestamp=gte.{_q(from_ts)}"
        f"&order=timestamp.desc"
        f"&select=id,contact_id,timestamp,conversation"
        f"&limit={limit}"
    )
    url = f"{base_url.rstrip('/')}/rest/v1/{table_tx}?{qs}"
    rows = _sb_get(url, key)
    return rows


# ---- Handler principal (Lambda proxy integration) ----
def triage_fetch_latest(event, context):
    req_id = get_req_id(event)
    method = (event.get("httpMethod") or "").upper()
    path = event.get("path") or ""

    # En v1 este endpoint es solo POST
    if method != "POST":
        return error(405, "METHOD_NOT_ALLOWED", "Use POST for this endpoint", req_id, method=method, path=path)

    # Content-Type debe ser JSON
    headers = event.get("headers") or {}
    ctype = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
    if "application/json" not in ctype:
        return error(400, "BAD_REQUEST", "Content-Type must be application/json", req_id, method=method, path=path)

    # Auth por API Key (simple por ahora)
    api_key = (headers.get("X-API-Key") or headers.get("x-api-key") or "").strip()
    expected = (os.getenv("PX_API_KEY") or "").strip()
    if not expected:
        # Seguridad: si no seteaste PX_API_KEY en el entorno, rechazá por defecto
        return error(401, "UNAUTHORIZED", "Server misconfigured: missing PX_API_KEY", req_id, method=method, path=path)
    if api_key != expected:
        return error(401, "UNAUTHORIZED", "Invalid or missing X-API-Key", req_id, method=method, path=path)
    
    # Body JSON
    print(f"[DBG] req_id={req_id} method={method} ctype={ctype} path={path}")
    print(f"[DBG] raw_body_type={type(event.get('body'))} isB64={event.get('isBase64Encoded')} raw_body_snip={(str(event.get('body')) or '')[:120]}")


    data = parse_json_body(event)
    print(f"[DBG] parsed_ok={isinstance(data, dict)} keys={list(data.keys()) if isinstance(data, dict) else None}")

    # national_id:  (la validación  vive en PX)
    if not isinstance(data, dict) or "national_id" not in data:
        return error(400, "BAD_REQUEST_national_id", "Missing 'national_id'", req_id, method=method, path=path)

    national_id = str(data.get("national_id") or "").strip()
    if not national_id:
        return error(400, "BAD_REQUEST_national_id", "Missing 'national_id'", req_id, method=method, path=path)

    # === DATA SOURCE: contacts + transactions ===
    cfg = _sb_env()
    print(f"[DBG] mode={'supabase' if cfg['use'] else 'stub'}")

    if cfg["use"]:
        if not (cfg["url"] and cfg["key"]):
            return error(503, "DEPENDENCY_ERROR", "Supabase not configured", req_id, method=method, path=path)

        try:
            contacts = sb_find_contact_by_national_id(cfg["url"], cfg["key"], cfg["table_contacts"], national_id)
        except Exception as e:
            return error(503, "DEPENDENCY_ERROR", f"Supabase contacts error: {e}", req_id, method=method, path=path)

        if not contacts:
            return error(404, "NOT_FOUND", "No triage in last 8h for national_id", req_id, method=method, path=path)
        if len(contacts) > 1:
            # Poco probable si tenés unique(national_id), pero lo contemplamos
            return error(409, "DATA_CONFLICT", "Multiple contacts for national_id", req_id, method=method, path=path)

        contact_id = contacts[0].get("contact_id")
        if contact_id is None:
            return error(503, "DEPENDENCY_ERROR", "Contact without contact_id", req_id, method=method, path=path)

        try:
            txs = sb_find_txs_for_contact(cfg["url"], cfg["key"], cfg["table_tx"], contact_id, hours_window=8, limit=2)
        except Exception as e:
            return error(503, "DEPENDENCY_ERROR", f"Supabase transactions error: {e}", req_id, method=method, path=path)

        # reglas ventana/empate
        if not txs:
            return error(404, "NOT_FOUND", "No triage in last 8h for national_id", req_id, method=method, path=path)

        # Empates: devolvemos SIEMPRE la más reciente (primer fila ordenada desc)
        tx = txs[0]

        triage_ts = tx.get("timestamp") or utc_now_iso()

        # conversation puede ser JSON en texto o texto plano; intentamos parsear
        conv_raw = tx.get("conversation") or ""
        try:
            conv = json.loads(conv_raw) if conv_raw else []
            if not isinstance(conv, list):
                # si era texto plano, lo empaquetamos como un solo mensaje "assistant"
                conv = [{"role": "assistant", "content": str(conv_raw), "timestamp": triage_ts}]
        except Exception:
            conv = [{"role": "assistant", "content": str(conv_raw), "timestamp": triage_ts}]

        # --- TRUNCADO ---
        # 1) tope de mensajes: conservar LOS ÚLTIMOS 100
        conv_truncated = False
        if len(conv) > 100:
            conv = conv[-100:]
            conv_truncated = True

        body = {
            "national_id": national_id,  # seguimos devolviendo el national_id del request
            "triage_timestamp": triage_ts if isinstance(triage_ts, str) and triage_ts.endswith("Z") else utc_now_iso(),
            "medical_digest": tx.get("medical_digest") or "",
            "conversation": conv,
            "conversation_truncated": conv_truncated,
            "request_id": req_id,
        }

        # 2) tope de tamaño: 512 KB (UTF-8). Si se excede, recortamos del inicio (dejamos lo más reciente).
        MAX_BYTES = 512 * 1024
        def _size_ok(obj) -> bool:
            return len(json.dumps(obj, ensure_ascii=False).encode("utf-8")) <= MAX_BYTES

        if not _size_ok(body):
            conv2 = list(body["conversation"])
            while conv2 and not _size_ok({**body, "conversation": conv2}):
                conv2 = conv2[1:]  # descartamos desde el inicio
            if len(conv2) != len(body["conversation"]):
                body["conversation"] = conv2
                body["conversation_truncated"] = True

        return response(200, body, req_id, method=method, path=path)





    # === STUB (si USE_SUPABASE != true) ===
    stub = {
        "national_id": national_id,
        "triage_timestamp": utc_now_iso(),
        "medical_digest": "stub: digest de ejemplo (<=1200 chars).",
        "conversation": [
            {"role": "user", "content": "…enmascarado…", "timestamp": utc_now_iso()},
            {"role": "assistant", "content": "…enmascarado…", "timestamp": utc_now_iso()},
        ],
        "conversation_truncated": False,
        "request_id": req_id,
    }
    return response(200, stub, req_id, method=method, path=path)




# Punto de entrada por defecto (si en serverless.yml apunta a handler.lambda_handler)
def lambda_handler(event, context):
    path = (event.get("path") or "").lower()
    method = (event.get("httpMethod") or "").upper()

    # aceptar ambas variantes de path: con ':' y con '/'
    if path.endswith("/v1/triage:fetch-latest") or path.endswith("/v1/triage/fetch-latest"):
        return triage_fetch_latest(event, context)

    req_id = get_req_id(event)
    return error(404, "NOT_FOUND", "Endpoint not found", req_id, method=method, path=path)




