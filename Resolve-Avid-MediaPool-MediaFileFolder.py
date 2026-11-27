#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mapa Media Pool (DaVinci Resolve)  <->  Avid MediaFiles/MXF

Recorre todos los bines del proyecto abierto en Resolve, lista los clips
.MP4 con su metadata de frame rate y busca en qué carpeta de
Avid MediaFiles/MXF hay un .mxf con el mismo nombre
(C0001.MP4 -> C0001.mxf / C0001_A1.mxf / C0001_A2.mxf = un solo clip).

Genera dos CSV (separador ;, se abren directo en Excel en español):
  - mapa_clips_resolve_avid.csv    -> una fila por clip
  - resumen_bines_resolve_avid.csv -> una fila por bin con su carpeta Avid

Cómo correrlo:
  Copiar este archivo a la carpeta de scripts de Resolve:
    Win: %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Utility\\
    Mac: ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/
  Con el proyecto abierto: Workspace > Scripts > Utility > mapa_mediapool_avid
  (necesita Python 3 instalado en la máquina)
"""

import os
import re
import csv
from collections import defaultdict, Counter

# ================== CONFIGURAR ==================
AVID_MXF_ROOT = r"F:\Avid MediaFiles\MXF"        # pegar acá la ruta real a la carpeta MXF
OUTPUT_DIR    = os.path.join(os.path.expanduser("~"), "Desktop")
SOLO_MP4      = True    # True: solo clips .MP4 del Media Pool. False: todos los clips con archivo
DELIM         = ";"
# ================================================

# Pistas de Avid: C0001_A1.mxf, C0001_A2.mxf, C0001_V1.mxf -> C0001
TRACK_SUFFIX = re.compile(r"_[VAD]\d{1,2}$", re.I)
# Por si aparece el formato largo de Avid: C0001.V1A3F9C2.mxf -> C0001
AVID_HASH    = re.compile(r"\.[VAD]\d{1,2}[0-9A-Za-z_]*$")

# Campos de metadata que se consideran "frame rate"
FPS_PATTERN  = re.compile(r"fps|frame\s*rate|framerate", re.I)


def get_resolve():
    try:
        return resolve  # noqa: F821  (existe al correr desde el menú Scripts / consola)
    except NameError:
        import DaVinciResolveScript as dvr
        return dvr.scriptapp("Resolve")


def key_mediapool(name):
    """C0001.MP4 -> c0001"""
    return os.path.splitext(name)[0].strip().lower()


def key_mxf(filename):
    """C0001.mxf / C0001_A1.mxf / C0001_A2.mxf -> c0001"""
    base = os.path.splitext(filename)[0]
    base = AVID_HASH.sub("", base)
    base = TRACK_SUFFIX.sub("", base)
    return base.strip().lower()


def scan_avid(root):
    """Devuelve {nombre_base: {carpetas}} para todos los .mxf bajo root."""
    index = defaultdict(set)
    total = 0
    for dirpath, _, files in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        if rel == ".":
            continue
        folder = rel.split(os.sep)[0]          # ej. "20251109"
        for f in files:
            if f.lower().endswith(".mxf"):
                index[key_mxf(f)].add(folder)
                total += 1
    return index, total


def walk_bins(folder, parent, out):
    here = f"{parent}/{folder.GetName()}" if parent else folder.GetName()
    for clip in (folder.GetClipList() or []):
        out.append((here, clip))
    for sub in (folder.GetSubFolderList() or []):
        walk_bins(sub, here, out)


def fps_fields(clip, props):
    """Todos los campos de frame rate: propiedades del clip + metadata."""
    found = {}
    for k, v in props.items():
        if FPS_PATTERN.search(k) and str(v).strip():
            found[k] = str(v)
    try:
        meta = clip.GetMetadata() or {}
    except Exception:
        meta = {}
    for k, v in meta.items():
        if FPS_PATTERN.search(k) and str(v).strip():
            found.setdefault(k, str(v))
    # coma decimal para que Excel en español no lea 23.976 como 23976
    return {k: v.replace(".", ",") for k, v in found.items()}


def main():
    if not os.path.isdir(AVID_MXF_ROOT):
        print(f"ERROR: no encuentro la carpeta {AVID_MXF_ROOT}")
        return

    r = get_resolve()
    project = r.GetProjectManager().GetCurrentProject()
    if not project:
        print("ERROR: no hay proyecto abierto en Resolve")
        return

    print("Escaneando MXF...")
    index, total_mxf = scan_avid(AVID_MXF_ROOT)
    n_folders = len(set(f for s in index.values() for f in s))
    print(f"  {total_mxf} archivos .mxf = {len(index)} clips en {n_folders} carpetas")

    clips = []
    walk_bins(project.GetMediaPool().GetRootFolder(), "", clips)

    rows = []            # (bin, clip, {fps}, carpetas)
    fps_cols = []        # columnas de frame rate encontradas, en orden de aparición
    summary = defaultdict(lambda: {"clips": 0, "match": 0, "folders": Counter(),
                                   "fps": set(), "sin": []})

    for bin_path, clip in clips:
        props = clip.GetClipProperty() or {}
        if not props.get("File Path", ""):
            continue                                  # timelines, compounds, generadores
        name = clip.GetName()
        if SOLO_MP4 and not name.lower().endswith(".mp4"):
            continue

        fps = fps_fields(clip, props)
        for k in fps:
            if k not in fps_cols:
                fps_cols.append(k)

        folders = sorted(index.get(key_mediapool(name), set()))
        rows.append((bin_path, name, fps, folders))

        s = summary[bin_path]
        s["clips"] += 1
        main_fps = fps.get("FPS") or next(iter(fps.values()), "")
        if main_fps:
            s["fps"].add(main_fps)
        if folders:
            s["match"] += 1
            for f in folders:
                s["folders"][f] += 1
        else:
            s["sin"].append(name)

    # "FPS" primero si existe
    if "FPS" in fps_cols:
        fps_cols.remove("FPS")
        fps_cols.insert(0, "FPS")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    p1 = os.path.join(OUTPUT_DIR, "mapa_clips_resolve_avid.csv")
    with open(p1, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=DELIM)
        w.writerow(["Bin Media Pool", "Clip"] + fps_cols + ["Carpeta Avid MXF"])
        for bin_path, name, fps, folders in sorted(rows, key=lambda x: (x[0], x[1])):
            w.writerow([bin_path, name]
                       + [fps.get(c, "") for c in fps_cols]
                       + [" | ".join(folders) if folders else "NO ENCONTRADO"])

    p2 = os.path.join(OUTPUT_DIR, "resumen_bines_resolve_avid.csv")
    with open(p2, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=DELIM)
        w.writerow(["Bin Media Pool", "Carpeta Avid MXF", "Clips en bin", "Clips encontrados",
                    "Otras carpetas (clips)", "FPS", "Clips no encontrados"])
        for b in sorted(summary):
            s = summary[b]
            top = s["folders"].most_common()
            principal = top[0][0] if top else "NO ENCONTRADO"
            otras = " | ".join(f"{f} ({n})" for f, n in top[1:])
            w.writerow([b, principal, s["clips"], s["match"], otras,
                        " | ".join(sorted(s["fps"])), " | ".join(s["sin"])])

    print(f"Listo: {len(rows)} clips en {len(summary)} bines")
    print(f"  Columnas de frame rate: {', '.join(fps_cols) or '(ninguna)'}")
    print(f"  {p1}")
    print(f"  {p2}")


main()
