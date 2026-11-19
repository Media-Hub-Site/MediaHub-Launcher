"""
core/config.py
──────────────
Configuración global del Launcher, categorías de secciones y catálogo dinámico de micro-aplicaciones.
Soporta sincronización en vivo con `catalog.json` remoto en GitHub (gestionable desde el Panel Web
en GitHub Pages), caché local offline en `~/.mediahub/catalog_cache.json` y descarga dinámica de iconos.
"""

import os
import json
import sys
import time
import hashlib
import requests

GITHUB_REPO = "Media-Hub-Site/MediaHub-Launcher"
ORG_NAME = "Media-Hub-Site"

CATALOG_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/catalog.json?ref=main"
CATALOG_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/catalog.json"
ADMIN_PANEL_URL = f"https://media-hub-site.github.io/MediaHub-Launcher/"

# Fallback si aún no existe archivo de versión local ni conexión
DEFAULT_LAUNCHER_VERSION = "v1.6.0"


def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_launcher_data_dir() -> str:
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    path = os.path.join(home, ".mediahub")
    os.makedirs(path, exist_ok=True)
    return path


def get_cached_catalog_file() -> str:
    return os.path.join(get_launcher_data_dir(), "catalog_cache.json")


def get_cached_icons_dir() -> str:
    path = os.path.join(get_launcher_data_dir(), "cache", "icons")
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
    3. DEFAULT_LAUNCHER_VERSION (ej. v1.6.0).
    """
    bundled_file = os.path.join(get_base_dir(), "version.json")
    if os.path.isfile(bundled_file):
        try:
            with open(bundled_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                v = data.get("version")
                if v:
                    return f"v{v.lstrip('v')}"
        except Exception:
            pass

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

# Definición base de Secciones / Categorías del Sidebar (Issue #53)
SECTION_CATEGORIES = {
    "all": {
        "icon": "✦",
        "name_es": "Explorar Todo",
        "name_en": "Explore All",
        "desc_es": "Todas las aplicaciones organizadas por secciones dentro del ecosistema Media Hub.",
        "desc_en": "All applications organized by sections across the Media Hub ecosystem.",
    },
    "tools": {
        "icon": "🛠️",
        "name_es": "Herramientas",
        "name_en": "Tools",
        "desc_es": "Conversión multimedia, documentos, enlaces, imágenes, subtítulos IA y personalización tipográfica.",
        "desc_en": "Multimedia conversion, documents, links, images, AI subtitles and custom typography.",
    },
    "studio": {
        "icon": "🎙️",
        "name_es": "Estudio & Creadores",
        "name_en": "Creator Studio",
        "desc_es": "Herramientas avanzadas de streaming, alertas con voces IA, síntesis sonora y conservatorio musical interactivo.",
        "desc_en": "Advanced streaming tools, AI voice alerts, mathematical sound synthesis and interactive music conservatory.",
    },
    "admin": {
        "icon": "📊",
        "name_es": "Administración",
        "name_en": "Management",
        "desc_es": "Finanzas personales, planimetría técnica para construcción, inventario y defensa de ciberseguridad.",
        "desc_en": "Personal finance, technical architectural blueprints, inventory and Blue Team cybersecurity.",
    },
    "games": {
        "icon": "🎮",
        "name_es": "Juegos",
        "name_en": "Games",
        "desc_es": "Colección de mini-juegos livianos para entretenimiento inmediato.",
        "desc_en": "Collection of lightweight mini-games for instant entertainment.",
    },
    "installed": {
        "icon": "✓",
        "name_es": "Instaladas",
        "name_en": "Installed",
        "desc_es": "Aplicaciones descargadas y listas para abrir en este equipo.",
        "desc_en": "Applications currently installed and ready to launch on this PC.",
    },
}

# Respaldo local (Offline Fallback) si aún no hay catalog.json ni conexión
DEFAULT_APP_REGISTRY = {
    "media": {
        "name_es":        "Convertidor Multimedia",
        "name_en":        "Multimedia Converter",
        "name":           "Convertidor Multimedia",
        "description_es": "Video, Audio e Imagen con 9 herramientas profesionales integradas (Corte, GIF, Compresión, Fusión).",
        "description_en": "Video, Audio and Image with 9 integrated professional tools (Cut, GIF, Compression, Merge).",
        "description":    "Video, Audio e Imagen con 9 herramientas profesionales integradas (Corte, GIF, Compresión, Fusión).",
        "repo":           f"{ORG_NAME}/MultimediaConverter",
        "exe":            "MediaHub-MultimediaConverter.exe",
        "dir":            "MediaHub-MultimediaConverter",
        "icon":           "media.png",
        "badge_es":       "9 EN 1",
        "badge_en":       "9 IN 1",
        "badge":          "9 EN 1",
        "category":       "tools",
        "is_hero":        True,
    },
    "image_tools": {
        "name_es":        "Herramientas de Imagen",
        "name_en":        "Image Tools",
        "name":           "Herramientas de Imagen",
        "description_es": "Borrador de fondos, escalador y marca de agua en lote para tus fotografías.",
        "description_en": "Background remover, AI upscaler and batch watermarking for your photos.",
        "description":    "Borrador de fondos, escalador y marca de agua en lote para tus fotografías.",
        "repo":           f"{ORG_NAME}/ImageTools",
        "exe":            "MediaHub-ImageTools.exe",
        "dir":            "MediaHub-ImageTools",
        "icon":           "quality.webp",
        "badge_es":       "CREATIVO",
        "badge_en":       "CREATIVE",
        "badge":          "CREATIVO",
        "category":       "tools",
    },
    "subtitle": {
        "name_es":        "Generador de Subtítulos",
        "name_en":        "Subtitle Generator",
        "name":           "Generador de Subtítulos",
        "description_es": "Transcripción y generación automática de subtítulos con Whisper AI de forma local.",
        "description_en": "Automatic subtitle transcription and burning with Whisper AI locally.",
        "description":    "Transcripción y generación automática de subtítulos con Whisper AI de forma local.",
        "repo":           f"{ORG_NAME}/SubtitleGenerator",
        "exe":            "MediaHub-SubtitleGenerator.exe",
        "dir":            "MediaHub-SubtitleGenerator",
        "icon":           "subtitle.png",
        "badge_es":       "IA LOCAL",
        "badge_en":       "LOCAL AI",
        "badge":          "IA LOCAL",
        "category":       "tools",
    },
    "docs": {
        "name_es":        "Convertidor de Documentos",
        "name_en":        "Document Converter",
        "name":           "Convertidor de Documentos",
        "description_es": "Conversión inteligente entre PDF, Word, Excel, PowerPoint e imágenes a 300 DPI.",
        "description_en": "Intelligent conversion between PDF, Word, Excel, PowerPoint and images at 300 DPI.",
        "description":    "Conversión inteligente entre PDF, Word, Excel, PowerPoint e imágenes a 300 DPI.",
        "repo":           f"{ORG_NAME}/DocumentConverter",
        "exe":            "MediaHub-DocumentConverter.exe",
        "dir":            "MediaHub-DocumentConverter",
        "icon":           "docs.png",
        "badge_es":       "OFICINA",
        "badge_en":       "OFFICE",
        "badge":          "OFICINA",
        "category":       "tools",
    },
    "link": {
        "name_es":        "Convertidor de Links",
        "name_en":        "Link Converter",
        "name":           "Convertidor de Links",
        "description_es": "Descarga por lotes desde YouTube, TikTok, Instagram y playlists con soporte paralelo.",
        "description_en": "Batch downloader from YouTube, TikTok, Instagram and playlists with parallel support.",
        "description":    "Descarga por lotes desde YouTube, TikTok, Instagram y playlists con soporte paralelo.",
        "repo":           f"{ORG_NAME}/LinkConverter",
        "exe":            "MediaHub-LinkConverter.exe",
        "dir":            "MediaHub-LinkConverter",
        "icon":           "link_converter.webp",
        "badge_es":       "BATCH",
        "badge_en":       "BATCH",
        "badge":          "BATCH",
        "category":       "tools",
    },
    "font_family": {
        "name_es":        "FontFamily Atelier",
        "name_en":        "FontFamily Atelier",
        "name":           "FontFamily Atelier",
        "description_es": "Estudio editorial de fuentes Unicode, caracteres invisibles, símbolos raros, marcos y emojis.",
        "description_en": "Editorial Unicode typography studio, invisible characters, rare symbols, frames and emojis.",
        "description":    "Estudio editorial de fuentes Unicode, caracteres invisibles, símbolos raros, marcos y emojis.",
        "repo":           f"{ORG_NAME}/FontFamily",
        "exe":            "FontFamily.exe",
        "dir":            "MediaHub-FontFamily",
        "icon":           "fontfamily.png",
        "badge_es":       "TIPOGRAFÍA",
        "badge_en":       "TYPOGRAPHY",
        "badge":          "TIPOGRAFÍA",
        "category":       "tools",
        "is_disabled":    False,
    },
    "streamstudio": {
        "name_es":        "StreamStudio",
        "name_en":        "StreamStudio",
        "name":           "StreamStudio",
        "description_es": "Suite de alertas OBS, puntos de canal con Voces IA y analíticas en vivo para Twitch.",
        "description_en": "OBS alerts suite, AI Voice channel points and live analytics for Twitch.",
        "description":    "Suite de alertas OBS, puntos de canal con Voces IA y analíticas en vivo para Twitch.",
        "repo":           f"{ORG_NAME}/StreamStudio",
        "exe":            "StreamStudio.exe",
        "dir":            "MediaHub-StreamStudio",
        "icon":           "streamstudio.png",
        "badge_es":       "STREAMING",
        "badge_en":       "STREAMING",
        "badge":          "STREAMING",
        "category":       "studio",
        "is_disabled":    False,
    },
    "audiolab": {
        "name_es":        "AudioLab",
        "name_en":        "AudioLab",
        "name":           "AudioLab",
        "description_es": "Laboratorio de síntesis matemática, fórmulas Bytebeat y efectos procedurales SFX.",
        "description_en": "Mathematical sound synthesis studio, Bytebeat formulas and procedural SFX.",
        "description":    "Laboratorio de síntesis matemática, fórmulas Bytebeat y efectos procedurales SFX.",
        "repo":           f"{ORG_NAME}/AudioLab",
        "exe":            "AudioLab.exe",
        "dir":            "MediaHub-AudioLab",
        "icon":           "audiolab.png",
        "badge_es":       "SÍNTESIS",
        "badge_en":       "SYNTH",
        "badge":          "SÍNTESIS",
        "category":       "studio",
        "is_disabled":    False,
    },
    "musical_trainer": {
        "name_es":        "MusicalTrainer",
        "name_en":        "MusicalTrainer",
        "name":           "MusicalTrainer",
        "description_es": "Conservatorio interactivo de lectura de partituras en 4 claves, armaduras, intervalos, acordes, diapasón y oído musical.",
        "description_en": "Interactive music conservatory for sight-reading across 4 clefs, key signatures, intervals, chords, fretboard and ear training.",
        "description":    "Conservatorio interactivo de lectura de partituras en 4 claves, armaduras, intervalos, acordes, diapasón y oído musical.",
        "repo":           f"{ORG_NAME}/MusicalTrainer",
        "exe":            "MusicalTrainer.exe",
        "dir":            "MediaHub-MusicalTrainer",
        "icon":           "musicaltrainer.png",
        "badge_es":       "CONSERVATORIO",
        "badge_en":       "CONSERVATORY",
        "badge":          "CONSERVATORIO",
        "category":       "studio",
        "is_disabled":    False,
    },
    "budget_manager": {
        "name_es":        "Gestor Presupuestario",
        "name_en":        "Budget Manager",
        "name":           "Gestor Presupuestario",
        "description_es": "Gestión financiera, seguimiento de gastos, presupuestos y balance en tiempo real.",
        "description_en": "Financial management, expense tracking, budgets and real-time cash balance.",
        "description":    "Gestión financiera, seguimiento de gastos, presupuestos y balance en tiempo real.",
        "repo":           f"{ORG_NAME}/GestorPresupuestario",
        "exe":            "GestorPresupuestario.exe",
        "dir":            "MediaHub-GestorPresupuestario",
        "icon":           "presupuesto.png",
        "badge_es":       "FINANZAS",
        "badge_en":       "FINANCE",
        "badge":          "FINANZAS",
        "category":       "admin",
        "is_disabled":    False,
    },
    "chile_planos": {
        "name_es":        "ChilePlanos",
        "name_en":        "ChilePlanos",
        "name":           "ChilePlanos",
        "description_es": "Hub de planimetría técnica y arquitectura para estudiantes y profesionales.",
        "description_en": "Technical planimetry and architectural hub for students and professionals.",
        "description":    "Hub de planimetría técnica y arquitectura para estudiantes y profesionales.",
        "repo":           f"{ORG_NAME}/ChilePlanos",
        "exe":            "ChilePlanos.exe",
        "dir":            "MediaHub-ChilePlanos",
        "icon":           "chileplanos.png",
        "badge_es":       "PLANOS",
        "badge_en":       "BLUEPRINTS",
        "badge":          "PLANOS",
        "category":       "admin",
        "is_disabled":    False,
    },
    "blueguard": {
        "name_es":        "BlueGuard",
        "name_en":        "BlueGuard",
        "name":           "BlueGuard",
        "description_es": "Asistente Blue Team de ciberseguridad, puertos, red y logs traducidos en tiempo real.",
        "description_en": "Real-time Blue Team cybersecurity assistant for network, ports and system logs.",
        "description":    "Asistente Blue Team de ciberseguridad, puertos, red y logs traducidos en tiempo real.",
        "repo":           f"{ORG_NAME}/BlueGuard",
        "exe":            "BlueGuard.exe",
        "dir":            "MediaHub-BlueGuard",
        "icon":           "blueguard.png",
        "badge_es":       "SEGURIDAD",
        "badge_en":       "SECURITY",
        "badge":          "SEGURIDAD",
        "category":       "admin",
        "is_disabled":    False,
    },
    "pokebinder": {
        "name_es":        "PokeBinder Inventory",
        "name_en":        "PokeBinder Inventory",
        "name":           "PokeBinder Inventory",
        "description_es": "Organizador visual de carpetas Pokémon TCG, cotización de cartas, mazos e inventario.",
        "description_en": "Visual Pokémon TCG binder organizer, card pricing, decks and inventory tracker.",
        "description":    "Organizador visual de carpetas Pokémon TCG, cotización de cartas, mazos e inventario.",
        "repo":           f"{ORG_NAME}/PokeBinderInventory",
        "exe":            "PokeBinder.exe",
        "dir":            "PokeBinder",
        "icon":           "pokebinder.png",
        "badge_es":       "TCG BINDER",
        "badge_en":       "TCG BINDER",
        "badge":          "TCG BINDER",
        "category":       "admin",
        "is_disabled":    False,
        "extra_assets": [
            {
                "name": "images.zip",
                "tag": "",
                "target_subdir": "assets",
                "extract": True,
                "description_es": "imágenes de cartas TCG",
                "description_en": "TCG card images",
            }
        ],
    },
}

# Diccionario vivo de aplicaciones activas (se muta in-place al sincronizar catalog.json)
APP_REGISTRY: dict[str, dict] = dict(DEFAULT_APP_REGISTRY)


def _normalize_app_entry(app_id: str, raw: dict) -> dict:
    """Garantiza que una entrada del catálogo JSON tenga todas las claves esperadas por el Launcher."""
    entry = dict(raw)
    name_es = entry.get("name_es") or entry.get("name") or app_id
    name_en = entry.get("name_en") or name_es
    desc_es = entry.get("description_es") or entry.get("description") or ""
    desc_en = entry.get("description_en") or desc_es
    badge_es = entry.get("badge_es") or entry.get("badge") or ""
    badge_en = entry.get("badge_en") or badge_es

    repo = entry.get("repo", f"{ORG_NAME}/{app_id}")
    if "/" not in repo:
        repo = f"{ORG_NAME}/{repo}"

    repo_short = repo.split("/")[-1]
    entry["name_es"] = name_es
    entry["name_en"] = name_en
    entry["name"] = name_es
    entry["description_es"] = desc_es
    entry["description_en"] = desc_en
    entry["description"] = desc_es
    entry["badge_es"] = badge_es
    entry["badge_en"] = badge_en
    entry["badge"] = badge_es
    entry["repo"] = repo
    entry["exe"] = entry.get("exe") or f"{repo_short}.exe"
    entry["dir"] = entry.get("dir") or f"MediaHub-{repo_short}"
    entry["icon"] = entry.get("icon") or f"{repo_short.lower()}.png"
    entry["category"] = entry.get("category") or "tools"
    entry["is_hero"] = bool(entry.get("is_hero", False))
    entry["is_disabled"] = bool(entry.get("is_disabled", False))
    return entry


def _catalog_fingerprint() -> str:
    """Devuelve un hash rápido del estado actual de APP_REGISTRY y SECTION_CATEGORIES."""
    payload = json.dumps(
        {"apps": APP_REGISTRY, "sections": SECTION_CATEGORIES},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def apply_catalog_dict(catalog_data: dict) -> bool:
    """
    Aplica un diccionario de catálogo (`catalog.json`) mutando `APP_REGISTRY` y
    `SECTION_CATEGORIES` in-place. Filtra las aplicaciones con `visible: false`.
    Devuelve True si hubo algún cambio respecto al estado anterior.
    """
    if not isinstance(catalog_data, dict):
        return False

    raw_apps = catalog_data.get("apps")
    if not isinstance(raw_apps, dict):
        return False

    before_fp = _catalog_fingerprint()

    raw_sections = catalog_data.get("sections")
    if isinstance(raw_sections, dict) and raw_sections:
        for sec_id, sec_meta in raw_sections.items():
            if isinstance(sec_meta, dict):
                SECTION_CATEGORIES[sec_id] = dict(sec_meta)

    visible_apps: dict[str, dict] = {}
    for app_id, app_meta in raw_apps.items():
        if not isinstance(app_meta, dict):
            continue
        if app_meta.get("visible", True) is False:
            continue
        visible_apps[app_id] = _normalize_app_entry(app_id, app_meta)

    APP_REGISTRY.clear()
    APP_REGISTRY.update(visible_apps)

    after_fp = _catalog_fingerprint()
    return before_fp != after_fp


def load_initial_catalog() -> None:
    """
    Carga el catálogo inicial al arrancar el Launcher:
    1. Lee `catalog.json` empaquetado con la aplicación.
    2. Si existe `~/.mediahub/catalog_cache.json` (última sincronización remota), lo aplica encima.
    """
    bundled_catalog = os.path.join(get_base_dir(), "catalog.json")
    if os.path.isfile(bundled_catalog):
        try:
            with open(bundled_catalog, "r", encoding="utf-8") as f:
                apply_catalog_dict(json.load(f))
        except Exception:
            pass

    cached_catalog = get_cached_catalog_file()
    if os.path.isfile(cached_catalog):
        try:
            with open(cached_catalog, "r", encoding="utf-8") as f:
                apply_catalog_dict(json.load(f))
        except Exception:
            pass


def ensure_app_icon_cached(app_id: str, app_meta: dict) -> None:
    """
    Si el icono de una aplicación nueva no está empaquetado localmente en `assets/hub/`,
    lo descarga automáticamente desde `icon_url` o desde el repositorio de la app en GitHub
    y lo guarda en `~/.mediahub/cache/icons/`.
    """
    icon_name = app_meta.get("icon", "")
    if not icon_name:
        return

    bundled_icon = os.path.join(get_base_dir(), "assets", "hub", icon_name)
    if os.path.isfile(bundled_icon):
        return

    cached_icon = os.path.join(get_cached_icons_dir(), icon_name)
    if os.path.isfile(cached_icon) and os.path.getsize(cached_icon) > 100:
        return

    repo = app_meta.get("repo", "")
    candidate_urls = []
    if app_meta.get("icon_url"):
        candidate_urls.append(app_meta["icon_url"])
    if repo:
        candidate_urls.append(f"https://raw.githubusercontent.com/{repo}/main/assets/hub/{icon_name}")
        candidate_urls.append(f"https://raw.githubusercontent.com/{repo}/master/assets/hub/{icon_name}")
    candidate_urls.append(f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/assets/hub/{icon_name}")

    for url in candidate_urls:
        try:
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200 and len(resp.content) > 100:
                with open(cached_icon, "wb") as f:
                    f.write(resp.content)
                return
        except Exception:
            continue


def sync_remote_catalog(timeout: float = 5.0) -> tuple[bool, int]:
    """
    Descarga la versión más reciente de `catalog.json` desde GitHub:
    1. Primero consulta la API Contents de GitHub (`Accept: application/vnd.github.raw+json`)
       para obtener cambios al instante sin esperar la caché CDN de 5 minutos.
    2. Si se supera el rate limit, usa `raw.githubusercontent.com` con cache-buster.
    Actualiza `APP_REGISTRY` in-place, descarga iconos nuevos si faltan y persiste
    en `~/.mediahub/catalog_cache.json`.
    Devuelve `(hubo_cambios, total_apps_visibles)`.
    """
    headers_api = {
        "User-Agent": "MediaHub-Launcher",
        "Accept": "application/vnd.github.raw+json",
        "Cache-Control": "no-cache",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers_api["Authorization"] = f"Bearer {token}"

    catalog_data = None
    try:
        resp = requests.get(CATALOG_API_URL, headers=headers_api, timeout=timeout)
        if resp.status_code == 200:
            catalog_data = resp.json()
    except Exception:
        catalog_data = None

    if not isinstance(catalog_data, dict) or "apps" not in catalog_data:
        try:
            bust_url = f"{CATALOG_RAW_URL}?t={int(time.time())}"
            resp = requests.get(
                bust_url,
                headers={"User-Agent": "MediaHub-Launcher", "Cache-Control": "no-cache"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                catalog_data = resp.json()
        except Exception:
            catalog_data = None

    if not isinstance(catalog_data, dict) or "apps" not in catalog_data:
        return False, len(APP_REGISTRY)

    # Persistir en caché local para inicios futuros offline
    try:
        with open(get_cached_catalog_file(), "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando caché del catálogo: {e}")

    changed = apply_catalog_dict(catalog_data)

    # Descargar iconos faltantes para apps nuevas
    for aid, ameta in list(APP_REGISTRY.items()):
        ensure_app_icon_cached(aid, ameta)

    return changed, len(APP_REGISTRY)


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


def get_section_metadata(section_id: str, lang: str = "es") -> dict:
    """Devuelve los metadatos de una sección/categoría traducidos al idioma solicitado."""
    sec = SECTION_CATEGORIES.get(section_id, {})
    return {
        "id": section_id,
        "icon": sec.get("icon", "•"),
        "name": sec.get(f"name_{lang}", sec.get("name_es", section_id)),
        "description": sec.get(f"desc_{lang}", sec.get("desc_es", "")),
    }


# Inicializar catálogo al importar el módulo
load_initial_catalog()
