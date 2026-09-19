Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run", "main.py", "serve", "--port", "8000"
Invoke-Command -ScriptBlock { npm run --prefix frontend dev }
