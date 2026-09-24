@echo off

cd /d "%~dp0"

python run_local.py

if errorlevel 1 (

  echo.

  echo No se pudo iniciar Inversor Hapi IA. Revisa el error anterior.

  pause

)

