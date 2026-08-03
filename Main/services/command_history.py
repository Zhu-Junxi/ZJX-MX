from __future__ import annotations

import copy
import filecmp
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.file_operations import retry_file_operation
from core.helpers import safe_read_json, safe_write_json


class SnapshotRestoreError(RuntimeError):
    """Raised when an undo/redo restore cannot be completed safely."""


@dataclass(frozen=True)
class ActionHistoryEntry:
    action_type: str
    label: str
    timestamp: str
    affected_item: str = ""
    status: str = "done"

    def display_text(self) -> str:
        prefix = self.timestamp[11:19] if "T" in self.timestamp and len(self.timestamp) >= 19 else self.timestamp
        status = f" [{self.status}]" if self.status and self.status != "done" else ""
        return f"{prefix} - {self.label}{status}"


class UndoableAction:
    """Base action object for the app's undo/redo history."""

    action_type = "action"

    def __init__(
        self,
        description: str,
        *,
        action_type: str | None = None,
        affected_item: str = "",
        previous_state: dict[str, Any] | None = None,
        new_state: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ):
        self.description = description
        self.display_label = description
        self.action_type = action_type or self.action_type
        self.affected_item = affected_item
        self.previous_state = previous_state or {}
        self.new_state = new_state or {}
        self.timestamp = timestamp or datetime.now().isoformat(timespec="seconds")

    def do(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError

    def redo(self):
        return self.do()

    def execute(self):
        return self.redo()

    def get_description(self) -> str:
        return self.display_label

    def history_entry(self, *, status: str = "done") -> ActionHistoryEntry:
        return ActionHistoryEntry(
            action_type=self.action_type,
            label=self.get_description(),
            timestamp=self.timestamp,
            affected_item=self.affected_item,
            status=status,
        )

    def cleanup(self):
        return None


Command = UndoableAction


@dataclass
class RestoreTransaction:
    restore_root: Path
    created_paths: list[Path] = field(default_factory=list)
    backup_paths: dict[Path, Path] = field(default_factory=dict)


class SnapshotCommand(UndoableAction):
    """Undoable action backed by before/after snapshots of one context folder."""

    def __init__(self, description, target_dir, *, action_type="snapshot", affected_item=""):
        super().__init__(
            description,
            action_type=action_type,
            affected_item=affected_item or str(target_dir),
        )
        self.target_dir = Path(target_dir)
        self.before_dir = None
        self.after_dir = None
        self.before_exists = None
        self.after_exists = None

    def capture_before(self):
        self.before_dir, self.before_exists = self._capture_snapshot("before")
        self.previous_state = {
            "target_dir": str(self.target_dir),
            "exists": bool(self.before_exists),
            "snapshot": str(self.before_dir),
        }

    def capture_after(self):
        self.after_dir, self.after_exists = self._capture_snapshot("after")
        self.new_state = {
            "target_dir": str(self.target_dir),
            "exists": bool(self.after_exists),
            "snapshot": str(self.after_dir),
        }

    def has_changes(self):
        if not self.before_dir or not self.after_dir:
            return False
        if bool(self.before_exists) != bool(self.after_exists):
            return True
        if not self.before_exists and not self.after_exists:
            return False
        return not self._dirs_equal(self.before_dir, self.after_dir)

    def do(self):
        if self.after_dir:
            self._restore_snapshot(self.after_dir, self.after_exists)

    def undo(self):
        if self.before_dir:
            self._restore_snapshot(self.before_dir, self.before_exists)

    def cleanup(self):
        for snapshot_dir in [self.before_dir, self.after_dir]:
            if snapshot_dir:
                shutil.rmtree(Path(snapshot_dir).parent, ignore_errors=True)

    def _capture_snapshot(self, label):
        snapshot_parent = Path(tempfile.mkdtemp(prefix=f"zjx_lms_{label}_"))
        snapshot_dir = snapshot_parent / "snapshot"
        target_existed = self.target_dir.exists()

        if target_existed:
            shutil.copytree(self.target_dir, snapshot_dir)
        else:
            snapshot_dir.mkdir(parents=True, exist_ok=True)

        return snapshot_dir, target_existed

    def _restore_snapshot(self, snapshot_dir, snapshot_exists=True):
        snapshot_dir = Path(snapshot_dir)
        if not snapshot_dir.exists():
            raise SnapshotRestoreError(f"Undo snapshot is missing: {snapshot_dir}")

        self.target_dir.parent.mkdir(parents=True, exist_ok=True)
        restore_root = self._restore_workspace()
        try:
            if snapshot_exists:
                if self.target_dir.exists():
                    self._restore_existing_target(snapshot_dir, restore_root)
                else:
                    self._restore_missing_target(snapshot_dir, restore_root)
            else:
                self._restore_deleted_target(restore_root)
        finally:
            self._remove_empty_restore_workspace(restore_root)

    def _restore_missing_target(self, snapshot_dir, restore_root):
        staged_dir = restore_root / f"{uuid.uuid4().hex}_staged"
        try:
            shutil.copytree(snapshot_dir, staged_dir)
            retry_file_operation(lambda: staged_dir.rename(self.target_dir), attempts=12, delay=0.15)
        except Exception as error:
            shutil.rmtree(staged_dir, ignore_errors=True)
            raise SnapshotRestoreError(
                "The undo snapshot could not be restored. No live files were changed."
            ) from error

    def _restore_deleted_target(self, restore_root):
        if not self.target_dir.exists():
            return

        backup_dir = restore_root / f"{uuid.uuid4().hex}_delete_backup"
        try:
            shutil.copytree(self.target_dir, backup_dir)
            retry_file_operation(lambda: shutil.rmtree(self.target_dir), attempts=12, delay=0.15)
        except Exception as error:
            if backup_dir.exists():
                self._restore_existing_target(backup_dir, restore_root)
            raise SnapshotRestoreError(
                "The undo/redo delete could not complete safely. Current files were restored from backup where possible."
            ) from error
        finally:
            shutil.rmtree(backup_dir, ignore_errors=True)

    def _restore_existing_target(self, snapshot_dir, restore_root):
        transaction = RestoreTransaction(restore_root=restore_root)
        try:
            self._ensure_snapshot_directories(snapshot_dir, transaction)
            self._restore_snapshot_files(snapshot_dir, transaction)
            self._remove_target_extras(snapshot_dir, transaction)
        except Exception as error:
            rollback_error = self._rollback_transaction(transaction)
            message = (
                "The undo/redo restore could not complete safely. "
                "No files were intentionally deleted. Close any open files in this vault and try again."
            )
            if rollback_error:
                message += " Some automatic rollback steps also failed; check the vault before continuing."
            raise SnapshotRestoreError(message) from error
        finally:
            self._cleanup_transaction(transaction)

    def _ensure_snapshot_directories(self, snapshot_dir, transaction):
        for source_dir in self._iter_dirs(snapshot_dir):
            relative = source_dir.relative_to(snapshot_dir)
            destination = self.target_dir / relative
            if not destination.exists():
                destination.mkdir(parents=True, exist_ok=True)
                transaction.created_paths.append(destination)

    def _restore_snapshot_files(self, snapshot_dir, transaction):
        for source_file in self._iter_files(snapshot_dir):
            relative = source_file.relative_to(snapshot_dir)
            destination = self.target_dir / relative
            if destination.exists() and self._files_equal(source_file, destination):
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                self._backup_path(destination, relative, transaction)
            else:
                transaction.created_paths.append(destination)
            self._copy_file_replace(source_file, destination, transaction.restore_root)

    def _remove_target_extras(self, snapshot_dir, transaction):
        snapshot_relatives = {
            path.relative_to(snapshot_dir)
            for path in snapshot_dir.rglob("*")
        }
        target_paths = sorted(
            [
                path for path in self.target_dir.rglob("*")
                if not self._is_restore_workspace_path(path)
                and path.relative_to(self.target_dir) not in snapshot_relatives
            ],
            key=lambda path: len(path.parts),
            reverse=True,
        )

        for path in target_paths:
            relative = path.relative_to(self.target_dir)
            if not path.exists():
                continue
            self._backup_path(path, relative, transaction)
            if path.is_dir():
                retry_file_operation(lambda item=path: shutil.rmtree(item), attempts=12, delay=0.15)
            else:
                retry_file_operation(lambda item=path: item.unlink(), attempts=12, delay=0.15)

    def _backup_path(self, path, relative, transaction):
        if relative in transaction.backup_paths:
            return transaction.backup_paths[relative]

        backup_path = transaction.restore_root / f"{uuid.uuid4().hex}_backup" / relative
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, backup_path)
        else:
            shutil.copy2(path, backup_path)
        transaction.backup_paths[relative] = backup_path
        return backup_path

    def _copy_file_replace(self, source_file, destination, restore_root):
        temp_file = restore_root / f"{uuid.uuid4().hex}_{destination.name}.tmp"
        try:
            shutil.copy2(source_file, temp_file)
            retry_file_operation(lambda: os.replace(temp_file, destination), attempts=12, delay=0.15)
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

    def _rollback_transaction(self, transaction):
        rollback_error = None

        for path in reversed(transaction.created_paths):
            try:
                if path.is_dir():
                    path.rmdir()
                elif path.exists():
                    path.unlink()
            except OSError as error:
                rollback_error = rollback_error or error

        for relative, backup_path in reversed(list(transaction.backup_paths.items())):
            destination = self.target_dir / relative
            try:
                if destination.exists():
                    if destination.is_dir():
                        shutil.rmtree(destination, ignore_errors=True)
                    else:
                        destination.unlink()
                destination.parent.mkdir(parents=True, exist_ok=True)
                if backup_path.is_dir():
                    shutil.copytree(backup_path, destination)
                else:
                    shutil.copy2(backup_path, destination)
            except OSError as error:
                rollback_error = rollback_error or error

        return rollback_error

    def _cleanup_transaction(self, transaction):
        for backup_path in transaction.backup_paths.values():
            shutil.rmtree(self._backup_root_for(backup_path), ignore_errors=True)

    def _backup_root_for(self, backup_path):
        root = Path(backup_path)
        while root.parent != self._restore_workspace_path_for_target():
            if root.parent == root:
                break
            root = root.parent
        return root

    def _restore_workspace_path_for_target(self):
        return self.target_dir.parent / ".zjx_lms_undo_restore"

    def _restore_workspace(self):
        restore_root = self._restore_workspace_path_for_target()
        restore_root.mkdir(parents=True, exist_ok=True)
        return restore_root

    def _is_restore_workspace_path(self, path):
        restore_root = self._restore_workspace_path_for_target()
        try:
            Path(path).resolve().relative_to(restore_root.resolve())
            return True
        except (ValueError, FileNotFoundError):
            return False

    def _remove_empty_restore_workspace(self, restore_root):
        try:
            Path(restore_root).rmdir()
        except OSError:
            pass

    def _iter_dirs(self, root):
        return sorted(
            [path for path in Path(root).rglob("*") if path.is_dir()],
            key=lambda path: len(path.parts),
        )

    def _iter_files(self, root):
        return sorted(path for path in Path(root).rglob("*") if path.is_file())

    def _files_equal(self, left, right):
        return Path(right).exists() and filecmp.cmp(left, right, shallow=False)

    def _dirs_equal(self, left, right):
        comparison = filecmp.dircmp(left, right)

        if comparison.left_only or comparison.right_only or comparison.funny_files:
            return False

        for filename in comparison.common_files:
            if not self._files_equal(Path(left) / filename, Path(right) / filename):
                return False

        for subdir in comparison.common_dirs:
            if not self._dirs_equal(Path(left) / subdir, Path(right) / subdir):
                return False

        return True


class CanvasSyncAction(SnapshotCommand):
    """Undoable broad Canvas sync over one user's vault subtree."""

    def __init__(self, user_dir, user_name="user"):
        super().__init__(
            f"Sync Canvas data for {user_name or 'user'}",
            user_dir,
            action_type="canvas_sync",
            affected_item=str(user_dir),
        )


class ResourceLibraryMultiContextAction(UndoableAction):
    """Undoable Resource Library operation that can touch several contexts."""

    action_type = "resource_library_multi_context"

    def __init__(self, description, context_dirs):
        self.commands = []
        seen = set()
        affected = []

        for context_dir in context_dirs:
            context_dir = Path(context_dir)
            key = str(context_dir.resolve()) if context_dir.exists() else str(context_dir)
            if key in seen:
                continue
            seen.add(key)
            affected.append(str(context_dir))
            self.commands.append(
                SnapshotCommand(
                    description,
                    context_dir,
                    action_type=self.action_type,
                    affected_item=str(context_dir),
                )
            )

        super().__init__(
            description,
            action_type=self.action_type,
            affected_item="; ".join(affected),
        )

    def capture_before(self):
        for command in self.commands:
            command.capture_before()
        self.previous_state = {"contexts": [command.previous_state for command in self.commands]}

    def capture_after(self):
        for command in self.commands:
            command.capture_after()
        self.new_state = {"contexts": [command.new_state for command in self.commands]}

    def has_changes(self):
        return any(command.has_changes() for command in self.commands)

    def do(self):
        self._restore_all(
            self.commands,
            restore=lambda command: command.do(),
            rollback=lambda command: command.undo(),
            action="redo",
        )

    def execute(self):
        return self.do()

    def undo(self):
        self._restore_all(
            list(reversed(self.commands)),
            restore=lambda command: command.undo(),
            rollback=lambda command: command.do(),
            action="undo",
        )

    def cleanup(self):
        for command in self.commands:
            command.cleanup()

    def _restore_all(self, commands, *, restore, rollback, action):
        restored = []
        try:
            for command in commands:
                restore(command)
                restored.append(command)
        except Exception as error:
            rollback_errors = []
            for command in reversed(restored):
                try:
                    rollback(command)
                except Exception as rollback_error:
                    rollback_errors.append(repr(rollback_error))

            message = (
                f"The Resource Library {action} could not complete safely. "
                "Completed context restores were rolled back. Close any open files in this vault and try again."
            )
            if rollback_errors:
                message = (
                    f"The Resource Library {action} could not complete safely, and one or more rollback steps "
                    "also failed. Check the vault before continuing, then close any open files and try again."
                )
            raise SnapshotRestoreError(message) from error


class FileRenameAction(UndoableAction):
    """Undoable rename for unmanaged local files or folders."""

    action_type = "rename_file"

    def __init__(self, source_path, destination_path, *, description=None):
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_path)
        label = description or f"Renamed file: {self.source_path.name} -> {self.destination_path.name}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.source_path),
            previous_state={"path": str(self.source_path), "name": self.source_path.name},
            new_state={"path": str(self.destination_path), "name": self.destination_path.name},
        )

    def do(self):
        self._rename(self.source_path, self.destination_path)

    def undo(self):
        self._rename(self.destination_path, self.source_path)

    def _rename(self, source, destination):
        source = Path(source)
        destination = Path(destination)

        if source == destination:
            return
        if not source.exists():
            raise SnapshotRestoreError(f"Cannot rename missing item: {source}")
        if destination.exists():
            raise SnapshotRestoreError(f"Cannot rename because destination already exists: {destination}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        retry_file_operation(lambda: source.rename(destination), attempts=12, delay=0.15)


class FileMoveAction(UndoableAction):
    """Undoable move for unmanaged local files or folders."""

    action_type = "move_file"

    def __init__(self, source_path, destination_path, *, description=None):
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_path)
        item_kind = "folder" if self.source_path.is_dir() else "file"
        label = description or f"Moved {item_kind}: {self.source_path.name} -> {self.destination_path.parent.name}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.source_path),
            previous_state={"path": str(self.source_path)},
            new_state={"path": str(self.destination_path)},
        )

    def do(self):
        self._move(self.source_path, self.destination_path)

    def undo(self):
        self._move(self.destination_path, self.source_path)

    def _move(self, source, destination):
        source = Path(source)
        destination = Path(destination)

        if source == destination:
            return
        if not source.exists():
            raise SnapshotRestoreError(f"Cannot move missing item: {source}")
        if destination.exists():
            raise SnapshotRestoreError(f"Cannot move because destination already exists: {destination}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        retry_file_operation(
            lambda: shutil.move(str(source), str(destination)),
            attempts=12,
            delay=0.15,
        )


class FileCreateAction(UndoableAction):
    """Undoable creation for unmanaged local files or folders."""

    action_type = "create_file"

    def __init__(self, path, *, is_directory=False, content=b"", description=None):
        self.path = Path(path)
        self.is_directory = is_directory
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.content = content or b""
        self.backup_parent = Path(tempfile.mkdtemp(prefix="zjx_lms_create_action_"))
        self.backup_path = self.backup_parent / self.path.name
        item_kind = "folder" if is_directory else "file"
        label = description or f"Created {item_kind}: {self.path.name}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.path),
            previous_state={"path": str(self.path), "exists": False},
            new_state={"path": str(self.path), "exists": True, "is_directory": is_directory},
        )

    def do(self):
        if self.backup_path.exists():
            self._restore_from_backup()
            return

        if self.path.exists():
            raise SnapshotRestoreError(f"Cannot create item because destination already exists: {self.path}")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.is_directory:
            self.path.mkdir(parents=True, exist_ok=False)
        else:
            self.path.write_bytes(self.content)

    def undo(self):
        if not self.path.exists():
            return
        if self.backup_path.exists():
            raise SnapshotRestoreError(f"Cannot undo create because backup already exists: {self.backup_path}")

        self.backup_parent.mkdir(parents=True, exist_ok=True)
        retry_file_operation(
            lambda: shutil.move(str(self.path), str(self.backup_path)),
            attempts=12,
            delay=0.15,
        )

    def cleanup(self):
        shutil.rmtree(self.backup_parent, ignore_errors=True)

    def _restore_from_backup(self):
        if self.path.exists():
            raise SnapshotRestoreError(f"Cannot redo create because destination already exists: {self.path}")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        retry_file_operation(
            lambda: shutil.move(str(self.backup_path), str(self.path)),
            attempts=12,
            delay=0.15,
        )


class FileCopyAction(UndoableAction):
    """Undoable copy/import of a file or folder into the vault."""

    action_type = "copy_file"

    def __init__(self, source_path, destination_path, *, description=None):
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_path)
        self.backup_parent = Path(tempfile.mkdtemp(prefix="zjx_lms_copy_action_"))
        self.backup_path = self.backup_parent / self.destination_path.name
        item_kind = "folder" if self.source_path.is_dir() else "file"
        label = description or f"Imported {item_kind}: {self.source_path.name}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.destination_path),
            previous_state={"source_path": str(self.source_path), "destination_exists": False},
            new_state={"path": str(self.destination_path), "exists": True},
        )

    def do(self):
        if self.backup_path.exists():
            self._restore_from_backup()
            return

        if not self.source_path.exists():
            raise SnapshotRestoreError(f"Cannot import missing item: {self.source_path}")
        if self.destination_path.exists():
            raise SnapshotRestoreError(f"Cannot import because destination already exists: {self.destination_path}")

        self.destination_path.parent.mkdir(parents=True, exist_ok=True)
        if self.source_path.is_dir():
            shutil.copytree(self.source_path, self.destination_path)
        else:
            retry_file_operation(
                lambda: shutil.copy2(self.source_path, self.destination_path),
                attempts=12,
                delay=0.15,
            )

    def undo(self):
        if not self.destination_path.exists():
            return
        if self.backup_path.exists():
            raise SnapshotRestoreError(f"Cannot undo import because backup already exists: {self.backup_path}")

        self.backup_parent.mkdir(parents=True, exist_ok=True)
        retry_file_operation(
            lambda: shutil.move(str(self.destination_path), str(self.backup_path)),
            attempts=12,
            delay=0.15,
        )

    def cleanup(self):
        shutil.rmtree(self.backup_parent, ignore_errors=True)

    def _restore_from_backup(self):
        if self.destination_path.exists():
            raise SnapshotRestoreError(f"Cannot redo import because destination already exists: {self.destination_path}")

        self.destination_path.parent.mkdir(parents=True, exist_ok=True)
        retry_file_operation(
            lambda: shutil.move(str(self.backup_path), str(self.destination_path)),
            attempts=12,
            delay=0.15,
        )


class FileContentUpdateAction(UndoableAction):
    """Undoable replacement of a file's bytes."""

    action_type = "edit_file"

    def __init__(self, path, before_content, after_content, *, description=None):
        self.path = Path(path)
        self.before_content = self._as_bytes(before_content)
        self.after_content = self._as_bytes(after_content)
        label = description or f"Edited file: {self.path.name}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.path),
            previous_state={"path": str(self.path), "bytes": len(self.before_content)},
            new_state={"path": str(self.path), "bytes": len(self.after_content)},
        )

    def do(self):
        self._write_content(self.after_content)

    def undo(self):
        self._write_content(self.before_content)

    def _write_content(self, content):
        if self.path.exists() and self.path.is_dir():
            raise SnapshotRestoreError(f"Cannot write file content because path is a folder: {self.path}")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.path.parent / f".{self.path.name}.{uuid.uuid4().hex}.tmp"
        try:
            temp_file.write_bytes(content)
            retry_file_operation(lambda: os.replace(temp_file, self.path), attempts=12, delay=0.15)
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

    def _as_bytes(self, content):
        if isinstance(content, bytes):
            return content
        if isinstance(content, str):
            return content.encode("utf-8")
        return bytes(content or b"")


class FileDeleteAction(UndoableAction):
    """Undoable delete for unmanaged local files or folders.

    The live item is moved into an action-owned backup instead of being
    permanently removed while the action remains in the undo/redo stacks.
    """

    action_type = "delete_file"

    def __init__(self, path, *, description=None):
        self.path = Path(path)
        self.backup_parent = Path(tempfile.mkdtemp(prefix="zjx_lms_delete_action_"))
        self.backup_path = self.backup_parent / self.path.name
        item_kind = "folder" if self.path.is_dir() else "file"
        label = description or f"Deleted {item_kind}: {self.path.name}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.path),
            previous_state={"path": str(self.path), "exists": True},
            new_state={"path": str(self.path), "exists": False},
        )

    def do(self):
        self._move_to_backup()

    def undo(self):
        self._restore_from_backup()

    def cleanup(self):
        shutil.rmtree(self.backup_parent, ignore_errors=True)

    def _move_to_backup(self):
        if not self.path.exists():
            raise SnapshotRestoreError(f"Cannot delete missing item: {self.path}")
        if self.backup_path.exists():
            raise SnapshotRestoreError(f"Cannot delete because backup already exists: {self.backup_path}")

        self.backup_parent.mkdir(parents=True, exist_ok=True)
        retry_file_operation(
            lambda: shutil.move(str(self.path), str(self.backup_path)),
            attempts=12,
            delay=0.15,
        )

    def _restore_from_backup(self):
        if not self.backup_path.exists():
            raise SnapshotRestoreError(f"Cannot undo delete because backup is missing: {self.backup_path}")
        if self.path.exists():
            raise SnapshotRestoreError(f"Cannot undo delete because destination already exists: {self.path}")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        retry_file_operation(
            lambda: shutil.move(str(self.backup_path), str(self.path)),
            attempts=12,
            delay=0.15,
        )


class ResourceAddAction(UndoableAction):
    """Undoable addition of a resource metadata entry."""

    action_type = "add_resource"

    def __init__(self, vault, user_id, course_id, assignment_id, resource, *, description=None):
        self.vault = vault
        self.user_id = user_id
        self.course_id = course_id
        self.assignment_id = assignment_id
        self.resource = copy.deepcopy(resource)
        self.resource["id"] = self.resource.get("id") or f"res_{uuid.uuid4().hex[:10]}"
        label = description or f"Added resource: {self.resource.get('title', self.resource['id'])}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=self.resource["id"],
            previous_state={"exists": False},
            new_state=copy.deepcopy(self.resource),
        )

    def do(self):
        if self._resource_exists():
            raise SnapshotRestoreError(f"Cannot add resource because it already exists: {self.resource['id']}")

        self.resource = copy.deepcopy(
            self.vault.add_resource(
                self.user_id,
                self.course_id,
                self.assignment_id,
                copy.deepcopy(self.resource),
            )
        )
        self.new_state = copy.deepcopy(self.resource)

    def undo(self):
        if not self._resource_exists():
            return

        self.vault.delete_resource(copy.deepcopy(self.resource), delete_physical=False)

    def _resource_exists(self):
        resources = self.vault.load_resources(self.user_id, self.course_id, self.assignment_id)
        return any(item.get("id") == self.resource.get("id") for item in resources)


class ResourceDeleteAction(UndoableAction):
    """Undoable removal of a resource metadata entry."""

    action_type = "delete_resource"

    def __init__(self, vault, resource, *, description=None):
        self.vault = vault
        self.resource = copy.deepcopy(resource)
        label = description or f"Deleted resource: {self.resource.get('title', self.resource.get('id', 'resource'))}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.resource.get("id", "")),
            previous_state=copy.deepcopy(self.resource),
            new_state={"exists": False},
        )

    def do(self):
        if not self._resource_exists():
            raise SnapshotRestoreError(f"Cannot delete missing resource: {self.resource.get('id')}")

        self.vault.delete_resource(copy.deepcopy(self.resource), delete_physical=False)

    def undo(self):
        if self._resource_exists():
            raise SnapshotRestoreError(f"Cannot restore resource because it already exists: {self.resource.get('id')}")

        self.resource = copy.deepcopy(
            self.vault.add_resource(
                self.resource["user_id"],
                self.resource["course_id"],
                self.resource.get("assignment_id"),
                copy.deepcopy(self.resource),
            )
        )
        self.previous_state = copy.deepcopy(self.resource)

    def _resource_exists(self):
        resources = self.vault.load_resources(
            self.resource["user_id"],
            self.resource["course_id"],
            self.resource.get("assignment_id"),
        )
        return any(item.get("id") == self.resource.get("id") for item in resources)


class ResourceUpdateAction(UndoableAction):
    """Undoable replacement of one resource metadata entry."""

    action_type = "edit_resource"

    def __init__(self, vault, before_resource, after_resource, *, description=None):
        self.vault = vault
        self.before_resource = copy.deepcopy(before_resource)
        self.after_resource = copy.deepcopy(after_resource)
        if self.before_resource.get("id") != self.after_resource.get("id"):
            raise ValueError("ResourceUpdateAction requires matching resource ids.")

        label = description or f"Edited resource: {self.before_resource.get('title', self.before_resource.get('id', 'resource'))}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.before_resource.get("id", "")),
            previous_state=copy.deepcopy(self.before_resource),
            new_state=copy.deepcopy(self.after_resource),
        )

    def do(self):
        self._replace_resource(self.after_resource)

    def undo(self):
        self._replace_resource(self.before_resource)

    def _replace_resource(self, resource):
        user_id = resource["user_id"]
        course_id = resource["course_id"]
        assignment_id = resource.get("assignment_id")
        resources = self.vault.load_resources(user_id, course_id, assignment_id)

        for index, existing in enumerate(resources):
            if existing.get("id") == resource.get("id"):
                resources[index] = copy.deepcopy(resource)
                self.vault.save_resources(user_id, course_id, assignment_id, resources)
                return

        raise SnapshotRestoreError(f"Cannot update missing resource: {resource.get('id')}")


class CourseCreateAction(UndoableAction):
    """Undoable creation of a course workspace."""

    action_type = "create_course"

    def __init__(self, vault, user_id, code, name, *, description=None):
        self.vault = vault
        self.user_id = user_id
        self.code = code
        self.name = name
        self.course = None
        label = description or f"Created course: {code}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item="",
            previous_state={"exists": False},
            new_state={"code": code, "name": name},
        )

    def do(self):
        if self.course:
            self._restore_course()
        else:
            self.course = copy.deepcopy(self.vault.add_course(self.user_id, self.code, self.name))
        self.affected_item = self.course["id"]
        self.new_state = copy.deepcopy(self.course)

    def undo(self):
        if not self.course:
            return
        if self.vault.get_course(self.user_id, self.course["id"]):
            self.vault.delete_course(self.user_id, self.course["id"])

    def _restore_course(self):
        course_id = self.course["id"]
        if self.vault.get_course(self.user_id, course_id):
            raise SnapshotRestoreError(f"Cannot restore course because it already exists: {course_id}")

        self.vault.course_dir(self.user_id, course_id).mkdir(parents=True, exist_ok=True)
        safe_write_json(self.vault.course_json_path(self.user_id, course_id), copy.deepcopy(self.course))
        self.vault.assignments_dir(self.user_id, course_id).mkdir(parents=True, exist_ok=True)
        self.vault.ensure_context_dirs(self.user_id, course_id, assignment_id=None)


class CourseUpdateAction(UndoableAction):
    """Undoable update of one course metadata object."""

    action_type = "edit_course"

    def __init__(self, vault, user_id, before_course, fields, *, description=None):
        self.vault = vault
        self.user_id = user_id
        self.before_course = copy.deepcopy(before_course)
        self.fields = copy.deepcopy(fields)
        self.after_course = None
        label = description or f"Edited course: {self.before_course.get('code', self.before_course.get('id', 'course'))}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.before_course.get("id", "")),
            previous_state=copy.deepcopy(self.before_course),
            new_state=copy.deepcopy(fields),
        )

    def do(self):
        if self.after_course:
            self._replace_course(self.after_course)
        else:
            updated = self.vault.update_course_fields(
                self.user_id,
                self.before_course["id"],
                **copy.deepcopy(self.fields),
            )
            if not updated:
                raise SnapshotRestoreError(f"Cannot update missing course: {self.before_course.get('id')}")
            self.after_course = copy.deepcopy(updated)
        self.new_state = copy.deepcopy(self.after_course)

    def undo(self):
        self._replace_course(self.before_course)

    def _replace_course(self, course):
        course_id = course["id"]
        if not self.vault.get_course(self.user_id, course_id):
            raise SnapshotRestoreError(f"Cannot replace missing course: {course_id}")

        safe_write_json(
            self.vault.course_json_path(self.user_id, course_id),
            copy.deepcopy(course),
        )


class AssignmentCreateAction(UndoableAction):
    """Undoable creation of an assignment workspace."""

    action_type = "create_assignment"

    def __init__(self, vault, user_id, course_id, title, due_date="", status="Not started", *, description=None):
        self.vault = vault
        self.user_id = user_id
        self.course_id = course_id
        self.title = title
        self.due_date = due_date
        self.status = status
        self.assignment = None
        label = description or f"Created assignment: {title}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item="",
            previous_state={"exists": False},
            new_state={"title": title, "due_date": due_date, "status": status},
        )

    def do(self):
        if self.assignment:
            self._restore_assignment()
        else:
            self.assignment = copy.deepcopy(
                self.vault.add_assignment(
                    self.user_id,
                    self.course_id,
                    self.title,
                    self.due_date,
                    self.status,
                )
            )
        self.affected_item = self.assignment["id"]
        self.new_state = copy.deepcopy(self.assignment)

    def undo(self):
        if not self.assignment:
            return
        if self.vault.get_assignment(self.user_id, self.course_id, self.assignment["id"]):
            self.vault.delete_assignment(self.user_id, self.course_id, self.assignment["id"])

    def _restore_assignment(self):
        assignment_id = self.assignment["id"]
        if self.vault.get_assignment(self.user_id, self.course_id, assignment_id):
            raise SnapshotRestoreError(f"Cannot restore assignment because it already exists: {assignment_id}")

        self.vault.assignment_dir(self.user_id, self.course_id, assignment_id).mkdir(parents=True, exist_ok=True)
        safe_write_json(
            self.vault.assignment_json_path(self.user_id, self.course_id, assignment_id),
            copy.deepcopy(self.assignment),
        )
        self.vault.ensure_context_dirs(self.user_id, self.course_id, assignment_id)


class UserCreateAction(UndoableAction):
    """Undoable creation of a user profile and vault folder."""

    action_type = "create_user"

    def __init__(self, vault, name, *, university="", canvas_access_token="", canvas_base_url="", description=None):
        self.vault = vault
        self.name = name
        self.university = university
        self.canvas_access_token = canvas_access_token
        self.canvas_base_url = canvas_base_url
        self.user = None
        label = description or f"Created user: {name}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item="",
            previous_state={"exists": False},
            new_state={"name": name, "university": university},
        )

    def do(self):
        if self.user:
            self._restore_user()
        else:
            self.user = copy.deepcopy(
                self.vault.add_user(
                    self.name,
                    university=self.university,
                    canvas_access_token=self.canvas_access_token,
                    canvas_base_url=self.canvas_base_url or "https://canvas.sydney.edu.au",
                )
            )
        self.affected_item = self.user["id"]
        self.new_state = copy.deepcopy(self.user)

    def undo(self):
        if not self.user:
            return
        if self.vault.get_user(self.user["id"]):
            self.vault.delete_user(self.user["id"])

    def _restore_user(self):
        user_id = self.user["id"]
        if self.vault.get_user(user_id):
            raise SnapshotRestoreError(f"Cannot restore user because it already exists: {user_id}")

        users_data = safe_read_json(self.vault.users_index_path(), {"users": []})
        users = list(users_data.get("users", []))
        users.append(copy.deepcopy(self.user))
        users_data["users"] = users
        safe_write_json(self.vault.users_index_path(), users_data)
        self.vault.create_user_structure(copy.deepcopy(self.user))


class UserUpdateAction(UndoableAction):
    """Undoable update of one user profile."""

    action_type = "edit_user"

    def __init__(self, vault, before_user, fields, *, description=None):
        self.vault = vault
        self.before_user = copy.deepcopy(before_user)
        self.fields = copy.deepcopy(fields)
        self.after_user = None
        label = description or f"Edited user: {self.before_user.get('name', self.before_user.get('id', 'user'))}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.before_user.get("id", "")),
            previous_state=copy.deepcopy(self.before_user),
            new_state=copy.deepcopy(fields),
        )

    def do(self):
        if self.after_user:
            self._replace_user(self.after_user)
        else:
            updated = self.vault.update_user(self.before_user["id"], **copy.deepcopy(self.fields))
            if not updated:
                raise SnapshotRestoreError(f"Cannot update missing user: {self.before_user.get('id')}")
            self.after_user = copy.deepcopy(updated)
        self.new_state = copy.deepcopy(self.after_user)

    def undo(self):
        self._replace_user(self.before_user)

    def _replace_user(self, user):
        user_id = user["id"]
        users_data = safe_read_json(self.vault.users_index_path(), {"users": []})
        users = [self.vault.normalise_user(item) for item in users_data.get("users", [])]

        for index, existing in enumerate(users):
            if existing.get("id") == user_id:
                users[index] = copy.deepcopy(user)
                users_data["users"] = users
                safe_write_json(self.vault.users_index_path(), users_data)
                self.vault.create_user_structure(copy.deepcopy(user))
                return

        raise SnapshotRestoreError(f"Cannot replace missing user: {user_id}")


class UserDeleteAction(UndoableAction):
    """Undoable deletion of a user profile entry and vault folder."""

    action_type = "delete_user"

    def __init__(self, vault, user, *, description=None):
        self.vault = vault
        self.user = copy.deepcopy(user)
        self.user_dir = self.vault.user_dir(self.user["id"])
        self.backup_parent = Path(tempfile.mkdtemp(prefix="zjx_lms_user_delete_action_"))
        self.backup_path = self.backup_parent / self.user_dir.name
        label = description or f"Deleted user: {self.user.get('name', self.user.get('id', 'user'))}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.user.get("id", "")),
            previous_state=copy.deepcopy(self.user),
            new_state={"exists": False},
        )

    def do(self):
        if not self.vault.get_user(self.user["id"]):
            raise SnapshotRestoreError(f"Cannot delete missing user: {self.user.get('id')}")
        if self.backup_path.exists():
            raise SnapshotRestoreError(f"Cannot delete user because backup already exists: {self.backup_path}")

        self.backup_parent.mkdir(parents=True, exist_ok=True)
        if self.user_dir.exists():
            retry_file_operation(
                lambda: shutil.move(str(self.user_dir), str(self.backup_path)),
                attempts=12,
                delay=0.15,
            )
        self._remove_user_entry()

    def undo(self):
        if self.vault.get_user(self.user["id"]):
            raise SnapshotRestoreError(f"Cannot restore user because it already exists: {self.user.get('id')}")
        if self.user_dir.exists():
            raise SnapshotRestoreError(f"Cannot restore user because folder already exists: {self.user_dir}")

        self._add_user_entry()
        if self.backup_path.exists():
            retry_file_operation(
                lambda: shutil.move(str(self.backup_path), str(self.user_dir)),
                attempts=12,
                delay=0.15,
            )
        else:
            self.vault.create_user_structure(copy.deepcopy(self.user))

    def cleanup(self):
        shutil.rmtree(self.backup_parent, ignore_errors=True)

    def _remove_user_entry(self):
        users_data = safe_read_json(self.vault.users_index_path(), {"users": []})
        users = [item for item in users_data.get("users", []) if item.get("id") != self.user.get("id")]
        users_data["users"] = users
        safe_write_json(self.vault.users_index_path(), users_data)

    def _add_user_entry(self):
        users_data = safe_read_json(self.vault.users_index_path(), {"users": []})
        users = list(users_data.get("users", []))
        if any(item.get("id") == self.user.get("id") for item in users):
            raise SnapshotRestoreError(f"Cannot restore duplicate user: {self.user.get('id')}")
        users.append(copy.deepcopy(self.user))
        users_data["users"] = users
        safe_write_json(self.vault.users_index_path(), users_data)


class AssignmentUpdateAction(UndoableAction):
    """Undoable update of one assignment metadata object."""

    action_type = "edit_assignment"

    def __init__(self, vault, user_id, course_id, before_assignment, fields, *, description=None):
        self.vault = vault
        self.user_id = user_id
        self.course_id = course_id
        self.before_assignment = copy.deepcopy(before_assignment)
        self.fields = copy.deepcopy(fields)
        self.after_assignment = None
        label = description or f"Edited assignment: {self.before_assignment.get('title', self.before_assignment.get('id', 'assignment'))}"
        super().__init__(
            label,
            action_type=self.action_type,
            affected_item=str(self.before_assignment.get("id", "")),
            previous_state=copy.deepcopy(self.before_assignment),
            new_state=copy.deepcopy(fields),
        )

    def do(self):
        if self.after_assignment:
            self._replace_assignment(self.after_assignment)
        else:
            updated = self.vault.update_assignment_fields(
                self.user_id,
                self.course_id,
                self.before_assignment["id"],
                **copy.deepcopy(self.fields),
            )
            if not updated:
                raise SnapshotRestoreError(f"Cannot update missing assignment: {self.before_assignment.get('id')}")
            self.after_assignment = copy.deepcopy(updated)
        self.new_state = copy.deepcopy(self.after_assignment)

    def undo(self):
        self._replace_assignment(self.before_assignment)

    def _replace_assignment(self, assignment):
        assignment_id = assignment["id"]
        if not self.vault.get_assignment(self.user_id, self.course_id, assignment_id):
            raise SnapshotRestoreError(f"Cannot replace missing assignment: {assignment_id}")

        safe_write_json(
            self.vault.assignment_json_path(self.user_id, self.course_id, assignment_id),
            copy.deepcopy(assignment),
        )


class CompositeAction(UndoableAction):
    """A single history entry made from several smaller undoable actions."""

    action_type = "composite"

    def __init__(self, description, actions, *, action_type=None, affected_item=""):
        self.actions = list(actions)
        super().__init__(
            description,
            action_type=action_type or self.action_type,
            affected_item=affected_item,
        )

    def do(self):
        completed = []
        try:
            for action in self.actions:
                action.do()
                completed.append(action)
        except Exception:
            for action in reversed(completed):
                try:
                    action.undo()
                except Exception:
                    pass
            raise

    def undo(self):
        for action in reversed(self.actions):
            action.undo()

    def cleanup(self):
        for action in self.actions:
            cleanup = getattr(action, "cleanup", None)
            if cleanup:
                cleanup()


class ActionHistoryManager:
    """Central undo/redo stack and readable action history manager."""

    def __init__(self, max_commands=50):
        self.max_commands = max_commands
        self.undo_stack: list[UndoableAction] = []
        self.redo_stack: list[UndoableAction] = []
        self.history_entries: list[ActionHistoryEntry] = []

    def perform(self, action: UndoableAction):
        action.do()
        self.push_done(action)
        return action

    def push_done(self, action: UndoableAction):
        self.undo_stack.append(action)
        self._cleanup_actions(self.redo_stack)
        self.redo_stack.clear()
        self.history_entries.append(self._history_entry_for(action, status="done"))
        self._trim()

    def undo(self):
        if not self.undo_stack:
            return None

        action = self.undo_stack[-1]
        action.undo()
        self.undo_stack.pop()
        self.redo_stack.append(action)
        self.history_entries.append(self._history_entry_for(action, status="undone"))
        return action

    def redo(self):
        if not self.redo_stack:
            return None

        action = self.redo_stack[-1]
        action.redo()
        self.redo_stack.pop()
        self.undo_stack.append(action)
        self.history_entries.append(self._history_entry_for(action, status="redone"))
        self._trim()
        return action

    def can_undo(self):
        return bool(self.undo_stack)

    def can_redo(self):
        return bool(self.redo_stack)

    def recent_descriptions(self, limit=8):
        return [
            entry.display_text()
            for entry in reversed(self.history_entries[-limit:])
        ]

    def clear(self):
        self._cleanup_actions(self.undo_stack + self.redo_stack)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.history_entries.clear()

    def _history_entry_for(self, action, *, status: str):
        if hasattr(action, "history_entry"):
            return action.history_entry(status=status)

        timestamp = getattr(action, "timestamp", None) or datetime.now().isoformat(timespec="seconds")
        description = getattr(action, "description", action.__class__.__name__)
        return ActionHistoryEntry(
            action_type=getattr(action, "action_type", "action"),
            label=str(description),
            timestamp=timestamp,
            affected_item=str(getattr(action, "affected_item", "")),
            status=status,
        )

    def _trim(self):
        while len(self.undo_stack) > self.max_commands:
            old_action = self.undo_stack.pop(0)
            cleanup = getattr(old_action, "cleanup", None)
            if cleanup:
                cleanup()
        if len(self.history_entries) > self.max_commands * 3:
            self.history_entries = self.history_entries[-self.max_commands * 3:]

    def _cleanup_actions(self, actions):
        for action in actions:
            cleanup = getattr(action, "cleanup", None)
            if cleanup:
                cleanup()


CommandHistory = ActionHistoryManager
