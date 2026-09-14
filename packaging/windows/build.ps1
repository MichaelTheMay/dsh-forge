[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$')]
    [string]$Version,
    [string]$CertificateThumbprint = '',
    [string]$TimestampUrl = 'http://timestamp.digicert.com',
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$buildRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'build\windows'))
$outputRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'dist\windows'))
$workspacePrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar

function Reset-WorkspaceDirectory([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to replace a directory outside the repository: $resolved"
    }
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    New-Item -ItemType Directory -Path $resolved | Out-Null
}

function Find-SignTool {
    $kitsRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    if (-not (Test-Path -LiteralPath $kitsRoot)) { return $null }
    return Get-ChildItem -LiteralPath $kitsRoot -Filter signtool.exe -Recurse -File |
        Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}

function Sign-Artifact([string]$Path, [string]$SignTool) {
    & $SignTool sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $Path
    if ($LASTEXITCODE -ne 0) { throw "Authenticode signing failed for $Path" }
    & $SignTool verify /pa /v $Path
    if ($LASTEXITCODE -ne 0) { throw "Authenticode verification failed for $Path" }
}

function New-ForgeIcon([string]$Path) {
    Add-Type -AssemblyName System.Drawing
    if (-not ('Forge.NativeIcon' -as [type])) {
        Add-Type @'
using System;
using System.Runtime.InteropServices;
namespace Forge { public static class NativeIcon { [DllImport("user32.dll")] public static extern bool DestroyIcon(IntPtr handle); } }
'@
    }
    $bitmap = New-Object Drawing.Bitmap 256, 256
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([Drawing.Color]::FromArgb(23, 51, 71))
    $teal = New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(8, 126, 139))
    $white = New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(242, 247, 248))
    $points = [Drawing.PointF[]]@(
        [Drawing.PointF]::new(128, 20), [Drawing.PointF]::new(236, 128),
        [Drawing.PointF]::new(128, 236), [Drawing.PointF]::new(20, 128)
    )
    $graphics.FillPolygon($teal, $points)
    $font = New-Object Drawing.Font 'Segoe UI', 105, ([Drawing.FontStyle]::Bold), ([Drawing.GraphicsUnit]::Pixel)
    $graphics.DrawString('F', $font, $white, 89, 63)
    $handle = $bitmap.GetHicon()
    try {
        $icon = [Drawing.Icon]::FromHandle($handle)
        $stream = [IO.File]::Open($Path, [IO.FileMode]::Create)
        try { $icon.Save($stream) } finally { $stream.Dispose(); $icon.Dispose() }
    } finally {
        [Forge.NativeIcon]::DestroyIcon($handle) | Out-Null
        $font.Dispose(); $white.Dispose(); $teal.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
    }
}

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    throw 'The Windows desktop package must be built on Windows.'
}
Reset-WorkspaceDirectory $buildRoot
Reset-WorkspaceDirectory $outputRoot

$metadataPath = Join-Path $buildRoot 'build-version.json'
@{ version = $Version; repository = 'MichaelTheMay/dsh-forge' } |
    ConvertTo-Json -Compress |
    Set-Content -LiteralPath $metadataPath -Encoding UTF8
$iconPath = Join-Path $buildRoot 'DSH-Forge.ico'
New-ForgeIcon $iconPath
$env:DSH_FORGE_BUILD_METADATA = $metadataPath
$env:DSH_FORGE_BUILD_ICON = $iconPath

python -m PyInstaller --noconfirm --clean `
    --distpath (Join-Path $buildRoot 'bundle') `
    --workpath (Join-Path $buildRoot 'work') `
    (Join-Path $PSScriptRoot 'DSHForge.spec')
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller failed. Install packaging/windows/requirements-build.txt in the active Python environment.'
}

$appDirectory = Join-Path $buildRoot 'bundle\DSH Forge'
$appExecutable = Join-Path $appDirectory 'DSH Forge.exe'
if (-not (Test-Path -LiteralPath $appExecutable)) { throw 'The packaged application executable was not produced.' }

$signTool = $null
if ($CertificateThumbprint) {
    $signTool = Find-SignTool
    if (-not $signTool) { throw 'signtool.exe was not found in the Windows 10 SDK.' }
    Sign-Artifact $appExecutable $signTool
} else {
    Write-Warning 'Artifacts are unsigned. Pass -CertificateThumbprint after importing a trusted code-signing certificate.'
}

$zipPath = Join-Path $outputRoot "DSH-Forge-$Version-Windows-x64.zip"
$zipCreated = $false
foreach ($attempt in 1..5) {
    try {
        Compress-Archive -LiteralPath $appDirectory -DestinationPath $zipPath -CompressionLevel Optimal -ErrorAction Stop
        $zipCreated = $true
        break
    } catch {
        if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
        if ($attempt -eq 5) { throw }
        Start-Sleep -Milliseconds 500
    }
}
if (-not $zipCreated) { throw 'The portable Windows archive was not produced.' }
$artifacts = @($zipPath)

if (-not $SkipInstaller) {
    $innoCandidates = @(
        $env:INNO_SETUP_PATH,
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    $iscc = $innoCandidates | Select-Object -First 1
    if (-not $iscc) {
        throw 'Inno Setup was not found. Install JRSoftware.InnoSetup or use -SkipInstaller.'
    }
    & $iscc "/DAppVersion=$Version" "/DSourceDir=$appDirectory" "/DOutputDir=$outputRoot" "/DIconPath=$iconPath" (Join-Path $PSScriptRoot 'DSHForge.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed.' }
    $installer = Join-Path $outputRoot "DSH-Forge-$Version-Setup.exe"
    if (-not (Test-Path -LiteralPath $installer)) { throw 'The Windows installer was not produced.' }
    if ($CertificateThumbprint) { Sign-Artifact $installer $signTool }
    $artifacts += $installer
}

$checksumLines = foreach ($artifact in $artifacts) {
    $hash = (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([IO.Path]::GetFileName($artifact))"
}
$checksumPath = Join-Path $outputRoot 'SHA256SUMS-Windows.txt'
[IO.File]::WriteAllLines($checksumPath, $checksumLines, [Text.Encoding]::ASCII)
$artifacts += $checksumPath

Write-Output 'Windows artifacts:'
$artifacts | ForEach-Object { Write-Output "  $_" }
