@echo off
setlocal
set "dados=%LOCALAPPDATA%\NOCFlow"
if not exist "%dados%" mkdir "%dados%"
if not exist "%dados%\.env" (
    if exist "%~dp0_internal\.env.example" (
        copy "%~dp0_internal\.env.example" "%dados%\.env" >nul
    ) else (
        copy "%~dp0.env.example" "%dados%\.env" >nul
    )
)
start "" notepad.exe "%dados%\.env"
