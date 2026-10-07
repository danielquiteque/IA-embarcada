@echo off
rem Executa compilar.ps1 sem depender da politica de execucao de scripts do Windows.
rem Uso:  ..\compilar.bat atividade-2-leitura-sensor
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0compilar.ps1" %*
