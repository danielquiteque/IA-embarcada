# Compila um projeto ESP-IDF desta pasta.
# Uso (PowerShell):  .\compilar.ps1 atividade-2-leitura-sensor
param([Parameter(Mandatory = $true)][string]$Projeto)

$env:IDF_TOOLS_PATH = 'C:\Espressif'
$env:IDF_PYTHON_ENV_PATH = 'C:\Espressif\tools\python_env\idf5.5_py3.12_env'
. C:\esp\v5.5.5\esp-idf\export.ps1 | Out-Null

Set-Location (Join-Path $PSScriptRoot $Projeto)
idf.py --version
idf.py build
