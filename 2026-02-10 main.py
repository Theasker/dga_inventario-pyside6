import sys
import sqlite3
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QFormLayout, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QHeaderView, QTableWidgetItem,
                             QComboBox, QPushButton, QLineEdit, QLabel, QMessageBox)
from PySide6.QtCore import Qt

# --- MODELO ---
class InventarioModel:
    def __init__(self, db_path='inventario.db'):
        self.db_path = db_path
        self.crear_estructura_si_no_existe()
        self.insertar_datos_prueba()
    
    def conectar(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON") # Activa la integridad referencial
        return conn
    
    def crear_estructura_si_no_existe(self):
        # Crea las tablas necesarias si no existen
        with self.conectar() as conn:
            cursor = conn.cursor()
            # 1. Secciones (Nivel superior)
            cursor.execute('''CREATE TABLE IF NOT EXISTS secciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL
            )''')

            # 2. Tipos de Dispositivo (PC, Monitor...) 
            cursor.execute('''CREATE TABLE IF NOT EXISTS tipos_dispositivo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL
            )''')

            # 3. Ubicaciones (Dependen de una sección) 
            cursor.execute('''CREATE TABLE IF NOT EXISTS ubicaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                seccion_id INTEGER,
                FOREIGN KEY (seccion_id) REFERENCES secciones(id)
            )''')

            # 4. Usuarios 
            cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                correo TEXT UNIQUE
            )''')

            # 5. Dispositivos (El hardware en sí) 
            cursor.execute('''CREATE TABLE IF NOT EXISTS dispositivos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_dispositivo_id INTEGER NOT NULL,
                marca TEXT NOT NULL,
                modelo TEXT NOT NULL,
                fecha_registro DATE,
                observaciones TEXT,
                FOREIGN KEY (tipo_dispositivo_id) REFERENCES tipos_dispositivo(id)
            )''')

            # 6. Asignaciones (Une dispositivo, ubicación y usuario)
            cursor.execute('''CREATE TABLE IF NOT EXISTS asignaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dispositivo_id INTEGER NOT NULL,
                ubicacion_id INTEGER NOT NULL,
                usuario_id INTEGER,
                FOREIGN KEY (dispositivo_id) REFERENCES dispositivos(id),
                FOREIGN KEY (ubicacion_id) REFERENCES ubicaciones(id),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )''')
            conn.commit()
            print("Estructura de base de datos verificada/creada con éxito.")

    def insertar_datos_prueba(self):
        # Inserta datos de prueba en las tablas
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO secciones (id, nombre) VALUES (1, 'COORDINACIÓN TECNOLÓGICA')")
            cursor.execute("INSERT OR IGNORE INTO tipos_dispositivo (id, nombre) VALUES (1, 'PC')")
            cursor.execute("INSERT OR IGNORE INTO ubicaciones (id, nombre, seccion_id) VALUES (1, 'Mesa 01', 1)")
            cursor.execute("INSERT OR IGNORE INTO usuarios (id, nombre, correo) VALUES (1, 'García López, Juan', 'juan.garcia@ejemplo.com')")
            
            cursor.execute("INSERT OR IGNORE INTO dispositivos (id, tipo_dispositivo_id, marca, modelo) VALUES (1, 1, 'Dell', 'Optiplex 7050')")
            
            cursor.execute("INSERT OR IGNORE INTO asignaciones (dispositivo_id, ubicacion_id, usuario_id) VALUES (1, 1, 1)")
            
            conn.commit()
            print("Datos de prueba guardados con éxito en el archivo .db")
            
        except sqlite3.Error as e:
            print(f"Error al insertar datos de prueba: {e}")
        finally:
            conn.close()
        
    # Obtiene todas las secciones para el filtro superior
    def obtener_secciones(self): 
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nombre FROM secciones")
            return cursor.fetchall()
    
    def obtener_inventario_completo(self, texto="", seccion_id=0): 
        query = """
        SELECT 
            u.nombre,        -- Lugar (Ubicación)
            usr.nombre,      -- Apellidos y Nombre
            usr.correo,      -- Correo
            td.nombre,       -- Tipo dispositivo
            d.marca,         -- Marca
            d.modelo,        -- Modelo
            d.fecha_registro,-- Fecha
            d.observaciones  -- Observaciones
        FROM dispositivos d
        LEFT JOIN tipos_dispositivo td ON d.tipo_dispositivo_id = td.id
        LEFT JOIN asignaciones a ON d.id = a.dispositivo_id
        LEFT JOIN ubicaciones u ON a.ubicacion_id = u.id
        LEFT JOIN usuarios usr ON a.usuario_id = usr.id
        WHERE 1=1
        """
        parametros = []
        
        if texto:
            query += " AND (" \
                "u.nombre LIKE ? " \
                "OR usr.nombre LIKE ? " \
                "OR usr.correo LIKE ? " \
                "OR td.nombre LIKE ? " \
                "OR d.marca LIKE ? " \
                "OR d.modelo LIKE ?)"
            term = f"%{texto}%" # Busca todo lo que lleve 
            parametros.extend([term, term, term, term, term, term])  # Usa el mismo parámetro 3 veces
        if seccion_id and seccion_id > 0:
            query += " AND u.seccion_id = ?"
            parametros.append(seccion_id)
        
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute(query, parametros)
            return cursor.fetchall()

    def añadir_seccion(self, nombre):
        try:
            with self.conectar() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO secciones (nombre) VALUES (?)", (nombre,)) # Hay que pasar una tupla
                conn.commit()
                return True
        except sqlite3.IntegrityError as e:
            print(f"Error al añadir sección: {e}")
            return False

    def añadir_dispositivo_completo(self, datos):
        try:
            # El bloque 'with' abre la conexión y la CIERRA al terminar
            with self.conectar() as conn: 
                cursor = conn.cursor()
                
                # Pasamos la conexión activa (conn) a las sub-funciones
                usuario_id = self.obtener_o_crear_usuario(datos['usuario_nombre'], datos['usuario_correo'], conn=conn)
                ubicacion_id = self.obtener_o_crear_ubicacion(datos['ubicacion_nombre'], datos['seccion_id'], conn=conn)

                # Insertar dispositivo
                cursor.execute("""
                    INSERT INTO dispositivos (tipo_dispositivo_id, marca, modelo, observaciones, fecha_registro)
                    VALUES (?, ?, ?, ?, DATE('now'))
                """, (datos['tipo_id'], datos['marca'], datos['modelo'], datos['observaciones']))
                dispositivo_id = cursor.lastrowid

                # Insertar asignación
                cursor.execute("""
                    INSERT INTO asignaciones (dispositivo_id, ubicacion_id, usuario_id)
                    VALUES (?, ?, ?)
                """, (dispositivo_id, ubicacion_id, usuario_id))
                
                conn.commit() # Guardamos todo el bloque de golpe
                return True
        except Exception as e:
            print(f"Error en el modelo: {e}")
            return False

    def obtener_o_crear_usuario(self, nombre=None, correo=None, conn=None):
        # Si no nos pasan una conexión, abrimos una nueva (dueño temporal)
        abierta_aqui = False
        if conn is None:
            conn = self.conectar()
            abierta_aqui = True
            
        cursor = conn.cursor()
        # Intentamos insertar. Si el nombre ya existe, IGNORE hará que no pase nada.
        cursor.execute("INSERT OR IGNORE INTO usuarios (nombre, correo) VALUES (?, ?)", (nombre, correo))
        
        # Recuperamos el ID de ese nombre (sea el que acabamos de crear o el antiguo)
        cursor.execute("SELECT id FROM usuarios WHERE nombre = ?", (nombre,))
        resultado = cursor.fetchone()[0]
        
        # Solo cerramos si nosotros mismos la abrimos
        if abierta_aqui: conn.close()
        return resultado
    
    def obtener_o_crear_ubicacion(self, nombre, seccion_id, conn=None):
        abierta_aqui = False
        if conn is None:
            conn = self.conectar()
            abierta_aqui = True
            
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO ubicaciones (nombre, seccion_id) VALUES (?, ?)", (nombre, seccion_id))
        cursor.execute("SELECT id FROM ubicaciones WHERE nombre = ? AND seccion_id = ?", (nombre, seccion_id))
        
        resultado = cursor.fetchone()[0]
        
        if abierta_aqui: conn.close()
        return resultado

    def obtener_usuarios(self):
        with self.conectar() as conn:
            return conn.execute("SELECT id, nombre, correo FROM usuarios").fetchall()

    def obtener_ubicaciones_por_seccion(self, seccion_id):
        with self.conectar() as conn:
            return conn.execute("SELECT id, nombre FROM ubicaciones WHERE seccion_id = ?", (seccion_id,)).fetchall()

    def obtener_tipos_dispositivo(self):
        with self.conectar() as conn:
            return conn.execute("SELECT id, nombre FROM tipos_dispositivo").fetchall()

    def actualizar_usuario(self, id_usuario, nombre, correo):
        try:
            with self.conectar() as conn:
                conn.execute("UPDATE usuarios SET nombre = ?, correo = ? WHERE id = ?", (nombre, correo, id_usuario))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error al actualizar usuario: {e}")
            return False

    def gestionar_usuario(self, nombre, correo, id_u=None):
        with self.conectar() as conn:
            if id_u:
                conn.execute("UPDATE usuarios SET nombre=?, correo=? WHERE id=?", (nombre, correo, id_u))
            else:
                conn.execute("INSERT OR IGNORE INTO usuarios (nombre, correo) VALUES (?, ?)", (nombre, correo))
            conn.commit()

    def eliminar_dispositivo(self, id_dispositivo):
        try:
            with self.conectar() as conn:
                # Primero eliminamos la asignación y luego el dispositivo
                conn.execute("DELETE FROM asignaciones WHERE dispositivo_id = ?", (id_dispositivo,))
                conn.execute("DELETE FROM dispositivos WHERE id = ?", (id_dispositivo,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error al eliminar: {e}")
            return False

# --- VISTA ---
class InventarioVista(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inventario del Servicio de Información y Documentación")
        self.resize(1100, 700)

        # Widget central
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._layout_principal = QVBoxLayout(self._central_widget)

        self._create_widgets()
        self._create_layout()
        self._create_style()

    def _create_widgets(self):
        # Elementos de la parte superior
        # Filtro de Sección
        self.lbl_seccion = QLabel("Sección:")
        self.cmb_seccion = QComboBox()
        self.btn_add_seccion = QPushButton("+")
        self.btn_add_seccion.setFixedSize(25, 25)

        # Cuadro de búsqueda
        self.txt_busqueda = QLineEdit()
        self.txt_busqueda.setPlaceholderText("Buscar...")

        # Botón para añadir nuevo dispositivo (fila vacía)
        self.btn_add_dispositivo = QPushButton("+ Dispositivo")      

        # Botón para nueva persona
        self.btn_add_user = QPushButton("+ Persona")

        # La tabla principal
        self.tabla_inventario = QTableWidget()
        self.tabla_inventario.setColumnCount(10)
        self.tabla_inventario.setHorizontalHeaderLabels([
            "ID", "Lugar", "Apellidos y Nombre", "Correo", 
            "Tipo dispositivo", "Marca", "Modelo", "Fecha", 
            "Observaciones", "Acciones"
        ])
        # Ocultamos la columna del ID (índice 0)
        self.tabla_inventario.setColumnHidden(0, True)
        # Permite editar celdas haciendo doble click
        self.tabla_inventario.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        header = self.tabla_inventario.horizontalHeader() # Para estirar las columnas
        header.setSectionResizeMode(QHeaderView.Interactive) 
        
        # Estiramos las columnas
        header.setSectionResizeMode(2, QHeaderView.Stretch) # Apellidos y Nombre
        header.setSectionResizeMode(8, QHeaderView.Stretch) # Observaciones
        
        # Ancho mínimo para que se lean los títulos
        self.tabla_inventario.setColumnWidth(1, 100) # Lugar
        self.tabla_inventario.setColumnWidth(4, 120) # Tipo
    
    def _create_layout(self):
        # Layout para la parte superior
        layout_superior = QHBoxLayout()
        layout_superior.addWidget(self.lbl_seccion)
        layout_superior.addWidget(self.cmb_seccion)
        layout_superior.addWidget(self.btn_add_seccion)
        layout_superior.addSpacing(10) # Espacio entre el botón y el cuadro de búsqueda
        layout_superior.addWidget(QLabel("🔍"))
        layout_superior.addWidget(self.txt_busqueda)
        layout_superior.addWidget(self.btn_add_dispositivo)
        layout_superior.addWidget(self.btn_add_user)

        layout_superior.addSpacing(10)

        self._layout_principal.addLayout(layout_superior)
        self._layout_principal.addWidget(self.tabla_inventario)
    
    def _create_style(self):
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #3d3d3d;
                    color: #E0E0E0;
                    font-family: 'Segoe UI', Arial;
                }
                QLineEdit, QComboBox {
                    background-color: #4f4f4f;
                    border: 1px solid #969696;
                    padding: 5px;
                    border-radius: 3px;
                    color: white;
                }
                QPushButton {
                    background-color: #969696;
                    color: #3d3d3d;
                    border-radius: 12px;
                    font-weight: bold;
                }
                QHeaderView::section {
                    background-color: #2d2d2d;
                    color: white;
                    padding: 5px;
                    border: 1px solid #555;
                }
                QTableWidget {
                    gridline-color: #555555;
                    background-color: #3d3d3d;
                    alternate-background-color: #454545;
                    border: 1px solid #969696;
                }
            """)

# --- VISTA (DIÁLOGOS) ---
class DialogoEntidad(QDialog):
    def __init__(self, titulo, campos, valores=None):
        super().__init__()
        self.setWindowTitle(titulo)
        layout = QFormLayout(self)
        self.inputs = {}
        for campo in campos:
            val = valores[campo] if valores and campo in valores else ""
            self.inputs[campo] = QLineEdit(str(val))
            layout.addRow(f"{campo}:", self.inputs[campo])
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def obtener_datos(self):
        return {k: v.text() for k, v in self.inputs.items()}

# --- VISTA - Ventana añadir nueva sección ---
class DialogoSeccion(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Añadir nueva sección")
        self.setMinimumWidth(300)

        layout = QFormLayout(self)
        self.txt_nombre = QLineEdit()
        layout.addRow("Nombre de la Sección:", self.txt_nombre)

        # Botones de Aceptar y Cancelar
        self.botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.botones.accepted.connect(self.accept)
        self.botones.rejected.connect(self.reject)
        layout.addRow(self.botones)

    def obtener_datos(self):
        return self.txt_nombre.text()

# --- VISTA - Ventana Usuarios ---
class DialogoUsuario(QDialog):
    def __init__(self, nombre="", correo="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestión de Usuario")
        layout = QFormLayout(self)

        self.txt_nombre = QLineEdit(nombre)
        self.txt_correo = QLineEdit(correo)
        layout.addRow("Nombre:", self.txt_nombre)
        layout.addRow("Correo:", self.txt_correo)

        # Botones de Aceptar y Cancelar
        self.botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.botones.accepted.connect(self.accept)
        self.botones.rejected.connect(self.reject)
        layout.addRow(self.botones)

# --- CONTROLADOR ---
class InventarioControlador:
    def __init__(self, modelo, vista):
        self.modelo = modelo
        self.vista = vista

        # Cargar datos iniciales
        self.cargar_filtros()
        self.actualizar_tabla()
        self._crear_eventos()

    def _crear_eventos(self):
        # Eventos de la vista
        # Actualiza la tabla al escribir en el cuadro de búsqueda
        self.vista.txt_busqueda.textChanged.connect(self.actualizar_tabla) 
        # Actualiza la tabla al seleccionar una sección
        self.vista.cmb_seccion.currentIndexChanged.connect(self.actualizar_tabla)
        # Abre la ventana para añadir una nueva sección
        self.vista.btn_add_seccion.clicked.connect(self.abrir_dialogo_seccion)
        # Cuando el usuario termina de editar una celda:
        self.vista.tabla_inventario.itemChanged.connect(self.celda_modificada)
        # Botón de nuevo dispositivo
        self.vista.btn_add_dispositivo.clicked.connect(self.añadir_fila_vacia)
        # Botón de guardar cambios
        self.vista.btn_guardar.clicked.connect(self.guardar_cambios_tabla)
        # Crear usuario
        self.vista.btn_add_user.clicked.connect(self.gestionar_usuario_nuevo)

    def abrir_dialogo_seccion(self):
        dialogo = DialogoSeccion(self.vista)
        if dialogo.exec() == QDialog.Accepted:
            nombre_nueva_seccion = dialogo.obtener_datos()
            if nombre_nueva_seccion:
                exito = self.modelo.añadir_seccion(nombre_nueva_seccion)
                if exito:
                    # Refrescamos el ComboBox para que aparezca la nueva sección
                    self.vista.cmb_seccion.clear()
                    self.cargar_filtros()
                else:
                    print("Error: La sección ya existe")

    def cargar_filtros(self):
        # Llena el combo de secciones
        secciones = self.modelo.obtener_secciones()
        self.vista.cmb_seccion.addItem("Todas", 0)  # Opción por defecto
        for id_sec, nombre in secciones:
            self.vista.cmb_seccion.addItem(nombre, id_sec)
    
    def actualizar_tabla(self):
        self.vista.tabla_inventario.setRowCount(0) # Limpia la tabla
        # 1. Leer los filtros de la interfaz
        texto = self.vista.txt_busqueda.text()
        # Obtiene el ID de la sección seleccionada
        seccion_id = self.vista.cmb_seccion.currentData()

        # 2. Pedir datos filtrados al modelo
        datos = self.modelo.obtener_inventario_completo(texto, seccion_id)
        
        # Bloqueamos señales para que no salte "celda_modificada" mientras cargamos
        self.vista.tabla_inventario.blockSignals(True)

        # 3. Rellenar la tabla
        for row_idx, row_data in enumerate(datos):
            self.vista.tabla_inventario.insertRow(row_idx) # Inserta una nueva fila
            for col_idx, value in enumerate(row_data): # Recorre los datos de la fila
                item = QTableWidgetItem(str(value) if value is not None else "") # Convierte a string
                item.setTextAlignment(Qt.AlignCenter)
                # col_idx + 1 para saltar la columna oculta
                self.vista.tabla_inventario.setItem(row_idx, col_idx + 1, item) # Inserta el item en la tabla

        # Activamos de nuevo señales 
        self.vista.tabla_inventario.blockSignals(False)
            
    def celda_modificada(self, item):
        # Actualiza la base de datos cuando se modifica una celda
        fila = item.row() # Obtiene la fila
        columna = item.column() # Obtiene la columna
        nuevo_valor = item.text() # Obtiene el nuevo valor
        
        print(f"Fila: {fila}, Columna {columna}: {nuevo_valor}")

    def añadir_fila_vacia(self):
        s_id = self.vista.cmb_seccion.currentData()
        if s_id == 0: return QMessageBox.warning(self.vista, "Aviso", "Selecciona una sección")
        
        row = self.vista.tabla_inventario.rowCount()
        self.vista.tabla_inventario.insertRow(row)
        self.vista.tabla_inventario.setItem(row, 0, QTableWidgetItem("NUEVA"))
        
        # Combo Lugar
        cb_lugar = QComboBox()
        for id_l, nom in self.modelo.obtener_ubicaciones(s_id): cb_lugar.addItem(nom, id_l)
        self.vista.tabla_inventario.setCellWidget(row, 1, cb_lugar)
        
        # Combo Usuario
        cb_user = QComboBox()
        for id_u, nom, _ in self.modelo.obtener_usuarios(): cb_user.addItem(nom, id_u)
        self.vista.tabla_inventario.setCellWidget(row, 2, cb_user)

        # Combo Tipo
        cb_tipo = QComboBox()
        for id_t, nom in self.modelo.obtener_tipos_dispositivo(): cb_tipo.addItem(nom, id_t)
        self.vista.tabla_inventario.setCellWidget(row, 4, cb_tipo)

        # Botón Guardar individual
        btn_save = QPushButton("💾")
        btn_save.clicked.connect(lambda: self.guardar_fila_nueva(row))
        self.vista.tabla_inventario.setCellWidget(row, 9, btn_save)
        
    def guardar_fila_nueva(self, fila):
        datos = {
            'ubicacion_id': self.vista.tabla_inventario.cellWidget(fila, 1).currentData(),
            'usuario_id': self.vista.tabla_inventario.cellWidget(fila, 2).currentData(),
            'tipo_id': self.vista.tabla_inventario.cellWidget(fila, 4).currentData(),
            'marca': self.vista.tabla_inventario.item(fila, 5).text() if self.vista.tabla_inventario.item(fila, 5) else "",
            'modelo': self.vista.tabla_inventario.item(fila, 6).text() if self.vista.tabla_inventario.item(fila, 6) else "",
            'observaciones': self.vista.tabla_inventario.item(fila, 8).text() if self.vista.tabla_inventario.item(fila, 8) else ""
        }
        if datos['marca'] and datos['modelo']:
            self.modelo.añadir_dispositivo_completo(datos)
            self.actualizar_tabla()

    def obtener_texto(self, fila, columna):
        # Primero intentamos leer si hay un combo
        widget = self.vista.tabla_inventario.cellWidget(fila, columna)
        if isinstance(widget, QComboBox):
            return widget.currentText()
        
        # Si no hay combo, leemos el item normal
        item = self.vista.tabla_inventario.item(fila, columna)
        return item.text() if item else ""

    def obtener_id_tipo(self, fila):
        widget = self.vista.tabla_inventario.cellWidget(fila, 4)
        if isinstance(widget, QComboBox):
            return widget.currentData() # Esto devuelve el ID que guardamos
        return 1 # Por defecto PC

    def configurar_fila_controles(self, row_idx, es_nueva=True):
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(2, 2, 2, 2)

        # Botón borrar
        btn_del = QPushButton("❌")
        btn_del.setFixedSize(28, 28)
        btn_del.setToolTip("Eliminar registro")

        layout.addWidget(btn_del) # Añadimos el widget del botón

        # Botón grabar registro
        if es_nueva:
            btn_save = QPushButton("💾")
            btn_save.setFixedSize(28, 28)
            btn_save.setToolTip("Guardar registro")
            layout.insertWidget(0, btn_save) # Insertamos el botón
            # Señal del botón guardar
            btn_save.clicked.connect(lambda: self.guardar_esta_fila(row_idx))
        
        # Señal del botón borrar
        btn_del.clicked.connect(lambda: self.eliminar_fila(row_idx))

        self.vista.tabla_inventario.setCellWidget(row_idx, 9, panel) # 

    def añadir_botones_accion(self, fila, d_id):
        btn_del = QPushButton("❌")
        btn_del.setFixedSize(30, 25)
        btn_del.clicked.connect(lambda: self.eliminar_registro(d_id))
        self.vista.tabla_inventario.setCellWidget(fila, 9, btn_del)

    def eliminar_registro(self, d_id):
        if QMessageBox.question(self.vista, "Confirmar", "¿Eliminar este dispositivo?") == QMessageBox.Yes:
            self.modelo.eliminar_registro(d_id)
            self.actualizar_tabla()
    
    def gestionar_usuario_nuevo(self):
        dial = DialogoEntidad("Nuevo Usuario", ["Nombre", "Correo"])
        if dial.exec():
            res = dial.obtener_datos()
            self.modelo.gestionar_usuario(res["Nombre"], res["Correo"])


if __name__ == "__main__":
    app = QApplication(sys.argv)

    modelo = InventarioModel("inventario.db")
    vista = InventarioVista()
    controlador = InventarioControlador(modelo, vista)

    vista.show()
    sys.exit(app.exec())