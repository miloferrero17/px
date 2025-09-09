from typing import Optional, List, Dict
from app.Model.enums import DataType
from app.Model.base_model import BaseModel
from app.Model.field import Field
from app.Model.exceptions import DatabaseError


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
      - nombre (text UNIQUE)
      - monto (numeric 12,2)  -- ARS (0 = sin copago; >0 = copago o precio particular)
      - activo (bool)
      - updated_at (timestamptz)
    """
    def __init__(self):
        data: Dict[str, Field] = {
            "id":         Field(None, DataType.INTEGER, False, True),
            "nombre":     Field(None, DataType.STRING,  False, False),
            # si tu enum DataType no tiene NUMBER/BOOLEAN/DATETIME, no pasa nada:
            "monto":      Field(None, getattr(DataType, "NUMBER", DataType.STRING),   False, False),
            "activo":     Field(None, getattr(DataType, "BOOLEAN", DataType.STRING),  False, False),
            "updated_at": Field(None, getattr(DataType, "DATETIME", DataType.STRING), False, False),
        }
        super().__init__("coverages", data)
        self.__data = data

    # ---------- Lecturas ----------

    def get_by_name_exact(self, name: str) -> Optional[CoverageRegister]:
        """Match EXACTO por nombre (y activo si existe ese campo)."""
        try:
            rows = super().get("nombre", name)  # devuelve lista de dicts o registros
            if not rows:
                return None
            # si hay campo 'activo', priorizamos activos
            def _active(r):
                return (r.get("activo") if isinstance(r, dict) else getattr(r, "activo", True)) is True
            # primero activo, sino el primero
            row = next((r for r in rows if _active(r)), rows[0])
            return CoverageRegister(**row) if isinstance(row, dict) else row
        except Exception as e:
            raise DatabaseError(f"[coverages.get_by_name_exact] {e}")


    def find_by_name(self, name: str) -> Optional[CoverageRegister]:
        """
        Búsqueda tolerante SIN usar self._db:
        1) exacto (activo si aplica)
        2) fallback: traer activos y matchear por substring (case-insensitive) en Python.
        """
        try:
            exact = self.get_by_name_exact(name)
            if exact:
                return exact

            # listar activos (si BaseModel.get soporta order_field, lo usamos)
            try:
                rows = super().get("activo", True, order_field="nombre")
            except Exception:
                rows = super().get("activo", True)

            if not rows:
                return None

            needle = name.casefold()
            for r in rows:
                nombre = (r["nombre"] if isinstance(r, dict) else getattr(r, "nombre", "")) or ""
                if needle in nombre.casefold():
                    return CoverageRegister(**r) if isinstance(r, dict) else r

            return None
        except Exception as e:
            raise DatabaseError(f"[coverages.find_by_name] {e}")


    def get_amount_by_name(self, name: str) -> Optional[float]:
        reg = self.find_by_name(name)
        if not reg:
            return None
        val = reg["monto"] if isinstance(reg, dict) else getattr(reg, "monto", None)
        if val is None:
            return None
        try:
            return float(val)
        except Exception:
            try:
                return float(str(val).replace(",", "."))
            except Exception:
                return None


    def list_active(self) -> List[CoverageRegister]:
        try:
            rows = super().get("activo", True)
            rows = rows or []
            return [CoverageRegister(**r) if isinstance(r, dict) else r for r in rows]
        except Exception as e:
            raise DatabaseError(f"[coverages.list_active] {e}")



    # ---------- Escrituras ----------

    def upsert(self, name: str, amount: float, active: bool = True) -> None:
        """Inserta/actualiza por nombre (UNIQUE)."""
        try:
            payload = {"nombre": name, "monto": float(amount), "activo": bool(active)}
            self._db.table(self._table_name).upsert(payload, on_conflict="nombre").execute()
        except Exception as e:
            raise DatabaseError(f"[coverages.upsert] {e}")

    def deactivate(self, name: str) -> None:
        """Desactiva una cobertura por nombre."""
        try:
            self._db.table(self._table_name).update({"activo": False}).eq("nombre", name).execute()
        except Exception as e:
            raise DatabaseError(f"[coverages.deactivate] {e}")
