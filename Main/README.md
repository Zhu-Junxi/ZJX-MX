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

All three platform scripts use PyInstaller, compile-check the Python sources, verify bundled assets, and create a release folder and archive. Run each script on its target operating system. Dependencies must be installed first; the scripts do not install packages automatically.

### Windows

```powershell
pip install -r requirements.txt -r requirements-build.txt
.\scripts\build_beta.ps1
```

Output: `release/ZJX-LMS-1.0.0-beta1-win64/` and matching `.zip`.

### Linux (including CachyOS) and macOS

From `Main`, prepare an environment with Python 3.10 or newer supported by the installed PySide6 and PyInstaller versions:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-build.txt

# On Linux:
./scripts/build_beta_linux.sh

# On macOS:
./scripts/build_beta_macos.sh
```

Both scripts prefer `.venv/bin/python`, then `python3`, then `python`. They work from any current directory. Supply an optional version, for example `./scripts/build_beta_linux.sh 1.0.0-beta2`, or use `--help`.

- Linux produces `release/ZJX-LMS-<version>-linux-<arch>/` and a matching `.tar.gz`. Extract the entire archive, then run the `ZJX LMS` executable inside the folder.
- macOS produces `release/ZJX-LMS-<version>-macos-<arch>/ZJX LMS.app` and a matching `.zip`. Open the `.app` in Finder or with `open`. Native `sips`, `iconutil`, and `ditto` tools generate the icon and preserve bundle metadata when archiving.

The default version is `1.0.0-beta1`; architecture follows the build interpreter. Rebuilding the same version replaces that platform/architecture's release folder and archive after packaged assets pass verification. Build and dist directories are shared, so run builds sequentially.

CachyOS builds require Python, `tar`, and system libraries needed by Qt for your desktop session. Use a virtual environment for Python dependencies. PyInstaller does not bundle glibc: a build made on rolling-release CachyOS may not run on distributions with older system libraries. Build on the oldest Linux environment you intend to support for broader distribution.

These are local beta packages without installers or Developer ID signing/notarization. macOS distribution outside your machine may require a separate signing and notarization workflow.

After building, extract the archive into a separate directory and launch the packaged app. Check window and tray icons, light/dark themes, PDF previews, and ordinary startup/exit. Linux tray support depends on the desktop session. macOS bundles must be built and smoke-tested on a Mac; a Linux build cannot validate them.

## Platform Notes

Run on startup is per-user and platform-specific: Windows uses the Run key, Linux uses freedesktop XDG Autostart, and macOS uses LaunchAgents. Minimize-to-tray depends on the current desktop session exposing a tray/status notifier; KDE Plasma, Xfce, LXQt, Cinnamon, MATE, and DDE-style sessions usually provide one, while GNOME/Wayland may require tray or AppIndicator support to be enabled.

## Local Data Location

By default, the vault is created at:

```text
~/ZJX-LMS
```

The vault location can be changed in Settings. Use **Settings > Backup Vault Folder** before beta testing, moving machines, or experimenting with real Canvas data. Use **Settings > Tools > Export Vault Archive** when you want a human-readable zip copy that can be archived outside the app.
