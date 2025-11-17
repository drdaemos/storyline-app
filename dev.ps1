Invoke-Command -ScriptBlock { 
    $env:DATABASE_URL = "sqlite:///memory/database.db"
    uv run alembic upgrade head 
}
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run", "main.py", "serve", "--port", "8000", "--reload"
Invoke-Command -ScriptBlock { npm run --prefix frontend dev }