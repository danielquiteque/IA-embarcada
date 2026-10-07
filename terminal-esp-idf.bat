@echo off
rem Abre um terminal com o ESP-IDF carregado (idf.py disponivel).
rem Uso:  ..\terminal-esp-idf.bat
set IDF_TOOLS_PATH=C:\Espressif
set IDF_PYTHON_ENV_PATH=C:\Espressif\tools\python_env\idf5.5_py3.12_env
call C:\esp\v5.5.5\esp-idf\export.bat
cmd /k
