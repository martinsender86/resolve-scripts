# Scripts para DaVinci Resolve

Colección de scripts de Python para **DaVinci Resolve** (Windows y Mac).

## Instalación

Copiá el `.py` a la carpeta de scripts de Resolve:
- **Windows:** `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\`
- **Mac:** `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/`

Con el proyecto abierto: **Workspace > Scripts > (nombre del script)**. Los mensajes salen en Workspace > Console (pestaña Py3). Cada script tiene arriba un bloque **CONFIGURACIÓN** para ajustar.

## Scripts

| Script | Qué hace | ¿Modifica el proyecto? |
|---|---|---|
| `Resolve-FPSReport.py` | Cuenta cuántos clips del Media Pool hay en cada frame rate (25, 23.976…), con detalle por carpeta. | No, solo lee |
| `Resolve-MediaPoolFolderCopy2Comments.py` | A los clips **seleccionados** del Media Pool les escribe en *Comments* el nombre de su carpeta (viaja al ALE como columna nativa de Avid). | Sí, metadata |
| `Resolve-TimelinesXFPS-ALE.py` | De los clips seleccionados, arma **una timeline por frame rate** (sin repetidos; gana `.mov` sobre `.mp4`) y opcionalmente exporta un ALE por timeline. | Crea timelines |
| `Resolve-RenderXMediaPoolFolderName.py` | Arma un render job por clip de la timeline, guardando cada render en una subcarpeta con el nombre de su carpeta del Media Pool. Usa el formato configurado en Deliver. | Agrega jobs |
| `Render Clip por Clip/render_clip_por_clip.py` | Exporta la timeline **clip por clip**, un job por clip. Si un clip falla (frame corrupto, media offline), lo anota y sigue. Deja un log CSV. | Agrega jobs |
| `Resolve-MarkerClips.py` | Lista los clips con markers de todas las timelines: ruta, si está online, tamaño, en qué timelines aparece y qué markers tiene. Exporta `.txt` y `.csv` al Escritorio. | No, solo lee |
| `Resolve-Avid-MediaPool-MediaFileFolder.py` | Cruza los clips del Media Pool con `Avid MediaFiles/MXF` y dice en qué carpeta MXF está cada uno. Genera dos CSV para Excel. | No, solo lee |

Algunos scripts tienen rutas por defecto (`F:\...`) en la configuración: cambialas por las tuyas.

Hay un instructivo de *Render Clip por Clip* en `docs/`.
