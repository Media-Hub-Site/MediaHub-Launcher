"""
core/config.py
──────────────
Configuración global del Launcher y registro de micro-aplicaciones.
La versión del launcher se resuelve dinámicamente con get_launcher_version().
"""

import os
import json
import sys

GITHUB_REPO = "Media-Hub-Site/MediaHub-Launcher"
ORG_NAME = "Media-Hub-Site"

# Fallback si aún no existe archivo de versión local ni conexión
DEFAULT_LAUNCHER_VERSION = "v1.0.0"

def get_launcher_data_dir() -> str:
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    path = os.path.join(home, ".mediahub")
    os.makedirs(path, exist_ok=True)
    return path

def get_launcher_version_file() -> str:
    return os.path.join(get_launcher_data_dir(), "launcher_version.json")

def get_launcher_version() -> str:
    """
    Obtiene la versión actual del launcher.
    Prioridad:
    1. Archivo local de instalación empaquetado (version.json junto al exe o root).
    2. Archivo persistido de usuario (~/.mediahub/launcher_version.json).
    3. DEFAULT_LAUNCHER_VERSION (ej. v1.0.0).
    """
    # 1. Comprobar version.json empaquetado con el ejecutable/código
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    bundled_file = os.path.join(base_dir, "version.json")
    if os.path.isfile(bundled_file):
        try:
            with open(bundled_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                v = data.get("version")
                if v:
                    return f"v{v.lstrip('v')}"
        except Exception:
            pass

    # 2. Comprobar archivo de versión del perfil del usuario
    user_file = get_launcher_version_file()
    if os.path.isfile(user_file):
        try:
            with open(user_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                v = data.get("version")
                if v:
                    return f"v{v.lstrip('v')}"
        except Exception:
            pass

    return DEFAULT_LAUNCHER_VERSION

def save_launcher_version(version: str):
    """Persiste la versión actual del launcher."""
    user_file = get_launcher_version_file()
    try:
        clean_v = version.lstrip("v")
        with open(user_file, "w", encoding="utf-8") as f:
            json.dump({"version": clean_v}, f, indent=2)
    except Exception as e:
        print(f"Error guardando version del launcher: {e}")


# Constante compatible hacia atrás
APP_VERSION = get_launcher_version()

# Registro de micro-apps: id → metadatos usados por el Launcher
APP_REGISTRY = {
    "media": {
        "name":    "Multimedia Converter",
        "repo":    f"{ORG_NAME}/MediaHub-MultimediaConverter",
        "exe":     "MediaHub-MultimediaConverter.exe",
        "dir":     "MediaHub-MultimediaConverter",
    },
    "docs": {
        "name":    "Document Converter",
        "repo":    f"{ORG_NAME}/MediaHub-DocumentConverter",
        "exe":     "MediaHub-DocumentConverter.exe",
        "dir":     "MediaHub-DocumentConverter",
    },
    "image_tools": {
        "name":    "Image Tools",
        "repo":    f"{ORG_NAME}/MediaHub-ImageTools",
        "exe":     "MediaHub-ImageTools.exe",
        "dir":     "MediaHub-ImageTools",
    },
    "link": {
        "name":    "Link Converter",
        "repo":    f"{ORG_NAME}/MediaHub-LinkConverter",
        "exe":     "MediaHub-LinkConverter.exe",
        "dir":     "MediaHub-LinkConverter",
    },
    "subtitle": {
        "name":    "Subtitle Generator",
        "repo":    f"{ORG_NAME}/MediaHub-SubtitleGenerator",
        "exe":     "MediaHub-SubtitleGenerator.exe",
        "dir":     "MediaHub-SubtitleGenerator",
    },
}
