#!/usr/bin/env bash
set -euo pipefail

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    printf 'Usage: %s [VERSION]\nDefault version: 1.0.0-beta1\nBuild on Linux using dependencies installed in Main/.venv or your Python environment.\n' "$0"
    exit 0
fi
[[ $# -le 1 ]] || fail "Expected at most one version argument."
VERSION=${1-1.0.0-beta1}
[[ $VERSION =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] || fail "Version must start with a letter or digit and contain only letters, digits, dots, underscores, or hyphens."
[[ $(uname -s) == Linux ]] || fail "This script must run on Linux."
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
RELEASE_NAME="ZJX-LMS-$VERSION-linux-$ARCH"
RELEASE_DIR="$REPO_ROOT/release/$RELEASE_NAME"
require_path() { [[ -e $1 ]] || fail "Missing $2: $1"; }
require_path ZJX-LMS.spec 'PyInstaller spec'
require_path assets/app_icon.ico 'app icon'
require_path assets/icons 'dark icon set'
require_path assets/icons_light 'light icon set'
for source in main.py app core services ui; do
    require_path "$source" 'source path'
done
command -v tar >/dev/null || fail "Missing tar"
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
DIST_APP="$REPO_ROOT/dist/ZJX LMS"
[[ -x "$DIST_APP/ZJX LMS" ]] || fail "Missing packaged executable: $DIST_APP/ZJX LMS"
ASSETS="$DIST_APP/_internal/assets"
[[ -d $ASSETS ]] || ASSETS="$DIST_APP/assets"
for asset in icons icons_light app_icon.ico; do
    require_path "$ASSETS/$asset" 'packaged asset'
done
ARCHIVE="$RELEASE_DIR.tar.gz"
mkdir -p -- "$REPO_ROOT/release"
rm -rf -- "$RELEASE_DIR"
rm -f -- "$ARCHIVE"
cp -a -- "$DIST_APP" "$RELEASE_DIR"
tar -czf "$ARCHIVE" -C "$REPO_ROOT/release" "$RELEASE_NAME"
[[ -x "$RELEASE_DIR/ZJX LMS" ]] || fail 'Missing release executable'
require_path "$ARCHIVE" 'release archive'
printf 'Built release folder: %s\nBuilt release archive: %s\n' "$RELEASE_DIR" "$ARCHIVE"
printf 'Smoke test: %q\n' "$RELEASE_DIR/ZJX LMS"

