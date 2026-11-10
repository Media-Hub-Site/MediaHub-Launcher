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

# Registro de micro-apps con soporte bilingüe (Español / English)
APP_REGISTRY = {
    "media": {
        "name_es":        "Convertidor Multimedia",
        "name_en":        "Multimedia Converter",
        "name":           "Convertidor Multimedia",
        "description_es": "Video, Audio e Imagen con 9 herramientas profesionales integradas (Corte, GIF, Compresión, Fusión).",
        "description_en": "Video, Audio and Image with 9 integrated professional tools (Cut, GIF, Compression, Merge).",
        "description":    "Video, Audio e Imagen con 9 herramientas profesionales integradas (Corte, GIF, Compresión, Fusión).",
        "repo":           f"{ORG_NAME}/MediaHub-MultimediaConverter",
        "exe":            "MediaHub-MultimediaConverter.exe",
        "dir":            "MediaHub-MultimediaConverter",
        "icon":           "media.png",
        "badge_es":       "9 EN 1",
        "badge_en":       "9 IN 1",
        "badge":          "9 EN 1",
        "is_hero":        True,
    },
    "docs": {
        "name_es":        "Convertidor de Documentos",
        "name_en":        "Document Converter",
        "name":           "Convertidor de Documentos",
        "description_es": "Conversión inteligente entre PDF, Word, Excel, PowerPoint e imágenes a 300 DPI.",
        "description_en": "Intelligent conversion between PDF, Word, Excel, PowerPoint and images at 300 DPI.",
        "description":    "Conversión inteligente entre PDF, Word, Excel, PowerPoint e imágenes a 300 DPI.",
        "repo":           f"{ORG_NAME}/MediaHub-DocumentConverter",
        "exe":            "MediaHub-DocumentConverter.exe",
        "dir":            "MediaHub-DocumentConverter",
        "icon":           "docs.png",
        "badge_es":       "OFICINA",
        "badge_en":       "OFFICE",
        "badge":          "OFICINA",
    },
    "link": {
        "name_es":        "Convertidor de Links",
        "name_en":        "Link Converter",
        "name":           "Convertidor de Links",
        "description_es": "Descarga por lotes desde YouTube, TikTok, Instagram y playlists con soporte paralelo.",
        "description_en": "Batch downloader from YouTube, TikTok, Instagram and playlists with parallel support.",
        "description":    "Descarga por lotes desde YouTube, TikTok, Instagram y playlists con soporte paralelo.",
        "repo":           f"{ORG_NAME}/MediaHub-LinkConverter",
        "exe":            "MediaHub-LinkConverter.exe",
        "dir":            "MediaHub-LinkConverter",
        "icon":           "link_converter.webp",
        "badge_es":       "BATCH",
        "badge_en":       "BATCH",
        "badge":          "BATCH",
    },
    "image_tools": {
        "name_es":        "Herramientas de Imagen",
        "name_en":        "Image Tools",
        "name":           "Herramientas de Imagen",
        "description_es": "Borrador de fondos, escalador y marca de agua en lote para tus fotografías.",
        "description_en": "Background remover, AI upscaler and batch watermarking for your photos.",
        "description":    "Borrador de fondos, escalador y marca de agua en lote para tus fotografías.",
        "repo":           f"{ORG_NAME}/MediaHub-ImageTools",
        "exe":            "MediaHub-ImageTools.exe",
        "dir":            "MediaHub-ImageTools",
        "icon":           "quality.webp",
        "badge_es":       "CREATIVO",
        "badge_en":       "CREATIVE",
        "badge":          "CREATIVO",
    },
    "subtitle": {
        "name_es":        "Generador de Subtítulos",
        "name_en":        "Subtitle Generator",
        "name":           "Generador de Subtítulos",
        "description_es": "Transcripción y generación automática de subtítulos con Whisper AI de forma local.",
        "description_en": "Automatic subtitle transcription and burning with Whisper AI locally.",
        "description":    "Transcripción y generación automática de subtítulos con Whisper AI de forma local.",
        "repo":           f"{ORG_NAME}/MediaHub-SubtitleGenerator",
        "exe":            "MediaHub-SubtitleGenerator.exe",
        "dir":            "MediaHub-SubtitleGenerator",
        "icon":           "subtitle.png",
        "badge_es":       "IA LOCAL",
        "badge_en":       "LOCAL AI",
        "badge":          "IA LOCAL",
    },
    # ── Casillas de Escalabilidad Futura (Próximamente) ───────────────
    "budget_manager": {
        "name_es":        "Gestor Presupuestario",
        "name_en":        "Budget Manager",
        "name":           "Gestor Presupuestario",
        "description_es": "Gestión financiera, seguimiento de gastos, presupuestos y balance en tiempo real.",
        "description_en": "Financial management, expense tracking, budgets and real-time cash balance.",
        "description":    "Gestión financiera, seguimiento de gastos, presupuestos y balance en tiempo real.",
        "repo":           None,
        "exe":            None,
        "dir":            None,
        "icon":           "proximamente.png",
        "badge_es":       "PRÓXIMAMENTE",
        "badge_en":       "COMING SOON",
        "badge":          "PRÓXIMAMENTE",
        "is_disabled":    True,
    },
    "chile_planos": {
        "name_es":        "ChilePlanos",
        "name_en":        "ChilePlanos",
        "name":           "ChilePlanos",
        "description_es": "Hub de planimetría técnica y arquitectura para estudiantes y profesionales.",
        "description_en": "Technical planimetry and architectural hub for students and professionals.",
        "description":    "Hub de planimetría técnica y arquitectura para estudiantes y profesionales.",
        "repo":           None,
        "exe":            None,
        "dir":            None,
        "icon":           "chileplanos.png",
        "badge_es":       "PRÓXIMAMENTE",
        "badge_en":       "COMING SOON",
        "badge":          "PRÓXIMAMENTE",
        "is_disabled":    True,
    },
    "streamer_hub": {
        "name_es":        "StreamerHub",
        "name_en":        "StreamerHub",
        "name":           "StreamerHub",
        "description_es": "Suite integral de herramientas y utilidades para creadores de contenido y streaming.",
        "description_en": "Comprehensive toolset and utilities for content creators and live streamers.",
        "description":    "Suite integral de herramientas y utilidades para creadores de contenido y streaming.",
        "repo":           None,
        "exe":            None,
        "dir":            None,
        "icon":           "proximamente.png",
        "badge_es":       "PRÓXIMAMENTE",
        "badge_en":       "COMING SOON",
        "badge":          "PRÓXIMAMENTE",
        "is_disabled":    True,
    },
}


def get_app_metadata(app_id: str, lang: str = "es") -> dict:
    """Devuelve los metadatos de una aplicación traducidos al idioma solicitado."""
    reg = APP_REGISTRY.get(app_id)
    if not reg:
        return {}
    meta = dict(reg)
    meta["name"] = reg.get(f"name_{lang}", reg.get("name", app_id))
    meta["description"] = reg.get(f"description_{lang}", reg.get("description", ""))
    meta["badge"] = reg.get(f"badge_{lang}", reg.get("badge", ""))
    return meta
