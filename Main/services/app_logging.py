from __future__ import annotations

import logging
import re
import sys
import traceback
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QObject, Signal, qInstallMessageHandler


SECRET_KEY_RE = re.compile(r"(?i)(token|password|secret|authorization|api[_-]?key)")
SECRET_VALUE_RE = re.compile(
    r"(?i)(['\"]?\b[\w-]*(?:token|password|secret|authorization|api[_-]?key)[\w-]*['\"]?\s*[:=]\s*)['\"]?([^'\"\s,;}]+)"
)
BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")

LOGGER_NAME = "zjx_lms"

_original_stdout = sys.stdout
_original_stderr = sys.stderr
_original_excepthook = sys.excepthook
_original_qt_handler = None
_logging_configured = False


def redact_secrets(value):
    text = str(value)
    text = SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}<redacted>", text)
    text = BEARER_RE.sub("Bearer <redacted>", text)
    return text


def redact_context_value(key, value):
    if SECRET_KEY_RE.search(str(key)):
        return "<redacted>"
    return redact_secrets(value)


class AppLogBus(QObject):
    entry_added = Signal(str)

    def __init__(self):
        super().__init__()
        self._entries = deque(maxlen=2000)
        self.log_file_path = None

    def add_entry(self, entry):
        entry = redact_secrets(entry).rstrip()
        if not entry:
            return
        self._entries.append(entry)
        self.entry_added.emit(entry)

    def entries(self):
        return list(self._entries)

    def clear_session(self):
        self._entries.clear()


app_log_bus = None


def get_app_log_bus():
    global app_log_bus
    if app_log_bus is None:
        app_log_bus = AppLogBus()
    return app_log_bus


class AppMemoryLogHandler(logging.Handler):
    def emit(self, record):
        try:
            get_app_log_bus().add_entry(self.format(record))
        except Exception:
            pass


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact_secrets(super().format(record))


class TeeLogStream:
    def __init__(self, original, level):
        self.original = original
        self.level = level
        self._buffer = ""
        self._writing = False

    def write(self, message):
        if not isinstance(message, str):
            message = str(message)

        try:
            if self.original is not None:
                self.original.write(message)
        except Exception:
            pass

        if self._writing:
            return len(message)

        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._log_line(line)

        return len(message)

    def flush(self):
        try:
            if self.original is not None:
                self.original.flush()
        except Exception:
            pass
        if self._buffer.strip():
            self._log_line(self._buffer)
            self._buffer = ""

    def isatty(self):
        return bool(getattr(self.original, "isatty", lambda: False)())

    def fileno(self):
        if self.original is None or not hasattr(self.original, "fileno"):
            raise OSError("No file descriptor available")
        return self.original.fileno()

    @property
    def encoding(self):
        return getattr(self.original, "encoding", "utf-8")

    def _log_line(self, line):
        line = line.rstrip()
        if not line:
            return
        try:
            self._writing = True
            logging.getLogger(LOGGER_NAME).log(self.level, line)
        except Exception:
            pass
        finally:
            self._writing = False


def get_app_logger():
    return logging.getLogger(LOGGER_NAME)


def setup_app_logging(vault_path, app_name="ZJX LMS", version=""):
    global _logging_configured, _original_qt_handler

    if _logging_configured:
        return get_app_logger()

    logger = get_app_logger()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = RedactingFormatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    memory_handler = AppMemoryLogHandler()
    memory_handler.setLevel(logging.DEBUG)
    memory_handler.setFormatter(formatter)
    memory_handler._zjx_lms_handler = True
    logger.addHandler(memory_handler)

    file_handler = None
    try:
        log_dir = Path(vault_path) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        get_app_log_bus().log_file_path = log_dir / "zjx-lms.log"
        file_handler = RotatingFileHandler(
            get_app_log_bus().log_file_path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler._zjx_lms_handler = True
        logger.addHandler(file_handler)
    except Exception as error:
        get_app_log_bus().add_entry(f"Logging file setup failed: {error}")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(memory_handler)
    if file_handler is not None:
        root_logger.addHandler(file_handler)

    sys.stdout = TeeLogStream(_original_stdout, logging.INFO)
    sys.stderr = TeeLogStream(_original_stderr, logging.ERROR)
    sys.excepthook = _exception_hook

    try:
        _original_qt_handler = qInstallMessageHandler(_qt_message_handler)
    except Exception as error:
        logger.debug("Qt message handler setup failed: %s", error)

    logging.captureWarnings(True)
    _logging_configured = True
    logger.info("%s %s logging started", app_name, version)
    logger.info("Vault path: %s", vault_path)
    return logger


def _exception_hook(exc_type, exc_value, exc_traceback):
    try:
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        get_app_logger().critical("Uncaught exception\n%s", details)
    except Exception:
        pass
    try:
        _original_excepthook(exc_type, exc_value, exc_traceback)
    except Exception:
        pass


def _qt_message_handler(mode, context, message):
    try:
        level = logging.WARNING
        mode_name = getattr(mode, "name", str(mode))
        if "Fatal" in mode_name or "Critical" in mode_name:
            level = logging.ERROR
        elif "Debug" in mode_name:
            level = logging.DEBUG
        elif "Info" in mode_name:
            level = logging.INFO
        get_app_logger().log(level, "Qt: %s", message)
    except Exception:
        pass

    if _original_qt_handler is not None:
        try:
            _original_qt_handler(mode, context, message)
        except Exception:
            pass


def log_debug(message, *args, **kwargs):
    get_app_logger().debug(redact_secrets(message), *args, **kwargs)


def log_info(message, *args, **kwargs):
    get_app_logger().info(redact_secrets(message), *args, **kwargs)


def log_warning(message, *args, **kwargs):
    get_app_logger().warning(redact_secrets(message), *args, **kwargs)


def log_error(message, *args, **kwargs):
    get_app_logger().error(redact_secrets(message), *args, **kwargs)


def log_exception(message, *args, **kwargs):
    get_app_logger().exception(redact_secrets(message), *args, **kwargs)


def log_user_visible_error(title, user_message, error=None, context=None):
    parts = [f"{title}: {user_message}"]
    if context:
        safe_context = {str(key): redact_context_value(key, value) for key, value in dict(context).items()}
        parts.append(f"context={safe_context}")
    if error is not None:
        parts.append(f"error={repr(error)}")
    get_app_logger().error(" | ".join(parts))
