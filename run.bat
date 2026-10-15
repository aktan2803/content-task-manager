@echo off
chcp 65001 > nul
title Content Task Manager Server

echo ========================================================
echo   ContentHub - Сервер обработки запросов на контент
echo ========================================================
echo.

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ОШИБКА] Виртуальное окружение venv не найдено!
    echo Создайте его: python -m venv venv ^&^& .\venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo Запуск веб-сервера...
echo Клиентская форма: http://localhost:8000
echo Панель задач:     http://localhost:8000/admin (код доступа: 7788)
echo.

start "" http://localhost:8000

.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
