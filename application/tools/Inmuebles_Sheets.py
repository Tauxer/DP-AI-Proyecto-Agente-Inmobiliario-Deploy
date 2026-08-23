"""
Tool: Consulta de inmuebles en alquiler en Google Sheets (SOLO LECTURA)
Lee la hoja de cálculo "Departamentos" con el listado de inmuebles disponibles,
usando la misma cuenta de servicio de Google Cloud que tools/Google_Sheets.py.

Expone una tool al agente:
- buscar_inmuebles: busca inmuebles por texto libre (dirección, zona, código,
  características) y devuelve el detalle de las coincidencias.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
import unicodedata

from dotenv import load_dotenv, find_dotenv
from langchain_core.tools import tool

import gspread
from google.oauth2.service_account import Credentials

load_dotenv(find_dotenv())

# ============================================
# CONFIGURACIÓN
# ============================================
GOOGLE_SHEET_ID2 = os.getenv("GOOGLE_SHEET_ID2")
GOOGLE_SHEETS_WORKSHEET2 = os.getenv("GOOGLE_SHEETS_WORKSHEET2", "Departamentos")
GOOGLE_SHEETS_HEADER_ROW2 = int(os.getenv("GOOGLE_SHEETS_HEADER_ROW2", "1"))
# Misma cuenta de servicio que tools/Google_Sheets.py (hay que compartirle
# también este segundo documento).
GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    "credentials/service-account.json",
)

# Scope de SOLO LECTURA
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

if not GOOGLE_SHEET_ID2:
    raise ValueError(
        "❌ Falta variable GOOGLE_SHEET_ID2 en .env"
    )


# ============================================
# CLIENTE GSPREAD (lazy + cache simple)
# ============================================
_worksheet = None


def _resolve_credentials_path(path: str) -> str:
    """Si la ruta es relativa, la resuelve contra el directorio del proyecto."""
    if os.path.isabs(path):
        return path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, path)


def _get_worksheet():
    """Conecta a Google Sheets de forma lazy y devuelve el worksheet."""
    global _worksheet
    if _worksheet is not None:
        return _worksheet

    creds_path = _resolve_credentials_path(GOOGLE_APPLICATION_CREDENTIALS)
    if not os.path.isfile(creds_path):
        raise FileNotFoundError(
            f"No se encontró el JSON de la cuenta de servicio en '{creds_path}'. "
            f"Descárgalo desde Google Cloud y colócalo en esa ruta."
        )

    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(GOOGLE_SHEET_ID2)
    _worksheet = sheet.worksheet(GOOGLE_SHEETS_WORKSHEET2)
    return _worksheet


# ============================================
# UTILIDADES
# ============================================
def _normalize(text) -> str:
    """Normaliza texto: minúsculas, sin acentos, sin espacios extra."""
    if text is None:
        return ""
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def _dedup_headers(headers: list) -> list:
    """Renombra duplicados con sufijo numérico (Total → Total, Total_2, Total_3)."""
    counts = {}
    out = []
    for h in headers:
        h = (h or "").strip() or "Columna"
        if h in counts:
            counts[h] += 1
            out.append(f"{h}_{counts[h]}")
        else:
            counts[h] = 1
            out.append(h)
    return out


def _cargar_datos():
    """Lee la hoja y devuelve (headers, data_rows)."""
    ws = _get_worksheet()
    all_values = ws.get_all_values()
    header_idx = GOOGLE_SHEETS_HEADER_ROW2 - 1
    if header_idx >= len(all_values):
        raise ValueError(
            f"La hoja no tiene fila {GOOGLE_SHEETS_HEADER_ROW2} para usar como encabezado."
        )
    headers = _dedup_headers(
        [(h or "").strip() or "Columna" for h in all_values[header_idx]]
    )
    data_rows = [r for r in all_values[header_idx + 1:] if any(c.strip() for c in r)]
    return headers, data_rows


def _fila_coincide(row: list, criterio_norm: str) -> bool:
    """True si alguna celda de la fila contiene el criterio buscado."""
    return any(criterio_norm in _normalize(v) for v in row)


# ============================================
# TOOLS EXPORTABLES
# ============================================
@tool
def buscar_inmuebles(criterio: str) -> str:
    """
    Busca inmuebles en alquiler que coincidan con un criterio de búsqueda libre
    (dirección, zona, código de unidad, dormitorios, precio, etc.) y devuelve
    el detalle completo de cada coincidencia encontrada en la hoja "Departamentos".

    Úsala cuando el usuario pregunte:
    - "¿Qué departamentos hay disponibles en tal zona?"
    - "¿Tienen algo en la calle X?"
    - "Muéstrame los inmuebles de 2 dormitorios"
    - "Dame el detalle del departamento X"

    Args:
        criterio: texto libre a buscar (dirección, zona, código, características).
    """
    print(f"   🏠 Buscando inmuebles para: '{criterio}'")
    try:
        headers, rows = _cargar_datos()
        criterio_norm = _normalize(criterio)
        if not criterio_norm:
            return "Indica un criterio de búsqueda (dirección, zona, código, etc.)."

        coincidencias = [r for r in rows if _fila_coincide(r, criterio_norm)]

        if not coincidencias:
            return f"No encontré inmuebles que coincidan con '{criterio}'."

        MAX_RESULTADOS = 5
        partes = [f"🏠 Encontré {len(coincidencias)} inmueble(s):", ""]
        for row in coincidencias[:MAX_RESULTADOS]:
            fila = dict(zip(headers, row))
            detalle = " | ".join(
                f"{col}: {val}" for col, val in fila.items() if str(val).strip()
            )
            partes.append(f"- {detalle}")

        if len(coincidencias) > MAX_RESULTADOS:
            restantes = len(coincidencias) - MAX_RESULTADOS
            partes.append(
                f"\n...y {restantes} más. Pide un criterio más específico "
                f"(zona, dormitorios, precio) para acotar la búsqueda."
            )

        return "\n".join(partes)
    except Exception as e:
        print(f"   ❌ Error en buscar_inmuebles: {e!r}")
        return f"Error al consultar el sheet de inmuebles: {str(e)}"
