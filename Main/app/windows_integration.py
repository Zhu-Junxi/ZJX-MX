from __future__ import annotations

import os
import sys
from pathlib import Path

from ui.icons import app_icon_path


NOTIFICATION_APP_NAME = "ZJX"
APP_USER_MODEL_ID = "ZJX"


def configure_windows_notification_identity():
    """Register the Windows app identity used by native tray notifications."""
    if not sys.platform.startswith("win"):
        return
    ensure_windows_notification_shortcut()
    set_windows_app_user_model_id()


def set_windows_app_user_model_id():
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def ensure_windows_notification_shortcut():
    """Create/update the Start Menu shortcut Windows uses for toast branding.

    Windows native notifications get their header icon from a Start Menu
    shortcut whose AppUserModelID matches the running process. If this fails,
    the app can still run; Windows may simply omit the notification header icon.
    """
    if not sys.platform.startswith("win"):
        return

    icon_path = app_icon_path()
    if not icon_path.exists():
        return

    try:
        import ctypes
        from ctypes import wintypes

        programs_dir = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        programs_dir.mkdir(parents=True, exist_ok=True)
        shortcut_path = programs_dir / "ZJX.lnk"
        target_path, arguments = _windows_shortcut_target()

        ctypes.windll.ole32.CoInitialize(None)
        try:
            shell_link = _create_shell_link(ctypes)
            _configure_shell_link(
                ctypes,
                wintypes,
                shell_link,
                target_path=target_path,
                arguments=arguments,
                icon_path=icon_path,
            )
            _set_shell_link_app_id(ctypes, wintypes, shell_link)
            _save_shell_link(ctypes, wintypes, shell_link, shortcut_path)
        finally:
            ctypes.windll.ole32.CoUninitialize()
    except Exception:
        pass


def _windows_shortcut_target():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve(), ""

    script_path = Path(__file__).resolve().parents[1] / "main.py"
    executable = Path(sys.executable).resolve()
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.exists():
        executable = pythonw
    return executable, f'"{script_path}"'


def _guid_bytes(ctypes, value):
    import uuid

    return (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID(value).bytes_le)


def _vtable_method(ctypes, com_pointer, index, restype, *argtypes):
    vtable = ctypes.cast(com_pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtable[index])


def _create_shell_link(ctypes):
    shell_link_clsid = _guid_bytes(ctypes, "00021401-0000-0000-C000-000000000046")
    shell_link_iid = _guid_bytes(ctypes, "000214F9-0000-0000-C000-000000000046")
    shell_link = ctypes.c_void_p()
    ctypes.oledll.ole32.CoCreateInstance(
        ctypes.byref(shell_link_clsid),
        None,
        1,
        ctypes.byref(shell_link_iid),
        ctypes.byref(shell_link),
    )
    return shell_link


def _configure_shell_link(ctypes, wintypes, shell_link, *, target_path, arguments, icon_path):
    set_working_dir = _vtable_method(ctypes, shell_link, 9, ctypes.HRESULT, wintypes.LPCWSTR)
    set_arguments = _vtable_method(ctypes, shell_link, 11, ctypes.HRESULT, wintypes.LPCWSTR)
    set_icon_location = _vtable_method(ctypes, shell_link, 17, ctypes.HRESULT, wintypes.LPCWSTR, ctypes.c_int)
    set_path = _vtable_method(ctypes, shell_link, 20, ctypes.HRESULT, wintypes.LPCWSTR)

    set_path(shell_link, str(target_path))
    set_arguments(shell_link, arguments)
    set_working_dir(shell_link, str(target_path.parent))
    set_icon_location(shell_link, str(icon_path), 0)


def _set_shell_link_app_id(ctypes, wintypes, shell_link):
    property_store_iid = _guid_bytes(ctypes, "886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")
    query_interface = _vtable_method(ctypes, shell_link, 0, ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    property_store = ctypes.c_void_p()
    if query_interface(shell_link, ctypes.byref(property_store_iid), ctypes.byref(property_store)) != 0:
        return

    class PROPERTYKEY(ctypes.Structure):
        _fields_ = [("fmtid", ctypes.c_byte * 16), ("pid", wintypes.DWORD)]

    class PROPVARIANT(ctypes.Structure):
        _fields_ = [
            ("vt", ctypes.c_ushort),
            ("wReserved1", ctypes.c_ushort),
            ("wReserved2", ctypes.c_ushort),
            ("wReserved3", ctypes.c_ushort),
            ("pwszVal", wintypes.LPWSTR),
        ]

    set_value = _vtable_method(ctypes, property_store, 6, ctypes.HRESULT, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))
    commit = _vtable_method(ctypes, property_store, 7, ctypes.HRESULT)
    app_id_key = PROPERTYKEY(_guid_bytes(ctypes, "9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), 5)
    app_id_value = PROPVARIANT(31, 0, 0, 0, APP_USER_MODEL_ID)
    set_value(property_store, ctypes.byref(app_id_key), ctypes.byref(app_id_value))
    commit(property_store)


def _save_shell_link(ctypes, wintypes, shell_link, shortcut_path):
    persist_file_iid = _guid_bytes(ctypes, "0000010b-0000-0000-C000-000000000046")
    query_interface = _vtable_method(ctypes, shell_link, 0, ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    persist_file = ctypes.c_void_p()
    if query_interface(shell_link, ctypes.byref(persist_file_iid), ctypes.byref(persist_file)) != 0:
        return
    save = _vtable_method(ctypes, persist_file, 6, ctypes.HRESULT, wintypes.LPCWSTR, wintypes.BOOL)
    save(persist_file, str(shortcut_path), True)
