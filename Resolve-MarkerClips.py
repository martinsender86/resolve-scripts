#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
listar_clips_marcados.py
------------------------
Recorre todos los timelines del proyecto abierto en DaVinci Resolve, encuentra
los clips que tienen markers y exporta al Escritorio un listado con:
  - nombre del clip
  - ruta completa en el disco
  - si el archivo está online (existe) y su tamaño
  - en qué timelines aparece y qué markers tiene (color, nombre, nota)

No copia ni modifica nada.

Genera dos archivos en el Escritorio:
  clips_marcados_<PROYECTO>_<fecha>.txt   -> para leer
  clips_marcados_<PROYECTO>_<fecha>.csv   -> para abrir en Excel

Dónde va (Windows):
  %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Utility
Se ejecuta desde Workspace > Scripts.
"""

import os
import re
import sys
import csv
import datetime

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Qué markers cuentan:
#   "item"     -> markers puestos sobre los clips en los timelines (recomendado)
#   "source"   -> markers del clip de origen (Media Pool / Source viewer)
#   "timeline" -> markers de la regla del timeline que caen encima del clip
#   "any"      -> cualquiera de los tres
MARKER_MODE = "item"

# Filtrar por color de marker, ej. ["Red", "Green"]. None = todos.
MARKER_COLORS = None

# Timelines a procesar por nombre. None = todos los del proyecto.
TIMELINE_NAMES = None

# Pistas a recorrer.
TRACK_TYPES = ["video", "audio"]

# Además del .txt, exportar un .csv para Excel.
EXPORT_CSV = True

# =============================================================================


def get_resolve():
    try:
        return resolve  # noqa: F821  (existe cuando corre dentro de Resolve)
    except NameError:
        pass
    try:
        import DaVinciResolveScript as dvr
    except ImportError:
        if sys.platform.startswith("win"):
            p = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                             "Blackmagic Design", "DaVinci Resolve", "Support",
                             "Developer", "Scripting", "Modules")
        elif sys.platform == "darwin":
            p = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
        else:
            p = "/opt/resolve/Developer/Scripting/Modules"
        sys.path.append(p)
        import DaVinciResolveScript as dvr
    return dvr.scriptapp("Resolve")


def say(msg=""):
    """print seguro para la consola de Resolve."""
    try:
        print(msg)
    except Exception:
        pass


def desktop_dir():
    """Carpeta real del Escritorio (también si está redirigida a OneDrive)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_DESKTOPDIRECTORY = 0x10
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:
                if os.path.isdir(buf.value):
                    return buf.value
        except Exception:
            pass
    for name in ("Desktop", "Escritorio", os.path.join("OneDrive", "Desktop"),
                 os.path.join("OneDrive", "Escritorio")):
        p = os.path.join(os.path.expanduser("~"), name)
        if os.path.isdir(p):
            return p
    return os.path.expanduser("~")


def safe_filename(s):
    return re.sub(r'[\\/:*?"<>|]+', "_", s).strip() or "proyecto"


def human_size(n):
    if n is None:
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return ("%.0f %s" if unit in ("B", "KB") else "%.2f %s") % (n, unit)
        n /= 1024.0


# -----------------------------------------------------------------------------
# Markers
# -----------------------------------------------------------------------------

def filter_markers(markers):
    if not markers:
        return {}
    if not MARKER_COLORS:
        return markers
    wanted = {c.lower() for c in MARKER_COLORS}
    return {f: m for f, m in markers.items()
            if str(m.get("color", "")).lower() in wanted}


def markers_for_item(item, mpi, tl_markers_abs):
    """Devuelve lista de (origen, info_marker) que hacen calificar al clip."""
    modes = ["item", "source", "timeline"] if MARKER_MODE == "any" else [MARKER_MODE]
    out = []
    if "item" in modes:
        for f, m in sorted(filter_markers(item.GetMarkers()).items()):
            out.append(("clip", m))
    if "source" in modes and mpi is not None:
        for f, m in sorted(filter_markers(mpi.GetMarkers()).items()):
            out.append(("origen", m))
    if "timeline" in modes and tl_markers_abs:
        start, end = item.GetStart(), item.GetEnd()
        for f, m in sorted(tl_markers_abs.items()):
            if start <= f < end:
                out.append(("timeline", m))
    return out


def marker_text(m):
    parts = [str(m.get("color", "") or "")]
    if m.get("name"):
        parts.append('"%s"' % m["name"])
    if m.get("note"):
        parts.append("nota: %s" % m["note"])
    return " ".join(p for p in parts if p)


# -----------------------------------------------------------------------------
# Principal
# -----------------------------------------------------------------------------

def main():
    resolve_app = get_resolve()
    if not resolve_app:
        say("No pude conectarme a Resolve.")
        return
    project = resolve_app.GetProjectManager().GetCurrentProject()
    if not project:
        say("No hay proyecto abierto.")
        return

    proj_name = project.GetName()

    # ruta -> {"name":..., "uses":[(timeline, track, marker_txt)], ...}
    clips = {}
    no_path = []
    per_timeline = []

    for i in range(1, project.GetTimelineCount() + 1):
        tl = project.GetTimelineByIndex(i)
        if not tl:
            continue
        tl_name = tl.GetName()
        if TIMELINE_NAMES and tl_name not in TIMELINE_NAMES:
            continue

        tl_markers_abs = {}
        if MARKER_MODE in ("timeline", "any"):
            st = tl.GetStartFrame()
            tl_markers_abs = {st + int(f): m for f, m in filter_markers(tl.GetMarkers()).items()}

        count = 0
        for ttype in TRACK_TYPES:
            for t in range(1, tl.GetTrackCount(ttype) + 1):
                track_label = "%s%d" % ("V" if ttype == "video" else "A", t)
                for item in tl.GetItemListInTrack(ttype, t) or []:
                    mpi = item.GetMediaPoolItem()
                    found = markers_for_item(item, mpi, tl_markers_abs)
                    if not found:
                        continue
                    count += 1
                    mk = " | ".join("%s%s" % ("" if src == "clip" else "[%s] " % src, marker_text(m))
                                    for src, m in found)
                    path = mpi.GetClipProperty("File Path") if mpi else None
                    if not path:
                        no_path.append((tl_name, track_label, item.GetName(), mk))
                        continue
                    c = clips.setdefault(path, {
                        "name": (mpi.GetName() if mpi else "") or os.path.basename(path),
                        "uses": [],
                    })
                    c["uses"].append((tl_name, track_label, mk))
        per_timeline.append((tl_name, count))

    # Estado en disco
    online = offline = 0
    total_bytes = 0
    for path, c in clips.items():
        if os.path.isfile(path):
            c["exists"] = True
            c["size"] = os.path.getsize(path)
            total_bytes += c["size"]
            online += 1
        else:
            c["exists"] = False
            c["size"] = None
            offline += 1

    # Ordenar por disco y carpeta
    ordered = sorted(clips.items(), key=lambda kv: kv[0].lower())

    # ---------------------------------------------------------------- TXT
    now = datetime.datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    base = "clips_marcados_%s_%s" % (safe_filename(proj_name), stamp)
    out_dir = desktop_dir()
    txt_path = os.path.join(out_dir, base + ".txt")

    L = []
    L.append("CLIPS MARCADOS - %s" % proj_name)
    L.append("Generado: %s" % now.strftime("%d/%m/%Y %H:%M"))
    L.append("Markers: %s | Colores: %s" % (MARKER_MODE, MARKER_COLORS or "todos"))
    L.append("=" * 78)
    L.append("")
    L.append("TIMELINES")
    for n, c in per_timeline:
        L.append("   %-50s %3d clips con marker" % (n, c))
    L.append("")
    L.append("RESUMEN")
    L.append("   Archivos únicos: %d   (online: %d | offline: %d)" % (len(clips), online, offline))
    L.append("   Volumen total online: %s" % human_size(total_bytes))
    L.append("")
    L.append("=" * 78)

    current_dir = None
    for path, c in ordered:
        d = os.path.dirname(path)
        if d != current_dir:
            current_dir = d
            L.append("")
            L.append("[%s]" % d)
        status = human_size(c["size"]) if c["exists"] else "*** OFFLINE / NO ENCONTRADO ***"
        L.append("   %s   (%s)" % (os.path.basename(path), status))
        L.append("      Ruta: %s" % path)
        for tl_name, track, mk in c["uses"]:
            L.append("      - %s / %s  ->  %s" % (tl_name, track, mk))

    if no_path:
        L.append("")
        L.append("=" * 78)
        L.append("CON MARKER PERO SIN ARCHIVO ASOCIADO (compound, multicam, títulos, generadores)")
        for tl_name, track, name, mk in no_path:
            L.append("   - %s / %s / %s  ->  %s" % (tl_name, track, name, mk))

    L.append("")
    L.append("SOLO RUTAS (para copiar y pegar):")
    for path, _ in ordered:
        L.append(path)

    try:
        with open(txt_path, "w", encoding="utf-8-sig") as fh:
            fh.write("\r\n".join(L) if sys.platform.startswith("win") else "\n".join(L))
        say("Listado guardado en: %s" % txt_path)
    except Exception as e:
        say("No pude guardar el .txt: %s" % e)
        for line in L:
            say(line)

    # ---------------------------------------------------------------- CSV
    if EXPORT_CSV:
        csv_path = os.path.join(out_dir, base + ".csv")
        try:
            # utf-8-sig + ';' para que Excel en español lo abra bien de un clic
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
                w = csv.writer(fh, delimiter=";")
                w.writerow(["Clip", "Carpeta", "Ruta completa", "Disco", "Estado",
                            "Tamaño (MB)", "Timeline", "Pista", "Markers"])
                for path, c in ordered:
                    drive = os.path.splitdrive(path)[0]
                    if not drive and path.startswith("/Volumes/"):
                        drive = "/".join(path.split("/")[:3])
                    for tl_name, track, mk in c["uses"]:
                        w.writerow([os.path.basename(path), os.path.dirname(path), path, drive,
                                    "online" if c["exists"] else "OFFLINE",
                                    ("%.1f" % (c["size"] / 1048576.0)).replace(".", ",") if c["size"] is not None else "",
                                    tl_name, track, mk])
            say("CSV guardado en:     %s" % csv_path)
        except Exception as e:
            say("No pude guardar el .csv: %s" % e)

    say("")
    say("%d archivos únicos | online: %d | offline: %d | %s"
        % (len(clips), online, offline, human_size(total_bytes)))


main()
