import webbrowser
import os
import sys
import copy
import json
import re
import subprocess
import zipfile
import tempfile
import threading
import shutil

import requests
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGridLayout, QFrame,
    QGraphicsDropShadowEffect, QMessageBox, QApplication,
    QMenu, QLineEdit, QScrollArea, QProgressBar
)
from PyQt6.QtGui import QPixmap, QIcon, QColor, QDrag, QAction
from PyQt6.QtCore import QMimeData, Qt, QSize, QThread, QTimer, pyqtSignal

from core.theme_manager import ThemeManager
from core.updater import CheckUpdateThread, UpdateDialog
from core.config import (
    APP_REGISTRY, SECTION_CATEGORIES, ADMIN_PANEL_URL,
    get_launcher_version, save_launcher_version,
    get_app_metadata, get_section_metadata,
    get_cached_icons_dir, apply_catalog_dict,
    fetch_remote_catalog_payload, sync_remote_catalog
)
from core.i18n import t, get_current_language, save_current_language, save_app_language, get_app_language
from core.sound_manager import SoundManager


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers de rutas, versiones y detección de instalación
# ─────────────────────────────────────────────────────────────────────────────

def get_asset_path(filename):
    """
    Devuelve la ruta absoluta de un asset del Launcher.
    Si es una app nueva agregada dinámicamente desde el catálogo web,
    busca también en la caché local `~/.mediahub/cache/icons/` y usa Media-Hub.ico como respaldo.
    """
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    bundled = os.path.join(base_dir, "assets", "hub", filename)
    if os.path.isfile(bundled):
        return bundled
    cached = os.path.join(get_cached_icons_dir(), os.path.basename(filename))
    if os.path.isfile(cached):
        return cached
    fallback = os.path.join(base_dir, "assets", "hub", "Media-Hub.ico")
    return fallback if os.path.isfile(fallback) else bundled


def get_hub_data_dir() -> str:
    """Carpeta raíz unificada para datos del Hub en el perfil de usuario: ~/.mediahub"""
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    hub_dir = os.path.join(home, ".mediahub")
    os.makedirs(hub_dir, exist_ok=True)
    return hub_dir


def get_apps_install_dir() -> str:
    """Carpeta raíz donde se instalan las micro-apps: ~/.mediahub/apps/"""
    path = os.path.join(get_hub_data_dir(), "apps")
    os.makedirs(path, exist_ok=True)
    return path


def get_installed_versions_file() -> str:
    """Archivo JSON donde guardamos las versiones instaladas: ~/.mediahub/installed_versions.json"""
    return os.path.join(get_hub_data_dir(), "installed_versions.json")


def load_installed_versions() -> dict:
    """Carga el diccionario {app_id: version_str} de apps instaladas."""
    fpath = get_installed_versions_file()
    if os.path.isfile(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_installed_version(app_id: str, version: str):
    """Guarda o actualiza la versión instalada de una micro-app."""
    data = load_installed_versions()
    data[app_id] = version.lstrip("v")
    fpath = get_installed_versions_file()
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error guardando versión instalada: {e}")


def remove_installed_version(app_id: str):
    """Elimina el registro de versión de una micro-app desinstalada."""
    data = load_installed_versions()
    if app_id in data:
        del data[app_id]
        fpath = get_installed_versions_file()
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error actualizando registro tras desinstalar: {e}")


def get_app_exe(app_id: str) -> str | None:
    """
    Devuelve la ruta al ejecutable de una micro-app si está instalada,
    o None si no lo está.
    """
    reg = APP_REGISTRY.get(app_id)
    if not reg:
        return None
    install_dir = os.path.join(get_apps_install_dir(), reg["dir"])
    exe_name = reg["exe"]
    exe_path = os.path.join(install_dir, exe_name)
    if os.path.isfile(exe_path):
        return exe_path

    # Respaldo si el zip contenía una subcarpeta
    if os.path.isdir(install_dir):
        for root, _, files in os.walk(install_dir):
            if exe_name in files:
                return os.path.join(root, exe_name)
    return None


def get_desktop_path() -> str:
    """Retorna la ruta absoluta del Escritorio del usuario (soporta OneDrive y Windows local)."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        desk = shell.SpecialFolders("Desktop")
        if os.path.isdir(desk):
            return desk
    except Exception:
        pass
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    onedrive_desk = os.path.join(home, "OneDrive", "Desktop")
    if os.path.isdir(onedrive_desk):
        return onedrive_desk
    standard_desk = os.path.join(home, "Desktop")
    return standard_desk


def get_desktop_shortcut_path(app_id: str) -> str:
    """Devuelve la ruta del archivo .lnk de acceso directo para la aplicación en el Escritorio."""
    reg = APP_REGISTRY.get(app_id, {})
    name = reg.get("name", app_id)
    # Sanitizar nombre para archivo
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
    return os.path.join(get_desktop_path(), f"{safe_name}.lnk")


def has_desktop_shortcut(app_id: str) -> bool:
    """Verifica si ya existe el acceso directo en el Escritorio."""
    return os.path.isfile(get_desktop_shortcut_path(app_id))


def create_desktop_shortcut(app_id: str) -> bool:
    """Crea un acceso directo en el Escritorio para la aplicación instalada."""
    exe = get_app_exe(app_id)
    if not exe or not os.path.isfile(exe):
        return False
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        lnk_path = get_desktop_shortcut_path(app_id)
        shortcut = shell.CreateShortcut(lnk_path)
        shortcut.TargetPath = exe
        shortcut.WorkingDirectory = os.path.dirname(exe)
        shortcut.Description = APP_REGISTRY.get(app_id, {}).get("description", "")
        # Buscar icono específico de la app en launcher assets o en el directorio de la app
        icon_path = get_asset_path(f"../icons/{app_id}.ico")
        if os.path.isfile(icon_path):
            shortcut.IconLocation = os.path.abspath(icon_path)
        else:
            app_dir = os.path.dirname(exe)
            for root, _, files in os.walk(app_dir):
                for f in files:
                    if f.endswith(".ico"):
                        shortcut.IconLocation = os.path.join(root, f)
                        break
                if getattr(shortcut, "IconLocation", None):
                    break
        shortcut.save()
        return True
    except Exception as e:
        print(f"Error creando acceso directo para {app_id}: {e}")
        return False


def remove_desktop_shortcut(app_id: str) -> bool:
    """Elimina el acceso directo del Escritorio si existe."""
    lnk_path = get_desktop_shortcut_path(app_id)
    if os.path.isfile(lnk_path):
        try:
            os.remove(lnk_path)
            return True
        except Exception as e:
            print(f"Error eliminando acceso directo {lnk_path}: {e}")
            return False
    return False


def get_sizes_cache_file() -> str:
    """Archivo JSON para cachear los tamaños de release de cada app."""
    return os.path.join(get_hub_data_dir(), "app_sizes.json")


def load_cached_sizes() -> dict:
    """Carga diccionario con {app_id: size_str}."""
    fpath = get_sizes_cache_file()
    if os.path.isfile(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cached_sizes(sizes: dict):
    """Guarda caché de tamaños de apps."""
    fpath = get_sizes_cache_file()
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(sizes, f, indent=2)
    except Exception as e:
        print(f"Error guardando cache de tamaños: {e}")


def launch_app(app_id: str):
    """Lanza la micro-app instalada como proceso independiente del sistema inyectando su idioma."""
    exe = get_app_exe(app_id)
    if exe and os.path.isfile(exe):
        try:
            reg = APP_REGISTRY.get(app_id, {})
            app_dir = reg.get("dir", app_id)
            app_lang = get_app_language(app_dir)

            env = os.environ.copy()
            env["MEDIAHUB_APP_LANG"] = app_lang
            env["MEDIAHUB_LANG"] = app_lang
            env["LANG"] = f"{app_lang}_ES.UTF-8" if app_lang == "es" else f"{app_lang}_US.UTF-8"

            # Iniciar como proceso desacoplado pasando --lang y variables de entorno
            # Si la aplicación es de consola/terminal (ej: juegos CLI), se debe asignar una ventana de consola propia (CREATE_NEW_CONSOLE)
            is_cli_app = reg.get("category") == "games" or reg.get("is_console", False)

            if os.name == "nt":
                if is_cli_app:
                    cflags = subprocess.CREATE_NEW_CONSOLE
                else:
                    cflags = subprocess.DETACHED_PROCESS
            else:
                cflags = 0

            subprocess.Popen(
                [exe, f"--lang={app_lang}"],
                cwd=os.path.dirname(exe),
                env=env,
                creationflags=cflags,
                close_fds=True
            )
        except Exception as e:
            QMessageBox.critical(
                None, t("dialog_not_installed_title"),
                f"No se pudo iniciar la aplicación:\n{e}\n\nRuta: {exe}"
            )
    else:
        QMessageBox.warning(
            None, t("dialog_not_installed_title"),
            t("dialog_not_installed_msg")
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Thread verificador de actualizaciones de micro-apps
# ─────────────────────────────────────────────────────────────────────────────

class SyncCatalogThread(QThread):
    """
    Descarga en segundo plano el catálogo dinámico (catalog.json) desde GitHub
    SIN mutar APP_REGISTRY en el hilo secundario (emite el payload al hilo GUI principal).
    """
    catalog_payload_ready = pyqtSignal(object, str, bool)  # (catalog_data_or_None, latest_sha, manual)

    def __init__(self, parent=None, known_sha: str = "", manual: bool = False):
        super().__init__(parent)
        self.known_sha = known_sha
        self.manual = manual

    def run(self):
        try:
            # Si es manual, forzamos descarga ignorando known_sha para verificar cambios inmediatos
            sha_to_check = "" if self.manual else self.known_sha
            catalog_data, latest_sha = fetch_remote_catalog_payload(timeout=4.5, known_sha=sha_to_check)
            self.catalog_payload_ready.emit(catalog_data, latest_sha, self.manual)
        except Exception:
            self.catalog_payload_ready.emit(None, "", self.manual)


class CheckMicroAppUpdatesThread(QThread):
    """Verifica en segundo plano si alguna app instalada tiene una versión más nueva en GitHub."""
    update_found = pyqtSignal(str, str)  # (app_id, new_version)
    status_changed = pyqtSignal(str)     # (status_message)

    def __init__(self, parent=None, apps_snapshot: dict | None = None):
        super().__init__(parent)
        self.apps_snapshot = copy.deepcopy(apps_snapshot if apps_snapshot is not None else dict(APP_REGISTRY))

    def run(self):
        try:
            installed = load_installed_versions()
            if installed:
                self.status_changed.emit(t("overlay_checking_updates"))
            headers = {"User-Agent": "MediaHub-Launcher"}
            for app_id, cur_v in list(installed.items()):
                reg = self.apps_snapshot.get(app_id)
                if not reg:
                    continue
                repo = reg.get("repo", "")
                if not repo:
                    continue
                try:
                    tag = ""
                    # 1. Consultar redirección 302 directa de GitHub (0 consumo de rate-limit API)
                    rel_url = f"https://github.com/{repo}/releases/latest"
                    head_res = requests.head(rel_url, headers=headers, allow_redirects=False, timeout=5)
                    loc = head_res.headers.get("Location", "")
                    if "/releases/tag/" in loc:
                        tag = loc.split("/releases/tag/")[-1].split("?")[0].strip().lstrip("v")

                    # 2. Respaldo API REST si no hubo redirección
                    if not tag:
                        url = f"https://api.github.com/repos/{repo}/releases/latest"
                        resp = requests.get(url, headers=headers, timeout=5)
                        if resp.status_code == 200:
                            tag = resp.json().get("tag_name", "").lstrip("v")

                    if tag and tag != cur_v:
                        cur_parts = [int(x) for x in cur_v.split(".") if x.isdigit()]
                        tag_parts = [int(x) for x in tag.split(".") if x.isdigit()]
                        if tag_parts > cur_parts:
                            self.update_found.emit(app_id, tag)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self.status_changed.emit("")


class FetchAppSizesThread(QThread):
    """Consulta en segundo plano el tamaño de descarga/release de cada app desde GitHub."""
    sizes_fetched = pyqtSignal(dict)  # {app_id: "143 MB"}

    def __init__(self, parent=None, apps_snapshot: dict | None = None, only_missing: bool = False):
        super().__init__(parent)
        self.apps_snapshot = copy.deepcopy(apps_snapshot if apps_snapshot is not None else dict(APP_REGISTRY))
        self.only_missing = only_missing

    def run(self):
        try:
            sizes = load_cached_sizes()
            changed = False
            headers = {"User-Agent": "MediaHub-Launcher"}
            token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"

            for app_id, reg in list(self.apps_snapshot.items()):
                if self.only_missing and sizes.get(app_id):
                    continue
                # Si ya está en caché en disco, no saturar la API de GitHub innecesariamente
                if sizes.get(app_id):
                    continue

                repo = reg.get("repo")
                if not repo or reg.get("is_disabled"):
                    continue
                try:
                    total_sz_bytes = 0
                    url = f"https://api.github.com/repos/{repo}/releases/latest"
                    resp = requests.get(url, headers=headers, timeout=6)
                    if resp.status_code == 200:
                        data = resp.json()
                        extra_names = {extra.get("name") for extra in reg.get("extra_assets", []) if extra.get("name")}
                        for asset in data.get("assets", []):
                            aname = asset.get("name", "")
                            if aname not in extra_names and aname.endswith((".zip", ".exe")):
                                total_sz_bytes += asset.get("size", 0)
                                break

                        for extra in reg.get("extra_assets", []):
                            extra_name = extra.get("name")
                            found_in_latest = False
                            for asset in data.get("assets", []):
                                if asset.get("name") == extra_name:
                                    total_sz_bytes += asset.get("size", 0)
                                    found_in_latest = True
                                    break
                            if not found_in_latest:
                                tag = extra.get("tag")
                                if tag:
                                    extra_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
                                    try:
                                        e_resp = requests.get(extra_url, headers=headers, timeout=5)
                                        if e_resp.status_code == 200:
                                            for e_asset in e_resp.json().get("assets", []):
                                                if e_asset.get("name") == extra_name:
                                                    total_sz_bytes += e_asset.get("size", 0)
                                                    break
                                    except Exception:
                                        pass
                    else:
                        # Fallback directo por HEAD sin API de GitHub (0 consumo de rate-limit)
                        repo_dir = reg.get("dir", "")
                        if repo_dir:
                            direct_url = f"https://github.com/{repo}/releases/latest/download/{repo_dir}.zip"
                            h_res = requests.head(direct_url, headers=headers, allow_redirects=True, timeout=6)
                            if h_res.status_code == 200:
                                cl = h_res.headers.get("Content-Length") or h_res.headers.get("content-length")
                                if cl and str(cl).isdigit():
                                    total_sz_bytes = int(cl)

                    if total_sz_bytes > 0:
                        mb = total_sz_bytes / (1024 * 1024)
                        sz_str = f"{mb:.1f} MB" if mb < 1024 else f"{mb/1024:.2f} GB"
                        if sizes.get(app_id) != sz_str:
                            sizes[app_id] = sz_str
                            changed = True
                except Exception:
                    pass
            if changed:
                save_cached_sizes(sizes)
            self.sizes_fetched.emit(sizes)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  Worker de descarga e instalación
# ─────────────────────────────────────────────────────────────────────────────

class InstallWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, str)
    error    = pyqtSignal(str)

    def __init__(self, app_id: str, target_lang: str = "es", parent=None):
        super().__init__(parent)
        self.app_id = app_id
        self.target_lang = target_lang

    def run(self):
        reg = APP_REGISTRY.get(self.app_id)
        if not reg:
            self.error.emit(f"App desconocida: {self.app_id}")
            return

        self.progress.emit(5, "Buscando versión más reciente en GitHub…")
        repo = reg["repo"]
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"

        # Headers con User-Agent estándar para evitar bloqueos y token si está disponible
        headers = {"User-Agent": "MediaHub-Launcher"}
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        release = None
        try:
            r = requests.get(api_url, headers=headers, timeout=10)
            r.raise_for_status()
            release = r.json()
        except Exception as e:
            # Fallback directo sin API de GitHub cuando se supera el rate limit de 60 req/h (HTTP 403)
            repo_dir = reg.get("dir", "")
            if repo_dir:
                fallback_asset = f"{repo_dir}.zip"
                fallback_url = f"https://github.com/{repo}/releases/latest/download/{fallback_asset}"
                release = {
                    "tag_name": "1.0.0",
                    "assets": [
                        {
                            "name": fallback_asset,
                            "browser_download_url": fallback_url,
                            "size": 0,
                        }
                    ],
                }
            else:
                self.error.emit(f"No se pudo consultar el repositorio:\n{e}")
                return

        latest_tag = release.get("tag_name", "latest")
        assets = release.get("assets", [])
        extra_assets = reg.get("extra_assets", [])
        extra_names = {extra.get("name") for extra in extra_assets if extra.get("name")}

        # Priorizar assets principales de la aplicación (excluyendo zips adicionales como images.zip)
        main_candidates = [a for a in assets if a.get("name") not in extra_names]
        asset = next((a for a in main_candidates if a.get("name", "").endswith(".zip")), None)
        if not asset:
            asset = next((a for a in main_candidates if a.get("name", "").endswith(".exe")), None)
        if not asset:
            asset = next((a for a in assets if a.get("name", "").endswith(".zip")), None)
        if not asset:
            asset = next((a for a in assets if a.get("name", "").endswith(".exe")), None)

        if not asset:
            self.error.emit(f"No se encontró instalador en el release {latest_tag}.")
            return

        download_url = asset["browser_download_url"]
        asset_name   = asset["name"]
        total        = asset.get("size", 0)

        self.progress.emit(10, f"Descargando {asset_name}…")
        tmp_file = os.path.join(tempfile.gettempdir(), asset_name)

        # Si la app define assets adicionales (ej. PokeBinder images.zip), distribuimos el porcentaje
        has_extras = len(extra_assets) > 0
        main_dl_pct_max = 50 if has_extras else 75

        try:
            with requests.get(download_url, stream=True, timeout=30) as dl:
                dl.raise_for_status()
                downloaded = 0
                with open(tmp_file, "wb") as f:
                    for chunk in dl.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = 10 + int(downloaded / total * (main_dl_pct_max - 10))
                            self.progress.emit(pct, f"Descargando… {downloaded // (1024*1024)} MB")
        except Exception as e:
            self.error.emit(f"Error al descargar:\n{e}")
            return

        self.progress.emit(main_dl_pct_max, "Instalando archivos…")
        install_base = get_apps_install_dir()
        dest_dir = os.path.join(install_base, reg["dir"])

        try:
            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir, ignore_errors=True)
            os.makedirs(dest_dir, exist_ok=True)

            if asset_name.endswith(".zip"):
                with zipfile.ZipFile(tmp_file, "r") as zf:
                    zf.extractall(dest_dir)
            else:
                subprocess.run([tmp_file, "/SILENT", f"/DIR={dest_dir}"], check=True)
            save_installed_version(self.app_id, latest_tag)
            save_app_language(reg["dir"], self.target_lang)
        except Exception as e:
            self.error.emit(f"Error al instalar:\n{e}")
            return

        # ── Descarga de Assets Adicionales (ej. images.zip en PokeBinder) ───────
        if has_extras:
            for extra in extra_assets:
                asset_name_extra = extra.get("name", "images.zip")
                tag_extra = extra.get("tag", "Assets")
                sub_target = extra.get("target_subdir", "assets")
                extract_extra = extra.get("extract", True)
                desc_label = extra.get(f"description_{self.target_lang}", asset_name_extra)

                self.progress.emit(55, f"Descargando {desc_label}…")
                extra_tmp = os.path.join(tempfile.gettempdir(), f"{self.app_id}_{asset_name_extra}")
                
                # Obtener URL directa (intentar release actual/latest o tag específico)
                extra_asset_obj = next((a for a in assets if a.get("name") == asset_name_extra), None)
                if extra_asset_obj:
                    extra_dl_url = extra_asset_obj.get("browser_download_url")
                elif tag_extra:
                    extra_dl_url = f"https://github.com/{repo}/releases/download/{tag_extra}/{asset_name_extra}"
                else:
                    # Si no hay tag específico, usar el endpoint canónico de descarga de latest
                    extra_dl_url = f"https://github.com/{repo}/releases/latest/download/{asset_name_extra}"
                try:
                    with requests.get(extra_dl_url, stream=True, timeout=60, headers=headers) as dl_e:
                        dl_e.raise_for_status()
                        total_e = int(dl_e.headers.get("content-length", 0))
                        dl_bytes = 0
                        with open(extra_tmp, "wb") as f_e:
                            for chunk in dl_e.iter_content(chunk_size=131072):
                                f_e.write(chunk)
                                dl_bytes += len(chunk)
                                if total_e > 0:
                                    pct_e = 55 + int(dl_bytes / total_e * 35)
                                    mb_done = dl_bytes // (1024 * 1024)
                                    mb_tot = total_e // (1024 * 1024)
                                    self.progress.emit(pct_e, f"{desc_label}… {mb_done}/{mb_tot} MB")
                except Exception as e:
                    self.error.emit(f"Error descargando {desc_label}:\n{e}")
                    return

                self.progress.emit(92, f"Instalando {desc_label}…")
                target_extract_dir = os.path.join(dest_dir, sub_target) if sub_target else dest_dir
                os.makedirs(target_extract_dir, exist_ok=True)

                try:
                    if extract_extra and asset_name_extra.endswith(".zip"):
                        with zipfile.ZipFile(extra_tmp, "r") as zf_e:
                            zf_e.extractall(target_extract_dir)
                    else:
                        shutil.copy2(extra_tmp, target_extract_dir)
                except Exception as e:
                    self.error.emit(f"Error descomprimiendo {desc_label}:\n{e}")
                    return

        self.progress.emit(100, t("status_ready"))
        curr_lang = get_current_language()
        meta = get_app_metadata(self.app_id, curr_lang)
        self.finished.emit(self.app_id, meta.get("name", reg.get("name", self.app_id)))


# ─────────────────────────────────────────────────────────────────────────────
#  Overlay de Carga / Espera (Issue #89)
# ─────────────────────────────────────────────────────────────────────────────

class LoadingBannerOverlay(QFrame):
    """
    Banner elegante y no invasivo en la parte inferior o central para notificar procesos
    en segundo plano (detección de actualizaciones, instalaciones simultáneas) sin bloquear
    la interacción del usuario ni dar sensación de congelamiento.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loadingBannerOverlay")
        self.setFixedHeight(54)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(14)

        self.spinner_label = QLabel("⏳")
        self.spinner_label.setStyleSheet("font-size: 16pt;")
        layout.addWidget(self.spinner_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(t("overlay_checking_updates"))
        self.title_label.setObjectName("loadingBannerTitle")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 9.5pt;")

        self.desc_label = QLabel(t("overlay_wait"))
        self.desc_label.setObjectName("loadingBannerDesc")
        self.desc_label.setStyleSheet("font-size: 8.5pt; opacity: 0.85;")

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.desc_label)
        layout.addLayout(text_layout)

        layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Modo indeterminado pulsante
        self.progress_bar.setFixedWidth(140)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                background-color: rgba(0, 0, 0, 0.25);
            }
            QProgressBar::chunk {
                background-color: #6366f1;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def apply_styles(self, is_dark: bool = True):
        bg = "rgba(30, 30, 46, 0.96)" if is_dark else "rgba(240, 242, 248, 0.96)"
        border = "rgba(99, 102, 241, 0.6)" if is_dark else "rgba(99, 102, 241, 0.5)"
        text_color = "#f8fafc" if is_dark else "#0f172a"
        sub_color = "#94a3b8" if is_dark else "#475569"

        self.setStyleSheet(f"""
            QFrame#loadingBannerOverlay {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QLabel#loadingBannerTitle {{
                color: {text_color};
            }}
            QLabel#loadingBannerDesc {{
                color: {sub_color};
            }}
        """)

    def show_message(self, title: str, subtitle: str = ""):
        self.title_label.setText(title)
        self.desc_label.setText(subtitle or t("overlay_wait"))
        self.show()
        self.raise_()

    def hide_overlay(self):
        self.hide()


# ─────────────────────────────────────────────────────────────────────────────
#  AppCard (Bento Grid Card)
# ─────────────────────────────────────────────────────────────────────────────

class AppCard(QFrame):
    def __init__(self, card_id, title, subtitle, icon_file, badge_text="", is_hero=False, is_disabled=False, parent=None):
        super().__init__(parent)
        self.card_id = card_id
        self.is_hero = is_hero
        self._is_disabled = is_disabled
        self._pending_update_version = None
        self._sm = SoundManager.instance()
        self.setAcceptDrops(True)

        if is_disabled:
            self.setObjectName("appCardDisabled")
            self.setMinimumHeight(200)
        elif is_hero:
            self.setObjectName("appCardHero")
            self.setMinimumHeight(416)
        else:
            self.setObjectName("appCard")
            self.setMinimumHeight(200)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 20)
        main_layout.setSpacing(12)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        self._icon_label = QLabel()
        pixmap = QPixmap(get_asset_path(icon_file))
        icon_size = 52 if is_hero else 44
        if not pixmap.isNull():
            self._icon_label.setPixmap(
                pixmap.scaled(icon_size, icon_size,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )
        self._icon_label.setFixedSize(icon_size, icon_size)
        top_layout.addWidget(self._icon_label)

        if badge_text:
            self._badge_label = QLabel(badge_text)
            self._badge_label.setObjectName("badgeTag")
            top_layout.addWidget(self._badge_label)

        top_layout.addStretch()

        self.options_btn = QPushButton("⋮")
        self.options_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.options_btn.setFixedSize(30, 30)
        self.options_btn.setToolTip("Opciones (Reinstalar / Desinstalar)")
        self.options_btn.clicked.connect(self._show_options_menu)
        self.options_btn.hide()
        top_layout.addWidget(self.options_btn)

        main_layout.addLayout(top_layout)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self._title_label = QLabel(title)
        self._title_label.setWordWrap(True)
        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setWordWrap(True)

        text_layout.addWidget(self._title_label)
        text_layout.addWidget(self._subtitle_label)
        main_layout.addLayout(text_layout)

        main_layout.addStretch()

        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)

        self._status_label = QLabel()
        action_layout.addWidget(self._status_label)
        action_layout.addStretch()

        self.action_btn = QPushButton()
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        action_layout.addWidget(self.action_btn)

        main_layout.addLayout(action_layout)

        self.refresh_state()

    def set_update_available(self, new_version: str):
        self._pending_update_version = new_version
        self._set_btn_state("update")

    def enterEvent(self, event):
        super().enterEvent(event)
        if not self._is_disabled and hasattr(self, "_sm"):
            self._sm.play("hover")

    def _show_options_menu(self):
        if hasattr(self, "_sm"):
            self._sm.play("click")
        menu = QMenu(self)
        is_dark = ThemeManager.instance().is_dark
        bg = "#1A1D27" if is_dark else "#FFFFFF"
        fg = "#F3F4F6" if is_dark else "#1F2937"
        border = "#272B3B" if is_dark else "#E5E7EB"
        hover = "#252B3B" if is_dark else "#F3F4F6"

        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 6px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 9.5pt;
                font-weight: 600;
            }}
            QMenu::item {{
                padding: 8px 18px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background-color: {hover};
            }}
        """)

        lang_act = menu.addAction(t("menu_change_lang"))
        lang_act.triggered.connect(lambda: self.window()._change_app_language(self.card_id))

        if has_desktop_shortcut(self.card_id):
            shortcut_act = menu.addAction(t("menu_remove_shortcut"))
            shortcut_act.triggered.connect(lambda: self.window()._remove_shortcut(self.card_id))
        else:
            shortcut_act = menu.addAction(t("menu_create_shortcut"))
            shortcut_act.triggered.connect(lambda: self.window()._create_shortcut(self.card_id))

        menu.addSeparator()

        reinstall_act = menu.addAction(t("menu_reinstall"))
        reinstall_act.triggered.connect(lambda: self.window()._reinstall_app(self.card_id))

        uninstall_act = menu.addAction(t("menu_uninstall"))
        uninstall_act.triggered.connect(lambda: self.window()._uninstall_app(self.card_id))

        menu.exec(self.options_btn.mapToGlobal(self.options_btn.rect().bottomLeft()))

    def refresh_state(self):
        if self._is_disabled or self.card_id not in APP_REGISTRY:
            self._set_btn_state("disabled")
            return

        exe = get_app_exe(self.card_id)
        if exe:
            if self._pending_update_version:
                self._set_btn_state("update")
            else:
                self._set_btn_state("open")
        else:
            self._pending_update_version = None
            self._set_btn_state("install")

    def _set_btn_state(self, state: str):
        self._btn_state = state
        installed = load_installed_versions()
        cur_ver = installed.get(self.card_id)

        cached_sizes = load_cached_sizes()
        size_str = cached_sizes.get(self.card_id, "")
        size_suffix = f" • {size_str}" if size_str else ""

        if state == "open":
            self.action_btn.setText(t("btn_open"))
            self.action_btn.setEnabled(True)
            v_text = f"v{cur_ver}" if cur_ver else ""
            ready_txt = t("status_ready")
            self._status_label.setText(f"{ready_txt} {v_text}{size_suffix}".strip())
            self.options_btn.show()
        elif state == "update":
            self.action_btn.setText(t("btn_update"))
            self.action_btn.setEnabled(True)
            up_symbol = t("status_update")
            self._status_label.setText(f"{up_symbol} v{self._pending_update_version}{size_suffix}")
            self.options_btn.show()
        elif state == "install":
            self.action_btn.setText(t("btn_install"))
            self.action_btn.setEnabled(True)
            uninst_txt = t("status_uninstalled")
            self._status_label.setText(f"{uninst_txt}{size_suffix}")
            self.options_btn.hide()
        else:
            self.action_btn.setText(t("btn_coming_soon"))
            self.action_btn.setEnabled(False)
            self._status_label.setText("")
            self.options_btn.hide()

    def update_texts(self):
        """Actualiza el título, subtítulo y badge según el idioma actual."""
        curr_lang = get_current_language()
        meta = get_app_metadata(self.card_id, curr_lang)
        if meta:
            self._title_label.setText(meta.get("name", self.card_id))
            self._subtitle_label.setText(meta.get("description", ""))
            if hasattr(self, "_badge_label"):
                self._badge_label.setText(meta.get("badge", ""))
        self.options_btn.setToolTip(t("options_tooltip"))
        self.refresh_state()

    def apply_styles(self, styles: dict):
        if self._is_disabled:
            self.setStyleSheet(styles["card_disabled"])
        elif self.is_hero:
            self.setStyleSheet(styles["card_hero"])
        else:
            self.setStyleSheet(styles["card_normal"])

        title_style = styles["card_hero_title"] if self.is_hero else styles["card_title"]
        self._title_label.setStyleSheet(title_style)
        self._subtitle_label.setStyleSheet(styles["card_subtitle"])

        if hasattr(self, "_badge_label"):
            self._badge_label.setStyleSheet(styles["tag_badge"])

        self.options_btn.setStyleSheet(styles["btn_options"])

        state = getattr(self, "_btn_state", "disabled")
        if state == "install":
            self.action_btn.setStyleSheet(styles["btn_install"])
            self._status_label.setStyleSheet(styles["status_uninstalled"])
        elif state == "update":
            self.action_btn.setStyleSheet(styles["btn_update"])
            self._status_label.setStyleSheet(styles["status_update"])
        elif state == "open":
            self.action_btn.setStyleSheet(styles["btn_open"])
            self._status_label.setStyleSheet(styles["status_installed"])
        else:
            self.action_btn.setStyleSheet(styles["btn_disabled"])
            self._status_label.setStyleSheet(styles["status_uninstalled"])


# ─────────────────────────────────────────────────────────────────────────────
#  HubWindow  —  MediaHub Launcher (Bento Grid)
# ─────────────────────────────────────────────────────────────────────────────

class HubWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Hub")
        self.setMinimumSize(980, 640)
        self.resize(1140, 720)
        self._tm = ThemeManager.instance()
        self._workers: dict[str, InstallWorker] = {}
        self._current_section: str = "all"
        self.init_ui()
        self._apply_theme()

        # 0. Sincronización dinámica del Catálogo Remoto (catalog.json) + Live Polling
        self._last_catalog_sha: str = ""
        self.catalog_sync_thread = None
        self._trigger_catalog_sync(manual=False)

        self._catalog_poll_timer = QTimer(self)
        self._catalog_poll_timer.setInterval(6000)
        self._catalog_poll_timer.timeout.connect(self._on_auto_catalog_poll)
        self._catalog_poll_timer.start()

        # 1. Actualizaciones Launcher
        self.update_thread = CheckUpdateThread(self)
        self.update_thread.update_available.connect(self.show_update_dialog)
        self.update_thread.latest_version_detected.connect(self._on_launcher_version_detected)
        self.update_thread.start()

        # 2. Actualizaciones micro-apps
        self.micro_apps_updater = CheckMicroAppUpdatesThread(self, apps_snapshot=dict(APP_REGISTRY))
        self.micro_apps_updater.update_found.connect(self._on_micro_app_update_found)
        self.micro_apps_updater.status_changed.connect(self._on_update_check_status_changed)
        self.micro_apps_updater.start()

        # 3. Consulta de tamaño de cada aplicación (Issue #4)
        self.sizes_thread = FetchAppSizesThread(self, apps_snapshot=dict(APP_REGISTRY), only_missing=True)
        self.sizes_thread.sizes_fetched.connect(self._on_app_sizes_fetched)
        self.sizes_thread.start()

    def _on_auto_catalog_poll(self):
        """Sincronización silenciosa en tiempo real cada 6s cuando no hay descargas en curso."""
        if self._workers:
            return
        self._trigger_catalog_sync(manual=False)

    def _trigger_catalog_sync(self, manual: bool = False):
        if self.catalog_sync_thread and self.catalog_sync_thread.isRunning():
            return
        if manual:
            SoundManager.instance().play("click")
            if hasattr(self, "sync_btn"):
                self.sync_btn.setEnabled(False)
                self.sync_btn.setText(t("btn_syncing"))
        self.catalog_sync_thread = SyncCatalogThread(
            self,
            known_sha=self._last_catalog_sha,
            manual=manual,
        )
        self.catalog_sync_thread.catalog_payload_ready.connect(self._on_catalog_payload_ready)
        self.catalog_sync_thread.start()

    def _on_catalog_payload_ready(self, catalog_data: object, latest_sha: str, manual: bool = False):
        if hasattr(self, "sync_btn"):
            self.sync_btn.setEnabled(True)
            self.sync_btn.setText(t("btn_sync_catalog"))

        if latest_sha:
            self._last_catalog_sha = latest_sha

        changed = False
        if isinstance(catalog_data, dict):
            # Mutar APP_REGISTRY exclusivamente en el hilo principal de Qt (thread-safe)
            changed = apply_catalog_dict(catalog_data)

        if changed and not self._workers:
            self.rebuild_catalog_ui()
            if not getattr(self, "sizes_thread", None) or not self.sizes_thread.isRunning():
                self.sizes_thread = FetchAppSizesThread(
                    self,
                    apps_snapshot=dict(APP_REGISTRY),
                    only_missing=True,
                )
                self.sizes_thread.sizes_fetched.connect(self._on_app_sizes_fetched)
                self.sizes_thread.start()
        elif manual:
            self._update_dock_status()
            self._refresh_sections_visibility()

    def show_update_dialog(self, version, description, download_url, size_mb):
        dialog = UpdateDialog(version, description, download_url, size_mb, self)
        dialog.exec()

    def _on_launcher_version_detected(self, latest_ver: str):
        # Si la versión local es menor o coincide, actualizamos el header
        curr = get_launcher_version()
        self.subtitle_label.setText(t("app_subtitle", version=curr))

    def _on_update_check_status_changed(self, msg: str):
        if not hasattr(self, "loading_banner"):
            return
        if msg:
            self._is_checking_updates = True
            self.loading_banner.show_message(msg, t("overlay_wait"))
            self._reposition_loading_banner()
        else:
            self._is_checking_updates = False
            self._update_loading_banner_visibility()

    def _update_loading_banner_visibility(self):
        if not hasattr(self, "loading_banner"):
            return
        workers_count = len(self._workers)
        if workers_count >= 2:
            self.loading_banner.show_message(
                t("overlay_installing_multiple", count=workers_count),
                t("overlay_wait")
            )
            self._reposition_loading_banner()
        elif getattr(self, "_is_checking_updates", False):
            self.loading_banner.show_message(t("overlay_checking_updates"), t("overlay_wait"))
            self._reposition_loading_banner()
        else:
            self.loading_banner.hide_overlay()

    def _reposition_loading_banner(self):
        if hasattr(self, "loading_banner") and self.loading_banner.isVisible():
            w = min(620, self.width() - 80)
            h = 54
            x = (self.width() - w) // 2
            # Ubicar arriba del dock footer con margen
            y = self.height() - h - 55
            self.loading_banner.setGeometry(x, y, w, h)
            self.loading_banner.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_loading_banner()

    def _on_micro_app_update_found(self, app_id: str, new_version: str):
        card = self._card_dict.get(app_id)
        if card:
            card.set_update_available(new_version)
            card.apply_styles(self._tm.hub_styles())
        self._update_dock_status()

    def _on_app_sizes_fetched(self, sizes: dict):
        """Actualiza el texto de las tarjetas con el tamaño real de cada app."""
        for card in self._card_dict.values():
            card.refresh_state()
            card.apply_styles(self._tm.hub_styles())

    # ── UI Layout ─────────────────────────────────────────────────────────────

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(36, 26, 36, 26)
        main_layout.setSpacing(20)

        # Header Bento
        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(2)

        current_ver = get_launcher_version()
        self.title_label = QLabel("Media Hub")
        self.title_label.setObjectName("hubTitle")
        self.subtitle_label = QLabel(f"Suite integral de herramientas y conversores multimedia • {current_ver}")
        self.subtitle_label.setObjectName("hubSubtitle")

        header_text_layout.addWidget(self.title_label)
        header_text_layout.addWidget(self.subtitle_label)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()

        # Barra de Búsqueda Rápida de Herramientas
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(t("search_placeholder"))
        self.search_input.setFixedWidth(160)
        self.search_input.setFixedHeight(34)
        self.search_input.textChanged.connect(self._filter_cards)
        header_layout.addWidget(self.search_input)

        self.sync_btn = QPushButton()
        self.sync_btn.setObjectName("hubSyncBtn")
        self.sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_btn.clicked.connect(lambda: self._trigger_catalog_sync(manual=True))
        header_layout.addWidget(self.sync_btn)

        self.sound_btn = QPushButton()
        self.sound_btn.setObjectName("hubSoundBtn")
        self.sound_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sound_btn.clicked.connect(self._toggle_sound)
        header_layout.addWidget(self.sound_btn)

        self.lang_btn = QPushButton()
        self.lang_btn.setObjectName("hubLangBtn")
        self.lang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_btn.clicked.connect(self._toggle_language)
        header_layout.addWidget(self.lang_btn)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_dark_mode)
        header_layout.addWidget(self.toggle_btn)

        main_layout.addLayout(header_layout)

        # ── Contenedor Principal: Sidebar de Secciones + Área de Contenido Bento ──
        body_layout = QHBoxLayout()
        body_layout.setSpacing(20)

        # 1. Sidebar Lateral de Secciones (Issue #53)
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("hubSidebar")
        self.sidebar_frame.setFixedWidth(220)
        self.sidebar_layout = QVBoxLayout(self.sidebar_frame)
        self.sidebar_layout.setContentsMargins(12, 16, 12, 16)
        self.sidebar_layout.setSpacing(6)

        self.sidebar_title_lbl = QLabel(t("sidebar_header"))
        self.sidebar_layout.addWidget(self.sidebar_title_lbl)

        self._sidebar_btns: dict[str, QPushButton] = {}
        self.sidebar_sep = QFrame()
        self.sidebar_sep.setFixedHeight(1)
        self._sync_sidebar_category_buttons()

        body_layout.addWidget(self.sidebar_frame)

        # 2. Área Desplazable con Secciones y Tarjetas Bento
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("hubScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.verticalScrollBar().setSingleStep(20)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("hubScrollContent")
        self.scroll_content.setStyleSheet("background: transparent;")

        self.sections_layout = QVBoxLayout(self.scroll_content)
        self.sections_layout.setSpacing(24)
        self.sections_layout.setContentsMargins(0, 2, 8, 12)
        self.sections_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._card_dict: dict[str, AppCard] = {}
        self._section_blocks: dict[str, dict] = {}
        self._populate_sections_content()

        self.scroll_area.setWidget(self.scroll_content)
        body_layout.addWidget(self.scroll_area, 1)
        main_layout.addLayout(body_layout, 1)

        # Footer Dock Bento
        self.footer_dock = QFrame()
        self.footer_dock.setObjectName("footerDock")
        dock_layout = QHBoxLayout(self.footer_dock)
        dock_layout.setContentsMargins(16, 8, 16, 8)

        self.dock_status_label = QLabel("● Todas las aplicaciones están gestionadas de forma aislada")
        self.dock_status_label.setObjectName("dockText")
        dock_layout.addWidget(self.dock_status_label)
        dock_layout.addStretch()

        self.admin_panel_btn = QPushButton(t("dock_admin_panel"))
        self.admin_panel_btn.setObjectName("dockLink")
        self.admin_panel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.admin_panel_btn.setToolTip(t("dock_admin_panel_tooltip"))
        self.admin_panel_btn.clicked.connect(self._open_admin_panel)
        # Solo visible si se detecta autenticación de administrador (Issue: admin privado)
        if not self._is_admin_user():
            self.admin_panel_btn.hide()
        dock_layout.addWidget(self.admin_panel_btn)

        self.feedback_btn = QPushButton(t("dock_feedback"))
        self.feedback_btn.setObjectName("dockLink")
        self.feedback_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.feedback_btn.setToolTip("Danos tu opinión o reporta errores para seguir mejorando Media Hub")
        self.feedback_btn.clicked.connect(self._open_feedback_form)
        dock_layout.addWidget(self.feedback_btn)

        self.dock_folder_btn = QPushButton(t("dock_folder"))
        self.dock_folder_btn.setObjectName("dockLink")
        self.dock_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dock_folder_btn.clicked.connect(self._open_apps_folder)
        dock_layout.addWidget(self.dock_folder_btn)

        main_layout.addWidget(self.footer_dock)

        # Overlay flotante de Carga / Espera (Issue #89)
        self.loading_banner = LoadingBannerOverlay(central_widget)

        self._update_dock_status()
        self._refresh_sections_visibility()

    def _populate_sections_content(self):
        """Construye dinámicamente los bloques de secciones y tarjetas desde APP_REGISTRY."""
        while self.sections_layout.count():
            item = self.sections_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        self._card_dict.clear()
        self._section_blocks.clear()
        self.lbl_games_empty_title = None
        self.lbl_games_empty_desc = None

        curr_lang = get_current_language()
        # Obtener secciones de contenido dinámicamente desde SECTION_CATEGORIES (omitiendo 'all' e 'installed')
        reserved_sec = {"all", "installed"}
        content_sections = [sid for sid in SECTION_CATEGORIES.keys() if sid not in reserved_sec]
        if not content_sections:
            content_sections = ["tools", "studio", "admin", "games"]

        # Reconstruir botones del Sidebar si cambiaron las categorías
        self._sync_sidebar_category_buttons()

        for sec_id in content_sections:
            sec_meta = get_section_metadata(sec_id, curr_lang)
            sec_widget = QWidget()
            sec_vbox = QVBoxLayout(sec_widget)
            sec_vbox.setContentsMargins(0, 0, 0, 0)
            sec_vbox.setSpacing(10)

            hdr_top = QHBoxLayout()
            hdr_top.setSpacing(10)
            lbl_sec_title = QLabel(f"{sec_meta['icon']}  {sec_meta['name']}")
            lbl_sec_badge = QLabel("0")
            div_line = QFrame()
            div_line.setFixedHeight(1)

            hdr_top.addWidget(lbl_sec_title)
            hdr_top.addWidget(lbl_sec_badge)
            hdr_top.addWidget(div_line, 1)
            sec_vbox.addLayout(hdr_top)

            lbl_sec_desc = QLabel(sec_meta["description"])
            lbl_sec_desc.setWordWrap(True)
            sec_vbox.addWidget(lbl_sec_desc)

            sec_grid = QGridLayout()
            sec_grid.setSpacing(16)
            sec_grid.setContentsMargins(0, 4, 0, 0)
            sec_grid.setColumnStretch(0, 11)
            sec_grid.setColumnStretch(1, 10)
            sec_grid.setColumnStretch(2, 10)

            sec_apps = [
                (aid, rmeta) for aid, rmeta in APP_REGISTRY.items()
                if rmeta.get("category", "tools") == sec_id
            ]

            has_hero_in_sec = any(rm.get("is_hero", False) for _, rm in sec_apps)
            hero_slots = [
                (0, 1), (0, 2),
                (1, 1), (1, 2),
                (2, 0), (2, 1), (2, 2),
                (3, 0), (3, 1), (3, 2),
                (4, 0), (4, 1), (4, 2),
                (5, 0), (5, 1), (5, 2),
            ]
            normal_slots = [
                (r, c) for r in range(10) for c in range(3)
            ]
            slot_idx = 0

            for app_id, raw_meta in sec_apps:
                meta = get_app_metadata(app_id, curr_lang)
                is_hero = raw_meta.get("is_hero", False)
                is_disabled = raw_meta.get("is_disabled", False)
                card = AppCard(
                    card_id=app_id,
                    title=meta.get("name", app_id),
                    subtitle=meta.get("description", ""),
                    icon_file=raw_meta.get("icon", "media.png"),
                    badge_text=meta.get("badge", ""),
                    is_hero=is_hero,
                    is_disabled=is_disabled,
                )
                card.action_btn.clicked.connect(lambda checked, aid=app_id: self._handle_card(aid))
                self._card_dict[app_id] = card

                if is_hero:
                    sec_grid.addWidget(card, 0, 0, 2, 1)
                else:
                    slots = hero_slots if has_hero_in_sec else normal_slots
                    if slot_idx < len(slots):
                        r, c = slots[slot_idx]
                        sec_grid.addWidget(card, r, c)
                        slot_idx += 1

            empty_placeholder = None
            if sec_id == "games" and not sec_apps:
                empty_placeholder = QFrame()
                empty_placeholder.setObjectName("appCardDisabled")
                ep_lay = QVBoxLayout(empty_placeholder)
                ep_lay.setContentsMargins(24, 20, 24, 20)
                ep_lay.setSpacing(6)
                self.lbl_games_empty_title = QLabel(t("games_empty_title"))
                self.lbl_games_empty_desc = QLabel(t("games_empty_desc"))
                self.lbl_games_empty_desc.setWordWrap(True)
                ep_lay.addWidget(self.lbl_games_empty_title)
                ep_lay.addWidget(self.lbl_games_empty_desc)
                sec_grid.addWidget(empty_placeholder, 0, 0, 1, 3)

            sec_vbox.addLayout(sec_grid)
            self.sections_layout.addWidget(sec_widget)

            self._section_blocks[sec_id] = {
                "widget": sec_widget,
                "lbl_title": lbl_sec_title,
                "lbl_badge": lbl_sec_badge,
                "div_line": div_line,
                "lbl_desc": lbl_sec_desc,
                "app_ids": [aid for aid, _ in sec_apps],
                "empty_placeholder": empty_placeholder,
            }

        self.installed_empty_card = QFrame()
        self.installed_empty_card.setObjectName("appCardDisabled")
        ie_lay = QVBoxLayout(self.installed_empty_card)
        ie_lay.setContentsMargins(24, 22, 24, 22)
        ie_lay.setSpacing(6)
        self.lbl_inst_empty_title = QLabel(t("installed_empty_title"))
        self.lbl_inst_empty_desc = QLabel(t("installed_empty_desc"))
        self.lbl_inst_empty_desc.setWordWrap(True)
        ie_lay.addWidget(self.lbl_inst_empty_title)
        ie_lay.addWidget(self.lbl_inst_empty_desc)
        self.installed_empty_card.hide()
        self.sections_layout.addWidget(self.installed_empty_card)
        self.sections_layout.addStretch()

    def rebuild_catalog_ui(self):
        """Reconstruye en caliente las tarjetas y secciones sin parpadeo y preservando el scroll."""
        vbar = self.scroll_area.verticalScrollBar() if hasattr(self, "scroll_area") else None
        saved_scroll = vbar.value() if vbar is not None else 0

        self.scroll_content.setUpdatesEnabled(False)
        try:
            self._populate_sections_content()
            self._apply_theme()
        finally:
            self.scroll_content.setUpdatesEnabled(True)

        if vbar is not None:
            QTimer.singleShot(0, lambda pos=saved_scroll: vbar.setValue(pos))

    def _is_admin_user(self) -> bool:
        """Determina si el usuario actual es administrador (cuenta con GitHub CLI o token configurado)."""
        if os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
            return True
        admin_flag = os.path.join(get_hub_data_dir(), "admin_mode")
        if os.path.isfile(admin_flag):
            return True
        try:
            cflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            tok = subprocess.check_output(
                ["gh", "auth", "token"],
                text=True,
                timeout=2,
                creationflags=cflags,
            ).strip()
            return bool(tok)
        except Exception:
            return False

    def _open_admin_panel(self):
        SoundManager.instance().play("click")
        url = ADMIN_PANEL_URL
        tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        if not tok:
            try:
                cflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                tok = subprocess.check_output(
                    ["gh", "auth", "token"],
                    text=True,
                    timeout=3,
                    creationflags=cflags,
                ).strip()
            except Exception:
                tok = ""
        if tok:
            url = f"{ADMIN_PANEL_URL}#token={tok}"
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _select_section(self, section_id: str):
        SoundManager.instance().play("click")
        self._current_section = section_id
        self._refresh_sections_visibility()
        self._style_sidebar_buttons(self._tm.hub_styles())

    def _filter_cards(self, query: str):
        self._refresh_sections_visibility()

    def _refresh_sections_visibility(self):
        query = self.search_input.text().strip().lower()
        curr_lang = get_current_language()
        sec_filter = self._current_section

        total_installed_visible = 0

        for sec_id, block in self._section_blocks.items():
            app_ids = block["app_ids"]
            visible_in_sec = 0

            for app_id in app_ids:
                card = self._card_dict.get(app_id)
                if not card:
                    continue
                meta = get_app_metadata(app_id, curr_lang)
                name = meta.get("name", "").lower()
                desc = meta.get("description", "").lower()
                badge = meta.get("badge", "").lower()

                match_query = (not query) or (query in name) or (query in desc) or (query in badge) or (query in app_id)
                if query or sec_filter == "all":
                    match_sec = True
                elif sec_filter == "installed":
                    match_sec = get_app_exe(app_id) is not None
                else:
                    match_sec = (sec_id == sec_filter)

                is_vis = match_query and match_sec
                card.setVisible(is_vis)
                if is_vis:
                    visible_in_sec += 1
                    if sec_filter == "installed":
                        total_installed_visible += 1

            block["lbl_badge"].setText(str(len(app_ids)))

            if sec_id == "games" and not app_ids:
                # La sección de juegos muestra su banner informativo en 'all' o 'games' si no hay búsqueda activa
                show_games_sec = (sec_filter in ("all", "games")) and (not query or "juego" in query or "game" in query)
                block["widget"].setVisible(show_games_sec)
            else:
                block["widget"].setVisible(visible_in_sec > 0)

        self.installed_empty_card.setVisible(sec_filter == "installed" and total_installed_visible == 0)
        self._update_sidebar_texts()

    def _sync_sidebar_category_buttons(self):
        """Sincroniza y reordena dinámicamente los botones de categorías del sidebar según SECTION_CATEGORIES."""
        if not hasattr(self, "sidebar_layout"):
            return

        # Limpiar layout del sidebar preservando título
        while self.sidebar_layout.count() > 1:
            it = self.sidebar_layout.takeAt(1)
            w = it.widget()
            if w is not None and w is not self.sidebar_title_lbl:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        self._sidebar_btns.clear()

        # Determinar orden dinámico de categorías
        sidebar_order = ["all"]
        reserved = {"all", "installed"}
        for sid in SECTION_CATEGORIES.keys():
            if sid not in reserved and sid not in sidebar_order:
                sidebar_order.append(sid)

        for sec_id in sidebar_order:
            btn = QPushButton()
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, sid=sec_id: self._select_section(sid))
            self.sidebar_layout.addWidget(btn)
            self._sidebar_btns[sec_id] = btn

        self.sidebar_sep = QFrame()
        self.sidebar_sep.setFixedHeight(1)
        self.sidebar_layout.addSpacing(4)
        self.sidebar_layout.addWidget(self.sidebar_sep)
        self.sidebar_layout.addSpacing(4)

        btn_inst = QPushButton()
        btn_inst.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_inst.clicked.connect(lambda checked: self._select_section("installed"))
        self.sidebar_layout.addWidget(btn_inst)
        self._sidebar_btns["installed"] = btn_inst

        self.sidebar_layout.addStretch()

    def _update_sidebar_texts(self):
        curr_lang = get_current_language()
        self.sidebar_title_lbl.setText(t("sidebar_header"))

        counts = {
            "all": len(APP_REGISTRY),
            "installed": sum(1 for aid in APP_REGISTRY if get_app_exe(aid) is not None),
        }
        for sec_id in SECTION_CATEGORIES.keys():
            if sec_id not in ("all", "installed"):
                counts[sec_id] = sum(1 for v in APP_REGISTRY.values() if v.get("category") == sec_id)

        for sec_id, btn in self._sidebar_btns.items():
            meta = get_section_metadata(sec_id, curr_lang)
            c = counts.get(sec_id, 0)
            count_str = f"  ({c})" if c > 0 or sec_id == "installed" else ""
            btn.setText(f"{meta['icon']}   {meta['name']}{count_str}")

    def _style_sidebar_buttons(self, styles: dict):
        for sec_id, btn in self._sidebar_btns.items():
            if sec_id == self._current_section:
                btn.setStyleSheet(styles["sidebar_btn_active"])
            else:
                btn.setStyleSheet(styles["sidebar_btn"])

    def _open_feedback_form(self):
        try:
            webbrowser.open("https://forms.gle/ECL2mwc8iH5UXkos9")
        except Exception as e:
            QMessageBox.information(
                self, "Encuesta de Satisfacción",
                f"Puedes acceder a la encuesta desde tu navegador en:\nhttps://forms.gle/ECL2mwc8iH5UXkos9"
            )

    def _open_apps_folder(self):
        path = get_apps_install_dir()
        try:
            os.startfile(path)
        except Exception as e:
            QMessageBox.warning(self, "Aviso", f"No se pudo abrir la carpeta:\n{e}")

    def _update_dock_status(self):
        installed = load_installed_versions()
        count = len(installed)
        total = len(APP_REGISTRY)
        updates_pending = sum(1 for c in self._card_dict.values() if getattr(c, "_pending_update_version", None))

        # Calcular tamaño ocupado en ~/.mediahub/apps
        apps_dir = get_apps_install_dir()
        size_mb = 0.0
        try:
            for root, dirs, files in os.walk(apps_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    if os.path.isfile(fp):
                        size_mb += os.path.getsize(fp)
            size_mb = size_mb / (1024 * 1024)
        except Exception:
            pass

        size_str = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_mb/1024:.2f} GB"

        if updates_pending > 0:
            self.dock_status_label.setText(t("dock_updates", count=updates_pending, size=size_str))
        else:
            self.dock_status_label.setText(t("dock_installed", count=count, total=total, size=size_str))

    # ── Card Handler ─────────────────────────────────────────────────────────

    def _handle_card(self, app_id: str):
        SoundManager.instance().play("click")
        card = self._card_dict.get(app_id)
        if not card:
            return
        state = getattr(card, "_btn_state", "disabled")
        if state == "open":
            launch_app(app_id)
        elif state in ("install", "update"):
            self._start_install_or_update(app_id)

    def _start_install_or_update(self, app_id: str):
        if app_id in self._workers:
            return

        reg = APP_REGISTRY.get(app_id)
        if not reg:
            return

        curr_lang = get_current_language()
        meta = get_app_metadata(app_id, curr_lang)
        app_name = meta.get("name", reg.get("name", app_id))

        # Diálogo para definir el idioma único de instalación (Issue #5)
        lang_dialog = QMessageBox(self)
        lang_dialog.setWindowTitle(t("dialog_choose_lang_title"))
        lang_dialog.setText(t("dialog_choose_lang_msg", name=app_name))
        es_btn = lang_dialog.addButton(t("lang_name_es"), QMessageBox.ButtonRole.ActionRole)
        en_btn = lang_dialog.addButton(t("lang_name_en"), QMessageBox.ButtonRole.ActionRole)
        cancel_btn = lang_dialog.addButton(QMessageBox.StandardButton.Cancel)

        if curr_lang == "en":
            lang_dialog.setDefaultButton(en_btn)
        else:
            lang_dialog.setDefaultButton(es_btn)

        lang_dialog.exec()
        clicked = lang_dialog.clickedButton()
        if clicked == cancel_btn or not clicked:
            return

        target_lang = "es" if clicked == es_btn else "en"

        card = self._card_dict[app_id]
        card.action_btn.setEnabled(False)
        card._status_label.setText("Descargando…" if curr_lang == "es" else "Downloading…")

        worker = InstallWorker(app_id, target_lang=target_lang, parent=self)
        worker.progress.connect(lambda pct, msg: self._on_install_progress(app_id, pct, msg))
        worker.finished.connect(self._on_install_done)
        worker.error.connect(lambda err: self._on_install_error(app_id, err))
        self._workers[app_id] = worker
        self._update_loading_banner_visibility()
        worker.start()

    def _on_install_progress(self, app_id: str, pct: int, msg: str):
        card = self._card_dict.get(app_id)
        if card:
            card._status_label.setText(f"{pct}%")

    def _on_install_done(self, app_id: str, name: str):
        SoundManager.instance().play("success")
        self._workers.pop(app_id, None)
        self._update_loading_banner_visibility()
        card = self._card_dict.get(app_id)
        if card:
            card._pending_update_version = None
            card.refresh_state()
            styles = self._tm.hub_styles()
            card.apply_styles(styles)
        self._update_dock_status()
        self._refresh_sections_visibility()

        # Preguntar al usuario si desea crear un acceso directo en el escritorio (Issue #3)
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(t("dialog_install_done_title"))
        msg_box.setText(t("dialog_install_done_msg", name=name))
        msg_box.setInformativeText(t("dialog_install_done_shortcut_prompt"))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        yes_btn = msg_box.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText(t("btn_yes_shortcut"))
        no_btn = msg_box.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText(t("btn_no_shortcut"))
        
        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.Yes:
            if create_desktop_shortcut(app_id):
                QMessageBox.information(
                    self, t("dialog_shortcut_created_title"),
                    t("dialog_shortcut_created_msg", name=name)
                )

    def _on_install_error(self, app_id: str, err: str):
        self._workers.pop(app_id, None)
        self._update_loading_banner_visibility()
        card = self._card_dict.get(app_id)
        if card:
            card.refresh_state()
            styles = self._tm.hub_styles()
            card.apply_styles(styles)
        QMessageBox.critical(self, "Error de instalación", err)

    def _change_app_language(self, app_id: str):
        reg = APP_REGISTRY.get(app_id)
        if not reg:
            return
        curr_lang = get_current_language()
        meta = get_app_metadata(app_id, curr_lang)
        app_name = meta.get("name", reg.get("name", app_id))
        app_dir = reg.get("dir", app_id)
        current_app_lang = get_app_language(app_dir)

        lang_dialog = QMessageBox(self)
        lang_dialog.setWindowTitle(t("dialog_choose_lang_title"))
        lang_dialog.setText(t("dialog_choose_lang_msg", name=app_name))
        es_btn = lang_dialog.addButton(t("lang_name_es"), QMessageBox.ButtonRole.ActionRole)
        en_btn = lang_dialog.addButton(t("lang_name_en"), QMessageBox.ButtonRole.ActionRole)
        cancel_btn = lang_dialog.addButton(QMessageBox.StandardButton.Cancel)

        if current_app_lang == "en":
            lang_dialog.setDefaultButton(en_btn)
        else:
            lang_dialog.setDefaultButton(es_btn)

        lang_dialog.exec()
        clicked = lang_dialog.clickedButton()
        if clicked == cancel_btn or not clicked:
            return

        chosen_lang = "es" if clicked == es_btn else "en"
        save_app_language(app_dir, chosen_lang)
        lang_label = t("lang_name_es") if chosen_lang == "es" else t("lang_name_en")
        QMessageBox.information(
            self,
            t("dialog_lang_updated_title"),
            t("dialog_lang_updated_msg", name=app_name, lang_name=lang_label)
        )

    def _reinstall_app(self, app_id: str):
        reg = APP_REGISTRY.get(app_id)
        app_name = reg["name"] if reg else app_id
        reply = QMessageBox.question(
            self,
            t("dialog_reinstall_title"),
            t("dialog_reinstall_msg", name=app_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_install_or_update(app_id)

    def _create_shortcut(self, app_id: str):
        reg = APP_REGISTRY.get(app_id, {})
        name = reg.get("name", app_id)
        if create_desktop_shortcut(app_id):
            QMessageBox.information(
                self, t("dialog_shortcut_created_title"),
                t("dialog_shortcut_created_msg", name=name)
            )
        else:
            QMessageBox.warning(
                self, "Aviso",
                f"No se pudo crear el acceso directo para {name}."
            )

    def _remove_shortcut(self, app_id: str):
        reg = APP_REGISTRY.get(app_id, {})
        name = reg.get("name", app_id)
        if remove_desktop_shortcut(app_id):
            QMessageBox.information(
                self, t("dialog_shortcut_removed_title"),
                t("dialog_shortcut_removed_msg", name=name)
            )

    def _uninstall_app(self, app_id: str):
        reg = APP_REGISTRY.get(app_id)
        if not reg:
            return
        app_name = reg["name"]

        reply = QMessageBox.question(
            self,
            t("dialog_uninstall_title"),
            t("dialog_uninstall_msg", name=app_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        install_base = get_apps_install_dir()
        app_dir = os.path.join(install_base, reg["dir"])

        try:
            if os.path.exists(app_dir):
                shutil.rmtree(app_dir)
            remove_installed_version(app_id)
            remove_desktop_shortcut(app_id)
            card = self._card_dict.get(app_id)
            if card:
                card._pending_update_version = None
                card.refresh_state()
                card.apply_styles(self._tm.hub_styles())
            self._update_dock_status()
            self._refresh_sections_visibility()
            QMessageBox.information(
                self,
                t("dialog_uninstall_done_title"),
                t("dialog_uninstall_done_msg", name=app_name)
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error al desinstalar",
                f"No se pudo completar la desinstalación de {app_name}:\n{e}\n\n"
                "Asegúrate de que la aplicación no esté abierta en segundo plano."
            )

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _toggle_sound(self):
        SoundManager.instance().toggle()
        self._apply_theme()

    def _toggle_language(self):
        SoundManager.instance().play("click")
        new_lang = "en" if get_current_language() == "es" else "es"
        save_current_language(new_lang)
        self._apply_theme()

    def _toggle_dark_mode(self):
        SoundManager.instance().play("click")
        self._tm.toggle()
        self._apply_theme()

    def _apply_theme(self):
        styles = self._tm.hub_styles()
        self.setStyleSheet(styles["window"])
        self.title_label.setStyleSheet(styles["title"])
        self.subtitle_label.setStyleSheet(styles["header_sub"])

        curr = get_launcher_version()
        self.subtitle_label.setText(t("app_subtitle", version=curr))
        self.search_input.setPlaceholderText(t("search_placeholder"))
        self.search_input.setStyleSheet(styles.get("search_input", ""))

        # Botón de sincronización de catálogo
        self.sync_btn.setStyleSheet(styles["toggle_btn"])
        self.sync_btn.setText(t("btn_sync_catalog"))
        self.sync_btn.setToolTip(t("btn_sync_catalog_tooltip"))

        # Botón de sonido
        sound_enabled = SoundManager.instance().is_enabled()
        self.sound_btn.setStyleSheet(styles["toggle_btn"])
        self.sound_btn.setText(t("btn_sound_on") if sound_enabled else t("btn_sound_off"))
        self.sound_btn.setToolTip(t("btn_sound_tooltip"))

        # Botón de idioma
        curr_lang = get_current_language()
        self.lang_btn.setStyleSheet(styles["toggle_btn"])
        self.lang_btn.setText("English" if curr_lang == "es" else "Español")
        self.lang_btn.setToolTip("Cambiar idioma / Switch language")

        self.toggle_btn.setStyleSheet(styles["toggle_btn"])
        self.toggle_btn.setText(
            t("btn_light_mode") if self._tm.is_dark else t("btn_dark_mode"))
        self.scroll_area.setStyleSheet(styles.get("scroll_area", ""))
        self.footer_dock.setStyleSheet(styles["dock"])

        self.admin_panel_btn.setText(t("dock_admin_panel"))
        self.admin_panel_btn.setToolTip(t("dock_admin_panel_tooltip"))
        self.feedback_btn.setText(t("dock_feedback"))
        self.feedback_btn.setToolTip(t("dock_feedback_tooltip"))
        self.dock_folder_btn.setText(t("dock_folder"))

        # Aplicar estilos al Sidebar y Cabeceras de Sección (Issue #53)
        self.sidebar_frame.setStyleSheet(styles["sidebar"])
        self.sidebar_title_lbl.setStyleSheet(styles["sidebar_label"])
        self.sidebar_sep.setStyleSheet(styles["section_divider"])
        self._update_sidebar_texts()
        self._style_sidebar_buttons(styles)

        for sec_id, block in self._section_blocks.items():
            sec_meta = get_section_metadata(sec_id, curr_lang)
            block["lbl_title"].setText(f"{sec_meta['icon']}  {sec_meta['name']}")
            block["lbl_title"].setStyleSheet(styles["section_header_title"])
            block["lbl_badge"].setStyleSheet(styles["tag_badge"])
            block["div_line"].setStyleSheet(styles["section_divider"])
            block["lbl_desc"].setText(sec_meta["description"])
            block["lbl_desc"].setStyleSheet(styles["section_header_desc"])
            if block.get("empty_placeholder") is not None:
                block["empty_placeholder"].setStyleSheet(styles["card_disabled"])

        if getattr(self, "lbl_games_empty_title", None) is not None:
            self.lbl_games_empty_title.setText(t("games_empty_title"))
            self.lbl_games_empty_title.setStyleSheet(styles["card_title"])
            self.lbl_games_empty_desc.setText(t("games_empty_desc"))
            self.lbl_games_empty_desc.setStyleSheet(styles["card_subtitle"])

        self.installed_empty_card.setStyleSheet(styles["card_disabled"])
        self.lbl_inst_empty_title.setText(t("installed_empty_title"))
        self.lbl_inst_empty_title.setStyleSheet(styles["card_title"])
        self.lbl_inst_empty_desc.setText(t("installed_empty_desc"))
        self.lbl_inst_empty_desc.setStyleSheet(styles["card_subtitle"])

        self._update_dock_status()
        self._refresh_sections_visibility()

        if hasattr(self, "loading_banner"):
            self.loading_banner.apply_styles(is_dark=self._tm.is_dark)

        for card in self._card_dict.values():
            card.update_texts()
            card.apply_styles(styles)
