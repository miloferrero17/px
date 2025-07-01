import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import os

# Ruta al archivo JSON (ajustada automáticamente)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'gmail-test-429212-6952b26370bf.json')

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Autenticación y cliente
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

# Abrir hoja
SPREADSHEET_ID = '131zP1xamAdXdVuYOH4ceqd_J_e-ubh3W32zrhozdsVg'
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# -------------------------------
# FUNCIONES
# -------------------------------

def leer_valor(celda: str) -> pd.DataFrame:
    """Devuelve el valor de una celda como DataFrame de 1 fila, 1 columna"""
    value = sheet.acell(celda).value
    return pd.DataFrame([[value]], columns=[celda])

def escribir_valor(celda: str, valor: str):
    """Escribe un valor en una celda"""
    sheet.update(celda, [[valor]])

def agregar_fila(valores: list):
    """Agrega una fila al final de la hoja"""
    sheet.append_row(valores)

def leer_toda_la_hoja() -> pd.DataFrame:
    rows = sheet.get_all_values()
    return pd.DataFrame(rows)


# -------------------------------
# TEST LOCAL
# -------------------------------
if __name__ == "__main__":
    print("✅ Valor A1 como DataFrame:")
    print(leer_valor("A1"))

    print("\n📝 Escribiendo en A2...")
    escribir_valor("A2", "Desde función pandas")

    print("\n➕ Agregando fila...")
    agregar_fila(["Nombre", "Edad", "Ciudad"])

    print("\n📋 Hoja completa:")
    print(leer_toda_la_hoja())
