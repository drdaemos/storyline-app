Invoke-Command -ScriptBlock { 
    $env:DATABASE_URL = "sqlite:///memory/conversations.db)"
    alembic upgrade head 
}
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run", "main.py", "serve", "--port", "8000", "--reload"
Invoke-Command -ScriptBlock { Set-Location frontend; npm run dev }