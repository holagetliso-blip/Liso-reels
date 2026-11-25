#!/usr/bin/env python3
"""
check.py — Valida el token y la cuenta antes de publicar nada.
1. GET /me?fields=id,user_id,username
2. Compara con IG_USER_ID
3. GET /<IG_USER_ID>/content_publishing_limit → cuántas publicaciones quedan hoy
"""
from common import ApiError, api, configurar_log, credenciales

log = configurar_log("check")


def main() -> int:
    token, ig_user_id = credenciales()

    # 1. Token válido y a qué cuenta pertenece
    try:
        yo = api("GET", "me", token, {"fields": "id,user_id,username"})
    except ApiError as e:
        log.error("El token no sirve: %s", e)
        if e.codigo == 190:
            log.error("Código 190 = token vencido o inválido. Generá uno nuevo en el panel de Meta y actualizá .env.")
        return 1

    username = yo.get("username", "?")
    ids = {str(yo.get("id", "")), str(yo.get("user_id", ""))} - {""}
    log.info("Token válido. Cuenta: @%s", username)

    # 2. ¿Coincide con IG_USER_ID?
    if ig_user_id in ids:
        log.info("IG_USER_ID coincide con la cuenta del token.")
    else:
        log.error("IG_USER_ID (%s) NO coincide con la cuenta del token (ids de la API: %s).", ig_user_id, ", ".join(sorted(ids)))
        log.error("Revisá en el panel de Meta el 'ID de la cuenta de Instagram' y pegalo en .env.")
        return 1

    if username.lower() != "get.liso":
        log.warning("Ojo: el token es de @%s, no de @get.liso.", username)

    # 3. Cuota de publicación
    try:
        lim = api("GET", f"{ig_user_id}/content_publishing_limit", token, {"fields": "quota_usage,config"})
    except ApiError as e:
        log.error("No pude leer el límite de publicación: %s", e)
        if e.codigo in (10, 200) or "permission" in str(e).lower():
            log.error("Falta el permiso instagram_business_content_publish en el token. Regeneralo con ese permiso.")
        return 1

    datos = (lim.get("data") or [{}])[0]
    usado = int(datos.get("quota_usage", 0))
    total = int((datos.get("config") or {}).get("quota_total", 100))
    log.info("Publicaciones por API en las últimas 24 h: %d de %d. Quedan %d.", usado, total, max(total - usado, 0))
    log.info("Todo OK. Podés correr: python3 publish.py --dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
