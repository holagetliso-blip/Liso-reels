#!/usr/bin/env python3
"""
refresh_token.py — Renueva el token de larga duración (60 días) y actualiza .env.
GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=...
Requisitos de Meta: el token tiene que tener más de 24 h y no estar vencido.
Correrlo al menos una vez por mes (ver README).
"""
from datetime import timedelta

from common import ApiError, api_get_raw, ahora, cargar_env, configurar_log, escribir_env, requerir

log = configurar_log("refresh_token")


def main() -> int:
    cargar_env()
    token = requerir("IG_ACCESS_TOKEN")
    try:
        r = api_get_raw("https://graph.instagram.com/refresh_access_token", token, {"grant_type": "ig_refresh_token"})
    except ApiError as e:
        log.error("No se pudo renovar el token: %s", e)
        log.error("Si el token tiene menos de 24 h, esperá un día. Si está vencido, generá uno nuevo en el panel de Meta.")
        return 1
    nuevo = r.get("access_token")
    if not nuevo:
        log.error("La API no devolvió access_token. Respuesta sin token: %s", {k: v for k, v in r.items() if k != "access_token"})
        return 1
    escribir_env("IG_ACCESS_TOKEN", nuevo)
    segundos = int(r.get("expires_in", 0))
    vence = ahora() + timedelta(seconds=segundos)
    escribir_env("IG_TOKEN_VENCE", vence.strftime("%Y-%m-%d"))
    log.info("Token renovado. Vence aprox. el %s (%d días). Guardado en .env.", vence.strftime("%d/%m/%Y"), segundos // 86400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
