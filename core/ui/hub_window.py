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
from core.config import APP_REGISTRY


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
        except Exception:
            app_dir = os.path.dirname(exe)
            subprocess.Popen([exe], cwd=app_dir)
def is_version_newer(current_ver: str, latest_ver: str) -> bool:
    """
    Compara semver básico (ej: '1.0.0' vs '1.1.0').
    Devuelve True si latest_ver es estrictamente superior a current_ver.
    """
    def to_tuple(v: str):
        v = v.lstrip("v")
        parts = []
        for x in v.split("."):
            m = re.match(r"\d+", x)
            parts.append(int(m.group(0)) if m else 0)
        return tuple(parts)

    try:
        return to_tuple(latest_ver) > to_tuple(current_ver)
    except Exception:
        return latest_ver != current_ver


# ─────────────────────────────────────────────────────────────────────────────
#  Worker de consulta de versiones remotas para las micro-apps
# ─────────────────────────────────────────────────────────────────────────────

class CheckMicroAppUpdatesThread(QThread):
    """
    Revisa en GitHub Releases la última versión de cada micro-app.
    Emite update_found(app_id, latest_version).
    """
    update_found = pyqtSignal(str, str)

    def run(self):
        installed = load_installed_versions()
        for app_id, reg in APP_REGISTRY.items():
            exe = get_app_exe(app_id)
            if not exe:
                continue  # Solo verificar actualizaciones para apps instaladas

            current_ver = installed.get(app_id, "0.0.0")
            repo = reg["repo"]
            api_url = f"https://api.github.com/repos/{repo}/releases/latest"
            try:
                resp = requests.get(api_url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    tag = data.get("tag_name", "").lstrip("v")
                    if tag and is_version_newer(current_ver, tag):
                        self.update_found.emit(app_id, tag)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
#  Worker de descarga / instalación / actualización
# ─────────────────────────────────────────────────────────────────────────────

class InstallWorker(QThread):
    """Descarga el release de una micro-app desde GitHub y lo extrae."""

    progress   = pyqtSignal(int, str)   # (porcentaje, texto)
    finished   = pyqtSignal(str, str)   # (app_id, app_name)
    error      = pyqtSignal(str)        # mensaje de error

    def __init__(self, app_id: str, parent=None):
        super().__init__(parent)
        self.app_id = app_id

    def run(self):
        reg = APP_REGISTRY.get(self.app_id)
        if not reg:
            self.error.emit("App desconocida.")
            return

        repo   = reg["repo"]
        api    = f"https://api.github.com/repos/{repo}/releases/latest"

        try:
            self.progress.emit(5, "Consultando GitHub…")
            resp = requests.get(api, timeout=15)
            if resp.status_code == 404:
                self.error.emit(
                    f"No se encontró ninguna versión disponible para '{reg['name']}'.\n\n"
                    "Causas posibles:\n"
                    "1. El repositorio está en modo 'Private'. Debe ser 'Public' para que el Launcher pueda descargar las releases sin requerir un token de GitHub.\n"
                    "2. Aún no se ha compilado ni publicado ninguna Release en GitHub Actions para esta aplicación."
                )
                return
            resp.raise_for_status()
            data = resp.json()
            latest_tag = data.get("tag_name", "1.0.0")
        except Exception as e:
            self.error.emit(f"No se pudo obtener la release:\n{e}")
            return

        # Buscar el asset ZIP o EXE
        asset_url  = None
        asset_name = None
        for asset in data.get("assets", []):
            name = asset["name"]
            if name.endswith(".zip") or name.endswith(".exe"):
                asset_url  = asset["browser_download_url"]
                asset_name = name
                break

        if not asset_url:
            self.error.emit("No se encontró ningún archivo de instalación en la release.")
            return

        # Descargar
        self.progress.emit(10, f"Descargando {asset_name}…")
        try:
            tmp_dir  = tempfile.mkdtemp()
            tmp_file = os.path.join(tmp_dir, asset_name)
            with requests.get(asset_url, stream=True, timeout=60) as dl:
                dl.raise_for_status()
                total = int(dl.headers.get("content-length", 0))
                downloaded = 0
                with open(tmp_file, "wb") as f:
                    for chunk in dl.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = 10 + int(downloaded / total * 70)
                            self.progress.emit(pct, f"Descargando… {downloaded // 1024} KB")
        except Exception as e:
            self.error.emit(f"Error al descargar:\n{e}")
            return

        # Instalar / Extraer de forma 100% limpia
        self.progress.emit(82, "Preparando e instalando archivos…")
        install_base = get_apps_install_dir()
        dest_dir = os.path.join(install_base, reg["dir"])

        try:
            # Si ya existía una versión anterior (reinstalación o actualización),
            # limpiamos el directorio para evitar archivos corruptos o mezclados.
            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir, ignore_errors=True)
            os.makedirs(dest_dir, exist_ok=True)

            if asset_name.endswith(".zip"):
                with zipfile.ZipFile(tmp_file, "r") as zf:
                    zf.extractall(dest_dir)
            else:
                subprocess.run([tmp_file, "/SILENT", f"/DIR={dest_dir}"],
                               check=True)
            # Guardar la versión instalada exitosamente
            save_installed_version(self.app_id, latest_tag)
        except Exception as e:
            self.error.emit(f"Error al instalar:\n{e}")
            return

        self.progress.emit(100, "¡Completado con éxito!")
        self.finished.emit(self.app_id, reg["name"])


# ─────────────────────────────────────────────────────────────────────────────
#  AppCard
# ─────────────────────────────────────────────────────────────────────────────

class AppCard(QFrame):
    def __init__(self, card_id, title, subtitle, icon_file,
                 is_disabled=False, parent=None):
        super().__init__(parent)
        self.card_id    = card_id
        self._is_disabled = is_disabled
        self._pending_update_version = None
        self.setAcceptDrops(True)

        if is_disabled:
            self.setObjectName("appCardDisabled")
        else:
            self.setObjectName("appCard")
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(15)
            shadow.setXOffset(0)
            shadow.setYOffset(4)
            shadow.setColor(QColor(0, 0, 0, 80))
            self.setGraphicsEffect(shadow)

        self.setFixedHeight(180)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Icon
        self._icon_label = QLabel()
        pixmap = QPixmap(get_asset_path(icon_file))
        if not pixmap.isNull():
            self._icon_label.setPixmap(
                pixmap.scaled(100, 100,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )
        self._icon_label.setFixedSize(100, 100)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._icon_label)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(5)

        self._title_label = QLabel(title)
        self._title_label.setWordWrap(True)
        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setWordWrap(True)

        content_layout.addWidget(self._title_label)
        content_layout.addWidget(self._subtitle_label)
        content_layout.addStretch()

        action_layout = QHBoxLayout()

        # Botón principal (Instalar / Abrir / Actualizar)
        self.action_btn = QPushButton()
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        action_layout.addWidget(self.action_btn)

        # Botón secundario de opciones (Reinstalar / Desinstalar)
        self.options_btn = QPushButton("⋮")
        self.options_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.options_btn.setFixedWidth(36)
        self.options_btn.setToolTip("Opciones de la aplicación (Reinstalar / Desinstalar)")
        self.options_btn.clicked.connect(self._show_options_menu)
        self.options_btn.hide()
        action_layout.addWidget(self.options_btn)

        action_layout.addStretch()

        # Etiqueta de estado y versión
        self._status_label = QLabel()
        action_layout.addWidget(self._status_label)

        content_layout.addLayout(action_layout)
        main_layout.addLayout(content_layout)

        # Actualizar botón según estado instalado
        self.refresh_state()

    def set_update_available(self, new_version: str):
        """Notifica a la tarjeta que hay una nueva versión disponible."""
        self._pending_update_version = new_version
        self._set_btn_state("update")

    def _show_options_menu(self):
        """Despliega el menú contextual con opciones para la app instalada."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #252836;
                color: #FFFFFF;
                border: 1px solid #3B4252;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: 600;
            }
            QMenu::item:selected {
                background-color: #3B5EFF;
                color: #FFFFFF;
            }
        """)

        reinstall_act = menu.addAction("🔄  Reinstalar")
        reinstall_act.triggered.connect(lambda: self.window()._reinstall_app(self.card_id))

        uninstall_act = menu.addAction("🗑️  Desinstalar")
        uninstall_act.triggered.connect(lambda: self.window()._uninstall_app(self.card_id))

        menu.exec(self.options_btn.mapToGlobal(self.options_btn.rect().bottomLeft()))

    def refresh_state(self):
        """Actualiza el botón según si la app está instalada o pendiente de actualización."""
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
        """state: 'open' | 'install' | 'update' | 'disabled'"""
        self._btn_state = state
        installed = load_installed_versions()
        cur_ver = installed.get(self.card_id)

        if state == "open":
            self.action_btn.setText(" ABRIR")
            self.action_btn.setIcon(
                self.style().standardIcon(self.style().StandardPixmap.SP_DialogApplyButton))
            self.action_btn.setEnabled(True)
            v_text = f" (v{cur_ver})" if cur_ver else ""
            self._status_label.setText(f"✅ Instalado{v_text}")
            self.options_btn.show()
        elif state == "update":
            self.action_btn.setText(" ACTUALIZAR")
            self.action_btn.setIcon(
                self.style().standardIcon(self.style().StandardPixmap.SP_BrowserReload))
            self.action_btn.setEnabled(True)
            self._status_label.setText(f"🚀 v{self._pending_update_version} disponible!")
            self.options_btn.show()
        elif state == "install":
            self.action_btn.setText(" INSTALAR")
            self.action_btn.setIcon(
                self.style().standardIcon(self.style().StandardPixmap.SP_ArrowDown))
            self.action_btn.setEnabled(True)
            self._status_label.setText("⬇ No instalado")
            self.options_btn.hide()
        else:
            self.action_btn.setText(" PRÓXIMAMENTE")
            self.action_btn.setEnabled(False)
            self._status_label.setText("")
            self.options_btn.hide()

    # ── Drag & Drop ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if not hasattr(self, 'drag_start_position'):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < 10:
            return
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.card_id)
        drag.setMimeData(mime_data)
        pixmap = self.grab()
        drag.setPixmap(pixmap.scaled(300, 150,
                                     Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
        drag.setHotSpot(event.pos())
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.source() != self:
            event.acceptProposedAction()

    def dropEvent(self, event):
        source_id = event.mimeData().text()
        target_id = self.card_id
        if hasattr(self.window(), "swap_cards"):
            self.window().swap_cards(source_id, target_id)
        event.acceptProposedAction()

    # ── Styles ───────────────────────────────────────────────────────────────

    def apply_styles(self, styles: dict):
        if self._is_disabled:
            self.setStyleSheet(styles["card_disabled"])
        else:
            self.setStyleSheet(styles["card_normal"])
        self._title_label.setStyleSheet(styles["card_title"])
        self._subtitle_label.setStyleSheet(styles["card_subtitle"])
        self._status_label.setStyleSheet(styles.get("portable", ""))
        self.options_btn.setStyleSheet(styles.get("btn_options", """
            QPushButton {
                background-color: #323545;
                color: #FFFFFF;
                border: 1px solid #45495E;
                border-radius: 6px;
                font-size: 14pt;
                font-weight: bold;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #43475D;
            }
            QPushButton:pressed {
                background-color: #282B38;
            }
        """))
        state = getattr(self, "_btn_state", "disabled")
        if state == "install":
            self.action_btn.setStyleSheet(styles["btn_install"])
        elif state == "update":
            self.action_btn.setStyleSheet(styles.get("btn_update", styles["btn_open"]))
        elif state == "open":
            self.action_btn.setStyleSheet(styles["btn_open"])
        else:
            self.action_btn.setStyleSheet(styles["btn_disabled"])


# ─────────────────────────────────────────────────────────────────────────────
#  HubWindow  —  MediaHub Launcher
# ─────────────────────────────────────────────────────────────────────────────

class HubWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Hub — Launcher")
        self.resize(900, 800)
        self._tm = ThemeManager.instance()
        self._workers: dict[str, InstallWorker] = {}
        self.init_ui()
        self._apply_theme()

        # 1. Verificar actualizaciones del Launcher en background
        self.update_thread = CheckUpdateThread(self)
        self.update_thread.update_available.connect(self.show_update_dialog)
        self.update_thread.start()

        # 2. Verificar actualizaciones de las Micro-Apps instaladas en background
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

    # ── Layout ───────────────────────────────────────────────────────────────

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 30, 40, 40)
        main_layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        self.title_label = QLabel("MEDIA HUB")
        self.title_label.setObjectName("hubTitle")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.toggle_btn = QPushButton()
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFixedHeight(38)
        self.toggle_btn.clicked.connect(self._toggle_dark_mode)
        header_layout.addWidget(self.toggle_btn)
        main_layout.addLayout(header_layout)

        # Cards
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(20)

        self.media_card = AppCard(
            card_id="media", title="MULTIMEDIA CONVERTER",
            subtitle="Video, Audio, Imagen y más",
            icon_file="media.png")
        self.media_card.action_btn.clicked.connect(
            lambda: self._handle_card("media"))

        self.docs_card = AppCard(
            card_id="docs", title="DOCUMENT CONVERTER",
            subtitle="PDF, Word, Excel, PowerPoint",
            icon_file="docs.png")
        self.docs_card.action_btn.clicked.connect(
            lambda: self._handle_card("docs"))

        self.image_tools_card = AppCard(
            card_id="image_tools", title="IMAGE TOOLS",
            subtitle="BG Eraser · Quality 4x · Watermark",
            icon_file="quality.webp")
        self.image_tools_card.action_btn.clicked.connect(
            lambda: self._handle_card("image_tools"))

        self.link_card = AppCard(
            card_id="link", title="LINK CONVERTER",
            subtitle="YouTube, TikTok, Instagram & more",
            icon_file="link_converter.webp")
        self.link_card.action_btn.clicked.connect(
            lambda: self._handle_card("link"))

        self.subtitle_card = AppCard(
            card_id="subtitle", title="SUBTITLE GENERATOR",
            subtitle="Whisper AI — transcripción local",
            icon_file="subtitle.png")
        self.subtitle_card.action_btn.clicked.connect(
            lambda: self._handle_card("subtitle"))

        self._card_dict = {
            "media":       self.media_card,
            "docs":        self.docs_card,
            "image_tools": self.image_tools_card,
            "link":        self.link_card,
            "subtitle":    self.subtitle_card,
        }

        # Orden persistido
        default_order = ["media", "docs", "image_tools", "link", "subtitle"]
        order = default_order[:]
        try:
            appdata = os.environ.get('ProgramData', '')
            path = os.path.join(appdata, "MediaHub", "settings.json")
            with open(path, 'r') as f:
                saved = json.load(f).get("hub_order", [])
                if len(saved) == len(order) and all(k in self._card_dict for k in saved):
                    order = saved
        except Exception:
            pass

        self._all_cards = [self._card_dict[k] for k in order]
        cols = 2
        for i, card in enumerate(self._all_cards):
            self.grid_layout.addWidget(card, i // cols, i % cols)

        main_layout.addLayout(self.grid_layout)

    # ── Card handler (Instalar / Abrir / Actualizar) ───────────────────────────

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
            return  # ya se está descargando/instalando

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
            card._status_label.setText(f"⏳ {msg}")

    def _on_install_done(self, app_id: str, name: str):
        self._workers.pop(app_id, None)
        card = self._card_dict.get(app_id)
        if card:
            card._pending_update_version = None
            card.refresh_state()
            styles = self._tm.hub_styles()
            card.apply_styles(styles)
        QMessageBox.information(self, "Operación exitosa",
                                f"✅ {name} se ha instalado/actualizado correctamente.\n"
                                f"Ya puedes usar la versión más reciente.")

    def _on_install_error(self, app_id: str, err: str):
        self._workers.pop(app_id, None)
        card = self._card_dict.get(app_id)
        if card:
            card.refresh_state()
            styles = self._tm.hub_styles()
            card.apply_styles(styles)
        QMessageBox.critical(self, "Error de instalación", err)

    def _reinstall_app(self, app_id: str):
        """Fuerza la reinstalación descargando nuevamente la última versión."""
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
        """Desinstala por completo la micro-app seleccionada."""
        reg = APP_REGISTRY.get(app_id)
        if not reg:
            return
        app_name = reg["name"]

        reply = QMessageBox.question(
            self,
            "Desinstalar aplicación",
            f"¿Estás seguro de que deseas desinstalar <b>{app_name}</b>?<br><br>"
            "Se eliminarán los archivos locales de la aplicación y volverá al estado 'No instalado'.",
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

    # ── Drag & Drop ──────────────────────────────────────────────────────────

    def swap_cards(self, id1, id2):
        idx1 = next(i for i, c in enumerate(self._all_cards) if c.card_id == id1)
        idx2 = next(i for i, c in enumerate(self._all_cards) if c.card_id == id2)
        self._all_cards[idx1], self._all_cards[idx2] = \
            self._all_cards[idx2], self._all_cards[idx1]
        for card in self._all_cards:
            self.grid_layout.removeWidget(card)
        cols = 2
        for i, card in enumerate(self._all_cards):
            self.grid_layout.addWidget(card, i // cols, i % cols)
        self.save_layout()

    def save_layout(self):
        order = [c.card_id for c in self._all_cards]
        appdata = os.environ.get('ProgramData', '')
        if appdata:
            path = os.path.join(appdata, "MediaHub", "settings.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump({"hub_order": order}, f)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _toggle_dark_mode(self):
        self._tm.toggle()
        self._apply_theme()

    def _apply_theme(self):
        styles = self._tm.hub_styles()
        self.setStyleSheet(styles["window"])
        self.title_label.setStyleSheet(styles["title"])
        self.toggle_btn.setStyleSheet(styles["toggle_btn"])
        self.toggle_btn.setText(
            "☀️  Modo Claro" if self._tm.is_dark else "🌙  Modo Oscuro")
        for card in self._all_cards:
            card.apply_styles(styles)
