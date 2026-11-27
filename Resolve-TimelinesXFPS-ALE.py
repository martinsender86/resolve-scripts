#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FPSTimelinesALE_Sel — DaVinci Resolve
Trabaja SOLO con los clips que tengas seleccionados en el Media Pool.

De esa seleccion toma los clips "Video" y "Video + Audio", omite los repetidos
(si hay mismo nombre con distinta extension, gana .mov sobre .mp4), los agrupa
por frame rate y arma UNA timeline por frame rate (sin mezclar).
Opcional: exporta un ALE por timeline.

Si no hay nada seleccionado, avisa y no hace nada.

Uso: seleccionar clips en el Media Pool > Workspace > Scripts > FPSTimelinesALE_Sel
Log: Workspace > Console (pestaña Py3)
"""

import os
import re
import time

# ================== CONFIGURACION ==================
PREFIJO_TIMELINE = "Clips"                # Nombre: "Clips_23.976fps", "Clips_25fps"...
CARPETA_TIMELINES = "_FPS_Timelines"      # Carpeta del Media Pool donde se crean las timelines
EXPORTAR_ALE = True                       # Exporta un ALE por cada timeline
CARPETA_EXPORT = r"F:\SOLRAC\EXPORTS\ALE Resolve-Avid"
SUBCARPETA_POR_CORRIDA = False            # True: subcarpeta "<proyecto>_<fecha>" por corrida
ORDENAR_POR_NOMBRE = True                 # Ordena los clips por nombre dentro de cada timeline
OMITIR_REPETIDOS = True                   # Si hay clips con el mismo nombre, deja uno solo
PRIORIDAD_EXTENSIONES = [".mov", ".mp4"]  # Ante nombres repetidos, gana la primera extension de la lista
MOSTRAR_OMITIDOS = True                   # Lista en la Console los clips que se omitieron
# ===================================================

TIPOS_VALIDOS = ("video", "video+audio")


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


CONOCIDOS = [23.976, 24.0, 25.0, 29.97, 30.0, 47.952, 48.0, 50.0, 59.94, 60.0, 119.88, 120.0]


def normalizar_fps(valor):
    try:
        f = float(str(valor).replace(",", ".").strip())
    except (TypeError, ValueError):
        return "SinFPS"
    for c in CONOCIDOS:
        if abs(f - c) < 0.01:
            return ("%.3f" % c).rstrip("0").rstrip(".")
    return ("%.3f" % f).rstrip("0").rstrip(".")


def prop(clip, nombre):
    try:
        return clip.GetClipProperty(nombre) or ""
    except Exception:
        return ""


def limpiar_nombre(texto):
    texto = re.sub(r'[\\/:*?"<>|\t\r\n]+', "_", texto).strip(" ._")
    return texto or "SinNombre"


def es_video(clip):
    tipo = str(prop(clip, "Type")).lower().replace(" ", "")
    return tipo in TIPOS_VALIDOS


def clips_seleccionados(mp):
    try:
        sel = mp.GetSelectedClips()
    except Exception:
        return []
    if not sel:
        return []
    if isinstance(sel, dict):
        sel = list(sel.values())
    return [c for c in sel if c and hasattr(c, "GetClipProperty")]


def nombre_y_extension(clip):
    """Devuelve (nombre_base_en_minusculas, extension) usando el nombre de archivo real."""
    archivo = str(prop(clip, "File Name") or "").strip()
    if not archivo:
        ruta = str(prop(clip, "File Path") or "").strip()
        archivo = os.path.basename(ruta) if ruta else clip.GetName()
    base, ext = os.path.splitext(archivo)
    if not ext:  # por si el nombre no trae extension, probamos con el nombre del clip
        base2, ext2 = os.path.splitext(clip.GetName())
        if ext2:
            base, ext = base2, ext2
    return base.strip().lower(), ext.lower()


def rango_extension(ext):
    prioridades = [e.lower() for e in PRIORIDAD_EXTENSIONES]
    return prioridades.index(ext) if ext in prioridades else len(prioridades)


def quitar_repetidos(clips):
    """
    1) Saca el mismo clip seleccionado dos veces (mismo ID o misma ruta de archivo).
    2) Entre clips con el mismo nombre base, deja el de extension con mas prioridad (.mov antes que .mp4).
    Devuelve (clips_que_quedan, lista_de_omitidos_con_motivo).
    """
    omitidos = []

    # 1) Duplicados exactos
    vistos, unicos = set(), []
    for c in clips:
        clave = str(prop(c, "File Path") or "").lower() or (c.GetUniqueId() if hasattr(c, "GetUniqueId") else id(c))
        if clave in vistos:
            omitidos.append((c.GetName(), "repetido (mismo archivo)"))
            continue
        vistos.add(clave)
        unicos.append(c)

    # 2) Mismo nombre, distinta extension
    por_nombre = {}
    orden = []
    for c in unicos:
        base, ext = nombre_y_extension(c)
        if base not in por_nombre:
            por_nombre[base] = []
            orden.append(base)
        por_nombre[base].append((c, ext))

    resultado = []
    for base in orden:
        grupo = por_nombre[base]
        if len(grupo) == 1:
            resultado.append(grupo[0][0])
            continue
        grupo_ordenado = sorted(grupo, key=lambda par: rango_extension(par[1]))
        ganador, ext_ganador = grupo_ordenado[0]
        resultado.append(ganador)
        for c, ext in grupo_ordenado[1:]:
            omitidos.append((c.GetName(), "mismo nombre que '{}' ({} tiene prioridad)".format(
                ganador.GetName(), ext_ganador or "sin extension")))

    return resultado, omitidos


def nombres_timelines(proyecto):
    nombres = set()
    for i in range(1, (proyecto.GetTimelineCount() or 0) + 1):
        tl = proyecto.GetTimelineByIndex(i)
        if tl:
            nombres.add(tl.GetName())
    return nombres


def nombre_unico(base, existentes):
    if base not in existentes:
        return base
    n = 2
    while "{}_{}".format(base, n) in existentes:
        n += 1
    return "{}_{}".format(base, n)


def buscar_o_crear_carpeta(mp, root, nombre):
    for sub in (root.GetSubFolderList() or []):
        if sub.GetName() == nombre:
            return sub
    return mp.AddSubFolder(root, nombre)


def orden_fps(k):
    try:
        return (0, float(k))
    except ValueError:
        return (1, 0.0)


def main():
    resolve = get_resolve()
    if not resolve:
        print("No pude conectarme a Resolve. Correlo desde Workspace > Scripts.")
        return
    proyecto = resolve.GetProjectManager().GetCurrentProject()
    if not proyecto:
        print("No hay proyecto abierto.")
        return

    mp = proyecto.GetMediaPool()
    root = mp.GetRootFolder()
    carpeta_original = mp.GetCurrentFolder()

    print("")
    print("=========== FPS TIMELINES ALE (SELECCION) ===========")
    print("Proyecto: {} | Timeline FPS del proyecto: {}".format(
        proyecto.GetName(), proyecto.GetSetting("timelineFrameRate")))

    # ---------- 1) Leer la seleccion ----------
    seleccion = clips_seleccionados(mp)
    if not seleccion:
        print("No hay clips seleccionados en el Media Pool.")
        print("Selecciona los clips y volve a correr el script.")
        print("=====================================================")
        return

    videos, salteados = [], 0
    for clip in seleccion:
        if es_video(clip):
            videos.append(clip)
        else:
            salteados += 1

    omitidos = []
    if OMITIR_REPETIDOS:
        videos, omitidos = quitar_repetidos(videos)

    grupos = {}
    for clip in videos:
        grupos.setdefault(normalizar_fps(prop(clip, "FPS")), []).append(clip)

    print("Clips seleccionados: {} | Omitidos por repetidos: {}".format(len(seleccion), len(omitidos)))
    if omitidos and MOSTRAR_OMITIDOS:
        print("--- Omitidos ---")
        for nombre, motivo in omitidos:
            print("  -  {}  ->  {}".format(nombre, motivo))
        print("----------------")
    if not grupos:
        print("Ninguno de los seleccionados es Video o Video + Audio.")
        print("=====================================================")
        return

    # ---------- 2) Preparar export ----------
    destino = None
    export_ale = getattr(resolve, "EXPORT_ALE", None)
    export_none = getattr(resolve, "EXPORT_NONE", None)
    if EXPORTAR_ALE:
        if export_ale is None:
            print("Esta version de Resolve no expone EXPORT_ALE: se crean las timelines sin exportar.")
        else:
            destino = CARPETA_EXPORT
            if SUBCARPETA_POR_CORRIDA:
                destino = os.path.join(destino, limpiar_nombre(proyecto.GetName()) + time.strftime("_%Y%m%d_%H%M"))
            if not os.path.isdir(destino):
                os.makedirs(destino)
            print("ALE en: {}".format(destino))
    print("-----------------------------------------------------")

    # ---------- 3) Crear timelines y exportar ----------
    carpeta_tl = buscar_o_crear_carpeta(mp, root, CARPETA_TIMELINES)
    if not carpeta_tl:
        print("No pude crear la carpeta '{}' en el Media Pool.".format(CARPETA_TIMELINES))
        return
    mp.SetCurrentFolder(carpeta_tl)

    existentes = nombres_timelines(proyecto)
    ok_tl, ok_ale, errores = 0, 0, 0

    for fps in sorted(grupos, key=orden_fps):
        clips = grupos[fps]
        if ORDENAR_POR_NOMBRE:
            clips = sorted(clips, key=lambda c: c.GetName().lower())

        nombre_tl = nombre_unico(limpiar_nombre("{}_{}fps".format(PREFIJO_TIMELINE, fps)), existentes)
        tl = mp.CreateTimelineFromClips(nombre_tl, clips)
        if not tl:
            errores += 1
            print("  ERR  {} fps: no se pudo crear la timeline".format(fps))
            continue
        existentes.add(nombre_tl)
        ok_tl += 1
        linea = "  OK   {:>8} fps : {:>5} clips -> timeline '{}'".format(fps, len(clips), nombre_tl)

        if destino:
            archivo = os.path.join(destino, nombre_tl + ".ale")
            if tl.Export(archivo, export_ale, export_none):
                ok_ale += 1
                linea += " -> " + os.path.basename(archivo)
            else:
                errores += 1
                linea += "  (ERR al exportar ALE)"
        print(linea)

    if carpeta_original:
        mp.SetCurrentFolder(carpeta_original)

    print("-----------------------------------------------------")
    print("Timelines: {} | ALE: {} | Errores: {} | Salteados (audio, stills, timelines...): {}".format(
        ok_tl, ok_ale, errores, salteados))
    print("=====================================================")


main()
