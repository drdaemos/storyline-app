# Run the web server (reloading, :8000) and the Vite dev server (:3000, proxies /api and /health) together.
# Open http://localhost:3000. Stop with Ctrl-C.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path "frontend/node_modules")) {
    npm install --prefix frontend
}

$backend = Start-Process -NoNewWindow -PassThru -FilePath "uv" -ArgumentList "run", "-m", "storyline.cli", "serve", "--port", "8000", "--reload"
try {
    npm run --prefix frontend dev
}
finally {
    if (-not $backend.HasExited) { taskkill /PID $backend.Id /T /F | Out-Null }
}
