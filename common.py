"""
Utilidades compartidas: .env, API de Instagram (Instagram Login), CSV y logs.
Nunca imprime ni registra el token.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
CSV_PATH = BASE_DIR / "calendario.csv"
LOG_DIR = BASE_DIR / "logs"
LOG_PATH = LOG_DIR / "publish.log"

API_HOST = "https://graph.instagram.com"
API_VERSION = "v27.0"
TZ = ZoneInfo("America/Argentina/Buenos_Aires")

# Columnas del calendario. Las primeras 10 las carga la persona; el resto las escriben los scripts.
COLUMNAS_BASE = [
    "Fecha", "Hora", "Archivo", "Creadora", "Qué muestra", "Descripción",
    "Hashtags", "Estado", "Notas", "URL_video",
]
COLUMNAS_SCRIPT = [
    "container_id", "media_id", "Publicado_en",
    "reach", "views", "likes", "comments", "saved", "shares", "Insights_en",
]
COLUMNAS = COLUMNAS_BASE + COLUMNAS_SCRIPT

METRICAS_REELS = ["reach", "views", "likes", "comments", "saved", "shares"]


# --------------------------------------------------------------------------- .env
def cargar_env() -> dict:
    """Lee .env (KEY=VALUE, sin comillas) y lo mete en os.environ sin pisar lo existente."""
    if not ENV_PATH.exists():
        raise SystemExit("No existe .env. Copiá .env.example a .env y completalo.")
    valores = {}
    for linea in ENV_PATH.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave, valor = clave.strip(), valor.strip().strip('"').strip("'")
        valores[clave] = valor
        os.environ.setdefault(clave, valor)
    return valores


def requerir(clave: str) -> str:
    valor = os.environ.get(clave, "").strip()
    if not valor:
        raise SystemExit(f"Falta {clave} en .env")
    return valor


def credenciales() -> tuple[str, str]:
    cargar_env()
    return requerir("IG_ACCESS_TOKEN"), requerir("IG_USER_ID")


def escribir_env(clave: str, valor: str) -> None:
    """Reemplaza (o agrega) una clave en .env conservando el resto del archivo."""
    lineas = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    hecho = False
    for i, linea in enumerate(lineas):
        if linea.split("=", 1)[0].strip() == clave:
            lineas[i] = f"{clave}={valor}"
            hecho = True
    if not hecho:
        lineas.append(f"{clave}={valor}")
    ENV_PATH.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    try:
        os.chmod(ENV_PATH, 0o600)
    except OSError:
        pass


# --------------------------------------------------------------------------- logs
def configurar_log(nombre: str) -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(nombre)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def ahora() -> datetime:
    return datetime.now(TZ)


# --------------------------------------------------------------------------- API
class ApiError(Exception):
    def __init__(self, mensaje: str, codigo: int | None = None, subcodigo: int | None = None, http: int | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.subcodigo = subcodigo
        self.http = http

    def __str__(self) -> str:
        partes = [self.mensaje]
        if self.codigo is not None:
            partes.append(f"code={self.codigo}")
        if self.subcodigo is not None:
            partes.append(f"subcode={self.subcodigo}")
        if self.http is not None:
            partes.append(f"http={self.http}")
        return " | ".join(partes)


def _ocultar_token(texto: str, token: str) -> str:
    return texto.replace(token, "***TOKEN***") if token else texto


def api(metodo: str, ruta: str, token: str, params: dict | None = None, body: dict | None = None, timeout: int = 60) -> dict:
    """
    Llama a graph.instagram.com/<version>/<ruta>.
    GET: params en query string. POST: body como JSON.
    El token va en el header Authorization y nunca en la URL ni en los logs.
    """
    url = f"{API_HOST}/{API_VERSION}/{ruta.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    datos = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo.upper())
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if datos is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(cuerpo).get("error", {})
        except json.JSONDecodeError:
            err = {}
        mensaje = _ocultar_token(err.get("error_user_msg") or err.get("message") or cuerpo[:300], token)
        raise ApiError(mensaje, err.get("code"), err.get("error_subcode"), e.code) from None
    except urllib.error.URLError as e:
        raise ApiError(f"Sin conexión con la API: {e.reason}") from None


def api_get_raw(url: str, token: str, params: dict, timeout: int = 60) -> dict:
    """GET a una URL completa (para refresh_access_token, que no lleva versión)."""
    params = dict(params)
    params["access_token"] = token
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(cuerpo).get("error", {})
        except json.JSONDecodeError:
            err = {}
        raise ApiError(_ocultar_token(err.get("message") or cuerpo[:300], token), err.get("code"), err.get("error_subcode"), e.code) from None


# --------------------------------------------------------------------------- CSV
def leer_calendario() -> list[dict]:
    if not CSV_PATH.exists():
        raise SystemExit("No existe calendario.csv")
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        lector = csv.DictReader(f)
        filas = []
        for fila in lector:
            completa = {c: (fila.get(c) or "").strip() for c in COLUMNAS}
            # conservar columnas extra que haya agregado la persona
            for k, v in fila.items():
                if k and k not in completa:
                    completa[k] = (v or "").strip()
            filas.append(completa)
    return filas


def escribir_calendario(filas: list[dict]) -> None:
    """Escribe de forma atómica (archivo temporal + rename) para no romper el CSV si se corta."""
    extras = []
    for fila in filas:
        for k in fila:
            if k not in COLUMNAS and k not in extras:
                extras.append(k)
    columnas = COLUMNAS + extras
    tmp = CSV_PATH.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow({c: fila.get(c, "") for c in columnas})
    tmp.replace(CSV_PATH)


def fecha_hora_fila(fila: dict) -> datetime | None:
    """Combina Fecha (2026-11-24) y Hora (11:30) en un datetime con zona de Buenos Aires."""
    try:
        return datetime.strptime(f"{fila['Fecha']} {fila['Hora']}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    except (ValueError, KeyError):
        return None


def fecha_hora_desde_texto(texto: str) -> datetime | None:
    try:
        return datetime.strptime(texto, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    except ValueError:
        return None
