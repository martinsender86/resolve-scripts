#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RenderPorCarpeta — DaVinci Resolve
Toma los clips de la timeline actual y arma un render job por cada uno.
Cada render va a:  CARPETA_DESTINO / <nombre de la carpeta del Media Pool del clip> / <nombre del clip>

Ejemplo: un clip que vive en la carpeta "CamA" del Media Pool se renderiza en
    F:\\SOLRAC\\EXPORTS\\Renders\\CamA\\C0001.mov

El FORMATO, CODEC y RESOLUCION son los que tengas configurados en la pagina Deliver:
el script solo cambia destino, nombre y rango (In/Out) de cada job.

Uso:
  1) Abri la timeline y configura el formato/codec en Deliver.
  2) Workspace > Scripts > RenderPorCarpeta
  3) Revisa la Render Queue y dale Render (o activa RENDERIZAR_AL_FINAL).
Log: Workspace > Console (pestaña Py3)
"""

import os
import re

# ================== CONFIGURACION ==================
CARPETA_DESTINO = r"F:\Avid MediaFiles"   # Disco/carpeta base de destino
RUTA_COMPLETA = False          # False: ...\CamA\   |   True: ...\Dia1\CamA\ (replica la ruta del Media Pool)
PISTA_VIDEO = 1                # Pista de video a recorrer (1 = V1). 0 = todas las pistas
SOLO_COLOR = ""                # Solo clips con este color en la timeline (ej: "Orange"). Vacio = todos
SALTEAR_DESHABILITADOS = True  # No renderiza clips deshabilitados en la timeline
NOMBRE_SIN_EXTENSION = True    # "C0001" en vez de "C0001.mov" como nombre de salida
RENDERIZAR_AL_FINAL = False    # True: arranca el render apenas arma los jobs
# ===================================================


def get_resolve():
    g = globals()
    if g.get("resolve"):
        return g["resolve"]
    if g.get("app"):
        try:
            return g["app"].GetResolve()
        except Exception:
            pass
    if g.get("bmd"):
        try:
            return g["bmd"].scriptapp("Resolve")
        except Exception:
            pass
    try:
        import DaVinciResolveScript as dvr
        return dvr.scriptapp("Resolve")
    except ImportError:
        return None


def limpiar(texto):
    """Nombre seguro para carpetas y archivos en Windows."""
    texto = re.sub(r'[\\/:*?"<>|\t\r\n]+', "_", str(texto)).strip(" .")
    return texto or "SinNombre"


def mapa_carpetas(folder, ruta, mapa):
    """mapa[id del clip del Media Pool] = ruta de carpetas (lista de nombres, sin 'Master')."""
    ruta_actual = ruta + [folder.GetName()]
    for clip in (folder.GetClipList() or []):
        try:
            mapa[clip.GetUniqueId()] = ruta_actual[1:] or ruta_actual
        except Exception:
            pass
    for sub in (folder.GetSubFolderList() or []):
        mapa_carpetas(sub, ruta_actual, mapa)


def item_habilitado(item):
    try:
        return item.GetClipEnabled()
    except Exception:
        return True


def main():
    resolve = get_resolve()
    if not resolve:
        print("No pude conectarme a Resolve. Correlo desde Workspace > Scripts.")
        return
    proyecto = resolve.GetProjectManager().GetCurrentProject()
    if not proyecto:
        print("No hay proyecto abierto.")
        return
    timeline = proyecto.GetCurrentTimeline()
    if not timeline:
        print("No hay timeline abierta.")
        return

    mp = proyecto.GetMediaPool()
    mapa = {}
    mapa_carpetas(mp.GetRootFolder(), [], mapa)

    pistas = range(1, (timeline.GetTrackCount("video") or 0) + 1) if PISTA_VIDEO == 0 else [PISTA_VIDEO]

    print("")
    print("=========== RENDER POR CARPETA ===========")
    print("Timeline: {} | Pistas: {}".format(timeline.GetName(), ", ".join("V%d" % p for p in pistas)))
    print("Destino base: {}".format(CARPETA_DESTINO))
    if SOLO_COLOR:
        print("Solo clips color: {}".format(SOLO_COLOR))
    print("------------------------------------------")

    usados = {}            # para no pisar archivos con el mismo nombre en la misma carpeta
    jobs, salteados, errores = 0, 0, 0

    for pista in pistas:
        for item in (timeline.GetItemListInTrack("video", pista) or []):
            if SALTEAR_DESHABILITADOS and not item_habilitado(item):
                salteados += 1
                continue
            if SOLO_COLOR and (item.GetClipColor() or "").lower() != SOLO_COLOR.lower():
                salteados += 1
                continue

            mpi = item.GetMediaPoolItem()
            if not mpi:  # titulos, generadores, etc.
                salteados += 1
                print("  --   '{}' no tiene clip de Media Pool (titulo/generador), salteado".format(item.GetName()))
                continue

            ruta = mapa.get(mpi.GetUniqueId(), ["Sin carpeta"])
            partes = ruta if RUTA_COMPLETA else [ruta[-1]]
            destino = os.path.join(CARPETA_DESTINO, *[limpiar(p) for p in partes])

            nombre = mpi.GetName() or item.GetName()
            if NOMBRE_SIN_EXTENSION:
                nombre = os.path.splitext(nombre)[0]
            nombre = limpiar(nombre)

            clave = (destino.lower(), nombre.lower())
            usados[clave] = usados.get(clave, 0) + 1
            if usados[clave] > 1:
                nombre = "{}_{}".format(nombre, usados[clave])

            try:
                if not os.path.isdir(destino):
                    os.makedirs(destino)
            except Exception as e:
                errores += 1
                print("  ERR  no pude crear {} ({})".format(destino, e))
                continue

            inicio = item.GetStart()
            fin = inicio + item.GetDuration() - 1

            ok = proyecto.SetRenderSettings({
                "SelectAllFrames": False,
                "MarkIn": inicio,
                "MarkOut": fin,
                "TargetDir": destino,
                "CustomName": nombre,
            })
            job = proyecto.AddRenderJob() if ok else None
            if job:
                jobs += 1
                print("  OK   {}  ->  {}".format(nombre, destino))
            else:
                errores += 1
                print("  ERR  no se pudo agregar el job de '{}'".format(nombre))

    print("------------------------------------------")
    print("Jobs agregados: {} | Salteados: {} | Errores: {}".format(jobs, salteados, errores))

    if jobs and RENDERIZAR_AL_FINAL:
        resolve.OpenPage("deliver")
        if proyecto.StartRendering():
            print("Render iniciado.")
        else:
            print("No se pudo iniciar el render. Revisa la Render Queue.")
    elif jobs:
        print("Revisa la Render Queue en Deliver y dale Render.")
    print("==========================================")


main()
