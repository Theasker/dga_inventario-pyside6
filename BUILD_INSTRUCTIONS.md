# Instrucciones para generar el ejecutable

Este documento describe cómo generar correctamente el ejecutable de la aplicación de inventario en Windows y Linux.

## Requisitos previos

1.  **Python 3.14+** instalado.
2.  **Entorno virtual** configurado y activado.
3.  **Dependencias** instaladas (`PySide6`, `reportlab`, `pillow`, `pyinstaller`).

```bash
pip install -r requirements.txt
pip install pyinstaller pillow
```

## Archivos Necesarios

Para que el ejecutable funcione correctamente con todos sus recursos, asegúrate de tener los siguientes archivos en la raíz del proyecto:
- `main.py`: Código principal.
- `inventory_icon.ico`: Icono de la aplicación (el generado con diseño tecnológico).
- `inventario.db`: Base de datos inicial.
- `logo_servicio.png`: Logo utilizado en la interfaz.
- `Inventario_Dir.spec`: Archivo de configuración de PyInstaller.

## Generación en Windows

Puedes usar el script automatizado `build_windows.ps1` o ejecutar manualmente:

```powershell
pyinstaller Inventario_Dir.spec --noconfirm
```

El resultado estará en la carpeta `dist/Inventario`.

## Generación en Linux

Aunque el desarrollo principal es en Windows, puedes generar una versión para Linux ejecutando el script `build_linux.sh`. 
*Nota: Debes ejecutar esto en una máquina Linux o WSL.*

```bash
chmod +x build_linux.sh
./build_linux.sh
```

## Solución de problemas con Git

Si intentas añadir el archivo `.spec` a Git y recibes un error de "ignored", es porque está en el `.gitignore`. Puedes forzar su inclusión con:

```bash
git add -f Inventario_Dir.spec
```
