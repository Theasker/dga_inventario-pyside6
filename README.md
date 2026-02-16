# Sistema de Inventario de Dispositivos Tecnológicos 🏢💻

Aplicación de escritorio robusta desarrollada en **Python** y **PySide6** para la gestión, control y auditoría de inventario de hardware. Diseñada originalmente para su uso en entornos administrativos del Gobierno de Aragón.

## Características Principales 🚀

* **Gestión Integral**: Control de Secciones, Ubicaciones (despachos/salas) y Dispositivos.
* **Buscador Inteligente**: Filtro en tiempo real insensible a tildes y mayúsculas para una localización rápida de equipos o usuarios.
* **Importación Masiva**: Carga de datos desde archivos **CSV** con validación de campos.
* **Informes Profesionales en PDF**: Generación de reportes detallados mediante **ReportLab**, con agrupación jerárquica por Sección -> Lugar y ordenación alfabética por usuario.
* **Base de Datos Local**: Implementación con **SQLite** para una portabilidad total sin necesidad de servidores externos.
* **Interfaz Adaptativa**: Diseño limpio y profesional con iconos personalizados y diálogos intuitivos.

## Requisitos del Sistema 📋

* Python 3.10 o superior.
* Dependencias de Python:
    * `PySide6` (Interfaz gráfica)
    * `reportlab` (Generación de PDFs)

## Instalación y Configuración 🛠️

1.  **Clonar el repositorio**:
    ```bash
    git clone [https://github.com/Theasker/dga_inventario-pyside6](https://github.com/Theasker/dga_inventario-pyside6)
    cd tu-repositorio
    ```

2.  **Crear un entorno virtual**:
    ```bash
    python -m venv venv
    source venv/Scripts/activate  # Linux
    venv\Scripts\activate.bat  # Windows
    ```

3.  **Instalar dependencias**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Ejecutar la aplicación**:
    ```bash
    python main.py
    ```

## Estructura del CSV para Importación 📊

Para importar datos correctamente, el archivo CSV debe estar delimitado por punto y coma (`;`) y contener los siguientes encabezados:
`seccion;lugar;tipo;marca;modelo;usuario;correo;observaciones`

## Compilación a Ejecutable 📦

Si deseas generar una versión distribuible para Windows sin necesidad de instalar Python:

```bash
pyinstaller --noconfirm --onedir --windowed --add-data "logo_servicio.png;." main.py