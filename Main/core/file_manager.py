from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from core.file_operations import move_path, remove_path, rename_path
from core.helpers import normalise_url, now_iso, unique_folder_path, unique_path
from core.url_shortcuts import (
    LINK_RESOURCE_TYPES,
    read_url_shortcut,
    shortcut_filename,
    url_shortcut_body,
    write_url_shortcut,
)


class FileManagerError(RuntimeError):
    """Base exception for file backend failures."""


class ResourceNotFoundError(FileManagerError):
    """Raised when a requested resource ID cannot be found."""


class InvalidFileOperationError(FileManagerError):
    """Raised when an operation is unsafe or invalid."""


@dataclass(frozen=True)
class ResourceScope:
    """Identifies one resource context inside a user vault."""

    user_id: str
    course_id: str
    assignment_id: str | None = None

    @classmethod
    def from_resource(cls, resource: dict) -> "ResourceScope":
        return cls(
            user_id=str(resource.get("user_id") or ""),
            course_id=str(resource.get("course_id") or ""),
            assignment_id=resource.get("assignment_id"),
        )

    def as_kwargs(self) -> dict:
        return {
            "user_id": self.user_id,
            "course_id": self.course_id,
            "assignment_id": self.assignment_id,
        }


@dataclass
class FileItem:
    """UI-neutral file/resource model returned by the backend."""

    id: str
    name: str
    type: str
    path: str = ""
    parent_path: str = ""
    scope: str = "course"
    owner_id: str = ""
    course_id: str = ""
    assignment_id: str | None = None
    created_at: str = ""
    modified_at: str = ""
    metadata: dict = field(default_factory=dict)
    is_external_link: bool = False

    @classmethod
    def from_resource(cls, resource: dict, absolute_path: Path | None = None) -> "FileItem":
        relative_path = str(resource.get("path") or "")
        parent_path = str(Path(relative_path).parent) if relative_path else str(resource.get("container_path") or "")
        if parent_path == ".":
            parent_path = ""

        metadata = {
            key: value
            for key, value in dict(resource).items()
            if key not in {"id", "title", "type", "path", "user_id", "course_id", "assignment_id", "created_at", "updated_at"}
        }
        if absolute_path is not None:
            metadata["absolute_path"] = str(absolute_path)

        assignment_id = resource.get("assignment_id")
        return cls(
            id=str(resource.get("id") or ""),
            name=str(resource.get("title") or resource.get("name") or "Untitled"),
            type=str(resource.get("type") or "unknown"),
            path=relative_path,
            parent_path=parent_path,
            scope="assignment" if assignment_id else "course",
            owner_id=str(resource.get("user_id") or ""),
            course_id=str(resource.get("course_id") or ""),
            assignment_id=assignment_id,
            created_at=str(resource.get("created_at") or ""),
            modified_at=str(resource.get("updated_at") or ""),
            metadata=metadata,
            is_external_link=resource.get("type") in LINK_RESOURCE_TYPES,
        )


@dataclass
class FileOperationResult:
    """Structured result that can be wrapped by future undo/redo actions."""

    ok: bool
    operation: str
    resource: dict | None = None
    before: dict | None = None
    after: dict | None = None
    old_path: Path | None = None
    new_path: Path | None = None
    affected_ids: list[str] = field(default_factory=list)
    error: str = ""


class ResourceMetadataStore:
    """Central metadata gateway over the existing per-context resources.json files."""

    def __init__(self, vault):
        self.vault = vault
        self._cache: dict[tuple[str, str, str | None], list[dict]] = {}

    def context_key(self, scope: ResourceScope | tuple[str, str, str | None]) -> tuple[str, str, str | None]:
        if isinstance(scope, ResourceScope):
            return (scope.user_id, scope.course_id, scope.assignment_id)
        return scope

    def invalidate(self, scope: ResourceScope | tuple[str, str, str | None] | None = None):
        if scope is None:
            self._cache.clear()
            return
        self._cache.pop(self.context_key(scope), None)

    def list(self, scope: ResourceScope, *, sync: bool = False) -> list[dict]:
        key = self.context_key(scope)
        if sync:
            self.vault.sync_context_resource_metadata(*key)
            self.invalidate(scope)
        if key not in self._cache:
            self._cache[key] = [dict(resource) for resource in self.vault.load_resources(*key)]
        return [dict(resource) for resource in self._cache[key]]

    def save(self, scope: ResourceScope, resources: Iterable[dict]):
        key = self.context_key(scope)
        items = [dict(resource) for resource in resources]
        self.vault.save_resources(*key, items)
        self._cache[key] = [dict(resource) for resource in items]

    def add(self, scope: ResourceScope, resource: dict) -> dict:
        created = self.vault.add_resource(scope.user_id, scope.course_id, scope.assignment_id, dict(resource))
        self.invalidate(scope)
        return dict(created)

    def update(self, resource: dict) -> dict:
        updated = self.vault.update_resource(dict(resource))
        self.invalidate(ResourceScope.from_resource(updated))
        return dict(updated)

    def delete(self, resource: dict):
        scope = ResourceScope.from_resource(resource)
        resources = [item for item in self.list(scope) if item.get("id") != resource.get("id")]
        self.save(scope, resources)

    def get(self, resource_id: str, scope: ResourceScope | None = None) -> dict | None:
        if scope is not None:
            for resource in self.list(scope):
                if resource.get("id") == resource_id:
                    return resource
            return None

        for resource in self.iter_all():
            if resource.get("id") == resource_id:
                return resource
        return None

    def iter_all(self) -> list[dict]:
        resources = []
        for user in self.vault.get_users():
            user_id = user.get("id")
            for course in self.vault.get_courses(user_id):
                course_id = course.get("id")
                resources.extend(self.list(ResourceScope(user_id, course_id)))
                for assignment in self.vault.get_assignments(user_id, course_id):
                    resources.extend(self.list(ResourceScope(user_id, course_id, assignment.get("id"))))
        return resources


class FileManager:
    """Reusable, UI-free backend for vault file and resource operations."""

    def __init__(self, vault, *, on_change: Callable[[FileOperationResult], None] | None = None):
        self.vault = vault
        self.metadata = ResourceMetadataStore(vault)
        self.on_change = on_change

    def _emit(self, result: FileOperationResult) -> FileOperationResult:
        if self.on_change:
            self.on_change(result)
        return result

    def context_dir(self, scope: ResourceScope) -> Path:
        return self.vault.context_dir(scope.user_id, scope.course_id, scope.assignment_id)

    def default_parent_for_type(self, scope: ResourceScope, resource_type: str) -> Path:
        if resource_type == "local_folder":
            return self.vault.context_folders_dir(scope.user_id, scope.course_id, scope.assignment_id)
        if resource_type == "note":
            return self.vault.context_notes_dir(scope.user_id, scope.course_id, scope.assignment_id)
        return self.vault.context_files_dir(scope.user_id, scope.course_id, scope.assignment_id)

    def _path_inside_context(self, scope: ResourceScope, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.context_dir(scope).resolve())
            return True
        except (FileNotFoundError, ValueError):
            try:
                path.parent.resolve().relative_to(self.context_dir(scope).resolve())
                return True
            except (FileNotFoundError, ValueError):
                return False

    def _candidate_inside_context(self, scope: ResourceScope, path: Path) -> bool:
        context = self.context_dir(scope).resolve()
        current = Path(path)
        while not current.exists() and current != current.parent:
            current = current.parent
        try:
            current.resolve().relative_to(context)
            return True
        except (FileNotFoundError, ValueError):
            return False

    def _relative_path(self, scope: ResourceScope, path: Path) -> str:
        return str(Path(path).relative_to(self.context_dir(scope)))

    def _safe_parent(self, scope: ResourceScope, parent: str | Path | None, resource_type: str) -> Path:
        parent_path = Path(parent) if parent else self.default_parent_for_type(scope, resource_type)
        if not self._candidate_inside_context(scope, parent_path):
            raise InvalidFileOperationError("Destination must be inside the resource context.")
        parent_path.mkdir(parents=True, exist_ok=True)
        if not self._path_inside_context(scope, parent_path):
            raise InvalidFileOperationError("Destination must be inside the resource context.")
        return parent_path

    def _resource_or_raise(self, resource_id: str, scope: ResourceScope | None = None) -> dict:
        resource = self.metadata.get(resource_id, scope)
        if not resource:
            raise ResourceNotFoundError(f"Resource not found: {resource_id}")
        return resource

    def _absolute_path(self, resource: dict) -> Path | None:
        return self.vault.resource_absolute_path(resource)

    def resolve_path(self, resource_id: str, scope: ResourceScope | None = None) -> Path | None:
        return self._absolute_path(self._resource_or_raise(resource_id, scope))

    def get_resource(self, resource_id: str, scope: ResourceScope | None = None) -> FileItem:
        resource = self._resource_or_raise(resource_id, scope)
        return FileItem.from_resource(resource, self._absolute_path(resource))

    def list_resources(self, scope: ResourceScope, *, sync: bool = True) -> list[FileItem]:
        return [
            FileItem.from_resource(resource, self._absolute_path(resource))
            for resource in self.metadata.list(scope, sync=sync)
        ]

    def list_children(self, scope: ResourceScope, parent_id_or_path: str | Path | None = None) -> list[FileItem]:
        resources = self.metadata.list(scope, sync=True)
        if parent_id_or_path is None:
            return [
                FileItem.from_resource(resource, self._absolute_path(resource))
                for resource in resources
                if not resource.get("container_path") and not self._resource_has_nested_parent(resource, resources)
            ]

        parent_path = self._resolve_parent_path(scope, parent_id_or_path)
        relative_parent = self._relative_path(scope, parent_path)
        children = []
        resource_by_path = {
            str(self._absolute_path(resource).resolve() if self._absolute_path(resource) and self._absolute_path(resource).exists() else self._absolute_path(resource)): resource
            for resource in resources
            if resource.get("path") and self._absolute_path(resource)
        }

        for entry in sorted(parent_path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            key = str(entry.resolve() if entry.exists() else entry)
            resource = resource_by_path.get(key)
            if resource:
                children.append(FileItem.from_resource(resource, entry))
            else:
                relative = self._relative_path(scope, entry)
                children.append(FileItem(
                    id=f"fs:{relative}",
                    name=entry.name,
                    type="local_folder" if entry.is_dir() else "local_file",
                    path=relative,
                    parent_path=relative_parent,
                    scope="assignment" if scope.assignment_id else "course",
                    owner_id=scope.user_id,
                    course_id=scope.course_id,
                    assignment_id=scope.assignment_id,
                    modified_at=now_iso(),
                    metadata={"absolute_path": str(entry), "managed": False},
                ))

        for resource in resources:
            if resource.get("container_path") == relative_parent:
                children.append(FileItem.from_resource(resource, self._absolute_path(resource)))
        return children

    def _resolve_parent_path(self, scope: ResourceScope, parent_id_or_path: str | Path) -> Path:
        candidate = Path(parent_id_or_path)
        if candidate.exists() or str(parent_id_or_path).startswith(str(self.context_dir(scope))):
            parent_path = candidate
        else:
            resource = self._resource_or_raise(str(parent_id_or_path), scope)
            parent_path = self._absolute_path(resource)
        if not parent_path or not parent_path.exists() or not parent_path.is_dir():
            raise InvalidFileOperationError("Parent folder does not exist.")
        if not self._path_inside_context(scope, parent_path):
            raise InvalidFileOperationError("Parent folder must be inside the resource context.")
        return parent_path

    def _resource_has_nested_parent(self, resource: dict, resources: list[dict]) -> bool:
        path = self._absolute_path(resource)
        if not path:
            return False
        try:
            resolved = path.resolve()
        except FileNotFoundError:
            resolved = path
        for candidate in resources:
            if candidate.get("id") == resource.get("id") or candidate.get("type") != "local_folder":
                continue
            folder = self._absolute_path(candidate)
            if not folder:
                continue
            try:
                resolved.relative_to(folder.resolve())
                return True
            except (FileNotFoundError, ValueError):
                continue
        return False

    def create_folder(self, scope: ResourceScope, name: str, parent: str | Path | None = None) -> FileOperationResult:
        parent_path = self._safe_parent(scope, parent, "local_folder")
        destination = unique_folder_path(parent_path, name)
        destination.mkdir(parents=True, exist_ok=False)
        resource = {
            "type": "local_folder",
            "title": Path(destination).name,
            "path": self._relative_path(scope, destination),
            "tags": [],
        }
        try:
            created = self.metadata.add(scope, resource)
        except Exception:
            remove_path(destination)
            raise
        return self._emit(FileOperationResult(True, "create_folder", resource=created, new_path=destination, affected_ids=[created["id"]]))

    def import_file(self, source_path: str | Path, scope: ResourceScope, destination_parent: str | Path | None = None) -> FileOperationResult:
        source = Path(source_path)
        if not source.is_file():
            raise InvalidFileOperationError("Source is not a file.")

        shortcut = read_url_shortcut(source)
        if shortcut:
            return self.add_external_link(
                scope,
                shortcut["title"],
                shortcut["url"],
                metadata={"tags": shortcut["tags"], "type": shortcut["type"]},
                parent=destination_parent,
            )

        parent = self._safe_parent(scope, destination_parent, "local_file")
        destination = unique_path(parent, source.name)
        shutil.copy2(source, destination)
        resource = {
            "type": "local_file",
            "title": destination.name,
            "path": self._relative_path(scope, destination),
            "tags": [],
        }
        try:
            created = self.metadata.add(scope, resource)
        except Exception:
            remove_path(destination)
            raise
        return self._emit(FileOperationResult(True, "import_file", resource=created, old_path=source, new_path=destination, affected_ids=[created["id"]]))

    def import_folder(self, source_path: str | Path, scope: ResourceScope, destination_parent: str | Path | None = None) -> FileOperationResult:
        source = Path(source_path)
        if not source.is_dir():
            raise InvalidFileOperationError("Source is not a folder.")
        parent = self._safe_parent(scope, destination_parent, "local_folder")
        destination = unique_folder_path(parent, source.name)
        shutil.copytree(source, destination)
        resource = {
            "type": "local_folder",
            "title": destination.name,
            "path": self._relative_path(scope, destination),
            "tags": [],
        }
        try:
            created = self.metadata.add(scope, resource)
        except Exception:
            remove_path(destination)
            raise
        return self._emit(FileOperationResult(True, "import_folder", resource=created, old_path=source, new_path=destination, affected_ids=[created["id"]]))

    def add_external_link(
        self,
        scope: ResourceScope,
        title: str,
        url: str,
        metadata: dict | None = None,
        parent: str | Path | None = None,
    ) -> FileOperationResult:
        metadata = dict(metadata or {})
        resource_type = metadata.pop("type", "external_link")
        if resource_type not in LINK_RESOURCE_TYPES:
            resource_type = "external_link"
        tags = list(metadata.pop("tags", []))
        clean_title = (title or "Link").strip() or "Link"
        parent_path = self._safe_parent(scope, parent, "local_file")
        destination = unique_path(parent_path, shortcut_filename(clean_title))
        shortcut_content = url_shortcut_body(normalise_url(url), title=clean_title, resource_type=resource_type, tags=tags, fallback_title=destination.stem)
        destination.write_text(shortcut_content, encoding="utf-8")
        resource = {
            **metadata,
            "type": resource_type,
            "title": clean_title,
            "url": normalise_url(url),
            "path": self._relative_path(scope, destination),
            "tags": tags,
        }
        try:
            created = self.metadata.add(scope, resource)
        except Exception:
            remove_path(destination)
            raise
        return self._emit(FileOperationResult(True, "add_external_link", resource=created, new_path=destination, affected_ids=[created["id"]]))

    def rename_resource(self, resource_id: str, new_name: str, scope: ResourceScope | None = None) -> FileOperationResult:
        resource = self._resource_or_raise(resource_id, scope)
        before = dict(resource)
        clean_name = str(new_name or "").strip()
        if not clean_name:
            raise InvalidFileOperationError("Resource name cannot be empty.")

        path = self._absolute_path(resource)
        old_path = path
        new_path = None
        if path and path.exists():
            if resource.get("type") == "local_folder":
                target = unique_folder_path(path.parent, clean_name)
            else:
                requested = Path(clean_name)
                filename = requested.name if requested.suffix else f"{requested.name}{path.suffix}"
                target = unique_path(path.parent, filename)
            if target != path:
                rename_path(path, target)
            new_path = target
            resource["path"] = self._relative_path(ResourceScope.from_resource(resource), target)
            resource["title"] = target.name if resource.get("type") not in LINK_RESOURCE_TYPES else target.stem
            if resource.get("type") in LINK_RESOURCE_TYPES:
                write_url_shortcut(target, resource.get("url", ""), title=clean_name, resource_type=resource.get("type", "external_link"), tags=resource.get("tags", []))
        else:
            resource["title"] = clean_name
        resource["updated_at"] = now_iso()
        updated = self.metadata.update(resource)
        return self._emit(FileOperationResult(True, "rename_resource", resource=updated, before=before, after=updated, old_path=old_path, new_path=new_path, affected_ids=[updated["id"]]))

    def move_resource(self, resource_id: str, new_parent: str | Path, scope: ResourceScope | None = None) -> FileOperationResult:
        resource = self._resource_or_raise(resource_id, scope)
        before = dict(resource)
        resource_scope = ResourceScope.from_resource(resource)

        if resource.get("type") in LINK_RESOURCE_TYPES and not resource.get("path"):
            if new_parent:
                parent_path = self._safe_parent(resource_scope, new_parent, "local_file")
                resource["container_path"] = self._relative_path(resource_scope, parent_path)
            else:
                resource.pop("container_path", None)
            updated = self.metadata.update(resource)
            return self._emit(FileOperationResult(True, "move_resource", resource=updated, before=before, after=updated, affected_ids=[updated["id"]]))

        source = self._absolute_path(resource)
        if not source or not source.exists():
            raise InvalidFileOperationError("Resource file is missing.")
        parent = self._safe_parent(resource_scope, new_parent, resource.get("type", "local_file"))
        if source.is_dir():
            try:
                parent.resolve().relative_to(source.resolve())
                raise InvalidFileOperationError("You cannot move a folder into itself or one of its subfolders.")
            except ValueError:
                pass
        if source.parent.resolve() == parent.resolve():
            return self._emit(FileOperationResult(True, "move_resource", resource=resource, before=before, after=resource, old_path=source, new_path=source, affected_ids=[resource["id"]]))
        destination = unique_folder_path(parent, source.name) if source.is_dir() else unique_path(parent, source.name)
        move_path(source, destination)
        resource["path"] = self._relative_path(resource_scope, destination)
        resource.pop("container_path", None)
        resource["updated_at"] = now_iso()
        try:
            updated = self.metadata.update(resource)
        except Exception:
            move_path(destination, source)
            raise
        return self._emit(FileOperationResult(True, "move_resource", resource=updated, before=before, after=updated, old_path=source, new_path=destination, affected_ids=[updated["id"]]))

    def copy_resource(self, resource_id: str, new_parent: str | Path | None = None, scope: ResourceScope | None = None) -> FileOperationResult:
        resource = self._resource_or_raise(resource_id, scope)
        resource_scope = ResourceScope.from_resource(resource)
        copied = dict(resource)
        copied.pop("id", None)
        copied.pop("created_at", None)
        copied.pop("updated_at", None)

        if resource.get("type") in LINK_RESOURCE_TYPES and not resource.get("path"):
            copied["title"] = f"{resource.get('title', 'Untitled')} copy"
            if new_parent:
                copied["container_path"] = self._relative_path(resource_scope, self._safe_parent(resource_scope, new_parent, "local_file"))
            else:
                copied.pop("container_path", None)
            created = self.metadata.add(resource_scope, copied)
            return self._emit(FileOperationResult(True, "copy_resource", resource=created, before=resource, after=created, affected_ids=[created["id"]]))

        source = self._absolute_path(resource)
        if not source or not source.exists():
            raise InvalidFileOperationError("Resource file is missing.")
        parent = self._safe_parent(resource_scope, new_parent, resource.get("type", "local_file"))
        destination = unique_folder_path(parent, source.name) if source.is_dir() else unique_path(parent, source.name)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        copied["title"] = destination.name
        copied["path"] = self._relative_path(resource_scope, destination)
        copied.pop("container_path", None)
        try:
            created = self.metadata.add(resource_scope, copied)
        except Exception:
            remove_path(destination)
            raise
        return self._emit(FileOperationResult(True, "copy_resource", resource=created, before=resource, after=created, old_path=source, new_path=destination, affected_ids=[created["id"]]))

    def delete_resource(self, resource_id: str, *, delete_physical: bool = True, scope: ResourceScope | None = None) -> FileOperationResult:
        resource = self._resource_or_raise(resource_id, scope)
        path = self._absolute_path(resource)
        if delete_physical and path and path.exists():
            if not self._path_inside_context(ResourceScope.from_resource(resource), path):
                raise InvalidFileOperationError("Refusing to delete a path outside the resource context.")
            remove_path(path)
        self.metadata.delete(resource)
        return self._emit(FileOperationResult(True, "delete_resource", before=resource, old_path=path, affected_ids=[resource["id"]]))

    def restore_resource(self, resource_id: str) -> FileOperationResult:
        raise InvalidFileOperationError("Deleted resource restore is not supported by the current vault format.")

    def update_metadata(self, resource_id: str, metadata_patch: dict, scope: ResourceScope | None = None) -> FileOperationResult:
        resource = self._resource_or_raise(resource_id, scope)
        before = dict(resource)
        for key, value in dict(metadata_patch or {}).items():
            if key in {"id", "user_id", "course_id", "assignment_id", "path"}:
                continue
            resource[key] = value
        resource["updated_at"] = now_iso()
        updated = self.metadata.update(resource)
        return self._emit(FileOperationResult(True, "update_metadata", resource=updated, before=before, after=updated, affected_ids=[updated["id"]]))

    def search_resources(self, query: str = "", filters: dict | None = None) -> list[FileItem]:
        filters = dict(filters or {})
        query_text = str(query or "").strip().lower()
        results = []
        for resource in self.metadata.iter_all():
            if query_text and query_text not in str(resource.get("title", "")).lower():
                continue
            if filters.get("type") and resource.get("type") != filters["type"]:
                continue
            if filters.get("user_id") and resource.get("user_id") != filters["user_id"]:
                continue
            if filters.get("course_id") and resource.get("course_id") != filters["course_id"]:
                continue
            if "assignment_id" in filters and resource.get("assignment_id") != filters["assignment_id"]:
                continue
            results.append(FileItem.from_resource(resource, self._absolute_path(resource)))
        return results

    def refresh_index(self, scope: ResourceScope | None = None):
        if scope is not None:
            self.metadata.list(scope, sync=True)
            return
        self.metadata.invalidate()
        for user in self.vault.get_users():
            for course in self.vault.get_courses(user.get("id")):
                course_scope = ResourceScope(user.get("id"), course.get("id"))
                self.metadata.list(course_scope, sync=True)
                for assignment in self.vault.get_assignments(user.get("id"), course.get("id")):
                    self.metadata.list(ResourceScope(user.get("id"), course.get("id"), assignment.get("id")), sync=True)

    def validate_operation(self, operation: str, **kwargs) -> FileOperationResult:
        try:
            if operation in {"import_file", "import_folder"}:
                source = Path(kwargs["source_path"])
                if operation == "import_file" and not source.is_file():
                    raise InvalidFileOperationError("Source file does not exist.")
                if operation == "import_folder" and not source.is_dir():
                    raise InvalidFileOperationError("Source folder does not exist.")
            if operation in {"move_resource", "copy_resource", "delete_resource", "rename_resource"}:
                self._resource_or_raise(kwargs["resource_id"], kwargs.get("scope"))
            return FileOperationResult(True, operation)
        except Exception as error:
            return FileOperationResult(False, operation, error=str(error))
