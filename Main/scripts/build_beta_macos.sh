#!/usr/bin/env bash
set -euo pipefail

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    printf 'Usage: %s [VERSION]\nDefault version: 1.0.0-beta1\nBuild on macOS using dependencies installed in Main/.venv or your Python environment.\n' "$0"
    exit 0
fi
[[ $# -le 1 ]] || fail "Expected at most one version argument."
VERSION=${1-1.0.0-beta1}
[[ $VERSION =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] || fail "Version must start with a letter or digit and contain only letters, digits, dots, underscores, or hyphens."
[[ $(uname -s) == Darwin ]] || fail "This script must run on macOS."
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$REPO_ROOT"

PYTHON=''
for candidate in "$REPO_ROOT/.venv/bin/python" python3 python; do
    if "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
        PYTHON=$candidate
        break
    fi
done
[[ -n $PYTHON ]] || fail "Python 3.10+ is required. Create Main/.venv or install Python."
printf 'Using Python: %s\n' "$PYTHON"
if ! "$PYTHON" - <<'PYDEPS'
import importlib.util
import sys
modules = ('PyInstaller', 'PySide6', 'requests', 'docx', 'pptx', 'openpyxl')
missing = [name for name in modules if importlib.util.find_spec(name) is None]
if missing:
    print('Missing dependencies: ' + ', '.join(missing), file=sys.stderr)
    sys.exit(1)
PYDEPS
then
    printf 'Install dependencies from Main with:\n  %q -m pip install -r requirements.txt -r requirements-build.txt\n' "$PYTHON" >&2
    exit 1
fi
ARCH=$("$PYTHON" -c 'import platform, struct; machine = platform.machine(); print("i686" if machine in ("x86_64", "AMD64") and struct.calcsize("P") == 4 else machine)')
[[ $ARCH =~ ^[a-zA-Z0-9_]+$ ]] || fail "Unsupported interpreter architecture: $ARCH"
RELEASE_NAME="ZJX-LMS-$VERSION-macos-$ARCH"
RELEASE_DIR="$REPO_ROOT/release/$RELEASE_NAME"
require_path() { [[ -e $1 ]] || fail "Missing $2: $1"; }
require_path ZJX-LMS.spec 'PyInstaller spec'
require_path assets/app_icon.ico 'app icon'
require_path assets/icons 'dark icon set'
require_path assets/icons_light 'light icon set'
for source in main.py app core services ui; do
    require_path "$source" 'source path'
done
for tool in sips iconutil ditto; do
    command -v "$tool" >/dev/null || fail "Missing macOS tool: $tool"
done
require_path assets/app_icon.png 'macOS icon source'
ICONSET="$REPO_ROOT/build/app_icon.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
    sips -z "$size" "$size" assets/app_icon.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    sips -z "$((size * 2))" "$((size * 2))" assets/app_icon.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$REPO_ROOT/build/app_icon.icns"

printf 'Running Python compile preflight...\n'
"$PYTHON" - <<'PYCOMPILE'
from pathlib import Path
import py_compile
sources = [Path('main.py')]
for directory in ('app', 'core', 'services', 'ui'):
    sources.extend(sorted(Path(directory).rglob('*.py')))
for source in sources:
    py_compile.compile(str(source), doraise=True)
PYCOMPILE
printf 'Running PyInstaller...\n'
"$PYTHON" -m PyInstaller --clean --noconfirm ZJX-LMS.spec
DIST_APP="$REPO_ROOT/dist/ZJX LMS.app"
[[ -x "$DIST_APP/Contents/MacOS/ZJX LMS" ]] || fail 'Missing packaged macOS executable'
require_path "$DIST_APP/Contents/Info.plist" 'bundle metadata'
require_path "$DIST_APP/Contents/Resources/app_icon.icns" 'bundle icon'
for asset in icons icons_light app_icon.ico; do
    require_path "$DIST_APP/Contents/Resources/assets/$asset" 'packaged asset'
done
ARCHIVE="$RELEASE_DIR.zip"
mkdir -p "$REPO_ROOT/release"
rm -rf -- "$RELEASE_DIR"
rm -f -- "$ARCHIVE"
mkdir -p "$RELEASE_DIR"
ditto "$DIST_APP" "$RELEASE_DIR/ZJX LMS.app"
ditto -c -k --sequesterRsrc --keepParent "$RELEASE_DIR" "$ARCHIVE"
[[ -x "$RELEASE_DIR/ZJX LMS.app/Contents/MacOS/ZJX LMS" ]] || fail 'Missing release executable'
require_path "$ARCHIVE" 'release archive'
printf 'Built release folder: %s\nBuilt release zip: %s\n' "$RELEASE_DIR" "$ARCHIVE"
printf 'Smoke test: open %q\n' "$RELEASE_DIR/ZJX LMS.app"

