[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath
)

$ErrorActionPreference = 'Stop'
$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = Join-Path $tempRoot ("dsh-forge-smoke-" + [Guid]::NewGuid().ToString('N'))
$installRoot = Join-Path $runRoot 'app'
$stateRoot = Join-Path $runRoot 'state'
$fixtureRoot = Join-Path $runRoot 'deepseek-harness'
New-Item -ItemType Directory -Path $runRoot | Out-Null
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null
[IO.File]::WriteAllText(
    (Join-Path $fixtureRoot 'package.json'),
    '{"name":"@deepseek-ai/deepseek-harness","version":"0.0-smoke"}',
    [Text.UTF8Encoding]::new($false)
)
[IO.File]::WriteAllText((Join-Path $fixtureRoot 'dsh'), "smoke fixture`r`n", [Text.Encoding]::ASCII)

$setup = Start-Process -FilePath $installer -ArgumentList @(
    '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
    ('/DIR=' + $installRoot), '/MERGETASKS=!desktopicon'
) -Wait -PassThru -WindowStyle Hidden
if ($setup.ExitCode -ne 0) { throw "Installer smoke test failed with exit code $($setup.ExitCode)." }

$app = Join-Path $installRoot 'DSH Forge.exe'
if (-not (Test-Path -LiteralPath $app)) { throw 'The installer did not create DSH Forge.exe.' }
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()
$process = Start-Process -FilePath $app -ArgumentList @(
    '--no-desktop', '--no-sync-catalog', '--port', $port, '--state-dir', $stateRoot,
    '--scan-root', $fixtureRoot
) -PassThru -WindowStyle Hidden

try {
    $status = $null
    foreach ($attempt in 1..40) {
        try {
            $status = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/v1/status" -TimeoutSec 1
            break
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $status) { throw 'The installed launcher did not answer its health endpoint.' }
    if ($status.api_version -ne 'v1' -or -not $status.application.packaged) {
        throw 'The installed launcher returned invalid application status.'
    }
    if (@($status.trees).Count -ne 1 -or $status.trees[0].version -ne '0.0-smoke') {
        throw 'The installed launcher did not detect the local DSH fixture.'
    }
    $page = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/" -TimeoutSec 3
    if ($page.StatusCode -ne 200 -or -not $page.Content.Contains('DSH Forge')) {
        throw 'The installed launcher did not serve the application UI.'
    }
    [pscustomobject]@{
        version = $status.application.version
        platform = $status.application.platform
        packaged = $status.application.packaged
        html_status = $page.StatusCode
        detected_versions = @($status.trees).Count
    } | ConvertTo-Json -Compress | Write-Output
} finally {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
    $uninstaller = Join-Path $installRoot 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) {
        $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @(
            '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
        ) -Wait -PassThru -WindowStyle Hidden
        if ($uninstall.ExitCode -ne 0) { throw "Uninstaller smoke test failed with exit code $($uninstall.ExitCode)." }
    }
    $resolvedRunRoot = [IO.Path]::GetFullPath($runRoot)
    if (-not $resolvedRunRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove smoke-test state outside the temporary directory: $resolvedRunRoot"
    }
    if (Test-Path -LiteralPath $resolvedRunRoot) {
        Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force
    }
}
