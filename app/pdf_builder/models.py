# models.py
from dataclasses import dataclass
from typing import List

@dataclass
class Paciente:
    nombre: str
    dni: str
    sexo: str
    fecha_nac: str
    obra_social: str
    plan: str
    credencial: str

@dataclass
class Doctor:
    nombre: str
    especialidad: str
    matricula: str
    email: str
    logo_url: str  # si quieres mostrar logo

@dataclass
class Receta:
    doctor: Doctor
    paciente: Paciente
    rp: List[str]          # líneas del “Rp:”
    diagnostico: str
    fecha: str             # ej. "21/04/2025"
