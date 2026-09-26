Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run", "-m", "storyline.cli", "serve", "--port", "8000"
Invoke-Command -ScriptBlock { npm run --prefix frontend dev }
