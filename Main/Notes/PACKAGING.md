# Packaging ZJX LMS Private Beta

The current repeatable packaged build is Windows-first and uses PyInstaller. The source app now supports Windows, Linux desktop sessions, and macOS at runtime; Linux/macOS packaged builds should be produced and smoke-tested on their target operating systems.

## One-time setup

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-build.txt
```

## Source smoke check

```powershell
python -m py_compile main.py (Get-ChildItem app,core,services,ui -Recurse -Filter *.py).FullName
python main.py
```

Before packaging, manually check:

- Fresh launch and first-run user creation.
- Canvas sync with one real Canvas user.
- Resource Library opens and previews at least one text/document/image file.
- Widgets Manager opens; create a note widget and paste an image.
- Settings > Notifications and Tray correctly reports startup registration and tray capability for the current operating system/session.
- On Linux, test at least one tray-capable session such as KDE Plasma/Xfce/LXQt/Cinnamon/MATE, and one trayless or extensionless GNOME session if available.
- Settings > Backup Vault Folder creates a timestamped vault copy.
- Settings > Tools > Export Vault Archive creates a readable zip archive in the selected folder.

## Build

```powershell
.\scripts\build_beta.ps1
```

The default output is:

```text
release\ZJX-LMS-1.0.0-beta1-win64\
release\ZJX-LMS-1.0.0-beta1-win64.zip
```

To choose a different beta label:

```powershell
.\scripts\build_beta.ps1 -Version "1.0.0-beta2"
```

## Packaged smoke check

Run:

```powershell
& ".\release\ZJX-LMS-1.0.0-beta1-win64\ZJX LMS.exe"
```

Verify:

- App icon and dark/light SVG icons render.
- The app can create and write to the default vault at `~/ZJX-LMS`.
- Run on startup can be enabled and disabled for the current OS:
  - Windows uses the current user's Run key.
  - Linux uses freedesktop XDG Autostart at `$XDG_CONFIG_HOME/autostart` or `~/.config/autostart`.
  - macOS uses a per-user LaunchAgent in `~/Library/LaunchAgents`.
- Minimize-to-tray works only when the desktop session exposes a system tray. GNOME/Wayland sessions may need AppIndicator/tray support enabled by the desktop.
- Existing vaults still open from Settings > Change Vault Folder.
- Canvas profile pictures cache locally after sync.
- Pasted note-widget images persist after restarting the packaged app.
- Export Vault Archive writes a zip to the selected destination and includes readable folder names plus link shortcut files.
- Offline launch works after a previous successful sync.

## Beta handoff notes

Ask testers to back up their vault before heavy testing. The app stores local data under `~/ZJX-LMS` by default, including Canvas metadata, access tokens, cached profile pictures, imported resources, widgets, and pasted note images.

Linux compatibility should be reported by desktop environment and session type rather than distro alone. Useful notes include GNOME/KDE/Xfce/LXQt/Cinnamon/MATE/DDE, Wayland vs X11, and whether Settings reports tray messages as available.
