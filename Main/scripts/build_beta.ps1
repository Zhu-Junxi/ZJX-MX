param(
    [string]$Version = "1.0.0-beta1"
)

$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $Candidate = @($venvPython)
        if (Test-PythonCommand $Candidate) {
            return $Candidate
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $Candidate = @($pythonCommand.Source)
        if (Test-PythonCommand $Candidate) {
            return $Candidate
        }
    }

    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        $Candidate = @($pyCommand.Source, "-3")
        if (Test-PythonCommand $Candidate) {
            return $Candidate
        }
    }

    throw "No Python interpreter found. Create .venv or install Python, then rerun this script."
}

function Test-PythonCommand {
    param(
        [string[]]$Command
    )

    $Executable = $Command[0]
    $InterpreterArgs = @()
    if ($Command.Count -gt 1) {
        $InterpreterArgs = $Command[1..($Command.Count - 1)]
    }

    try {
        & $Executable @InterpreterArgs --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Invoke-Python {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    $InterpreterArgs = @()
    if ($PythonCommand.Count -gt 1) {
        $InterpreterArgs = $PythonCommand[1..($PythonCommand.Count - 1)]
    }

    $Executable = $PythonCommand[0]
    & $Executable @InterpreterArgs @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE`: $Executable $($InterpreterArgs -join ' ') $($Arguments -join ' ')"
    }
}

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Description
    )

    if (-not (Test-Path $Path)) {
        throw "Missing $Description`: $Path"
    }
}

function Resolve-PackagedAssetRoot {
    foreach ($Candidate in @(
        (Join-Path $DistAppDir "_internal\assets"),
        (Join-Path $DistAppDir "assets")
    )) {
        if (Test-Path $Candidate) {
            return $Candidate
        }
    }

    throw "Missing packaged assets directory under $DistAppDir"
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ReleaseName = "ZJX-LMS-$Version-win64"
$ReleaseDir = Join-Path $RepoRoot "release"
$BuildDir = Join-Path $RepoRoot "build"
$DistDir = Join-Path $RepoRoot "dist"
$DistAppDir = Join-Path $DistDir "ZJX LMS"
$DistExe = Join-Path $DistAppDir "ZJX LMS.exe"
$NamedReleaseDir = Join-Path $ReleaseDir $ReleaseName
$ReleaseExe = Join-Path $NamedReleaseDir "ZJX LMS.exe"
$ZipPath = Join-Path $ReleaseDir "$ReleaseName.zip"

Set-Location $RepoRoot

$PythonCommand = @(Resolve-PythonCommand)
$PythonDisplay = $PythonCommand -join " "
Write-Host "Using Python: $PythonDisplay"

Assert-PathExists "ZJX-LMS.spec" "PyInstaller spec"
Assert-PathExists "assets\app_icon.ico" "app icon"
Assert-PathExists "assets\icons" "dark icon set"
Assert-PathExists "assets\icons_light" "light icon set"

$CompileTargets = @("main.py")
foreach ($SourceDir in @("app", "core", "services", "ui")) {
    Assert-PathExists $SourceDir "source directory"
    $CompileTargets += Get-ChildItem -LiteralPath $SourceDir -Recurse -Filter "*.py" | ForEach-Object { $_.FullName }
}

Write-Host "Running Python compile preflight..."
Invoke-Python -m py_compile @CompileTargets

Write-Host "Running PyInstaller..."
Invoke-Python -m PyInstaller --clean --noconfirm "ZJX-LMS.spec"

Assert-PathExists $DistExe "packaged executable"
$PackagedAssetRoot = Resolve-PackagedAssetRoot
Assert-PathExists (Join-Path $PackagedAssetRoot "icons") "packaged dark icon set"
Assert-PathExists (Join-Path $PackagedAssetRoot "icons_light") "packaged light icon set"
Assert-PathExists (Join-Path $PackagedAssetRoot "app_icon.ico") "packaged app icon"

if (Test-Path $NamedReleaseDir) {
    Remove-Item -LiteralPath $NamedReleaseDir -Recurse -Force
}
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Copy-Item -LiteralPath $DistAppDir -Destination $NamedReleaseDir -Recurse
Compress-Archive -LiteralPath $NamedReleaseDir -DestinationPath $ZipPath -Force

Assert-PathExists $ReleaseExe "release executable"
Assert-PathExists $ZipPath "release zip"

Write-Host "Built release folder: $NamedReleaseDir"
Write-Host "Built release zip:    $ZipPath"
Write-Host "Built executable:     $ReleaseExe"
Write-Host "Smoke test:           & '$ReleaseExe'"
