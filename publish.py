#!/usr/bin/env python3
"""
publish.py — Publica como Reel de prueba (trial reel) cada fila Pendiente cuya fecha/hora ya pasó
(o falta menos de 10 minutos).

Flujo por fila:
  1. POST /<IG_USER_ID>/media  (media_type=REELS, video_url, caption, trial_params)
  2. Polling GET /<container>?fields=status_code hasta FINISHED (máx. 5 min)
  3. POST /<IG_USER_ID>/media_publish  (creation_id)
  4. Guarda en calendario.csv: Estado=Publicado, media_id, Publicado_en

Opciones:
  --dry-run            muestra qué publicaría, sin llamar a la API
  --only ARCHIVO       procesa solo la fila cuyo Archivo coincide
  --ignore-time        ignora fecha/hora (sirve para la primera prueba)
  --strategy MANUAL|SS_PERFORMANCE   (default: SS_PERFORMANCE)
"""
from __future__ import annotations

import argparse
import time
from datetime import timedelta

from common import (
    ApiError, api, ahora, configurar_log, credenciales, escribir_calendario,
    fecha_hora_desde_texto, fecha_hora_fila, leer_calendario,
)

log = configurar_log("publish")

VENTANA_ANTICIPO = timedelta(minutes=10)      # publica si falta menos de esto
SEPARACION_MINIMA = timedelta(minutes=5)      # nunca dos reels con menos de 5 min
POLL_INTERVALO = 20                            # segundos entre consultas de estado
POLL_MAXIMO = 5 * 60                           # Meta recomienda no más de 5 minutos
SHARE_TO_FEED = None                           # None = no mandar el campo (recomendado para trial reels)


def caption_de(fila: dict) -> str:
    desc = fila.get("Descripción", "").strip()
    tags = fila.get("Hashtags", "").strip()
    return f"{desc}\n\n{tags}".strip() if tags else desc


def ultima_publicacion(filas: list[dict]):
    ultimo = None
    for f in filas:
        dt = fecha_hora_desde_texto(f.get("Publicado_en", ""))
        if dt and (ultimo is None or dt > ultimo):
            ultimo = dt
    return ultimo


def es_error_limite_trial(e: ApiError) -> bool:
    m = str(e).lower()
    return "trial" in m and ("maximum" in m or "máximo" in m or "limit" in m)


def crear_contenedor(token: str, ig_user_id: str, fila: dict, strategy: str) -> str:
    body = {
        "media_type": "REELS",
        "video_url": fila["URL_video"],
        "caption": caption_de(fila),
        "trial_params": {"graduation_strategy": strategy},
    }
    if SHARE_TO_FEED is not None:
        body["share_to_feed"] = SHARE_TO_FEED
    r = api("POST", f"{ig_user_id}/media", token, body=body)
    cid = r.get("id")
    if not cid:
        raise ApiError(f"La API no devolvió id de contenedor: {r}")
    return str(cid)


def esperar_contenedor(token: str, container_id: str) -> None:
    inicio = time.monotonic()
    while True:
        r = api("GET", container_id, token, {"fields": "status_code,status"})
        estado = r.get("status_code", "?")
        if estado == "FINISHED":
            return
        if estado in ("ERROR", "EXPIRED"):
            raise ApiError(f"Contenedor en estado {estado}: {r.get('status', '')}")
        if time.monotonic() - inicio > POLL_MAXIMO:
            raise ApiError(f"El contenedor sigue en {estado} después de 5 minutos. Reintentá más tarde.")
        log.info("  contenedor %s en %s, espero %ds…", container_id, estado, POLL_INTERVALO)
        time.sleep(POLL_INTERVALO)


def publicar_contenedor(token: str, ig_user_id: str, container_id: str) -> str:
    r = api("POST", f"{ig_user_id}/media_publish", token, body={"creation_id": container_id})
    mid = r.get("id")
    if not mid:
        raise ApiError(f"media_publish no devolvió id: {r}")
    return str(mid)


def main() -> int:
    ap = argparse.ArgumentParser(description="Publica reels de prueba desde calendario.csv")
    ap.add_argument("--dry-run", action="store_true", help="no llama a la API")
    ap.add_argument("--only", metavar="ARCHIVO", help="solo la fila con ese Archivo")
    ap.add_argument("--ignore-time", action="store_true", help="ignora fecha/hora del calendario")
    ap.add_argument("--strategy", choices=["MANUAL", "SS_PERFORMANCE"], default="SS_PERFORMANCE")
    args = ap.parse_args()

    filas = leer_calendario()
    hoy = ahora()
    limite = hoy + VENTANA_ANTICIPO

    candidatas = []
    for i, f in enumerate(filas):
        if f.get("Estado", "").strip().lower() != "pendiente":
            continue
        if args.only and f.get("Archivo", "").strip() != args.only:
            continue
        dt = fecha_hora_fila(f)
        if dt is None and not args.ignore_time:
            log.warning("Fila %d (%s): Fecha/Hora inválidas, la salteo.", i + 2, f.get("Archivo"))
            continue
        if not args.ignore_time and dt > limite:
            continue
        candidatas.append((i, f))

    candidatas.sort(key=lambda t: fecha_hora_fila(t[1]) or hoy)

    if not candidatas:
        log.info("Nada para publicar ahora (%s).", hoy.strftime("%d/%m %H:%M"))
        return 0

    if args.dry_run:
        print(f"\n=== DRY RUN — {len(candidatas)} fila(s) se publicarían ahora ({hoy.strftime('%d/%m %H:%M')}) ===")
        for i, f in candidatas:
            problemas = []
            if not f.get("URL_video"):
                problemas.append("falta URL_video")
            if not f.get("Descripción"):
                problemas.append("sin Descripción")
            print(f"\n[fila {i + 2}] {f.get('Fecha')} {f.get('Hora')}  {f.get('Archivo')}  ({f.get('Creadora')})")
            print(f"  estrategia: {args.strategy}")
            print(f"  URL: {f.get('URL_video') or '—'}")
            print("  caption:\n    " + caption_de(f).replace("\n", "\n    "))
            if problemas:
                print("  ⚠ " + ", ".join(problemas))
        print()
        return 0

    token, ig_user_id = credenciales()
    ultimo = ultima_publicacion(filas)
    publicados = 0

    for i, f in candidatas:
        nombre = f.get("Archivo") or f"fila {i + 2}"

        if not f.get("URL_video"):
            f["Estado"] = "Error"
            f["Notas"] = "Falta URL_video (el video tiene que estar en una URL pública)"
            log.error("%s: falta URL_video, la marco como Error.", nombre)
            escribir_calendario(filas)
            continue

        # separación mínima de 5 minutos entre publicaciones
        if ultimo is not None:
            faltan = (ultimo + SEPARACION_MINIMA) - ahora()
            if faltan.total_seconds() > 0:
                segundos = int(faltan.total_seconds()) + 1
                log.info("Última publicación hace poco; espero %ds antes de %s.", segundos, nombre)
                time.sleep(segundos)

        log.info("Publicando %s (%s)…", nombre, f.get("Creadora", ""))
        try:
            cid = crear_contenedor(token, ig_user_id, f, args.strategy)
            f["container_id"] = cid
            escribir_calendario(filas)
            log.info("  contenedor creado: %s", cid)
            esperar_contenedor(token, cid)
            mid = publicar_contenedor(token, ig_user_id, cid)
            ultimo = ahora()
            f["media_id"] = mid
            f["Estado"] = "Publicado"
            f["Publicado_en"] = ultimo.strftime("%Y-%m-%d %H:%M")
            f["Notas"] = ""
            publicados += 1
            escribir_calendario(filas)
            log.info("  PUBLICADO como reel de prueba. media_id=%s", mid)
        except ApiError as e:
            f["Estado"] = "Error"
            f["Notas"] = str(e)[:300]
            escribir_calendario(filas)
            log.error("  ERROR en %s: %s", nombre, e)
            if es_error_limite_trial(e):
                log.error("Instagram no acepta más reels de prueba hoy. Freno hasta mañana.")
                f["Notas"] = "Límite diario de reels de prueba alcanzado: " + str(e)[:200]
                escribir_calendario(filas)
                break
        except KeyboardInterrupt:
            log.warning("Interrumpido por el usuario.")
            escribir_calendario(filas)
            return 130

    log.info("Listo: %d publicado(s) de %d candidata(s).", publicados, len(candidatas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
