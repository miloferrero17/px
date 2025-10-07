# app/obs/logs.py
import os, json, time, uuid, traceback
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Optional, Union, Dict, Any
import hashlib


# ===== Config
PX_ENV = os.getenv("PX_ENV", "dev")
PX_SERVICE = os.getenv("PX_SERVICE", "px-engine")
PX_VERSION = os.getenv("PX_VERSION", "v1")
SCHEMA_VERSION = 1  # formato del log

# ===== Contexto por request/tx/nodo/span
CTX_REQUEST_ID = ContextVar("request_id", default=None)
CTX_TX_ID      = ContextVar("tx_id", default=None)
CTX_NODE_ID    = ContextVar("node_id", default=None)
CTX_SPAN_ID    = ContextVar("span_id", default=None)

def _now_ms(): return int(time.time() * 1000)
def _id(prefix): return f"{prefix}_{uuid.uuid4().hex[:12]}"
def _clean(d):   return {k: v for k, v in d.items() if v is not None}

def _emit(level: str, payload: dict):
    base = {
        "ts": _now_ms(),
        "env": PX_ENV,
        "service": PX_SERVICE,
        "version": PX_VERSION,
        "schema_version": SCHEMA_VERSION,
        "level": level,
        "request_id": CTX_REQUEST_ID.get(),
        "tx_id": CTX_TX_ID.get(),
        "node_id": CTX_NODE_ID.get(),
        "span_id": CTX_SPAN_ID.get(),
    }
    base.update(payload or {})
    print(json.dumps(_clean(base), ensure_ascii=False))

# =====

def set_request_id(rid: Optional[str] = None) -> str:
    """Setea o genera request_id y lo guarda en el contexto."""
    rid = rid or _id("req")
    CTX_REQUEST_ID.set(rid)
    return rid

def set_tx_id(tx_id: Optional[Union[int, str]]):
    """Guarda tx_id (puede ser None) en el contexto."""
    CTX_TX_ID.set(tx_id)
    return tx_id

@contextmanager
def node_ctx(node_id: int, *, tx_id: Optional[Union[int, str]] = None, request_id: Optional[str] = None):
    """
    Emite ENGINE_STEP enter/exit con latencia y setea contexto (node_id, tx_id, request_id).
    Usar para envolver la ejecución de un nodo.
    """
    prev_req = CTX_REQUEST_ID.set(request_id or CTX_REQUEST_ID.get() or _id("req"))
    prev_tx  = CTX_TX_ID.set(tx_id if tx_id is not None else CTX_TX_ID.get())
    prev_node= CTX_NODE_ID.set(node_id)
    prev_span= CTX_SPAN_ID.set(_id("span"))

    t0 = time.perf_counter()
    _emit("INFO", {"event":"ENGINE_STEP", "phase":"enter", "status":"OK"})

    err = None
    try:
        yield
        status = "OK"
    except Exception as e:
        status = "ERROR"
        err = {"error_type": type(e).__name__, "error_msg": str(e), "stack": traceback.format_exc()}
        raise
    finally:
        dur = int((time.perf_counter() - t0) * 1000)
        payload = {"event":"ENGINE_STEP","phase":"exit","status":status,"latency_ms":dur}
        if err: payload.update(err)
        _emit("INFO" if status=="OK" else "ERROR", payload)
        CTX_SPAN_ID.reset(prev_span); CTX_NODE_ID.reset(prev_node)
        CTX_TX_ID.reset(prev_tx);     CTX_REQUEST_ID.reset(prev_req)

def enrich_exit_with_next(next_node_id: Optional[int] = None, decision: Optional[str] = None):
    """Enriquecimiento opcional del exit del nodo con próximo nodo y decisión."""
    _emit("INFO", _clean({"event":"ENGINE_STEP_EXIT_ENRICH","next_node_id":next_node_id,"decision":decision}))

@contextmanager
def provider_call(provider: str, operation: str):
    """
    Envuelve una llamada a proveedor y emite un PROVIDER_CALL con status y latency_ms.
    """
    prev_span = CTX_SPAN_ID.set(_id("span"))
    t0 = time.perf_counter()
    err = None
    try:
        yield
        status = "OK"
    except Exception as e:
        status = "ERROR"
        err = {"error_type": type(e).__name__, "error_msg": str(e), "stack": traceback.format_exc()}
        raise
    finally:
        dur = int((time.perf_counter() - t0) * 1000)
        payload = {
            "event":"PROVIDER_CALL",
            "provider": provider,
            "operation": operation,
            "status": status,
            "latency_ms": dur,
        }
        if err: payload.update(err)
        _emit("INFO" if status=="OK" else "ERROR", payload)
        CTX_SPAN_ID.reset(prev_span)

def log_provider_result(*, provider: str, operation: str,
                        provider_ref: Optional[str] = None,
                        bytes_len: Optional[int] = None,
                        to_hash: Optional[str] = None,
                        extra: Optional[Dict[str, Any]] = None):    
    """
    Detalle de resultado del proveedor (ej. Twilio SID) sin PII.
    """
    payload = {
        "event":"PROVIDER_RESULT",
        "provider": provider,
        "operation": operation,
        "provider_ref": provider_ref,
        "bytes_len": bytes_len,
        "to_hash": to_hash,
    }
    if extra: payload.update(extra)
    _emit("INFO", payload)

def pii_hash(raw: Optional[str], length: int = 12) -> Optional[str]:
    """Hash corto para PII (teléfono, email, etc.). No emite nada si raw es None."""
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def op_log(provider: str, operation: str, status: str, t0: Optional[float] = None, **kwargs):
    """
    Log operativo 'one-shot'. Usa el contexto actual (request_id/tx_id/node_id/span_id).
    - Si se pasa t0, calcula latency_ms automáticamente.
    - No imprime PII: to_phone se hashea y sale como 'to_hash'.
    - Acepta kwargs opcionales: latency_ms, error, error_code, bytes_len, provider_ref, to_phone, extra.
    """

    # ---- kwargs opcionales ----
    latency_ms = kwargs.get("latency_ms")
    if latency_ms is None and t0 is not None:
        latency_ms = int((time.perf_counter() - t0) * 1000)

    error: Optional[str] = kwargs.get("error")
    error_code: Optional[str] = kwargs.get("error_code")
    bytes_len: Optional[int] = kwargs.get("bytes_len")
    provider_ref: Optional[str] = kwargs.get("provider_ref")
    to_phone: Optional[str] = kwargs.get("to_phone")
    extra: Optional[Dict[str, Any]] = kwargs.get("extra")

    # ---- contexto (no PII) ----
    request_id = kwargs.get("request_id") or CTX_REQUEST_ID.get()
    tx_id      = kwargs.get("tx_id")      or CTX_TX_ID.get()
    node_id    = kwargs.get("node_id")    or CTX_NODE_ID.get()
    span_id    = kwargs.get("span_id")    or CTX_SPAN_ID.get()

    payload = {
        "event": "OP_LOG",
        "provider": provider,
        "operation": operation,
        "status": status,
        "latency_ms": latency_ms,
        "error": error,
        "error_code": error_code,
        "bytes_len": bytes_len,
        "provider_ref": provider_ref,
        "to_hash": pii_hash(to_phone) if to_phone else None,  # <- hash en vez de número
        "request_id": request_id,
        "tx_id": tx_id,
        "node_id": node_id,
        "span_id": span_id,
    }

    if isinstance(extra, dict):
        payload.update({k: v for k, v in extra.items() if v is not None})

    _emit("INFO" if str(status).upper() == "OK" else "ERROR", _clean(payload))

import functools

def log_latency(func):
    """
    Decorador simple para medir latencia de funciones internas (engine, message_p, etc.).
    Emite un evento FUNC_CALL estructurado con latency_ms y status.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        status = "OK"
        try:
            return func(*args, **kwargs)
        except Exception as e:
            status = "ERROR"
            _emit("ERROR", {
                "event": "FUNC_CALL",
                "provider": "engine",
                "operation": func.__name__,
                "status": status,
                "error_type": type(e).__name__,
                "error_msg": str(e),
            })
            raise
        finally:
            dur = int((time.perf_counter() - t0) * 1000)
            _emit("INFO" if status == "OK" else "ERROR", {
                "event": "FUNC_CALL",
                "provider": "engine",
                "operation": func.__name__,
                "status": status,
                "latency_ms": dur,
            })
    return wrapper
