import sys
from pathlib import Path

from PySide6.QtGui import QIcon


def asset_root() -> Path:
    """Return the asset root in development and PyInstaller builds."""
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


ICON_ROOT = asset_root() / "icons"
ICON_LIGHT_ROOT = asset_root() / "icons_light"
APP_ICON_PATH = asset_root() / "app_icon.ico"
APP_ICON_FALLBACK_PATHS = (
    asset_root() / "app_icon.ico",
    asset_root() / "app_icon.png",
    asset_root() / "app_icon.svg",
)

# The app ships separate SVG strokes for dark and light themes.  The dark
# icons use soft light strokes; the light icons use stronger slate strokes so
# they remain readable on white and pale surfaces.
_CURRENT_ICON_THEME = "dark"

RESOURCE_ICON_NAMES = {
    "local_file": "file",
    "local_folder": "folder",
    "note": "note",
    "external_link": "link",
    "youtube": "video",
    "google_drive": "cloud",
    "canvas": "canvas",
}


def set_icon_theme(theme: str) -> None:
    """Set the global icon tone used by load_icon()."""
    global _CURRENT_ICON_THEME
    _CURRENT_ICON_THEME = "light" if str(theme).lower() == "light" else "dark"


def current_icon_theme() -> str:
    return _CURRENT_ICON_THEME


def icon_path(name: str, theme: str | None = None) -> Path:
    theme = "light" if str(theme or _CURRENT_ICON_THEME).lower() == "light" else "dark"
    root = ICON_LIGHT_ROOT if theme == "light" else ICON_ROOT
    themed_path = root / f"{name}.svg"
    if themed_path.exists():
        return themed_path
    return ICON_ROOT / f"{name}.svg"


def load_icon(name: str, theme: str | None = None) -> QIcon:
    path = icon_path(name, theme)
    if path.exists():
        return QIcon(str(path))
    return QIcon()


def icon_for_resource_type(resource_type: str, theme: str | None = None) -> QIcon:
    return load_icon(RESOURCE_ICON_NAMES.get(resource_type, "file"), theme)


def app_icon_path() -> Path:
    """Return the packaged app icon path."""
    return APP_ICON_PATH


def app_icon_paths() -> tuple[Path, ...]:
    """Return app icon candidates in preferred native order."""
    return APP_ICON_FALLBACK_PATHS


def load_app_icon() -> QIcon:
    """Load the application icon with fallbacks so tray icons never go blank."""
    for path in app_icon_paths():
        if not path.exists():
            continue
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    return QIcon()
