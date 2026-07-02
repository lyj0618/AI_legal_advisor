@echo off
chcp 65001 >nul
echo 正在停止占用 8002/8003 端口的旧后端...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002" ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8003" ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul

cd /d "%~dp0..\backend"
echo 启动新版后端 http://127.0.0.1:8002 ...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
pause
