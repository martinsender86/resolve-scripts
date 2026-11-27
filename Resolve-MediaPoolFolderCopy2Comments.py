#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Folder2Meta_Sel — DaVinci Resolve
Igual que Folder2Meta, pero trabaja SOLO con los clips seleccionados en el Media Pool.
A cada clip seleccionado le escribe en Comments el nombre de la carpeta
del Media Pool donde esta.

Si no hay nada seleccionado, avisa y no hace nada.

Uso: seleccionar clips en el Media Pool > Workspace > Scripts > Folder2Meta_Sel
Log: Workspace > Console (pestaña Py3)
"""

# ================== CONFIGURACION ==================
CAMPO_METADATA = "Comments"      # Campo destino. "Comments" viaja en el ALE como columna "Comments" (nativa en Avid)
RUTA_COMPLETA = False            # False: "CamA"   |   True: "Dia1 / CamA"
SEPARADOR = " / "                # Separador si RUTA_COMPLETA = True
INCLUIR_ROOT = False             # Con RUTA_COMPLETA, incluir "Master" al principio
SOBRESCRIBIR = True              # False: no toca clips que ya tengan algo en el campo
TIPOS_A_SALTEAR = ("Timeline", "Compound", "Fusion Title", "Generator")
# ===================================================


def get_resolve():
    """Obtiene el objeto Resolve, corra adentro o afuera de la app."""
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
    """El ALE es texto separado por tabs: sacamos tabs y saltos de linea."""
    return " ".join(str(texto).replace("\t", " ").split())


def armar_valor(ruta):
    """ruta = lista de nombres de carpeta desde Master hasta la carpeta del clip."""
    if not RUTA_COMPLETA:
        return limpiar(ruta[-1])
    partes = ruta if (INCLUIR_ROOT or len(ruta) == 1) else ruta[1:]
    return limpiar(SEPARADOR.join(partes))


def es_salteable(clip):
    try:
        tipo = clip.GetClipProperty("Type") or ""
    except Exception:
        tipo = ""
    return any(t.lower() in tipo.lower() for t in TIPOS_A_SALTEAR)


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


def mapa_carpetas(folder, ruta, mapa):
    """mapa[id del clip] = ruta de carpetas donde esta (desde Master)."""
    ruta = ruta + [folder.GetName()]
    for clip in (folder.GetClipList() or []):
        try:
            mapa[clip.GetUniqueId()] = ruta
        except Exception:
            pass
    for sub in (folder.GetSubFolderList() or []):
        mapa_carpetas(sub, ruta, mapa)


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

    print("")
    print("=== Folder2Meta (SELECCION) ===")
    print("Proyecto: {} | Campo: {}".format(proyecto.GetName(), CAMPO_METADATA))

    seleccion = clips_seleccionados(mp)
    if not seleccion:
        print("No hay clips seleccionados en el Media Pool.")
        print("Selecciona los clips y volve a correr el script.")
        return
    print("Clips seleccionados: {}".format(len(seleccion)))
    print("-------------------")

    # La API no dice en que carpeta esta un clip: armamos el mapa recorriendo el Media Pool
    mapa = {}
    mapa_carpetas(mp.GetRootFolder(), [], mapa)

    stats = {"ok": 0, "error": 0, "salteados": 0, "con_dato": 0, "sin_carpeta": 0}
    for clip in seleccion:
        nombre = clip.GetName()
        if es_salteable(clip):
            stats["salteados"] += 1
            continue
        ruta = mapa.get(clip.GetUniqueId())
        if not ruta:
            stats["sin_carpeta"] += 1
            print("  ??   {}  (no encontre su carpeta)".format(nombre))
            continue
        if not SOBRESCRIBIR and (clip.GetMetadata(CAMPO_METADATA) or "").strip():
            stats["con_dato"] += 1
            continue
        valor = armar_valor(ruta)
        if clip.SetMetadata(CAMPO_METADATA, valor):
            stats["ok"] += 1
            print("  OK   {}  ->  {} = '{}'".format(nombre, CAMPO_METADATA, valor))
        else:
            stats["error"] += 1
            print("  ERR  {}  (no se pudo escribir '{}')".format(nombre, CAMPO_METADATA))

    print("-------------------")
    print("Escritos: {ok} | Errores: {error} | Timelines/otros salteados: {salteados} | "
          "Ya tenian dato: {con_dato} | Sin carpeta: {sin_carpeta}".format(**stats))


main()
