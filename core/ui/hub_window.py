import webbrowser
import os
import sys
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
    QMenu, QLineEdit, QScrollArea
)
from PyQt6.QtGui import QPixmap, QIcon, QColor, QDrag, QAction
from PyQt6.QtCore import QMimeData, Qt, QSize, QThread, pyqtSignal

from core.theme_manager import ThemeManager
from core.updater import CheckUpdateThread, UpdateDialog
from core.config import APP_REGISTRY, get_launcher_version, save_launcher_version, get_app_metadata
from core.i18n import t, get_current_language, save_current_language, save_app_language, get_app_language


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers de rutas, versiones y detección de instalación
# ─────────────────────────────────────────────────────────────────────────────

def get_asset_path(filename):
    """Devuelve la ruta absoluta de un asset del Launcher."""
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base_dir, "assets", "hub", filename)


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
        # Buscar icono si existe
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
            subprocess.Popen(
                [exe, f"--lang={app_lang}"],
                cwd=os.path.dirname(exe),
                env=env,
                creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
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

class CheckMicroAppUpdatesThread(QThread):
    """Verifica en segundo plano si alguna app instalada tiene una versión más nueva en GitHub."""
    update_found = pyqtSignal(str, str)  # (app_id, new_version)

    def run(self):
        installed = load_installed_versions()
        for app_id, cur_v in installed.items():
            reg = APP_REGISTRY.get(app_id)
            if not reg:
                continue
            try:
                url = f"https://api.github.com/repos/{reg['repo']}/releases/latest"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    tag = data.get("tag_name", "").lstrip("v")
                    if tag and tag != cur_v:
                        cur_parts = [int(x) for x in cur_v.split(".") if x.isdigit()]
                        tag_parts = [int(x) for x in tag.split(".") if x.isdigit()]
                        if tag_parts > cur_parts:
                            self.update_found.emit(app_id, tag)
            except Exception:
                pass


class FetchAppSizesThread(QThread):
    """Consulta en segundo plano el tamaño de descarga/release de cada app desde GitHub."""
    sizes_fetched = pyqtSignal(dict)  # {app_id: "143 MB"}

    def run(self):
        sizes = load_cached_sizes()
        changed = False
        for app_id, reg in APP_REGISTRY.items():
            repo = reg.get("repo")
            if not repo or reg.get("is_disabled"):
                continue
            try:
                url = f"https://api.github.com/repos/{repo}/releases/latest"
                resp = requests.get(url, timeout=6)
                if resp.status_code == 200:
                    data = resp.json()
                    for asset in data.get("assets", []):
                        if asset.get("name", "").endswith((".zip", ".exe")):
                            sz_bytes = asset.get("size", 0)
                            if sz_bytes > 0:
                                mb = sz_bytes / (1024 * 1024)
                                sz_str = f"{mb:.1f} MB" if mb < 1024 else f"{mb/1024:.2f} GB"
                                if sizes.get(app_id) != sz_str:
                                    sizes[app_id] = sz_str
                                    changed = True
                            break
            except Exception:
                pass
        if changed:
            save_cached_sizes(sizes)
        self.sizes_fetched.emit(sizes)


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

        try:
            r = requests.get(api_url, timeout=10)
            r.raise_for_status()
            release = r.json()
        except Exception as e:
            self.error.emit(f"No se pudo consultar el repositorio:\n{e}")
            return

        latest_tag = release.get("tag_name", "latest")
        assets = release.get("assets", [])

        asset = next((a for a in assets if a["name"].endswith(".zip")), None)
        if not asset:
            asset = next((a for a in assets if a["name"].endswith(".exe")), None)

        if not asset:
            self.error.emit(f"No se encontró instalador en el release {latest_tag}.")
            return

        download_url = asset["browser_download_url"]
        asset_name   = asset["name"]
        total        = asset.get("size", 0)

        self.progress.emit(10, f"Descargando {asset_name}…")
        tmp_file = os.path.join(tempfile.gettempdir(), asset_name)

        try:
            with requests.get(download_url, stream=True, timeout=30) as dl:
                dl.raise_for_status()
                downloaded = 0
                with open(tmp_file, "wb") as f:
                    for chunk in dl.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = 10 + int(downloaded / total * 70)
                            self.progress.emit(pct, f"Descargando… {downloaded // (1024*1024)} MB")
        except Exception as e:
            self.error.emit(f"Error al descargar:\n{e}")
            return

        self.progress.emit(85, "Instalando archivos…")
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

        self.progress.emit(100, t("status_ready"))
        curr_lang = get_current_language()
        meta = get_app_metadata(self.app_id, curr_lang)
        self.finished.emit(self.app_id, meta.get("name", reg.get("name", self.app_id)))


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

    def _show_options_menu(self):
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
        self.setMinimumSize(940, 620)
        self.resize(980, 680)
        self._tm = ThemeManager.instance()
        self._workers: dict[str, InstallWorker] = {}
        self.init_ui()
        self._apply_theme()

        # 1. Actualizaciones Launcher
        self.update_thread = CheckUpdateThread(self)
        self.update_thread.update_available.connect(self.show_update_dialog)
        self.update_thread.latest_version_detected.connect(self._on_launcher_version_detected)
        self.update_thread.start()

        # 2. Actualizaciones micro-apps
        self.micro_apps_updater = CheckMicroAppUpdatesThread(self)
        self.micro_apps_updater.update_found.connect(self._on_micro_app_update_found)
        self.micro_apps_updater.start()

        # 3. Consulta de tamaño de cada aplicación (Issue #4)
        self.sizes_thread = FetchAppSizesThread(self)
        self.sizes_thread.sizes_fetched.connect(self._on_app_sizes_fetched)
        self.sizes_thread.start()

    def show_update_dialog(self, version, description, download_url, size_mb):
        dialog = UpdateDialog(version, description, download_url, size_mb, self)
        dialog.exec()

    def _on_launcher_version_detected(self, latest_ver: str):
        # Si la versión local es menor o coincide, actualizamos el header
        curr = get_launcher_version()
        self.subtitle_label.setText(f"Suite integral de herramientas y conversores multimedia • {curr}")

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
        self.search_input.setFixedWidth(200)
        self.search_input.setFixedHeight(34)
        self.search_input.textChanged.connect(self._filter_cards)
        header_layout.addWidget(self.search_input)

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

        # Bento Grid Dinámico y Escalable con Scroll
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

        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setContentsMargins(0, 2, 8, 2)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._card_dict = {}

        # Generar tarjetas dinámicamente desde APP_REGISTRY
        # Slot 0 (Hero): 0, 0 span (2, 1)
        # Slots siguientes distribuidos en cuadrícula
        slot_positions = [
            (0, 1), (0, 2),
            (1, 1), (1, 2),
            (2, 0), (2, 1), (2, 2),
            (3, 0), (3, 1), (3, 2)
        ]
        slot_idx = 0

        curr_lang = get_current_language()
        for app_id, raw_meta in APP_REGISTRY.items():
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
                is_disabled=is_disabled
            )
            card.action_btn.clicked.connect(lambda checked, aid=app_id: self._handle_card(aid))
            self._card_dict[app_id] = card

            if is_hero:
                self.grid_layout.addWidget(card, 0, 0, 2, 1)
            else:
                if slot_idx < len(slot_positions):
                    r, c = slot_positions[slot_idx]
                    self.grid_layout.addWidget(card, r, c)
                    slot_idx += 1

        self.grid_layout.setColumnStretch(0, 11)
        self.grid_layout.setColumnStretch(1, 10)
        self.grid_layout.setColumnStretch(2, 10)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        # Footer Dock Bento
        self.footer_dock = QFrame()
        self.footer_dock.setObjectName("footerDock")
        dock_layout = QHBoxLayout(self.footer_dock)
        dock_layout.setContentsMargins(16, 8, 16, 8)

        self.dock_status_label = QLabel("● Todas las aplicaciones están gestionadas de forma aislada")
        self.dock_status_label.setObjectName("dockText")
        dock_layout.addWidget(self.dock_status_label)
        dock_layout.addStretch()

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
        self._update_dock_status()

    def _filter_cards(self, query: str):
        query = query.strip().lower()
        for app_id, card in self._card_dict.items():
            reg = APP_REGISTRY.get(app_id, {})
            name = reg.get("name", "").lower()
            desc = reg.get("description", "").lower()
            match = (not query) or (query in name) or (query in desc) or (query in app_id)
            card.setVisible(match)

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
        worker.start()

    def _on_install_progress(self, app_id: str, pct: int, msg: str):
        card = self._card_dict.get(app_id)
        if card:
            card._status_label.setText(f"{pct}%")

    def _on_install_done(self, app_id: str, name: str):
        self._workers.pop(app_id, None)
        card = self._card_dict.get(app_id)
        if card:
            card._pending_update_version = None
            card.refresh_state()
            styles = self._tm.hub_styles()
            card.apply_styles(styles)
        self._update_dock_status()
        
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

    def _toggle_language(self):
        new_lang = "en" if get_current_language() == "es" else "es"
        save_current_language(new_lang)
        self._apply_theme()

    def _toggle_dark_mode(self):
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

        self.feedback_btn.setText(t("dock_feedback"))
        self.feedback_btn.setToolTip(t("dock_feedback_tooltip"))
        self.dock_folder_btn.setText(t("dock_folder"))

        self._update_dock_status()

        for card in self._card_dict.values():
            card.update_texts()
            card.apply_styles(styles)
