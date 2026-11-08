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
    QMenu
)
from PyQt6.QtGui import QPixmap, QIcon, QColor, QDrag, QAction
from PyQt6.QtCore import QMimeData, Qt, QSize, QThread, pyqtSignal

from core.theme_manager import ThemeManager
from core.updater import CheckUpdateThread, UpdateDialog
from core.config import APP_REGISTRY, APP_VERSION


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


def launch_app(app_id: str):
    """Lanza la micro-app instalada como proceso independiente del sistema."""
    exe = get_app_exe(app_id)
    if exe and os.path.isfile(exe):
        try:
            os.startfile(exe)
        except Exception as e:
            QMessageBox.critical(
                None, "Error al abrir",
                f"No se pudo iniciar la aplicación:\n{e}\n\nRuta: {exe}"
            )
    else:
        QMessageBox.warning(
            None, "No instalada",
            "La aplicación aún no está instalada.\n"
            "Haz clic en 'Instalar' para descargarla automáticamente."
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


# ─────────────────────────────────────────────────────────────────────────────
#  Worker de descarga e instalación
# ─────────────────────────────────────────────────────────────────────────────

class InstallWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, str)
    error    = pyqtSignal(str)

    def __init__(self, app_id: str, parent=None):
        super().__init__(parent)
        self.app_id = app_id

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

        # Buscar asset .zip o .exe
        asset = next((a for a in assets if a["name"].endswith(".zip")), None)
        if not asset:
            asset = next((a for a in assets if a["name"].endswith(".exe")), None)

        if not asset:
            self.error.emit(f"No se encontró instalador en el release {latest_tag}.")
            return

        download_url = asset["browser_download_url"]
        asset_name   = asset["name"]
        total        = asset.get("size", 0)

        # Descarga
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

        # Instalar / Extraer de forma 100% limpia
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
        except Exception as e:
            self.error.emit(f"Error al instalar:\n{e}")
            return

        self.progress.emit(100, "¡Listo!")
        self.finished.emit(self.app_id, reg["name"])


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
        elif is_hero:
            self.setObjectName("appCardHero")
        else:
            self.setObjectName("appCard")

        # Layout Bento Moderno
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 20)
        main_layout.setSpacing(12)

        # Header de la tarjeta: Icono + Badge Tag
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

        # Botón secundario de opciones ⋮
        self.options_btn = QPushButton("⋮")
        self.options_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.options_btn.setFixedSize(30, 30)
        self.options_btn.setToolTip("Opciones (Reinstalar / Desinstalar)")
        self.options_btn.clicked.connect(self._show_options_menu)
        self.options_btn.hide()
        top_layout.addWidget(self.options_btn)

        main_layout.addLayout(top_layout)

        # Textos: Título y descripción
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

        # Footer de la tarjeta: Estado y Botón de Acción
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

        reinstall_act = menu.addAction("🔄  Reinstalar")
        reinstall_act.triggered.connect(lambda: self.window()._reinstall_app(self.card_id))

        uninstall_act = menu.addAction("🗑️  Desinstalar")
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

        if state == "open":
            self.action_btn.setText("Abrir")
            self.action_btn.setEnabled(True)
            v_text = f"v{cur_ver}" if cur_ver else ""
            self._status_label.setText(f"● Listo {v_text}".strip())
            self.options_btn.show()
        elif state == "update":
            self.action_btn.setText("Actualizar")
            self.action_btn.setEnabled(True)
            self._status_label.setText(f"↑ v{self._pending_update_version}")
            self.options_btn.show()
        elif state == "install":
            self.action_btn.setText("Instalar")
            self.action_btn.setEnabled(True)
            self._status_label.setText("No instalada")
            self.options_btn.hide()
        else:
            self.action_btn.setText("Próximamente")
            self.action_btn.setEnabled(False)
            self._status_label.setText("")
            self.options_btn.hide()

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
        # Proporción panorámica moderna 980x650
        self.setMinimumSize(940, 620)
        self.resize(980, 650)
        self._tm = ThemeManager.instance()
        self._workers: dict[str, InstallWorker] = {}
        self.init_ui()
        self._apply_theme()

        # 1. Actualizaciones Launcher
        self.update_thread = CheckUpdateThread(self)
        self.update_thread.update_available.connect(self.show_update_dialog)
        self.update_thread.start()

        # 2. Actualizaciones micro-apps
        self.micro_apps_updater = CheckMicroAppUpdatesThread(self)
        self.micro_apps_updater.update_found.connect(self._on_micro_app_update_found)
        self.micro_apps_updater.start()

    def show_update_dialog(self, version, description, download_url, size_mb):
        dialog = UpdateDialog(version, description, download_url, size_mb, self)
        dialog.exec()

    def _on_micro_app_update_found(self, app_id: str, new_version: str):
        card = self._card_dict.get(app_id)
        if card:
            card.set_update_available(new_version)
            card.apply_styles(self._tm.hub_styles())
        self._update_dock_status()

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

        self.title_label = QLabel("Media Hub")
        self.title_label.setObjectName("hubTitle")
        self.subtitle_label = QLabel(f"Suite integral de herramientas y conversores multimedia • {APP_VERSION}")
        self.subtitle_label.setObjectName("hubSubtitle")

        header_text_layout.addWidget(self.title_label)
        header_text_layout.addWidget(self.subtitle_label)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()

        # Conmutador Tema
        self.toggle_btn = QPushButton()
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_dark_mode)
        header_layout.addWidget(self.toggle_btn)

        main_layout.addLayout(header_layout)

        # Bento Grid
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(16)

        # 1. Hero Card: Multimedia Converter (Columna 0, fila 0, abarca 2 filas)
        self.media_card = AppCard(
            card_id="media",
            title="Multimedia Converter",
            subtitle="Video, Audio e Imagen con 9 herramientas profesionales integradas (Corte, GIF, Compresión, Fusión).",
            icon_file="media.png",
            badge_text="9 EN 1",
            is_hero=True
        )
        self.media_card.action_btn.clicked.connect(lambda: self._handle_card("media"))

        # 2. Document Converter (Columna 1, fila 0)
        self.docs_card = AppCard(
            card_id="docs",
            title="Document Converter",
            subtitle="Conversión inteligente entre PDF, Word, Excel, PowerPoint e imágenes a 300 DPI.",
            icon_file="docs.png",
            badge_text="OFICINA"
        )
        self.docs_card.action_btn.clicked.connect(lambda: self._handle_card("docs"))

        # 3. Link Converter (Columna 2, fila 0)
        self.link_card = AppCard(
            card_id="link",
            title="Link Converter",
            subtitle="Descarga por lotes desde YouTube, TikTok, Instagram y playlists con soporte paralelo.",
            icon_file="link_converter.webp",
            badge_text="BATCH"
        )
        self.link_card.action_btn.clicked.connect(lambda: self._handle_card("link"))

        # 4. Image Tools (Columna 1, fila 1)
        self.image_tools_card = AppCard(
            card_id="image_tools",
            title="Image Tools",
            subtitle="Borrador de fondos, escalador y marca de agua en lote para tus fotografías.",
            icon_file="quality.webp",
            badge_text="CREATIVO"
        )
        self.image_tools_card.action_btn.clicked.connect(lambda: self._handle_card("image_tools"))

        # 5. Subtitle Generator (Columna 2, fila 1)
        self.subtitle_card = AppCard(
            card_id="subtitle",
            title="Subtitle Generator",
            subtitle="Transcripción y generación automática de subtítulos con Whisper AI de forma local.",
            icon_file="subtitle.png",
            badge_text="IA LOCAL"
        )
        self.subtitle_card.action_btn.clicked.connect(lambda: self._handle_card("subtitle"))

        self._card_dict = {
            "media":       self.media_card,
            "docs":        self.docs_card,
            "link":        self.link_card,
            "image_tools": self.image_tools_card,
            "subtitle":    self.subtitle_card,
        }

        # Bento layout placements:
        # Hero card: row 0, col 0, rowSpan 2, colSpan 1
        self.grid_layout.addWidget(self.media_card, 0, 0, 2, 1)
        # Top right cards:
        self.grid_layout.addWidget(self.docs_card, 0, 1)
        self.grid_layout.addWidget(self.link_card, 0, 2)
        # Bottom right cards:
        self.grid_layout.addWidget(self.image_tools_card, 1, 1)
        self.grid_layout.addWidget(self.subtitle_card, 1, 2)

        self.grid_layout.setColumnStretch(0, 11)
        self.grid_layout.setColumnStretch(1, 10)
        self.grid_layout.setColumnStretch(2, 10)

        main_layout.addLayout(self.grid_layout)

        # Footer Dock Bento
        self.footer_dock = QFrame()
        self.footer_dock.setObjectName("footerDock")
        dock_layout = QHBoxLayout(self.footer_dock)
        dock_layout.setContentsMargins(16, 8, 16, 8)

        self.dock_status_label = QLabel("● Todas las aplicaciones están gestionadas de forma aislada")
        self.dock_status_label.setObjectName("dockText")
        dock_layout.addWidget(self.dock_status_label)
        dock_layout.addStretch()

        self.dock_folder_btn = QPushButton("📁 Abrir carpeta de apps")
        self.dock_folder_btn.setObjectName("dockLink")
        self.dock_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dock_folder_btn.clicked.connect(self._open_apps_folder)
        dock_layout.addWidget(self.dock_folder_btn)

        main_layout.addWidget(self.footer_dock)
        self._update_dock_status()

    def _open_apps_folder(self):
        """Abre la carpeta donde residen las micro-apps."""
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

        if updates_pending > 0:
            self.dock_status_label.setText(f"🚀 Hay {updates_pending} actualización(es) disponible(s) para tus herramientas.")
        else:
            self.dock_status_label.setText(f"✓ {count} de {total} herramientas instaladas • Almacenamiento optimizado")

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

        card = self._card_dict[app_id]
        card.action_btn.setEnabled(False)
        card._status_label.setText("⏳ Descargando…")

        worker = InstallWorker(app_id, parent=self)
        worker.progress.connect(lambda pct, msg: self._on_install_progress(app_id, pct, msg))
        worker.finished.connect(self._on_install_done)
        worker.error.connect(lambda err: self._on_install_error(app_id, err))
        self._workers[app_id] = worker
        worker.start()

    def _on_install_progress(self, app_id: str, pct: int, msg: str):
        card = self._card_dict.get(app_id)
        if card:
            card._status_label.setText(f"⏳ {pct}%")

    def _on_install_done(self, app_id: str, name: str):
        self._workers.pop(app_id, None)
        card = self._card_dict.get(app_id)
        if card:
            card._pending_update_version = None
            card.refresh_state()
            styles = self._tm.hub_styles()
            card.apply_styles(styles)
        self._update_dock_status()
        QMessageBox.information(
            self, "Operación exitosa",
            f"✅ {name} se ha instalado/actualizado correctamente.\n"
            f"Ya puedes usar la versión más reciente."
        )

    def _on_install_error(self, app_id: str, err: str):
        self._workers.pop(app_id, None)
        card = self._card_dict.get(app_id)
        if card:
            card.refresh_state()
            styles = self._tm.hub_styles()
            card.apply_styles(styles)
        QMessageBox.critical(self, "Error de instalación", err)

    def _reinstall_app(self, app_id: str):
        reg = APP_REGISTRY.get(app_id)
        app_name = reg["name"] if reg else app_id
        reply = QMessageBox.question(
            self,
            "Reinstalar aplicación",
            f"¿Deseas descargar y reinstalar <b>{app_name}</b>?<br><br>"
            "Esto sobreescribirá los archivos de la app con la versión más reciente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_install_or_update(app_id)

    def _uninstall_app(self, app_id: str):
        reg = APP_REGISTRY.get(app_id)
        if not reg:
            return
        app_name = reg["name"]

        reply = QMessageBox.question(
            self,
            "Desinstalar aplicación",
            f"¿Estás seguro de que deseas desinstalar <b>{app_name}</b>?<br><br>"
            "Se eliminarán los archivos locales de la aplicación y volverá al estado 'No instalada'.",
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
            card = self._card_dict.get(app_id)
            if card:
                card._pending_update_version = None
                card.refresh_state()
                card.apply_styles(self._tm.hub_styles())
            self._update_dock_status()
            QMessageBox.information(
                self,
                "Desinstalación completa",
                f"✅ {app_name} se ha desinstalado correctamente."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error al desinstalar",
                f"No se pudo completar la desinstalación de {app_name}:\n{e}\n\n"
                "Asegúrate de que la aplicación no esté abierta en segundo plano."
            )

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _toggle_dark_mode(self):
        self._tm.toggle()
        self._apply_theme()

    def _apply_theme(self):
        styles = self._tm.hub_styles()
        self.setStyleSheet(styles["window"])
        self.title_label.setStyleSheet(styles["title"])
        self.subtitle_label.setStyleSheet(styles["header_sub"])
        self.toggle_btn.setStyleSheet(styles["toggle_btn"])
        self.toggle_btn.setText(
            "☀️  Modo Claro" if self._tm.is_dark else "🌙  Modo Oscuro")
        self.footer_dock.setStyleSheet(styles["dock"])

        for card in self._card_dict.values():
            card.apply_styles(styles)
