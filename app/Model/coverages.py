from typing import Optional, List, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field
from app.Model.exceptions import DatabaseError
import re, unicodedata



class CoverageRegister:
    """Registro dinámico; acepta cualquier campo proveniente de la DB."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return f"CoverageRegister({self.__dict__})"


class Coverages(BaseModel):
    """
    Modelo para la tabla 'coverages':
    - id (bigserial PK)
    - name (text)
    - coverage_type (text)  -- OOSS | Prepaga | Mutual
    - amount (numeric 12,2) -- 0 = sin copago; >0 = copago o precio particular
    - active (bool)
    - updated_at (timestamptz)
    """

    def __init__(self):
        data: Dict[str, Field] = {
            "id":         Field(None, DataType.INTEGER,  False, True),
            "name":       Field(None, DataType.STRING,   False, False),   # antes: nombre
            "coverage_type":  Field(None, DataType.STRING,   False, False),
            "plan":       Field(None, DataType.STRING,   False, False),
            "amount":     Field(None, getattr(DataType, "NUMBER", DataType.STRING),   False, False),   # antes: monto
            "active":     Field(None, getattr(DataType, "BOOLEAN", DataType.STRING),  False, False),   # antes: activo
            "updated_at": Field(None, getattr(DataType, "DATETIME", DataType.STRING), False, False),
        }
        super().__init__("coverages", data)
        self.__data = data

    # ---------- Lecturas ----------
     # --- Normalización interna (evita repetir en nodos) ---

# ... dentro de class Coverages:

    @staticmethod
    def _norm_name(name: str) -> str:
        s = ''.join(c for c in unicodedata.normalize('NFD', name or '') if unicodedata.category(c) != 'Mn')
        return re.sub(r'\s+', ' ', s).strip().upper()

    @staticmethod
    def _norm_plan(plan: str) -> str:
        s = ''.join(c for c in unicodedata.normalize('NFD', plan or '') if unicodedata.category(c) != 'Mn')
        return (re.sub(r'\s+', '', s).strip().upper()) or 'UNICO'

    @staticmethod
    def _to_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except Exception:
            try:
                return float(str(val).replace(',', '.'))
            except Exception:
                return None

    def get_by_name_exact(self, name: str) -> Optional[CoverageRegister]:
        """Match por name, tolerante a mayúsculas/acentos. Prioriza activos (vía REST de BaseModel)."""
        try:
            name_n = self._norm_name(name)

            # Único camino: traer activos y comparar normalizado en Python
            rows = self.list_active()
            for r in rows:
                _name = (r.__dict__.get("name") if isinstance(r, CoverageRegister) else getattr(r, "name", "")) or ""
                if self._norm_name(_name) == name_n:
                    return r

            return None
        except Exception as e:
            raise DatabaseError(f"[coverages.get_by_name_exact] {e}")


    def find_by_name(self, name: str) -> Optional[CoverageRegister]:
        """Exacto (tolerante) y si no, substring normalizado sobre activos."""
        try:
            exact = self.get_by_name_exact(name)
            if exact:
                return exact

            rows = self.list_active()
            needle = self._norm_name(name)
            for r in rows:
                _name = (r.__dict__.get("name") if isinstance(r, CoverageRegister) else getattr(r, "name", "")) or ""
                if needle in self._norm_name(_name):
                    return r
            return None
        except Exception as e:
            raise DatabaseError(f"[coverages.find_by_name] {e}")

    def get_amount_by_name(self, name: str) -> Optional[float]:
        reg = self.find_by_name(name)
        if not reg:
            return None
        val = reg.__dict__.get("amount") if isinstance(reg, CoverageRegister) else getattr(reg, "amount", None)
        return self._to_float(val)

    def get_amount_by_name_and_plan(self, name: str, plan: str) -> Optional[float]:
        """
        DEPRECATED/ON-HOLD: 'plan' ya no existe en la tabla.
        Mantiene la firma por compatibilidad pero ignora 'plan' y busca sólo por 'name'.
        """
        try:
            return self.get_amount_by_name(name)
        except Exception as e:
            raise DatabaseError(f"Error in get_amount_by_name_and_plan (on-hold): {e}")




    def list_active(self) -> List[CoverageRegister]:
        try:
            rows = super().get("active", True) or []
            # BaseModel.get devuelve objetos *Register; si viniera dict, lo normalizamos
            return [CoverageRegister(**r) if isinstance(r, dict) else r for r in rows]
        except Exception as e:
            raise DatabaseError(f"[coverages.list_active] {e}")



        
    




    # ---------- Escrituras ----------

    def upsert(self, name: str, amount: float, plan: str = "UNICO",
            coverage_type: Optional[str] = None, active: bool = True) -> None:
        """
        Inserta/actualiza por 'name'. 'plan' queda on-hold (no se persiste).
        Requiere UNIQUE(name) en DB para on_conflict='name'.
        """
        try:
            payload = {"name": name, "amount": float(amount), "active": bool(active)}
            if coverage_type is not None:
                payload["coverage_type"] = coverage_type
            super().upsert(payload, on_conflict="name")
        except Exception as e:
            raise DatabaseError(f"[coverages.upsert] {e}")


    from urllib.parse import quote  # arriba del archivo si no lo tenés
    import requests                 # arriba del archivo si no lo tenés

    def deactivate(self, name: str, plan: Optional[str] = None) -> None:
        """Desactiva por name. 'plan' on-hold (no se usa)."""
        try:
            url = f"{self.base_url}?name=eq.{quote(name)}"
            r = requests.patch(url, headers=self.headers, json={"active": False}, timeout=10)
            if r.status_code >= 400:
                raise DatabaseError(f"HTTP {r.status_code}: {r.text}")
        except Exception as e:
            raise DatabaseError(f"[coverages.deactivate] {e}")


