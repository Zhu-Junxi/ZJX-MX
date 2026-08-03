# File Backend

`core.file_manager.FileManager` is the UI-neutral backend for resource and
file operations. It wraps the existing `VaultManager` layout, so current vaults
and `resources.json` files remain compatible.

## Structure

- `ResourceScope` identifies a user/course/assignment context.
- `FileItem` is the stable resource model returned to UI code.
- `ResourceMetadataStore` centralises reads and writes to `resources.json` and
  keeps a small per-context cache.
- `FileManager` owns high-level operations such as import, copy, move, rename,
  delete, link creation, listing, metadata updates, search, and path resolution.
- `FileOperationResult` returns the old/new paths, affected IDs, and before/after
  metadata needed by future undo/redo wrappers.

The backend does not import PySide6 and should stay usable by tests, sync code,
export code, or a redesigned UI.

## How UI Code Should Use It

Create one service beside the vault:

```python
from core.file_manager import FileManager, ResourceScope

self.vault = VaultManager(vault_path)
self.file_manager = FileManager(self.vault)
scope = ResourceScope(self.current_user_id, self.current_course_id, self.current_assignment_id)
result = self.file_manager.import_file(source_path, scope)
```

UI widgets should call these high-level methods instead of copying files,
renaming paths, or editing `resources.json` directly.

## Adding Operations

Add new file/resource commands to `FileManager` first, then have UI handlers call
that method. Keep validation, path resolution, conflict handling, metadata
updates, and rollback in the backend. UI code should only handle prompts,
selection, progress, and presentation.

## Metadata And Cache

Metadata is still stored in the existing per-context `resources.json` files.
Writes go through `safe_write_json`, which uses a temporary file and replace for
atomic updates where the OS supports it. The metadata cache is invalidated after
mutating operations and can be refreshed with `refresh_index`.

## Undo/Redo Integration

`FileOperationResult` intentionally includes `before`, `after`, `old_path`,
`new_path`, and `affected_ids`. Existing undo actions can wrap backend methods
or be gradually moved into this service without needing UI-specific state.
