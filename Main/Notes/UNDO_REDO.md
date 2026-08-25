# Undo/Redo Architecture

The undo/redo system lives in `services/command_history.py`.

## Core Pieces

- `UndoableAction` is the base class for future explicit actions.
- `ActionHistoryManager` is the central undo/redo manager.
- `CommandHistory` is kept as an alias so existing app code does not need to change at once.
- `SnapshotCommand` is the centralized compatibility primitive for named broad actions and legacy helpers. UI handlers should not instantiate it directly.
- `CanvasSyncAction` wraps a broad Canvas sync as one named undoable action.
- `ResourceLibraryMultiContextAction` wraps Resource Library operations that touch several course/assignment contexts and rolls back completed context restores if one context fails.
- `FileRenameAction` is the first concrete file action. It is used for unmanaged file/folder renames in the main Files explorer and Resource Library.
- `FileMoveAction` moves unmanaged files/folders between explicit source and destination paths.
- `FileCreateAction` creates unmanaged files/folders and moves created content into a temporary backup on undo, so redo restores the actual current content rather than recreating stale defaults.
- `FileCopyAction` imports/copies files or folders into the vault. Undo moves the imported vault item into a backup, so redo restores the user's imported copy rather than re-copying a changed external source.
- `FileContentUpdateAction` replaces file bytes and can undo/redo exact content changes. It is useful for text files, notes, and URL shortcut files.
- `FileDeleteAction` is the concrete unmanaged delete action. It moves the item into an action-owned backup so undo/redo can restore or re-delete it without permanently removing the user's data while the action is still in history.
- `ResourceAddAction` adds/removes a resource metadata entry by stable resource id.
- `ResourceDeleteAction` removes/restores a resource metadata entry by stable resource id. It is currently used for metadata-only resource deletion.
- `ResourceUpdateAction` replaces one resource metadata entry by stable resource id while preserving the exact before/after metadata states.
- `CompositeAction` groups smaller actions into one user-visible history entry. It is used when a user operation must update both files and metadata.

Current composite handlers include:

- Create folder: `FileCreateAction` + `ResourceAddAction`
- Create text file: `FileCreateAction` + `ResourceAddAction`
- Create Microsoft file: generate the Office file in a temporary folder, then `FileCopyAction` + `ResourceAddAction`
- Create course: `CourseCreateAction`
- Create assignment: `AssignmentCreateAction`
- Create/edit/delete user: `UserCreateAction` / `UserUpdateAction` / `UserDeleteAction`
- Edit assignment: `AssignmentUpdateAction`
- Dashboard assignment complete/active toggles and todo add/edit/toggle/delete: `AssignmentUpdateAction`
- Delete course/assignment: `FileDeleteAction` on the course or assignment directory
- Import local files/folders and dropped items: `FileCopyAction` + `ResourceAddAction`
- Paste copied resources/file entries: `FileCopyAction` and/or `ResourceAddAction` in one `CompositeAction`
- Move/cut resources and file entries in the main Files view: `FileMoveAction`, `ResourceUpdateAction`, and optional `ResourceAddAction` in one `CompositeAction`
- Canvas sync: `CanvasSyncAction`, a named broad-sync action over the user's vault subtree.
- Resource Library cross-context moves: `ResourceLibraryMultiContextAction`, a named multi-context action with rollback between touched contexts.
- Add external/Google link: `FileCreateAction` for the `.url` shortcut + `ResourceAddAction`
- Add note: `FileCreateAction` for the note body + `ResourceAddAction`
- Delete resource or selected resources: `FileDeleteAction` for physical files/folders where present + `ResourceDeleteAction`
- Edit external link: `FileContentUpdateAction` for the `.url` shortcut + `ResourceUpdateAction`
- Edit note: `FileContentUpdateAction` for the note body + `ResourceUpdateAction`
- Edit text file in the in-app editor: `FileContentUpdateAction`; resource-backed text files also use `ResourceUpdateAction`
- Rename local resource: `FileRenameAction` for the file/folder + `ResourceUpdateAction`

## Adding A Future Action

Create a small class that inherits `UndoableAction` and implements:

```python
def do(self):
    ...

def undo(self):
    ...
```

`redo()` calls `do()` by default. Override it only when redo needs different behavior.

Set a readable description and metadata:

```python
action = RenameFileAction(
    "Renamed file: old_name.pdf -> new_name.pdf",
    action_type="rename_file",
    affected_item=str(path),
    previous_state={...},
    new_state={...},
)
```

Run new explicit actions through:

```python
self.command_history.perform(action)
self.update_history_panel()
```

Example:

```python
action = FileRenameAction(old_path, new_path, description="Renamed file: old.pdf -> new.pdf")
self.command_history.perform(action)
self.update_history_panel()
```

Delete example:

```python
action = FileDeleteAction(path, description=f"Deleted file: {path.name}")
self.command_history.perform(action)
self.update_history_panel()
```

Composite file-plus-metadata create example:

```python
action = CompositeAction(
    f"Created file: {path.name}",
    [
        FileCreateAction(path, content=initial_text),
        ResourceAddAction(vault, user_id, course_id, assignment_id, resource),
    ],
    action_type="create_file",
    affected_item=str(path),
)
self.command_history.perform(action)
self.update_history_panel()
```

Composite file-plus-metadata edit example:

```python
action = CompositeAction(
    f"Edited resource: {resource['title']}",
    [
        FileContentUpdateAction(path, before_bytes, after_bytes),
        ResourceUpdateAction(vault, before_resource, after_resource),
    ],
    action_type="edit_resource",
    affected_item=resource["id"],
)
self.command_history.perform(action)
self.update_history_panel()
```

## Existing Snapshot Pattern

Legacy compatibility helpers still support:

```python
command = self.begin_undo_snapshot("Created folder: Week 3 Notes")
try:
    ...
    self.commit_undo_snapshot(command)
except Exception:
    self.discard_undo_snapshot(command)
    raise
```

Raw `SnapshotCommand` use should stay in `services.command_history.py` and compatibility helpers only. UI handlers should dispatch named actions through the manager. Snapshot restores are in-place and transactional: they stage replacements, back up changed paths, roll back on failure where possible, and keep the history entry retryable if undo/redo is blocked.

Prefer explicit small actions for new code. Use named broad actions only when a workflow touches an external or multi-context state surface that is safer to restore transactionally than to decompose.

Batch import handlers reserve pending destination paths before executing the composite action. This keeps same-name files unique even though the action objects are built before any copy happens.

## Invariants

- New actions clear the redo stack.
- Actions that hold temporary backups clean them up when they leave the undo/redo stacks.
- Failed undo/redo does not pop the history entry.
- Undo/redo refreshes the app UI through `refresh_after_history_restore`.
- History entries are human-readable and include a timestamp plus status.
- Snapshot-backed broad actions must not delete live data before replacement or rollback data exists.

## Verification

Last completed verification:

```powershell
python -m unittest Main.tests.test_command_history
python -m unittest discover Main\tests
python -m py_compile Main\services\command_history.py Main\app\actions.py Main\app\canvas_actions.py Main\app\resource_actions.py Main\app\entity_actions.py Main\app\dashboard_views.py Main\app\main_window.py Main\ui\resource_library_window.py Main\tests\test_command_history.py
```

Expected result: all tests pass and all listed files compile.
