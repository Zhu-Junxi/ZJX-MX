param(
    [string]$Version = "1.0.0-beta1"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ReleaseName = "ZJX-LMS-$Version-win64"
$ReleaseDir = Join-Path $RepoRoot "release"
$BuildDir = Join-Path $RepoRoot "build"
$DistDir = Join-Path $RepoRoot "dist"
$NamedReleaseDir = Join-Path $ReleaseDir $ReleaseName
$ZipPath = Join-Path $ReleaseDir "$ReleaseName.zip"

Set-Location $RepoRoot

python -m PyInstaller --clean --noconfirm "ZJX-LMS.spec"

if (Test-Path $NamedReleaseDir) {
    Remove-Item -LiteralPath $NamedReleaseDir -Recurse -Force
}
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Copy-Item -LiteralPath (Join-Path $DistDir "ZJX LMS") -Destination $NamedReleaseDir -Recurse
Compress-Archive -LiteralPath $NamedReleaseDir -DestinationPath $ZipPath -Force

Write-Host "Built release folder: $NamedReleaseDir"
Write-Host "Built release zip:    $ZipPath"
Write-Host "Smoke test:           & '$NamedReleaseDir\ZJX LMS.exe'"
