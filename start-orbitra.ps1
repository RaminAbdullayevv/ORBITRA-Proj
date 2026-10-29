param([switch]$Smoke, [switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $created = $false
    foreach ($candidate in @('py', 'python')) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            try {
                if ($candidate -eq 'py') { & py -3 -m venv (Join-Path $backend '.venv') }
                else { & python -m venv (Join-Path $backend '.venv') }
                $created = $LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $python)
                if ($created) { break }
            } catch {}
        }
    }
    if (-not $created) { throw 'Python 3.11+ quraşdırın və skripti yenidən başladın.' }
}
if (-not $SkipInstall) {
    & $python -m pip install -r (Join-Path $backend 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency quraşdırması uğursuz oldu.' }
    if (-not (Test-Path -LiteralPath (Join-Path $frontend 'node_modules'))) {
        Push-Location $frontend
        try { & npm install; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency quraşdırması uğursuz oldu.' } }
        finally { Pop-Location }
    }
}
Push-Location $backend
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Main database migration uğursuz oldu.' }
    & $python -m scripts.setup_security
    if ($LASTEXITCODE -ne 0) { throw 'Telemetriya açarının qurulması uğursuz oldu.' }
    & $python -m scripts.merge_device_history
    if ($LASTEXITCODE -ne 0) { throw 'Köhnə Device tarixçəsinin köçürülməsi uğursuz oldu.' }
    & $python -m scripts.manage_users init
    if ($LASTEXITCODE -ne 0) { throw 'Hesabların qurulması uğursuz oldu.' }
} finally { Pop-Location }
$services = @(
    @{ Name='ORBITRA API'; Dir=$backend; File=$python; Args=@('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') },
    @{ Name='ORBITRA UI'; Dir=$frontend; File='npm.cmd'; Args=@('run','dev','--','--host','localhost','--port','5173','--strictPort') }
)
$jobs = foreach ($item in $services) {
    Start-Job -Name $item.Name -ArgumentList $item.Dir,$item.File,$item.Args -ScriptBlock {
        param($directory,$file,$arguments)
        Set-Location -LiteralPath $directory
        & $file @arguments
    }
}
Write-Host 'ORBITRA: http://localhost:5173/login'
Write-Host 'Lokal demo giriş məlumatları START_HERE.md sənədindədir.'
Write-Host 'İki xidmət bu pəncərə açıq qaldıqca işləyir. Dayandırmaq üçün Ctrl+C.'
try {
    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseProxy = $false
    $http = New-Object System.Net.Http.HttpClient($handler)
    $http.Timeout = [TimeSpan]::FromSeconds(2)
    try {
        foreach ($url in @('http://127.0.0.1:8000/api/v1/health','http://localhost:5173/login')) {
            $ready = $false
            for ($attempt = 0; $attempt -lt 60; $attempt++) {
                foreach ($job in $jobs) {
                    if ($job.State -ne 'Running') { throw "$($job.Name) dayandı: $($job.State)" }
                }
                try {
                    $response = $http.GetAsync($url).GetAwaiter().GetResult()
                    if ($response.IsSuccessStatusCode) { $ready = $true; break }
                } catch {}
                Start-Sleep -Seconds 1
            }
            if (-not $ready) { throw "Hazırlıq yoxlaması uğursuz oldu: $url" }
            Write-Host "OK: $url"
        }
    } finally { $http.Dispose(); $handler.Dispose() }
    if ($Smoke) { return }
    while ($true) {
        foreach ($job in $jobs) {
            if ($job.State -ne 'Running') { throw "$($job.Name) dayandı: $($job.State)" }
        }
        Start-Sleep -Seconds 2
    }
} finally {
    $jobs | Stop-Job -ErrorAction SilentlyContinue
    $jobs | Remove-Job -Force -ErrorAction SilentlyContinue
}
