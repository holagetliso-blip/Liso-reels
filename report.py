#!/usr/bin/env python3
"""
report.py — Trae insights (reach, views, likes, comments, saved, shares) de cada reel
publicado hace más de 24 h, los guarda en calendario.csv e imprime un ranking por alcance.

Opciones:
  --all     vuelve a consultar también los que ya tienen insights
"""
from __future__ import annotations

import argparse
from datetime import timedelta

from common import (
    METRICAS_REELS, ApiError, api, ahora, configurar_log, credenciales,
    escribir_calendario, fecha_hora_desde_texto, leer_calendario,
)

log = configurar_log("report")


def insights(token: str, media_id: str) -> dict:
    """Pide todas las métricas juntas; si alguna no está disponible, las pide una por una."""
    try:
        r = api("GET", f"{media_id}/insights", token, {"metric": ",".join(METRICAS_REELS)})
        return {d["name"]: (d.get("values") or [{}])[0].get("value", "") for d in r.get("data", [])}
    except ApiError as e:
        log.warning("  consulta conjunta falló (%s); pruebo métrica por métrica", e)
    out = {}
    for m in METRICAS_REELS:
        try:
            r = api("GET", f"{media_id}/insights", token, {"metric": m})
            for d in r.get("data", []):
                out[d["name"]] = (d.get("values") or [{}])[0].get("value", "")
        except ApiError as e:
            out[m] = ""
            log.warning("  %s no disponible: %s", m, e)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="reconsultar también los que ya tienen insights")
    args = ap.parse_args()

    token, _ = credenciales()
    filas = leer_calendario()
    corte = ahora() - timedelta(hours=24)
    consultadas = 0

    for i, f in enumerate(filas):
        mid = f.get("media_id", "").strip()
        if not mid:
            continue
        pub = fecha_hora_desde_texto(f.get("Publicado_en", ""))
        if pub and pub > corte:
            continue
        if f.get("Insights_en") and not args.all:
            continue
        log.info("Insights de %s (media_id %s)…", f.get("Archivo"), mid)
        try:
            datos = insights(token, mid)
        except ApiError as e:
            log.error("  no se pudo: %s", e)
            continue
        for m in METRICAS_REELS:
            f[m] = str(datos.get(m, ""))
        f["Insights_en"] = ahora().strftime("%Y-%m-%d %H:%M")
        consultadas += 1
        escribir_calendario(filas)

    log.info("Insights actualizados en %d reel(s).", consultadas)

    con_datos = [f for f in filas if f.get("reach", "").strip().isdigit()]
    if not con_datos:
        print("Todavía no hay reels con insights.")
        return 0
    con_datos.sort(key=lambda f: int(f["reach"]), reverse=True)
    print(f"\n{'#':>2}  {'Alcance':>8} {'Views':>8} {'Likes':>6} {'Coment':>6} {'Guard':>6} {'Comp':>6}  Archivo / Creadora")
    for n, f in enumerate(con_datos, 1):
        print(f"{n:>2}  {f['reach']:>8} {f.get('views',''):>8} {f.get('likes',''):>6} {f.get('comments',''):>6} "
              f"{f.get('saved',''):>6} {f.get('shares',''):>6}  {f.get('Archivo')} / {f.get('Creadora')}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
