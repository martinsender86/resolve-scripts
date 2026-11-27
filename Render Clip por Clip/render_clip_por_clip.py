#!/usr/bin/env python3
# Exporta el timeline actual CLIP POR CLIP, cada clip como un job separado.
# Si un clip falla (frame corrupto, media offline, etc.), se anota en el log
# y se sigue con el siguiente. Al final deja un log CSV.
#
# Antes de correrlo:
#   1. Abrí el timeline que querés exportar.
#   2. En Deliver, configurá todo como siempre en modo "Individual clips"
#      (formato, codec, destino, naming, handles). NO lo agregues a la cola.
#   3. Corré este script desde Workspace > Scripts.
#
# El script usa esa configuración de Deliver y solo cambia el In/Out para
# que cada job abarque un clip.

import csv
import os
import time
from datetime import datetime

# --- Config -------------------------------------------------------------------
PISTA = 1                     # pista de video a recorrer (1 = V1)
POLL_SEGUNDOS = 2
LOG_DIR = os.path.expanduser("~/Desktop")   # cambiar si el Escritorio está en OneDrive

# --- Conexión a Resolve -------------------------------------------------------
try:
    resolve  # definido si se corre desde el menú Scripts de Resolve
except NameError:
    try:
        resolve = app.GetResolve()  # noqa: F821
    except NameError:
        import DaVinciResolveScript as dvr
        resolve = dvr.scriptapp("Resolve")

project = resolve.GetProjectManager().GetCurrentProject()
if not project:
    raise SystemExit("No hay proyecto abierto.")
timeline = project.GetCurrentTimeline()
if not timeline:
    raise SystemExit("No hay timeline abierto.")

# --- Clips de la pista --------------------------------------------------------
items = timeline.GetItemListInTrack("video", PISTA) or []
clips = []
for it in items:
    if it.GetMediaPoolItem() is None:   # saltea títulos, generadores, adjustment clips
        continue
    clips.append(it)

if not clips:
    raise SystemExit(f"No hay clips con media en V{PISTA}.")

print(f"Timeline '{timeline.GetName()}': {len(clips)} clips en V{PISTA}")

# Modo Individual clips, respetando el resto de la config de Deliver
project.SetCurrentRenderMode(0)

# --- Crear un job por clip ----------------------------------------------------
jobs = []
for n, it in enumerate(clips, 1):
    inicio_tl = it.GetStart()
    fin_tl = it.GetEnd() - 1            # GetEnd es exclusivo
    ok = project.SetRenderSettings({
        "SelectAllFrames": False,
        "MarkIn": inicio_tl,
        "MarkOut": fin_tl,
    })
    job_id = project.AddRenderJob() if ok else None
    jobs.append((n, it.GetName(), inicio_tl, fin_tl, job_id))
    if not job_id:
        print(f"   ! No se pudo crear el job para {it.GetName()}")

# --- Renderizar uno por uno ---------------------------------------------------
resultados = []
for n, nombre, tc_in, tc_out, job_id in jobs:
    print(f"[{n}/{len(jobs)}] {nombre}...")
    inicio = datetime.now()

    if not job_id:
        resultados.append([n, nombre, tc_in, tc_out, "No se creó el job", "", "", ""])
        continue

    if not project.StartRendering(job_id):
        resultados.append([n, nombre, tc_in, tc_out, "No arrancó",
                           "StartRendering devolvió False",
                           inicio.isoformat(timespec="seconds"), ""])
        print("   -> no pudo arrancar")
        continue

    while project.IsRenderingInProgress():
        time.sleep(POLL_SEGUNDOS)

    st = project.GetRenderJobStatus(job_id) or {}
    estado = st.get("JobStatus", "Desconocido")
    error = st.get("Error", "")
    duracion = str(datetime.now() - inicio).split(".")[0]
    resultados.append([n, nombre, tc_in, tc_out, estado, error,
                       inicio.isoformat(timespec="seconds"), duracion])
    print(f"   -> {estado}{' | ' + error if error else ''}")

# --- Log ----------------------------------------------------------------------
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = os.path.join(LOG_DIR, f"render_clips_{timeline.GetName()}_{stamp}.csv")
with open(log_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["#", "Clip", "Frame In", "Frame Out", "Estado", "Error", "Inicio", "Duración"])
    w.writerows(resultados)

fallidos = [r for r in resultados if r[4] != "Complete"]
print(f"\nListo. {len(resultados) - len(fallidos)} OK, {len(fallidos)} con problemas.")
for r in fallidos:
    print(f"  FALLÓ #{r[0]}: {r[1]}  ({r[4]}{' - ' + r[5] if r[5] else ''})")
print(f"Log: {log_path}")
