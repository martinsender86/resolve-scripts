#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FPSReport — DaVinci Resolve
Cuenta cuantos clips del Media Pool hay en cada frame rate (25, 23.976, etc.).
Es de SOLO LECTURA: no modifica nada del proyecto.

Uso: Workspace > Scripts > FPSReport
Resultado: Workspace > Console (pestaña Py3)
"""

# ================== CONFIGURACION ==================
SOLO_CARPETA_ACTUAL = False   # True: analiza solo la carpeta abierta y sus subcarpetas
DETALLE_POR_CARPETA = True    # Muestra el conteo de cada carpeta
LISTAR_CLIPS = False          # True: lista el nombre de cada clip bajo su frame rate
INCLUIR_SOLO_AUDIO = False    # Los clips de solo audio no tienen frame rate real; por defecto se excluyen
TIPOS_A_SALTEAR = ("Timeline", "Compound", "Fusion", "Generator", "Title", "Multicam")
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


# Frame rates conocidos, para agrupar variantes como 23.98 / 23.976 / 23.976023
CONOCIDOS = [23.976, 24.0, 25.0, 29.97, 30.0, 47.952, 48.0, 50.0, 59.94, 60.0, 119.88, 120.0]


def normalizar_fps(valor):
    try:
        f = float(str(valor).replace(",", ".").strip())
    except (TypeError, ValueError):
        return "Sin dato"
    for c in CONOCIDOS:
        if abs(f - c) < 0.01:
            return ("%.3f" % c).rstrip("0").rstrip(".")
    return ("%.3f" % f).rstrip("0").rstrip(".")


def prop(clip, nombre):
    try:
        return clip.GetClipProperty(nombre) or ""
    except Exception:
        return ""


def recorrer(folder, ruta, datos):
    ruta = ruta + [folder.GetName()]
    nombre_carpeta = " / ".join(ruta)

    for clip in (folder.GetClipList() or []):
        tipo = str(prop(clip, "Type"))
        if any(t.lower() in tipo.lower() for t in TIPOS_A_SALTEAR):
            datos["salteados"] += 1
            continue
        es_solo_audio = tipo.strip().lower() == "audio"
        if es_solo_audio and not INCLUIR_SOLO_AUDIO:
            datos["solo_audio"] += 1
            continue

        fps = normalizar_fps(prop(clip, "FPS"))
        datos["total"].setdefault(fps, []).append(clip.GetName())
        datos["carpetas"].setdefault(nombre_carpeta, {})
        datos["carpetas"][nombre_carpeta][fps] = datos["carpetas"][nombre_carpeta].get(fps, 0) + 1

    for sub in (folder.GetSubFolderList() or []):
        recorrer(sub, ruta, datos)


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
    inicio = mp.GetCurrentFolder() if SOLO_CARPETA_ACTUAL else mp.GetRootFolder()

    datos = {"total": {}, "carpetas": {}, "salteados": 0, "solo_audio": 0}
    recorrer(inicio, [], datos)

    total_clips = sum(len(v) for v in datos["total"].values())

    print("")
    print("=========== FPS REPORT ===========")
    print("Proyecto: {}".format(proyecto.GetName()))
    print("Timeline FPS del proyecto: {}".format(proyecto.GetSetting("timelineFrameRate")))
    print("Analizado desde: {}".format(inicio.GetName()))
    print("----------------------------------")
    for fps in sorted(datos["total"], key=orden_fps):
        print("  {:>8} fps : {:>5} clips".format(fps, len(datos["total"][fps])))
    print("----------------------------------")
    print("  TOTAL      : {:>5} clips".format(total_clips))
    print("  (Salteados: {} timelines/compounds/etc. | {} clips de solo audio)".format(
        datos["salteados"], datos["solo_audio"]))

    if DETALLE_POR_CARPETA and datos["carpetas"]:
        print("")
        print("--------- POR CARPETA ---------")
        for carpeta in sorted(datos["carpetas"]):
            conteo = datos["carpetas"][carpeta]
            detalle = " | ".join("{} fps: {}".format(f, conteo[f]) for f in sorted(conteo, key=orden_fps))
            marca = "  <-- MEZCLA" if len(conteo) > 1 else ""
            print("  {}  ->  {}{}".format(carpeta, detalle, marca))

    if LISTAR_CLIPS:
        print("")
        print("--------- CLIPS ---------")
        for fps in sorted(datos["total"], key=orden_fps):
            print("[{} fps]".format(fps))
            for nombre in sorted(datos["total"][fps]):
                print("    " + nombre)

    print("==================================")


main()
