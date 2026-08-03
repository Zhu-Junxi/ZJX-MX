from __future__ import annotations

import errno
import gc
import shutil
import time
from pathlib import Path


WINDOWS_SHARING_VIOLATION = 32
WINDOWS_LOCK_VIOLATION = 33


def is_transient_file_lock(error):
    """Return True for Windows file locks that often clear after preview release."""
    if not isinstance(error, OSError):
        return False

    winerror = getattr(error, "winerror", None)
    if winerror in {WINDOWS_SHARING_VIOLATION, WINDOWS_LOCK_VIOLATION}:
        return True

    return error.errno in {errno.EACCES, errno.EPERM} and "being used by another process" in str(error).lower()


def retry_file_operation(operation, *, attempts=8, delay=0.12):
    last_error = None
    for attempt in range(attempts):
        try:
            return operation()
        except OSError as error:
            if not is_transient_file_lock(error) or attempt == attempts - 1:
                raise
            last_error = error
            gc.collect()
            time.sleep(delay * (attempt + 1))

    if last_error is not None:
        raise last_error
    return None


def rename_path(source_path, destination_path):
    source_path = Path(source_path)
    destination_path = Path(destination_path)
    return retry_file_operation(lambda: source_path.rename(destination_path))


def move_path(source_path, destination_path):
    source_path = Path(source_path)
    destination_path = Path(destination_path)
    return retry_file_operation(lambda: shutil.move(str(source_path), str(destination_path)))


def remove_path(path):
    path = Path(path)

    def remove():
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    return retry_file_operation(remove)
