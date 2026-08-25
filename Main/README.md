# ZJX LMS

ZJX LMS is a local-first desktop learning manager with Canvas sync support. It stores users, courses, assignments, resources, widgets, cached Canvas profile pictures, and pasted note-widget images in a local vault. Canvas access tokens remain local to the user profile JSON.

## Run From Source

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Private Beta Scope

- First-run onboarding and UID-based users.
- Canvas course, assignment, announcement, and profile picture sync.
- Canvas course skip/pin preferences.
- Local resource vault, file explorer, Resource Library, undo/redo, and archive flow.
- Desktop widgets for assignment countdowns, shortcuts, and pinned notes with pasted image support.
- Dark/light themes, system theme option, accent colour, UI zoom, scroll tuning, tray behaviour, and due-date urgency colours.
- Vault backup action in Settings for private beta safety.
- Human-readable vault export in Settings > Tools for creating a portable zip archive of users, courses, assignments, files, notes, folders, and link resources.

## Packaging

Windows private beta packaging uses PyInstaller. Runtime support also covers Linux desktop sessions and macOS from source; see [PACKAGING.md](PACKAGING.md) for platform smoke checks and startup/tray notes.

Quick build after installing build requirements:

```powershell
pip install -r requirements-build.txt
.\scripts\build_beta.ps1
```

Default output:

```text
release\ZJX-LMS-1.0.0-beta1-win64\
release\ZJX-LMS-1.0.0-beta1-win64.zip
```

## Platform Notes

Run on startup is per-user and platform-specific: Windows uses the Run key, Linux uses freedesktop XDG Autostart, and macOS uses LaunchAgents. Minimize-to-tray depends on the current desktop session exposing a tray/status notifier; KDE Plasma, Xfce, LXQt, Cinnamon, MATE, and DDE-style sessions usually provide one, while GNOME/Wayland may require tray or AppIndicator support to be enabled.

## Local Data Location

By default, the vault is created at:

```text
~/ZJX-LMS
```

The vault location can be changed in Settings. Use **Settings > Backup Vault Folder** before beta testing, moving machines, or experimenting with real Canvas data. Use **Settings > Tools > Export Vault Archive** when you want a human-readable zip copy that can be archived outside the app.
