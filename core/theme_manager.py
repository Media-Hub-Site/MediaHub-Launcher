"""
core/theme_manager.py
─────────────────────
Singleton that stores the current dark/light preference and provides
ready-to-use style strings for every part of the app.
Refined Bento-Grid aesthetic (Apple / Windows 11 Fluent inspired).
"""

from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────────────
#  Color palettes
# ──────────────────────────────────────────────────────────────────────────────

_APP_COLORS_LIGHT = {
    "bg":           "#F8F9FA",
    "card":         "#FFFFFF",
    "text_main":    "#111827",
    "text_muted":   "#6B7280",
    "border":       "#E5E7EB",
    "accent":       "#2563EB",
    "accent_hover": "#1D4ED8",
    "accent_soft":  "#EFF6FF",
    "drop_bg":      "#F9FAFB",
}

_APP_COLORS_DARK = {
    "bg":           "#0D0E12",
    "card":         "#15171E",
    "text_main":    "#F3F4F6",
    "text_muted":   "#9CA3AF",
    "border":       "#262A36",
    "accent":       "#3B82F6",
    "accent_hover": "#60A5FA",
    "accent_soft":  "#1E2433",
    "drop_bg":      "#12141A",
}

# ──────────────────────────────────────────────────────────────────────────────
#  Hub-level palettes (Bento Grid Apple / Win11 Modern)
# ──────────────────────────────────────────────────────────────────────────────

_HUB_LIGHT = {
    "window_bg":        "#F3F4F6",
    "card_bg":          "#FFFFFF",
    "card_border":      "#E5E7EB",
    "card_border_hover":"#D1D5DB",
    "card_disabled_bg": "#F9FAFB",
    "card_disabled_border": "#E5E7EB",
    "card_title":       "#111827",
    "card_subtitle":    "#4B5563",
    "tag_bg":           "#F3F4F6",
    "tag_fg":           "#4B5563",
    "status_installed": "#059669",
    "status_available": "#2563EB",
    "status_uninstalled":"#6B7280",
    "status_update":    "#D97706",
    "toggle_bg":        "#FFFFFF",
    "toggle_bg_hover":  "#F9FAFB",
    "toggle_border":    "#E5E7EB",
    "toggle_color":     "#1F2937",
    "header_sub":       "#6B7280",
    "dock_bg":          "#FFFFFF",
    "dock_border":      "#E5E7EB",
    "dock_text":        "#374151",
    "btn_open_bg":      "#18181B",
    "btn_open_fg":      "#FFFFFF",
    "btn_open_hover":   "#27272A",
    "btn_open_press":   "#09090B",
    "btn_install_bg":   "#2563EB",
    "btn_install_fg":   "#FFFFFF",
    "btn_install_hover":"#1D4ED8",
    "btn_install_press":"#1E40AF",
    "btn_update_bg":    "#EA580C",
    "btn_update_fg":    "#FFFFFF",
    "btn_update_hover": "#C2410C",
    "btn_update_press": "#9A3412",
    "btn_disabled_bg":  "#F3F4F6",
    "btn_disabled_fg":  "#9CA3AF",
    "options_bg":       "#F3F4F6",
    "options_fg":       "#374151",
    "options_border":   "#E5E7EB",
    "options_hover":    "#E5E7EB",
    "scroll_thumb":     "#D1D5DB",
    "scroll_thumb_hover":"#9CA3AF",
    "search_bg":        "#FFFFFF",
    "search_fg":        "#111827",
    "search_border":    "#E5E7EB",
    "search_focus":     "#2563EB",
}

_HUB_DARK = {
    "window_bg":        "#0B0C10",
    "card_bg":          "#14161D",
    "card_border":      "#202430",
    "card_border_hover":"#32384A",
    "card_disabled_bg": "#101117",
    "card_disabled_border": "#1A1D27",
    "card_title":       "#F9FAFB",
    "card_subtitle":    "#9CA3AF",
    "tag_bg":           "#1C202C",
    "tag_fg":           "#94A3B8",
    "status_installed": "#10B981",
    "status_available": "#60A5FA",
    "status_uninstalled":"#6B7280",
    "status_update":    "#F59E0B",
    "toggle_bg":        "#151720",
    "toggle_bg_hover":  "#1E212D",
    "toggle_border":    "#272B3B",
    "toggle_color":     "#E5E7EB",
    "header_sub":       "#828B9E",
    "dock_bg":          "#12141B",
    "dock_border":      "#1E222D",
    "dock_text":        "#9CA3AF",
    "btn_open_bg":      "#F4F4F5",
    "btn_open_fg":      "#09090B",
    "btn_open_hover":   "#E4E4E7",
    "btn_open_press":   "#D4D4D8",
    "btn_install_bg":   "#3B82F6",
    "btn_install_fg":   "#FFFFFF",
    "btn_install_hover":"#2563EB",
    "btn_install_press":"#1D4ED8",
    "btn_update_bg":    "#F97316",
    "btn_update_fg":    "#FFFFFF",
    "btn_update_hover": "#EA580C",
    "btn_update_press": "#C2410C",
    "btn_disabled_bg":  "#1B1D27",
    "btn_disabled_fg":  "#4B5563",
    "options_bg":       "#1A1D27",
    "options_fg":       "#E2E8F0",
    "options_border":   "#272B3B",
    "options_hover":    "#2B3042",
    "scroll_thumb":     "#2E3547",
    "scroll_thumb_hover":"#47526D",
    "search_bg":        "#151720",
    "search_fg":        "#F3F4F6",
    "search_border":    "#272B3B",
    "search_focus":     "#3B82F6",
}


# ──────────────────────────────────────────────────────────────────────────────
#  Style generators
# ──────────────────────────────────────────────────────────────────────────────

RADIUS_LG = 16
RADIUS_MD = 12
RADIUS_SM = 8


def _build_app_styles(c: dict) -> dict:
    """Build all micro-app QSS strings from a color dict `c`."""

    window_style = f"""
        QWidget {{
            background-color: {c["bg"]};
            color: {c["text_main"]};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
        }}
        QLabel {{
            background: transparent;
        }}
        QMessageBox {{
            background-color: {c["bg"]};
        }}
        QMessageBox QPushButton {{
            background: {c["accent_soft"]};
            border: 1px solid {c["border"]};
            border-radius: {RADIUS_SM}px;
            padding: 8px 14px;
            font-weight: 600;
            min-width: 90px;
        }}
        QProgressDialog {{
            background: {c["bg"]};
            border: 1px solid {c["border"]};
            border-radius: {RADIUS_MD}px;
        }}
        QProgressBar {{
            background: {c["card"]};
            border: 1px solid {c["border"]};
            border-radius: {RADIUS_SM}px;
            min-height: 10px;
            text-align: center;
            color: {c["text_main"]};
        }}
        QProgressBar::chunk {{
            background: {c["accent"]};
            border-radius: {RADIUS_SM}px;
        }}
    """

    card_style = f"""
        QFrame#mainCard {{
            background: {c["card"]};
            border: 1px solid {c["border"]};
            border-radius: {RADIUS_LG}px;
        }}
    """

    button = (
        f"QPushButton{{background:{c['accent']};color:#FFFFFF;"
        f"padding:10px 14px;border-radius:{RADIUS_SM}px;border:none;font-weight:600;}}"
        f"QPushButton:hover{{background:{c['accent_hover']};}}"
        f"QPushButton:pressed{{background:{c['accent']};}}"
        f"QPushButton:disabled{{background:{c['accent_soft']};color:{c['text_muted']};}}"
    )

    soft_button = (
        f"QPushButton{{background:{c['accent_soft']};color:{c['text_main']};"
        f"padding:8px 12px;border-radius:{RADIUS_SM}px;border:1px solid {c['border']};font-weight:600;}}"
        f"QPushButton:hover{{background:{c['card']};}}"
        f"QPushButton:pressed{{background:{c['accent_soft']};}}"
    )

    remove_button = (
        f"QPushButton{{background:#EF4444;color:#FFFFFF;"
        f"padding:10px 14px;border-radius:{RADIUS_SM}px;border:none;font-weight:600;}}"
        f"QPushButton:hover{{background:#DC2626;}}"
        f"QPushButton:pressed{{background:#B91C1C;}}"
        f"QPushButton:disabled{{background:{c['accent_soft']};color:{c['text_muted']};}}"
    )

    convert_button = (
        f"QPushButton{{background:#10B981;color:#FFFFFF;"
        f"padding:10px 14px;border-radius:{RADIUS_SM}px;border:none;font-weight:600;}}"
        f"QPushButton:hover{{background:#059669;}}"
        f"QPushButton:pressed{{background:#047857;}}"
        f"QPushButton:disabled{{background:{c['accent_soft']};color:{c['text_muted']};}}"
    )

    ffmpeg_button = (
        f"QPushButton{{background:#EF4444;color:#FFFFFF;"
        f"padding:8px 12px;border-radius:{RADIUS_SM}px;border:none;font-weight:600;}}"
        f"QPushButton:hover{{background:#DC2626;}}"
        f"QPushButton:pressed{{background:#B91C1C;}}"
    )

    combo = (
        f"QComboBox{{background:{c['card']};border:1px solid {c['border']};padding:6px 10px;"
        f"border-radius:{RADIUS_SM}px;color:{c['text_main']};min-height:22px;}}"
        f"QComboBox:hover{{border:1px solid {c['accent']};}}"
        f"QComboBox:focus{{border:1px solid {c['accent']};}}"
        f"QComboBox::drop-down{{border:none;padding-right:8px;}}"
        f"QComboBox QAbstractItemView{{background:{c['card']};border:1px solid {c['border']};"
        f"color:{c['text_main']};outline:none;padding:4px;"
        f"selection-background-color:{c['accent']};selection-color:#FFFFFF;}}"
        f"QComboBox QAbstractItemView::item{{min-height:28px;color:{c['text_main']};padding:4px 8px;}}"
        f"QComboBox QAbstractItemView::item:selected{{background-color:{c['accent']};color:#FFFFFF;}}"
    )

    drop_label = (
        f"background: {c['drop_bg']};"
        f"border: 2px dashed {c['border']};"
        f"color: {c['text_muted']};"
        "padding: 14px;"
        f"border-radius: {RADIUS_MD}px;"
    )

    doc_btn = f"""
        QPushButton {{
            background-color: {c['card']};
            border: 1px solid {c['border']};
            border-radius: {RADIUS_SM}px;
            padding: 12px 20px;
            text-align: left;
            font-size: 11pt;
            font-weight: 600;
            color: {c['text_main']};
        }}
        QPushButton:hover {{
            background-color: {c['accent_soft']};
            border: 1px solid {c['accent']};
        }}
        QPushButton:pressed {{
            background-color: {c['accent_soft']};
        }}
    """

    return {
        "window":         window_style,
        "card":           card_style,
        "button":         button,
        "soft_button":    soft_button,
        "remove_button":  remove_button,
        "convert_button": convert_button,
        "ffmpeg_button":  ffmpeg_button,
        "combo":          combo,
        "drop_label":     drop_label,
        "doc_btn":        doc_btn,
    }


def _build_hub_styles(h: dict) -> dict:
    """Build modern Bento-Grid hub QSS strings from a hub color dict `h`."""

    window = f"""
        QMainWindow {{
            background-color: {h['window_bg']};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
        }}
    """

    title = f"""
        QLabel#hubTitle {{
            color: {h['card_title']};
            font-size: 21pt;
            font-weight: 800;
            letter-spacing: -0.5px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
    """

    header_sub = f"""
        QLabel#hubSubtitle {{
            color: {h['header_sub']};
            font-size: 10.5pt;
            font-weight: 500;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
    """

    card_normal = f"""
        QFrame#appCard {{
            background-color: {h['card_bg']};
            border: 1px solid {h['card_border']};
            border-radius: 16px;
        }}
        QFrame#appCard:hover {{
            border: 1px solid {h['card_border_hover']};
        }}
    """

    card_hero = f"""
        QFrame#appCardHero {{
            background-color: {h['card_bg']};
            border: 1px solid {h['card_border']};
            border-radius: 16px;
        }}
        QFrame#appCardHero:hover {{
            border: 1px solid {h['card_border_hover']};
        }}
    """

    card_disabled = f"""
        QFrame#appCardDisabled {{
            background-color: {h['card_disabled_bg']};
            border: 1px solid {h['card_disabled_border']};
            border-radius: 16px;
        }}
    """

    card_title = f"""
        QLabel {{
            color: {h['card_title']};
            font-size: 13pt;
            font-weight: 700;
            letter-spacing: -0.2px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
    """

    card_hero_title = f"""
        QLabel {{
            color: {h['card_title']};
            font-size: 15pt;
            font-weight: 800;
            letter-spacing: -0.3px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
    """

    card_subtitle = f"""
        QLabel {{
            color: {h['card_subtitle']};
            font-size: 9.5pt;
            font-weight: 400;
            line-height: 1.3;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
    """

    tag_badge = f"""
        QLabel {{
            background-color: {h['tag_bg']};
            color: {h['tag_fg']};
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 8.5pt;
            font-weight: 600;
            letter-spacing: 0.3px;
        }}
    """

    btn_install = f"""
        QPushButton {{
            background-color: {h['btn_install_bg']};
            color: {h['btn_install_fg']};
            border: none;
            border-radius: 9px;
            padding: 8px 18px;
            font-weight: 700;
            font-size: 10pt;
            letter-spacing: 0.2px;
        }}
        QPushButton:hover  {{ background-color: {h['btn_install_hover']}; }}
        QPushButton:pressed {{ background-color: {h['btn_install_press']}; }}
    """

    btn_open = f"""
        QPushButton {{
            background-color: {h['btn_open_bg']};
            color: {h['btn_open_fg']};
            border: none;
            border-radius: 9px;
            padding: 8px 18px;
            font-weight: 700;
            font-size: 10pt;
            letter-spacing: 0.2px;
        }}
        QPushButton:hover  {{ background-color: {h['btn_open_hover']}; }}
        QPushButton:pressed {{ background-color: {h['btn_open_press']}; }}
    """

    btn_update = f"""
        QPushButton {{
            background-color: {h['btn_update_bg']};
            color: {h['btn_update_fg']};
            border: none;
            border-radius: 9px;
            padding: 8px 18px;
            font-weight: 700;
            font-size: 10pt;
            letter-spacing: 0.2px;
        }}
        QPushButton:hover  {{ background-color: {h['btn_update_hover']}; }}
        QPushButton:pressed {{ background-color: {h['btn_update_press']}; }}
    """

    btn_disabled = f"""
        QPushButton {{
            background-color: {h['btn_disabled_bg']};
            color: {h['btn_disabled_fg']};
            border: none;
            border-radius: 9px;
            padding: 8px 18px;
            font-weight: 600;
            font-size: 10pt;
        }}
    """

    btn_options = f"""
        QPushButton {{
            background-color: {h['options_bg']};
            color: {h['options_fg']};
            border: 1px solid {h['options_border']};
            border-radius: 8px;
            font-size: 12pt;
            font-weight: bold;
            padding: 2px;
        }}
        QPushButton:hover {{
            background-color: {h['options_hover']};
        }}
    """

    status_installed = f"QLabel {{ color: {h['status_installed']}; font-weight: 600; font-size: 9pt; }}"
    status_available = f"QLabel {{ color: {h['status_available']}; font-weight: 600; font-size: 9pt; }}"
    status_uninstalled = f"QLabel {{ color: {h['status_uninstalled']}; font-weight: 500; font-size: 9pt; }}"
    status_update = f"QLabel {{ color: {h['status_update']}; font-weight: 700; font-size: 9pt; }}"

    toggle = f"""
        QPushButton {{
            background-color: {h['toggle_bg']};
            color: {h['toggle_color']};
            border: 1px solid {h['toggle_border']};
            border-radius: 12px;
            padding: 6px 14px;
            font-size: 10pt;
            font-weight: 600;
        }}
        QPushButton:hover  {{ background-color: {h['toggle_bg_hover']}; }}
    """

    dock = f"""
        QFrame#footerDock {{
            background-color: {h['dock_bg']};
            border: 1px solid {h['dock_border']};
            border-radius: 12px;
            padding: 4px 16px;
        }}
        QLabel#dockText {{
            color: {h['dock_text']};
            font-size: 9pt;
            font-weight: 500;
        }}
        QPushButton#dockLink {{
            background: transparent;
            color: {h['btn_install_bg']};
            border: none;
            font-size: 9pt;
            font-weight: 600;
            padding: 4px 8px;
        }}
        QPushButton#dockLink:hover {{
            text-decoration: underline;
        }}
    """

    scroll_area = f"""
        QScrollArea {{
            background: transparent;
            background-color: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 8px;
            margin: 0px 2px 0px 0px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {h['scroll_thumb']};
            min-height: 36px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {h['scroll_thumb_hover']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
            border: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
    """

    search_input = f"""
        QLineEdit {{
            background-color: {h['search_bg']};
            color: {h['search_fg']};
            border: 1px solid {h['search_border']};
            border-radius: 10px;
            padding: 4px 10px;
            font-size: 9.5pt;
        }}
        QLineEdit:focus {{
            border: 1px solid {h['search_focus']};
        }}
    """

    return {
        "window":           window,
        "title":            title,
        "header_sub":       header_sub,
        "card_normal":      card_normal,
        "card_hero":        card_hero,
        "card_disabled":    card_disabled,
        "card_title":       card_title,
        "card_hero_title":  card_hero_title,
        "card_subtitle":    card_subtitle,
        "tag_badge":        tag_badge,
        "btn_install":      btn_install,
        "btn_open":         btn_open,
        "btn_update":       btn_update,
        "btn_disabled":     btn_disabled,
        "btn_options":      btn_options,
        "status_installed": status_installed,
        "status_available": status_available,
        "status_uninstalled": status_uninstalled,
        "status_update":    status_update,
        "toggle_btn":       toggle,
        "dock":             dock,
        "scroll_area":      scroll_area,
        "search_input":     search_input,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  ThemeManager singleton
# ──────────────────────────────────────────────────────────────────────────────

class ThemeManager:
    _inst: "ThemeManager | None" = None

    def __init__(self):
        # Default a modo oscuro por coherencia visual pro
        self._dark = True

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    # ── State ────────────────────────────────────────────────────────────────
    @property
    def is_dark(self) -> bool:
        return self._dark

    def set_dark(self, value: bool) -> None:
        self._dark = value

    def toggle(self) -> bool:
        self._dark = not self._dark
        return self._dark

    # ── Style accessors ──────────────────────────────────────────────────────
    def hub_styles(self) -> dict:
        """Return hub-level QSS dict."""
        return _build_hub_styles(_HUB_DARK if self._dark else _HUB_LIGHT)

    def app_styles(self) -> dict:
        """Return micro-app QSS dict."""
        return _build_app_styles(_APP_COLORS_DARK if self._dark else _APP_COLORS_LIGHT)

    def app_colors(self) -> dict:
        """Return the raw color tokens dict for micro-apps."""
        return _APP_COLORS_DARK if self._dark else _APP_COLORS_LIGHT
