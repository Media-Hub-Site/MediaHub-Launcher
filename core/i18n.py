"""
core/i18n.py
────────────
Gestor central de internacionalización (i18n) para Media Hub.
Permite persistir y alternar el idioma base entre Español ('es') e Inglés ('en').
"""

import os
import json
import locale

LANG_CONFIG_FILE = os.path.join(
    os.environ.get("USERPROFILE") or os.path.expanduser("~"),
    ".mediahub",
    "language.json"
)

DEFAULT_LANG = "es"

STRINGS = {
    "es": {
        "app_title": "Media Hub",
        "app_subtitle": "Suite integral de herramientas y conversores multimedia • {version}",
        "search_placeholder": "Filtrar herramientas...",
        "btn_light_mode": "Modo Claro",
        "btn_dark_mode": "Modo Oscuro",
        "dock_isolated": "● Todas las aplicaciones están gestionadas de forma aislada",
        "dock_updates": "Hay {count} actualización(es) disponible(s) • Ocupado: {size}",
        "dock_installed": "✓ {count} de {total} herramientas instaladas • {size} en disco",
        "dock_feedback": "Encuesta de Satisfacción",
        "dock_feedback_tooltip": "Danos tu opinión o reporta errores para seguir mejorando Media Hub",
        "dock_folder": "Abrir carpeta de apps",
        "status_ready": "● Listo",
        "status_uninstalled": "No instalada",
        "status_update": "↑",
        "btn_open": "Abrir",
        "btn_install": "Instalar",
        "btn_update": "Actualizar",
        "btn_coming_soon": "Próximamente",
        "badge_coming_soon": "PRÓXIMAMENTE",
        "options_tooltip": "Opciones (Idioma / Reinstalar / Desinstalar)",
        "menu_change_lang": "Idioma de la aplicación...",
        "menu_create_shortcut": "Crear acceso directo",
        "menu_remove_shortcut": "Quitar acceso directo",
        "menu_reinstall": "Reinstalar",
        "menu_uninstall": "Desinstalar",
        "dialog_shortcut_created_title": "Acceso Directo Creado",
        "dialog_shortcut_created_msg": "Se ha creado el acceso directo de <b>{name}</b> en tu Escritorio.<br>Puedes abrir la aplicación directamente cuando quieras sin abrir el Launcher.",
        "dialog_shortcut_removed_title": "Acceso directo eliminado",
        "dialog_shortcut_removed_msg": "Se eliminó el acceso directo de <b>{name}</b> del Escritorio.",
        "dialog_shortcut_fail": "No se pudo crear el acceso directo para {name}.",
        "dialog_install_done_title": "Instalación completada",
        "dialog_install_done_msg": "<b>{name}</b> se ha instalado correctamente.",
        "dialog_install_done_shortcut_prompt": "¿Deseas crear un acceso directo en tu Escritorio para abrirla de forma independiente?",
        "btn_yes_shortcut": "Sí, crear acceso directo",
        "btn_no_shortcut": "No, gracias",
        "dialog_reinstall_title": "Reinstalar aplicación",
        "dialog_reinstall_msg": "¿Deseas descargar y reinstalar <b>{name}</b>?<br><br>Esto sobreescribirá los archivos de la app con la versión más reciente.",
        "dialog_uninstall_title": "Desinstalar aplicación",
        "dialog_uninstall_msg": "¿Estás seguro de que deseas desinstalar <b>{name}</b>?<br><br>Se eliminarán los archivos locales de la aplicación y volverá al estado 'No instalada'.",
        "dialog_uninstall_done_title": "Desinstalación completa",
        "dialog_uninstall_done_msg": "{name} se ha desinstalado correctamente.",
        "dialog_not_installed_title": "No instalada",
        "dialog_not_installed_msg": "La aplicación aún no está instalada.\nHaz clic en 'Instalar' para descargarla automáticamente.",
        "dialog_choose_lang_title": "Seleccionar idioma de la aplicación",
        "dialog_choose_lang_msg": "Elige el idioma en el que deseas utilizar <b>{name}</b>:",
        "dialog_lang_updated_title": "Idioma actualizado",
        "dialog_lang_updated_msg": "El idioma de <b>{name}</b> se ha cambiado a <b>{lang_name}</b>.",
        "lang_name_es": "Español",
        "lang_name_en": "English",
        "btn_select": "Seleccionar",
    },
    "en": {
        "app_title": "Media Hub",
        "app_subtitle": "Comprehensive multimedia toolkit and converters suite • {version}",
        "search_placeholder": "Search tools...",
        "btn_light_mode": "Light Mode",
        "btn_dark_mode": "Dark Mode",
        "dock_isolated": "● All applications are managed in an isolated environment",
        "dock_updates": "{count} update(s) available • Storage used: {size}",
        "dock_installed": "✓ {count} of {total} tools installed • {size} on disk",
        "dock_feedback": "Satisfaction Survey",
        "dock_feedback_tooltip": "Give us your feedback or report bugs to help us improve Media Hub",
        "dock_folder": "Open apps folder",
        "status_ready": "● Ready",
        "status_uninstalled": "Not installed",
        "status_update": "↑",
        "btn_open": "Open",
        "btn_install": "Install",
        "btn_update": "Update",
        "btn_coming_soon": "Coming Soon",
        "badge_coming_soon": "COMING SOON",
        "options_tooltip": "Options (Language / Reinstall / Uninstall)",
        "menu_change_lang": "Application language...",
        "menu_create_shortcut": "Create desktop shortcut",
        "menu_remove_shortcut": "Remove desktop shortcut",
        "menu_reinstall": "Reinstall",
        "menu_uninstall": "Uninstall",
        "dialog_shortcut_created_title": "Shortcut Created",
        "dialog_shortcut_created_msg": "Desktop shortcut for <b>{name}</b> has been created.<br>You can now open the app directly without opening the Launcher.",
        "dialog_shortcut_removed_title": "Shortcut Removed",
        "dialog_shortcut_removed_msg": "Desktop shortcut for <b>{name}</b> has been removed.",
        "dialog_shortcut_fail": "Could not create desktop shortcut for {name}.",
        "dialog_install_done_title": "Installation Complete",
        "dialog_install_done_msg": "<b>{name}</b> has been installed successfully.",
        "dialog_install_done_shortcut_prompt": "Would you like to create a desktop shortcut to launch it independently?",
        "btn_yes_shortcut": "Yes, create shortcut",
        "btn_no_shortcut": "No, thanks",
        "dialog_reinstall_title": "Reinstall application",
        "dialog_reinstall_msg": "Do you want to re-download and reinstall <b>{name}</b>?<br><br>This will overwrite local files with the latest release.",
        "dialog_uninstall_title": "Uninstall application",
        "dialog_uninstall_msg": "Are you sure you want to uninstall <b>{name}</b>?<br><br>Local files will be removed and status will return to 'Not installed'.",
        "dialog_uninstall_done_title": "Uninstallation Complete",
        "dialog_uninstall_done_msg": "{name} has been uninstalled successfully.",
        "dialog_not_installed_title": "Not Installed",
        "dialog_not_installed_msg": "The application is not installed yet.\nClick 'Install' to download it automatically.",
        "dialog_choose_lang_title": "Select Application Language",
        "dialog_choose_lang_msg": "Choose the language in which you want to use <b>{name}</b>:",
        "dialog_lang_updated_title": "Language Updated",
        "dialog_lang_updated_msg": "The language for <b>{name}</b> has been changed to <b>{lang_name}</b>.",
        "lang_name_es": "Español",
        "lang_name_en": "English",
        "btn_select": "Select",
    }
}


def detect_system_language() -> str:
    """Detecta el idioma preferido del sistema operativo ('es' o 'en')."""
    try:
        lang, _ = locale.getdefaultlocale()
        if lang and lang.lower().startswith("es"):
            return "es"
    except Exception:
        pass
    return "es"


def get_current_language() -> str:
    """Obtiene el idioma configurado para el Launcher ('es' o 'en')."""
    if os.path.isfile(LANG_CONFIG_FILE):
        try:
            with open(LANG_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lang = data.get("language")
                if lang in ("es", "en"):
                    return lang
        except Exception:
            pass
    # Si no existe, detectar del sistema y guardar
    detected = detect_system_language()
    save_current_language(detected)
    return detected


def save_current_language(lang: str):
    """Guarda el idioma configurado para el Launcher."""
    if lang not in ("es", "en"):
        lang = "es"
    os.makedirs(os.path.dirname(LANG_CONFIG_FILE), exist_ok=True)
    try:
        with open(LANG_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"language": lang}, f, indent=2)
    except Exception as e:
        print(f"Error guardando idioma: {e}")


def get_app_lang_file(app_dir_name: str) -> str:
    """Ruta al archivo de configuración de idioma de una micro-app."""
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(home, ".mediahub", "apps", app_dir_name, "config_lang.json")


def save_app_language(app_dir_name: str, lang: str):
    """Guarda la selección de idioma ('es'/'en') de una micro-app instalada."""
    fpath = get_app_lang_file(app_dir_name)
    try:
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump({"language": lang}, f, indent=2)
    except Exception as e:
        print(f"Error guardando idioma de app {app_dir_name}: {e}")


def get_app_language(app_dir_name: str) -> str:
    """Lee el idioma configurado para una micro-app instalada."""
    fpath = get_app_lang_file(app_dir_name)
    if os.path.isfile(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("language", get_current_language())
        except Exception:
            pass
    return get_current_language()


def t(key: str, **kwargs) -> str:
    """Traduce una clave al idioma activo."""
    lang = get_current_language()
    text = STRINGS.get(lang, STRINGS["es"]).get(key, STRINGS["es"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
