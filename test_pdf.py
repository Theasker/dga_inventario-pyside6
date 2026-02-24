import sys
import os

# Añadir el directorio actual al path para poder importar main
sys.path.append(os.path.abspath("."))

try:
    from main import exportar_pdf_compacto
except ImportError as e:
    print(f"Error al importar main: {e}")
    sys.exit(1)

def test_generar_pdf():
    print("Iniciando prueba de generación de PDF...")
    
    # Datos de prueba simulando la estructura de sqlite3.Row con textos largos
    datos_prueba = [
        {
            'seccion': 'SERVICIOS GENERALES Y ADMINISTRACIÓN DE PERSONAL',
            'lugar': 'Despacho de Dirección - Planta 1 - Sala A',
            'tipo': 'Ordenador de Sobremesa de Alto Rendimiento',
            'marca': 'Dell Technologies Inc.',
            'modelo': 'Optiplex 7050 Ultra Slim Form Factor',
            'usuario': 'María del Carmen de los Ángeles González-López (m.gonzalez@departamento.ejemplo.es)',
            'fecha': '2024-02-24',
            'observaciones': 'Equipo con doble monitor y tarjeta gráfica dedicada para diseño.'
        },
        {
            'seccion': 'TECNOLOGÍA',
            'lugar': 'Laboratorio de Pruebas de Software',
            'tipo': 'Portátil Convertible 2-en-1',
            'marca': 'Lenovo',
            'modelo': 'ThinkPad X1 Yoga Gen 6',
            'usuario': '---',
            'fecha': '2024-02-20',
            'observaciones': 'Pantalla táctil compatible con lápiz digital.'
        }
    ]
    
    nombre_archivo = "test_informe_compacto.pdf"
    
    try:
        if os.path.exists(nombre_archivo):
            os.remove(nombre_archivo)
            
        exportar_pdf_compacto(nombre_archivo, datos_prueba)
        
        if os.path.exists(nombre_archivo):
            tamano = os.path.getsize(nombre_archivo)
            print(f"EXITO: PDF generado correctamente ({tamano} bytes)")
            print(f"Archivo creado en: {os.path.abspath(nombre_archivo)}")
        else:
            print("ERROR: El archivo PDF no se creó.")
            sys.exit(1)
            
    except Exception as e:
        print(f"ERROR durante la generacion: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_generar_pdf()
