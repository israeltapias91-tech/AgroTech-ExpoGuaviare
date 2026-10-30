# Genera el .exe de la app de Windows con PyInstaller.
# No empaqueta credenciales: la configuración se lee de config.ini (privado,
# excluido de versiones) en tiempo de ejecución.
#
# Requisitos previos (ejecutar una vez):
#   pip install pyinstaller
#
# Uso:
#   .\scripts\generar_exe.ps1

$ErrorActionPreference = "Stop"

$raiz = Get-Location
$script = "$raiz\src\main.py"
$nombre = "ExpoGuaviare_AgroTech"

if (-not (Test-Path $script)) {
    Write-Error "No se encontró $script. Ejecutar desde la raíz del proyecto."
    exit 1
}

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Error "PyInstaller no está instalado. Ejecutar: pip install pyinstaller"
    exit 1
}

Write-Host "Generando ejecutable de un solo archivo..."
pyinstaller `
    --name $nombre `
    --onedir `
    --windowed `
    --noconsole `
    --add-data "src\ui;src/ui" `
    "$script"

Write-Host "Listo. El ejecutable está en: $raiz\dist\$nombre\$nombre.exe"
Write-Host "No incluye credenciales: configurar config.ini junto al ejecutable antes de usar."
