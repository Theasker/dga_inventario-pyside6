
import sys
import os
import sqlite3
import unicodedata
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QMainWindow,
    QProgressBar,
    QSizePolicy,
    QStatusBar,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QHeaderView,
    QTableWidgetItem,
    QComboBox,
    QPushButton,
    QLineEdit,
    QLabel,
    QMessageBox,
    QFileDialog,
    QDialog, 
    QFormLayout, 
    QDialogButtonBox,
    QDateEdit,
    QFrame
)
from PySide6.QtCore import Qt, QDate

def remover_tildes(texto):
    if texto is None: return ""
    texto = str(texto).lower()
    return "".join(c for c in unicodedata.normalize('NFD', texto)
                   if unicodedata.category(c) != 'Mn')

def resource_path(relative_path):
    """ Obtiene la ruta absoluta de los recursos, compatible con PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- MODELO ---
class InventarioModel:
    def __init__(self, db_path="inventario.db"):
        self.db_path = db_path
        self.crear_estructura_si_no_existe()

    def conectar(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")  # Integridad referencial
        return conn

    def crear_estructura_si_no_existe(self):
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS secciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS tipos_dispositivo (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                nombre TEXT UNIQUE NOT NULL)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS ubicaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                seccion_id INTEGER,
                UNIQUE(nombre, seccion_id), 
                FOREIGN KEY (seccion_id) REFERENCES secciones(id))''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL, 
                correo TEXT UNIQUE)''')
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS dispositivos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tipo_dispositivo_id INTEGER NOT NULL,
                marca TEXT NOT NULL, modelo TEXT NOT NULL, fecha_registro DATE, observaciones TEXT,
                FOREIGN KEY (tipo_dispositivo_id) REFERENCES tipos_dispositivo(id))"""
            )
            cursor.execute('''CREATE TABLE IF NOT EXISTS asignaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dispositivo_id INTEGER,
                ubicacion_id INTEGER,
                usuario_id INTEGER,  -- Aquí permitimos nulos
                FOREIGN KEY(dispositivo_id) REFERENCES dispositivos(id) ON DELETE CASCADE,
                FOREIGN KEY(ubicacion_id) REFERENCES ubicaciones(id),
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')

            # Datos base iniciales
            cursor.execute(
                """INSERT OR IGNORE INTO tipos_dispositivo (nombre) 
                        VALUES ('PC'), ('Monitor'), ('Impresora'), ('Teclado'), ('Cámara'), ('WebCam'), ('Auriculares'), ('Teléfono')"""
            )
            conn.commit()

    def obtener_secciones(self):
        with self.conectar() as conn:
            return conn.execute("SELECT id, nombre FROM secciones").fetchall()

    def obtener_usuarios(self):
        with self.conectar() as conn:
            return conn.execute(
                "SELECT id, nombre, correo FROM usuarios ORDER BY nombre"
            ).fetchall()

    def obtener_tipos_dispositivo(self):
        with self.conectar() as conn:
            return conn.execute("SELECT id, nombre FROM tipos_dispositivo").fetchall()

    def obtener_ubicaciones_por_seccion(self, seccion_id):
        with self.conectar() as conn:
            return conn.execute(
                "SELECT id, nombre FROM ubicaciones WHERE seccion_id = ?", (seccion_id,)
            ).fetchall()

    def obtener_inventario_completo(self, busqueda="", seccion_id=None):
        termino_limpio = f"%{remover_tildes(busqueda)}%"
        conn = self.conectar()
        # Registramos la función para que SQLite entienda 'BUSCAR'
        conn.create_function("BUSCAR", 1, remover_tildes)
        
        query = '''SELECT d.id, l.nombre, u.nombre, u.correo, t.nombre, d.marca, d.modelo, d.fecha_registro, d.observaciones
                   FROM dispositivos d
                   JOIN asignaciones a ON d.id = a.dispositivo_id
                   JOIN ubicaciones l ON a.ubicacion_id = l.id
                   JOIN tipos_dispositivo t ON d.tipo_dispositivo_id = t.id
                   LEFT JOIN usuarios u ON a.usuario_id = u.id
                   JOIN secciones s ON l.seccion_id = s.id
                   WHERE (
                       BUSCAR(u.nombre) LIKE ? OR 
                       BUSCAR(d.marca) LIKE ? OR 
                       BUSCAR(d.modelo) LIKE ? OR 
                       BUSCAR(d.observaciones) LIKE ? OR
                       BUSCAR(l.nombre) LIKE ?
                   )'''
        params = [termino_limpio] * 5
        if seccion_id and seccion_id != 0:
            query += " AND s.id = ?"
            params.append(seccion_id)
            
        query += " ORDER BY d.id DESC"
        try:
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()

    def añadir_dispositivo_completo(self, datos):
        with self.conectar() as conn:
            cursor = conn.cursor()
            # La fecha solo se guarda en la tabla 'dispositivos'
            cursor.execute(
                "INSERT INTO dispositivos (tipo_dispositivo_id, marca, modelo, observaciones, fecha_registro) VALUES (?, ?, ?, ?, ?)",
                (datos['tipo_id'], datos['marca'], datos['modelo'], datos['observaciones'], datos['fecha'])
            )
            dispositivo_id = cursor.lastrowid
            
            # Eliminamos el campo 'fecha' de la tabla 'asignaciones'
            cursor.execute(
                "INSERT INTO asignaciones (dispositivo_id, ubicacion_id, usuario_id) VALUES (?, ?, ?)",
                (dispositivo_id, datos['ubicacion_id'], datos['usuario_id'])
            )
            return True

    def eliminar_registro(self, d_id):
        with self.conectar() as conn:
            conn.execute("DELETE FROM asignaciones WHERE dispositivo_id=?", (d_id,))
            conn.execute("DELETE FROM dispositivos WHERE id=?", (d_id,))
            conn.commit()

    def eliminar_seccion(self, id_sec):
        try:
            with self.conectar() as conn:
                conn.execute("DELETE FROM secciones WHERE id = ?", (id_sec,))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # No se puede borrar si tiene dependencias

    def eliminar_ubicacion(self, id_ub):
        try:
            with self.conectar() as conn:
                conn.execute("DELETE FROM ubicaciones WHERE id = ?", (id_ub,))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def eliminar_usuario(self, id_usr):
        try:
            with self.conectar() as conn:
                conn.execute("DELETE FROM usuarios WHERE id = ?", (id_usr,))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def actualizar_nombre_entidad(self, tabla, id_ent, nuevo_nombre):
        """Método genérico para renombrar Secciones, Lugares o Usuarios"""
        try:
            with self.conectar() as conn:
                conn.execute(f"UPDATE {tabla} SET nombre = ? WHERE id = ?", (nuevo_nombre, id_ent))
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    def actualizar_dispositivo_completo(self, d_id, datos):
        with self.conectar() as conn:
            cursor = conn.cursor()
            # CAMBIO: La fecha ahora se actualiza en la tabla 'dispositivos'
            cursor.execute('''UPDATE dispositivos 
                              SET tipo_dispositivo_id=?, marca=?, modelo=?, observaciones=?, fecha_registro=? 
                              WHERE id=?''',
                           (datos['tipo_id'], datos['marca'], datos['modelo'], datos['observaciones'], datos['fecha'], d_id))
            
            # CAMBIO: La asignación ya no lleva fecha
            cursor.execute('''UPDATE asignaciones 
                              SET ubicacion_id=?, usuario_id=? 
                              WHERE dispositivo_id=?''',
                           (datos['ubicacion_id'], datos['usuario_id'], d_id))
            conn.commit()
            return True

    def añadir_seccion(self, nombre):
        with self.conectar() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO secciones (nombre) VALUES (?)", (nombre,)
            )
            conn.commit()

    def añadir_usuario(self, nombre, correo):
        with self.conectar() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO usuarios (nombre, correo) VALUES (?, ?)",
                (nombre, correo),
            )
            conn.commit()

    def actualizar_usuario_completo(self, id_usr, nuevo_nombre, nuevo_correo):
        try:
            with self.conectar() as conn:
                conn.execute(
                    "UPDATE usuarios SET nombre = ?, correo = ? WHERE id = ?",
                    (nuevo_nombre, nuevo_correo, id_usr)
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error al actualizar usuario: {e}")
            return False

    def añadir_ubicacion(self, nombre, seccion_id):
        try:
            with self.conectar() as conn:
                conn.execute(
                    "INSERT INTO ubicaciones (nombre, seccion_id) VALUES (?, ?)",
                    (nombre, seccion_id),
                )
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    def añadir_tipo_dispositivo(self, nombre):
        try:
            with self.conectar() as conn:
                conn.execute("INSERT INTO tipos_dispositivo (nombre) VALUES (?)", (nombre,))
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    def importar_desde_csv(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self.vista, "Importar Inventario", "", "CSV Files (*.csv)"
        )
        if not ruta:
            return

        try:
            with open(ruta, newline='', encoding='utf-8') as f:
                lector = csv.reader(f, delimiter=';')
                try:
                    next(lector)  # Saltar cabecera
                except StopIteration:
                    return

                contador = 0
                for i, fila in enumerate(lector, 1):
                    try:
                        if len(fila) < 9:
                            continue

                        # Extracción de datos según tu CSV
                        sede_txt    = fila[0].strip()
                        usuario_txt = fila[1].strip()
                        tipo_txt    = fila[4].strip()
                        marca       = fila[5].strip()
                        modelo_txt  = fila[6].strip()
                        sn_txt      = fila[7].strip()
                        fecha_txt   = fila[8].strip()

                        # Obtener o Crear IDs en la base de datos
                        id_ubi  = self.modelo.obtener_o_crear_ubicacion(sede_txt)
                        id_usu  = self.modelo.obtener_o_crear_usuario(usuario_txt)
                        id_tipo = self.modelo.obtener_o_crear_tipo(tipo_txt)

                        # Insertar el dispositivo final
                        obs = f"S/N: {sn_txt}"
                        exito = self.modelo.insertar_dispositivo(
                            id_tipo, marca, modelo_txt, id_ubi, id_usu, fecha_txt, obs
                        )
                        
                        if exito:
                            contador += 1
                            
                    except Exception as row_err:
                        print(f"Error procesando fila {i}: {row_err}")
                        continue

                self.actualizar_tabla()
                QMessageBox.information(self.vista, "Éxito", f"Se han importado {contador} registros.")

        except Exception as e:
            QMessageBox.critical(self.vista, "Error Crítico", f"No se pudo leer el archivo: {str(e)}")

    def obtener_todas_las_ubicaciones(self):
        query = """
            SELECT u.id, u.nombre, s.nombre 
            FROM ubicaciones u 
            JOIN secciones s ON u.seccion_id = s.id 
            ORDER BY s.nombre, u.nombre
        """
        with self.conectar() as conn:
            return conn.execute(query).fetchall()

    def obtener_datos_para_informe(self):
        query = """
            SELECT s.nombre as seccion, l.nombre as lugar, t.nombre as tipo, 
                   d.marca, d.modelo, u.nombre as usuario, a.fecha
            FROM dispositivos d
            JOIN asignaciones a ON d.id = a.dispositivo_id
            JOIN ubicaciones l ON a.ubicacion_id = l.id
            JOIN secciones s ON l.seccion_id = s.id
            JOIN tipos_dispositivo t ON d.tipo_dispositivo_id = t.id
            LEFT JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY s.nombre, l.nombre, t.nombre
        """
        with self.conectar() as conn:
            conn.row_factory = sqlite3.Row # Para acceder por nombre de columna
            return conn.execute(query).fetchall()

    def obtener_datos_informe_agrupado(self):
        query = """
            SELECT s.nombre as seccion, 
                   l.nombre as lugar, 
                   t.nombre as tipo, 
                   d.marca, 
                   d.modelo, 
                   CASE 
                       WHEN u.nombre IS NOT NULL AND u.correo IS NOT NULL AND u.correo != '' 
                            THEN u.nombre || ' (' || u.correo || ')'
                       WHEN u.nombre IS NOT NULL THEN u.nombre
                       ELSE '---'
                   END as usuario,
                   d.fecha_registro as fecha,
                   d.observaciones
            FROM dispositivos d
            JOIN asignaciones a ON d.id = a.dispositivo_id
            JOIN ubicaciones l ON a.ubicacion_id = l.id
            JOIN secciones s ON l.seccion_id = s.id
            JOIN tipos_dispositivo t ON d.tipo_dispositivo_id = t.id
            LEFT JOIN usuarios u ON a.usuario_id = u.id
            ORDER BY s.nombre ASC, l.nombre ASC, u.nombre ASC
        """
        conn = self.conectar()
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(query).fetchall()
        finally:
            conn.close()

    def insertar_tipo(self, nombre):
        query = "INSERT INTO tipos (nombre) VALUES (?)"
        cursor = self.db.conn.cursor()
        cursor.execute(query, (nombre,))
        self.db.conn.commit()
        return cursor.lastrowid

    def insertar_ubicacion(self, nombre):
        query = "INSERT INTO ubicaciones (nombre) VALUES (?)"
        cursor = self.db.conn.cursor()
        cursor.execute(query, (nombre,))
        self.db.conn.commit()
        return cursor.lastrowid

    def obtener_o_crear_seccion(self, nombre, conn=None):
        if not nombre: nombre = "General"
        def logica(c):
            res = c.execute("SELECT id FROM secciones WHERE nombre = ?", (nombre.strip(),)).fetchone()
            if res: return res[0]
            cursor = c.cursor()
            cursor.execute("INSERT INTO secciones (nombre) VALUES (?)", (nombre.strip(),))
            return cursor.lastrowid
        if conn: return logica(conn)
        with self.conectar() as c: return logica(c)

    def obtener_o_crear_tipo_dispositivo(self, nombre, conn=None):
        if not nombre: nombre = "Otros"
        def logica(c):
            res = c.execute("SELECT id FROM tipos_dispositivo WHERE nombre = ?", (nombre.strip(),)).fetchone()
            if res: return res[0]
            cursor = c.cursor()
            cursor.execute("INSERT INTO tipos_dispositivo (nombre) VALUES (?)", (nombre.strip(),))
            return cursor.lastrowid
        if conn: return logica(conn)
        with self.conectar() as c: return logica(c)

    def obtener_o_crear_ubicacion(self, nombre, seccion_id, conn=None):
        if not nombre: nombre = "Almacén"
        def logica(c):
            res = c.execute("SELECT id FROM ubicaciones WHERE nombre = ? AND seccion_id = ?", (nombre.strip(), seccion_id)).fetchone()
            if res: return res[0]
            cursor = c.cursor()
            cursor.execute("INSERT INTO ubicaciones (nombre, seccion_id) VALUES (?, ?)", (nombre.strip(), seccion_id))
            return cursor.lastrowid
        if conn: return logica(conn)
        with self.conectar() as c: return logica(c)

    def obtener_o_crear_usuario(self, nombre, correo=None, conn=None):
        if not nombre: return None
        def logica(c):
            res = c.execute("SELECT id, correo FROM usuarios WHERE nombre = ?", (nombre.strip(),)).fetchone()
            if res:
                u_id, c_actual = res
                if correo and not c_actual:
                    c.execute("UPDATE usuarios SET correo = ? WHERE id = ?", (correo.strip(), u_id))
                return u_id
            cursor = c.cursor()
            cursor.execute("INSERT INTO usuarios (nombre, correo) VALUES (?, ?)", 
                           (nombre.strip(), correo.strip() if correo else None))
            return cursor.lastrowid
        if conn: return logica(conn)
        with self.conectar() as c: return logica(c)

    def actualizar_seccion_de_ubicacion(self, id_ub, nueva_seccion_id):
        try:
            with self.conectar() as conn:
                conn.execute("UPDATE ubicaciones SET seccion_id = ? WHERE id = ?", (nueva_seccion_id, id_ub))
                conn.commit()
                return True
        except sqlite3.Error:
            return False

# --- VISTA ---
class InventarioVista(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inventario del Servicio de Información y Documentación")
        self.resize(1200, 800)

        # Carga del icono usando la función de ruta segura
        icon_path = resource_path("logo_servicio.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setWindowIcon(QIcon(resource_path("logo_servicio.png")))
        
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._layout_principal = QVBoxLayout(self._central_widget)
        self._create_widgets()
        self._create_layout()
        self._apply_style()

    def _create_widgets(self):
        # --- Grupo SECCIÓN ---
        self.frame_seccion = QFrame()
        self.cmb_seccion = QComboBox()
        self.cmb_seccion.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # Hacemos que el combo pueda expandirse horizontalmente
        self.cmb_seccion.setMinimumWidth(200) # Establecer un ancho mínimo para que no se vea muy pequeño al inicio
        self.btn_add_seccion = QPushButton("+")
        self.btn_add_seccion.setFixedSize(30, 30)       
        self.btn_gear_seccion = QPushButton("⚙️")
        self.btn_gear_seccion.setFixedSize(30, 30)
        
        # --- Búsqueda ---
        self.txt_busqueda = QLineEdit()
        self.txt_busqueda.setPlaceholderText("Buscar...")

        # --- Grupo LUGAR ---
        self.frame_lugar = QFrame()
        self.btn_add_lugar = QPushButton("+ Lugar") 
        self.btn_gear_lugar = QPushButton("⚙️")
        self.btn_gear_lugar.setFixedSize(30, 30)

        # --- Grupo PERSONA ---
        self.frame_persona = QFrame()
        self.btn_add_user = QPushButton("+ Persona")
        self.btn_gear_user = QPushButton("⚙️")
        self.btn_gear_user.setFixedSize(30, 30)

        self.btn_add_dispositivo = QPushButton("+ Dispositivo")

        # --- Botón importar
        self.btn_importar = QPushButton("📥 Importar CSV")
        self.btn_importar.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")

        # --- Botón exportar informe
        self.btn_pdf = QPushButton("📄 Informe PDF")

        # Creación de la tabla -------------------------------
        self.tabla_inventario = QTableWidget()
        self.tabla_inventario.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla_inventario.setSelectionBehavior(QAbstractItemView.SelectRows) # Recomendado
        self.tabla_inventario.setColumnCount(10)
        self.tabla_inventario.setHorizontalHeaderLabels(
            [
                "ID",
                "Lugar",
                "Usuario",
                "Correo",
                "Tipo",
                "Marca",
                "Modelo",
                "Fecha",
                "Observaciones",
                "Acciones",
            ]
        )
        self.tabla_inventario.setColumnHidden(0, True)

        # Ajuste de la cabecera vertical (índice 1, 2, 3...)
        v_header = self.tabla_inventario.verticalHeader()
        v_header.setSectionResizeMode(QHeaderView.Fixed)
        v_header.setFixedWidth(45)

        # Permitir que las columnas sean redimensionables interactivamente
        header = self.tabla_inventario.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Estirar "Usuario"
        header.setSectionResizeMode(8, QHeaderView.Stretch)  # Estirar "Observaciones"
        # FIN creación de tabla -----------------------

        # Crear el selector de fecha
        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)  # Esto despliega un calendario real al hacer clic
        self.date_picker.setDate(QDate.currentDate())  # Por defecto, la fecha de hoy
        self.date_picker.setDisplayFormat("yyyy/MM/dd")  # Lo que ve el usuario

        # Barra de Estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_contador = QLabel("Dispositivos: 0")
        self.lbl_autor = QLabel("Desarrollado por Mauricio Segura  ")
        self.status_bar.addWidget(self.lbl_contador)
        self.status_bar.addPermanentWidget(self.lbl_autor)

        # Barra de Progreso
        self.progreso = QProgressBar()
        self.progreso.setVisible(False)  # Oculta hasta que empiece la carga
        self.progreso.setTextVisible(True)
        self.progreso.setFormat("%p% - Importando: %v de %m")

    def _create_layout(self):
        ly_superior = QHBoxLayout()

        # Layout interno SECCIÓN
        self.frame_seccion.setObjectName("frameVerde") # Asignamos nombre para el estilo        
        ly_seccion = QHBoxLayout(self.frame_seccion)
        ly_seccion.addWidget(QLabel("Sección:"))
        ly_seccion.addWidget(self.cmb_seccion)
        ly_seccion.addWidget(self.btn_add_seccion)
        ly_seccion.addWidget(self.btn_gear_seccion)
        ly_superior.addWidget(self.frame_seccion)

        # Layout interno LUGAR
        self.frame_lugar.setObjectName("frameAzul")
        ly_lugar = QHBoxLayout(self.frame_lugar)
        ly_lugar.addWidget(self.btn_add_lugar)
        ly_lugar.addWidget(self.btn_gear_lugar)
        ly_superior.addWidget(self.frame_lugar)

        # Layout interno PERSONA
        self.frame_persona.setObjectName("frameNaranja")
        ly_persona = QHBoxLayout(self.frame_persona)
        ly_persona.addWidget(self.btn_add_user)
        ly_persona.addWidget(self.btn_gear_user)
        ly_superior.addWidget(self.frame_persona)

        # Espacio y Buscador
        ly_superior.addSpacing(10)
        ly_superior.addWidget(QLabel("🔍"))      
        ly_superior.addWidget(self.txt_busqueda)
        ly_superior.addSpacing(10)

        # Botones de acción
        ly_superior.addWidget(self.btn_add_dispositivo)
        ly_superior.addWidget(self.btn_pdf)
        ly_superior.addWidget(self.btn_importar)

        # Barra de progreso
        self._layout_principal.addWidget(self.progreso)

        # Añadir todo al layout principal
        self._layout_principal.addLayout(ly_superior)
        self._layout_principal.addWidget(self.tabla_inventario)

    def _apply_style(self):
        # Estilo general oscuro
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #3d3d3d; color: #E0E0E0; font-family: 'Segoe UI'; }
            QLineEdit, QComboBox { background-color: #4f4f4f; border: 1px solid #969696; padding: 4px; color: white; }
            QPushButton { background-color: #969696; color: #3d3d3d; border-radius: 4px; font-weight: bold; padding: 5px; }
            QHeaderView::section { background-color: #2d2d2d; color: white; border: 1px solid #555; }
            
            /* Quitamos el borde que heredan los Labels dentro de los marcos */
            QFrame QLabel { border: none; background: transparent; }
            
            /* Estilos específicos para cada marco usando su ID */
            QFrame#frameVerde { border: 2px solid #A5D6A7; border-radius: 8px; background-color: #454545; }
            QFrame#frameAzul { border: 2px solid #90CAF9; border-radius: 8px; background-color: #454545; }
            QFrame#frameNaranja { border: 2px solid #FFCC80; border-radius: 8px; background-color: #454545; }
        """)

        # Estilo específico para el botón de importar y exportar
        self.btn_importar.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_pdf.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        
        # Barra de progreso
        self.progreso.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bbb;
                border-radius: 5px;
                text-align: center;
                height: 25px;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
            }
        """)

# --- VISTA. Diálogo Gestión ---
class VentanaGestion(QDialog):
    def __init__(self, titulo, tabla_db, modelo, funcion_datos, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(550, 400) # Un poco más ancha para la nueva columna
        self.modelo = modelo
        self.tabla_db = tabla_db
        self.funcion_datos = funcion_datos
        
        layout = QVBoxLayout(self)
        self.tabla = QTableWidget()
        
        # El número de columnas inicial se ajustará en cargar_datos
        layout.addWidget(self.tabla)
        self.cargar_datos()
        
        # Evento para editar al cambiar el texto de una celda
        self.tabla.itemChanged.connect(self.editar_registro)

    def cargar_datos(self):
        self.tabla.blockSignals(True)
        datos = self.funcion_datos()
        self.tabla.setRowCount(0)
        
        # 1. CONFIGURACIÓN DE COLUMNAS SEGÚN TABLA
        if self.tabla_db == "usuarios":
            self.tabla.setColumnCount(3)
            self.tabla.setHorizontalHeaderLabels(["Nombre", "Correo", "Acción"])
        elif self.tabla_db == "ubicaciones":
            self.tabla.setColumnCount(3) # Nombre | Cambiar Sección | Acción
            self.tabla.setHorizontalHeaderLabels(["Nombre Lugar", "Cambiar Sección", "Acción"])
            todas_las_secciones = self.modelo.obtener_secciones() # Necesario para el combo
        else:
            self.tabla.setColumnCount(2)
            self.tabla.setHorizontalHeaderLabels(["Nombre", "Acción"])

        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 2. LLENADO DE DATOS
        for row_idx, fila_data in enumerate(datos):
            id_ent, nombre = fila_data[0], fila_data[1]
            self.tabla.insertRow(row_idx)
            
            # Celda Nombre (Columna 0)
            item_nom = QTableWidgetItem(str(nombre))
            item_nom.setData(Qt.UserRole, id_ent)
            self.tabla.setItem(row_idx, 0, item_nom)
            
            col_boton = 1 # Posición por defecto del botón eliminar
            
            # --- CASO ESPECIAL: USUARIOS (Columna Correo) ---
            if self.tabla_db == "usuarios":
                correo = fila_data[2] if len(fila_data) > 2 else ""
                item_mail = QTableWidgetItem(str(correo))
                item_mail.setData(Qt.UserRole, id_ent)
                self.tabla.setItem(row_idx, 1, item_mail)
                col_boton = 2
                
            # --- CASO ESPECIAL: UBICACIONES (Columna Cambiar Sección) ---
            elif self.tabla_db == "ubicaciones":
                cb_seccion = QComboBox()
                seccion_actual_id = 0
                # Buscamos la sección actual de este lugar para marcarla en el combo
                # Para esto, el modelo debería devolver la sección_id en fila_data[2]
                for s_id, s_nom in todas_las_secciones:
                    cb_seccion.addItem(s_nom, s_id)
                
                # Intentamos preseleccionar la sección correcta si viene en los datos
                if len(fila_data) > 2:
                    idx = cb_seccion.findData(fila_data[2])
                    if idx >= 0: cb_seccion.setCurrentIndex(idx)

                # Conexión para actualizar la sección en la DB al cambiar el combo
                cb_seccion.currentIndexChanged.connect(
                    lambda idx, u_id=id_ent, cb=cb_seccion: self.modelo.actualizar_seccion_de_ubicacion(u_id, cb.currentData())
                )
                self.tabla.setCellWidget(row_idx, 1, cb_seccion)
                col_boton = 2

            # 3. BOTÓN ELIMINAR
            btn_del = QPushButton("Eliminar")
            btn_del.setStyleSheet("background-color: #c0392b; color: white;")
            btn_del.clicked.connect(lambda _, i=id_ent: self.borrar(i))
            self.tabla.setCellWidget(row_idx, col_boton, btn_del)
            
        self.tabla.blockSignals(False)

    def editar_registro(self, item):
        fila = item.row()
        id_ent = item.data(Qt.UserRole)
        
        if self.tabla_db == "usuarios":
            nom = self.tabla.item(fila, 0).text().strip()
            item_correo = self.tabla.item(fila, 1)
            mail = item_correo.text().strip() if item_correo else ""
            if nom:
                self.modelo.actualizar_usuario_completo(id_ent, nom, mail)
        else:
            nuevo_nom = item.text().strip()
            if nuevo_nom:
                self.modelo.actualizar_nombre_entidad(self.tabla_db, id_ent, nuevo_nom)

    def borrar(self, id_ent):
        if QMessageBox.question(self, "Confirmar", "¿Eliminar registro?") == QMessageBox.Yes:
            exito = False
            if self.tabla_db == "secciones": 
                exito = self.modelo.eliminar_seccion(id_ent)
            elif self.tabla_db == "ubicaciones": 
                exito = self.modelo.eliminar_ubicacion(id_ent)
            elif self.tabla_db == "usuarios": 
                exito = self.modelo.eliminar_usuario(id_ent)
            
            if not exito:
                QMessageBox.critical(self, "Error", "No se puede borrar: El registro está siendo usado en el inventario.")
            self.cargar_datos()

# --- VISTA. Diálogo Univsersal ---
class DialogoEntidad(QDialog):
    def __init__(self, titulo, campos, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.inputs = {}
        layout = QVBoxLayout(self)
        form = QFormLayout()

        for nombre_campo in campos:
            line_edit = QLineEdit()
            form.addRow(f"{nombre_campo}:", line_edit)
            self.inputs[nombre_campo] = line_edit

        layout.addLayout(form)
        self.botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.botones.accepted.connect(self.accept)
        self.botones.rejected.connect(self.reject)
        layout.addWidget(self.botones)

    def obtener_datos(self):
        # Devuelve un diccionario con {campo: valor}
        return {nombre: widget.text().strip() for nombre, widget in self.inputs.items()}

# --- CONTROLADOR ---
class InventarioControlador:
    def __init__(self, modelo, vista):
        self.modelo = modelo
        self.vista = vista
        self.cargar_filtros()
        self.actualizar_tabla()
        self.conectar_eventos()

    def conectar_eventos(self):
        self.vista.btn_add_dispositivo.clicked.connect(self.añadir_fila_vacia)
        self.vista.btn_add_user.clicked.connect(self.añadir_usuario_rapido)
        self.vista.btn_gear_user.clicked.connect(self.abrir_gestion_usuarios)
        self.vista.btn_add_seccion.clicked.connect(self.añadir_seccion_rapida)
        self.vista.btn_gear_seccion.clicked.connect(self.abrir_gestion_secciones)
        self.vista.btn_add_lugar.clicked.connect(self.gestionar_lugar_nuevo)
        self.vista.btn_gear_lugar.clicked.connect(self.abrir_gestion_lugares)
        self.vista.txt_busqueda.textChanged.connect(self.actualizar_tabla)
        self.vista.cmb_seccion.currentIndexChanged.connect(self.actualizar_tabla)
        self.vista.btn_importar.clicked.connect(self.importar_datos)
        self.vista.btn_pdf.clicked.connect(self.generar_informe_pdf)
        
        # ¿menús contextuales o botones de gestión aquí?        
        self.vista.cmb_seccion.setToolTip("Doble clic para gestionar secciones")

    def cargar_filtros(self, id_a_mantener=None):
        # Guardamos qué había seleccionado si no nos pasan un ID
        if id_a_mantener is None:
            id_a_mantener = self.vista.cmb_seccion.currentData()

        self.vista.cmb_seccion.blockSignals(True)
        self.vista.cmb_seccion.clear()
        self.vista.cmb_seccion.addItem("Todas", 0)
        
        index_a_seleccionar = 0
        for i, (id_s, nom) in enumerate(self.modelo.obtener_secciones(), 1):
            self.vista.cmb_seccion.addItem(nom, id_s)
            if id_s == id_a_mantener:
                index_a_seleccionar = i
                
        self.vista.cmb_seccion.setCurrentIndex(index_a_seleccionar)
        self.vista.cmb_seccion.blockSignals(False)

    def actualizar_tabla(self):
        self.vista.tabla_inventario.blockSignals(True)
        self.vista.tabla_inventario.setRowCount(0)
        
        texto = self.vista.txt_busqueda.text().strip()
        id_seccion = self.vista.cmb_seccion.currentData()

        datos = self.modelo.obtener_inventario_completo(texto, id_seccion)

        for r_idx, r_data in enumerate(datos):
            self.vista.tabla_inventario.insertRow(r_idx)
            for c_idx in range(9):
                val = r_data[c_idx]
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setTextAlignment(Qt.AlignCenter)
                self.vista.tabla_inventario.setItem(r_idx, c_idx, item)

            self._insertar_botones_accion(r_idx, r_data)

        self.vista.tabla_inventario.blockSignals(False)
        # CORREGIDO: Llamada al contador corregida
        self.actualizar_contador_dispositivos()

    def actualizar_contador_dispositivos(self):
        total = self.vista.tabla_inventario.rowCount()
        self.vista.lbl_contador.setText(f"Dispositivos visualizados: {total}")

    def filtrar_datos(self):
        termino = remover_tildes(self.vista.txt_buscar.text())
        # Desactivamos el refresco visual para ganar velocidad punta
        self.vista.tabla_inventario.setUpdatesEnabled(False)
        
        try:
            for i in range(self.vista.tabla_inventario.rowCount()):
                match = False
                for j in range(self.vista.tabla_inventario.columnCount()):
                    item = self.vista.tabla_inventario.item(i, j)
                    if item and termino in remover_tildes(item.text()):
                        match = True
                        break
                self.vista.tabla_inventario.setRowHidden(i, not match)
        finally:
            # Reactivamos y actualizamos contador
            self.vista.tabla_inventario.setUpdatesEnabled(True)
            self.actualizar_contador()

    def _insertar_botones_accion(self, fila, datos_fila):
        panel = QWidget()
        ly = QHBoxLayout(panel)
        ly.setContentsMargins(2, 0, 2, 0)
        ly.setSpacing(4)

        btn_edit = QPushButton("✏️")
        btn_edit.setFixedSize(30, 25)
        btn_edit.setToolTip("Editar registro")
        # Usamos default arguments en lambda para capturar el valor actual de la iteración
        btn_edit.clicked.connect(lambda _, r=fila, d=datos_fila: self.activar_edicion_fila(r, d))

        btn_del = QPushButton("❌")
        btn_del.setFixedSize(30, 25)
        btn_del.setToolTip("Eliminar registro")
        btn_del.clicked.connect(lambda _, d_id=datos_fila[0]: self.eliminar_registro(d_id))

        ly.addWidget(btn_edit)
        ly.addWidget(btn_del)
        self.vista.tabla_inventario.setCellWidget(fila, 9, panel)

    def añadir_fila_vacia(self):
        s_id = self.vista.cmb_seccion.currentData()
        if s_id == 0:
            return QMessageBox.warning(self.vista, "Aviso", "Selecciona una sección específica antes de añadir.")

        row = self.vista.tabla_inventario.rowCount()
        self.vista.tabla_inventario.insertRow(row)
        self.vista.tabla_inventario.setItem(row, 0, QTableWidgetItem("NUEVA"))

        cb_lugar = QComboBox()
        cb_lugar.addItem("- Seleccionar Lugar -", None)
        for id_l, nom in self.modelo.obtener_ubicaciones_por_seccion(s_id):
            cb_lugar.addItem(nom, id_l)
        self.vista.tabla_inventario.setCellWidget(row, 1, cb_lugar)

        cb_user = QComboBox()
        cb_user.addItem("- Sin asignar -", None)
        
        # Cargamos usuarios y sus correos
        usuarios_data = self.modelo.obtener_usuarios()
        for id_u, nom, mail in usuarios_data:
            cb_user.addItem(nom, id_u)
            # Guardamos el correo en un rol de datos interno
            cb_user.setItemData(cb_user.count()-1, mail, Qt.UserRole + 1)

        # Función para actualizar el correo visualmente al elegir usuario
        def actualizar_mail_nuevo():
            mail = cb_user.currentData(Qt.UserRole + 1)
            item_m = QTableWidgetItem(str(mail) if mail else "")
            # Bloqueamos la edición manual en la tabla principal
            item_m.setFlags(Qt.ItemIsEnabled) 
            item_m.setTextAlignment(Qt.AlignCenter)
            self.vista.tabla_inventario.setItem(row, 3, item_m)

        cb_user.currentIndexChanged.connect(actualizar_mail_nuevo)
        self.vista.tabla_inventario.setCellWidget(row, 2, cb_user)

        cb_tipo = QComboBox()
        for id_t, nom in self.modelo.obtener_tipos_dispositivo():
            cb_tipo.addItem(nom, id_t)
        self.vista.tabla_inventario.setCellWidget(row, 4, cb_tipo)

        for col in [5, 6, 8]:
            self.vista.tabla_inventario.setItem(row, col, QTableWidgetItem(""))

        # Ponemos el DatePicker por defecto con la fecha de hoy
        date_nuevo = QDateEdit()
        date_nuevo.setCalendarPopup(True)
        date_nuevo.setDisplayFormat("yyyy-MM-dd")
        date_nuevo.setDate(QDate.currentDate())
        self.vista.tabla_inventario.setCellWidget(row, 7, date_nuevo)

        panel = QWidget()
        ly = QHBoxLayout(panel)
        ly.setContentsMargins(0, 0, 0, 0)
        btn_save = QPushButton("💾")
        btn_save.setFixedSize(30, 25)
        btn_del = QPushButton("🗑️")
        btn_del.setFixedSize(30, 25)

        ly.addWidget(btn_save)
        ly.addWidget(btn_del)

        btn_save.clicked.connect(lambda: self.guardar_fila_especifica(row))
        btn_del.clicked.connect(lambda: self.vista.tabla_inventario.removeRow(row))
        self.vista.tabla_inventario.setCellWidget(row, 9, panel)

    def añadir_usuario_rapido(self):
        dial = DialogoEntidad("Nueva Persona", ["Nombre", "Correo"], self.vista)
        if dial.exec():
            datos = dial.obtener_datos()
            if datos["Nombre"]:
                self.modelo.añadir_usuario(datos["Nombre"], datos["Correo"])
                self.actualizar_tabla()
            else:
                QMessageBox.warning(self.vista, "Error", "El nombre es obligatorio.")

    def añadir_seccion_rapida(self):
        dial = DialogoEntidad("Nueva Sección", ["Nombre"], self.vista)
        if dial.exec():
            nom = dial.obtener_datos()["Nombre"]
            if nom:
                self.modelo.añadir_seccion(nom)
                self.cargar_filtros()
            else:
                QMessageBox.warning(self.vista, "Error", "El nombre es obligatorio.")

    def gestionar_lugar_nuevo(self):
        s_id = self.vista.cmb_seccion.currentData()
        if s_id == 0:
            return QMessageBox.warning(self.vista, "Aviso", "Primero selecciona una Sección.")
        
        dial = DialogoEntidad(f"Nuevo Lugar en {self.vista.cmb_seccion.currentText()}", ["Nombre"], self.vista)
        if dial.exec():
            nom = dial.obtener_datos()["Nombre"]
            if nom:
                if self.modelo.añadir_ubicacion(nom, s_id):
                    self.actualizar_tabla()
                else:
                    QMessageBox.warning(self.vista, "Error", "El lugar ya existe en esta sección.")

    def guardar_fila_especifica(self, fila):
        try:
            id_ubicacion = self.vista.tabla_inventario.cellWidget(fila, 1).currentData()
            item_marca = self.vista.tabla_inventario.item(fila, 5)
            item_modelo = self.vista.tabla_inventario.item(fila, 6)
            
            marca = item_marca.text().strip() if item_marca else ""
            modelo = item_modelo.text().strip() if item_modelo else ""

            if not id_ubicacion:
                return QMessageBox.warning(self.vista, "Error", "Debes seleccionar un Lugar")
            if not marca or not modelo:
                return QMessageBox.warning(self.vista, "Error", "Marca y Modelo son obligatorios")

            datos = {
                "ubicacion_id": id_ubicacion,
                "usuario_id": self.vista.tabla_inventario.cellWidget(fila, 2).currentData(),
                "tipo_id": self.vista.tabla_inventario.cellWidget(fila, 4).currentData(),
                "marca": marca,
                "modelo": modelo,
                "observaciones": self.vista.tabla_inventario.item(fila, 8).text() if self.vista.tabla_inventario.item(fila, 8) else "",
            }
            
            if self.modelo.añadir_dispositivo_completo(datos):
                self.actualizar_tabla()
        except Exception as e:
            QMessageBox.critical(self.vista, "Error", f"No se pudo guardar: {e}")

    def eliminar_registro(self, d_id):
        if QMessageBox.question(self.vista, "Borrar", "¿Eliminar dispositivo permanentemente?") == QMessageBox.Yes:
            self.modelo.eliminar_registro(d_id)
            self.actualizar_tabla()  

    # Métodos para abrir las ventanas de gestión (para activarlos con botón derecho)
    def abrir_gestion_secciones(self):
        dial = VentanaGestion("Gestor de Secciones", "secciones", self.modelo, self.modelo.obtener_secciones, self.vista)
        dial.exec()
        self.cargar_filtros()

    def abrir_gestion_lugares(self):
        s_id = self.vista.cmb_seccion.currentData()
        if s_id == 0: 
            return QMessageBox.warning(self.vista, "Aviso", "Selecciona una sección específica primero para gestionar sus lugares.")
        
        # Abrimos la gestión filtrada por la sección que el usuario tiene seleccionada
        dial = VentanaGestion(
            f"Gestor de Lugares - {self.vista.cmb_seccion.currentText()}", 
            "ubicaciones", 
            self.modelo, 
            lambda: self.modelo.obtener_ubicaciones_por_seccion(s_id), 
            self.vista
        )
        dial.exec()
        self.actualizar_tabla()

    def abrir_gestion_usuarios(self):
        dial = VentanaGestion("Gestor de Usuarios", "usuarios", self.modelo, self.modelo.obtener_usuarios, self.vista)
        dial.exec()
        self.actualizar_tabla() # Esto ya llama a la función correcta con todos los bloqueos

    def activar_edicion_fila(self, fila, datos_originales):
        """Convierte una fila estática en campos editables"""
        d_id = datos_originales[0]
        s_id = self.vista.cmb_seccion.currentData()
        
        # Si estamos en "Todas las secciones", necesitamos saber a qué sección pertenece el registro
        # Para simplificar, asumimos que el usuario edita dentro de una sección filtrada.
        if s_id == 0:
            return QMessageBox.warning(self.vista, "Aviso", "Por favor, selecciona la sección específica arriba para editar sus registros.")

        # 1. Combo Lugar
        cb_lugar = QComboBox()
        ubicaciones = self.modelo.obtener_todas_las_ubicaciones() # <--- Nuevo método necesario
        for u_id, nombre_ub, nombre_sec in ubicaciones:
            # Mostramos "Ubicación (Sección)" para que el usuario sepa a dónde lo mueve
            cb_lugar.addItem(f"{nombre_ub} ({nombre_sec})", u_id)
        
        # Seleccionamos la que ya tenía
        indice = cb_lugar.findText(datos_originales[1], Qt.MatchContains)
        cb_lugar.setCurrentIndex(indice)
        self.vista.tabla_inventario.setCellWidget(fila, 1, cb_lugar)

        # 2. Combo Usuario
        cb_user = QComboBox()
        cb_user.addItem("- Sin asignar -", None)

        # Obtenemos los usuarios para tener los correos disponibles
        usuarios_data = self.modelo.obtener_usuarios() 
        for id_u, nom, mail in usuarios_data:
            cb_user.addItem(nom, id_u)
            # Guardamos el mail en un rol de datos interno para recuperarlo luego
            cb_user.setItemData(cb_user.count()-1, mail, Qt.UserRole + 1)

        def actualizar_mail_visual():
            mail = cb_user.currentData(Qt.UserRole + 1)
            item_m = QTableWidgetItem(str(mail) if mail else "")
            item_m.setFlags(Qt.ItemIsEnabled) # Solo lectura
            item_m.setTextAlignment(Qt.AlignCenter)
            self.vista.tabla_inventario.setItem(fila, 3, item_m)

        cb_user.currentIndexChanged.connect(actualizar_mail_visual)
        # ------------------------------------------------
        
        index_u = cb_user.findText(datos_originales[2] if datos_originales[2] else "- Sin asignar -")
        cb_user.setCurrentIndex(index_u)
        self.vista.tabla_inventario.setCellWidget(fila, 2, cb_user)

        # 3. Combo Tipo
        cb_tipo = QComboBox()
        for id_t, nom in self.modelo.obtener_tipos_dispositivo():
            cb_tipo.addItem(nom, id_t)
        index_t = cb_tipo.findText(datos_originales[4])
        cb_tipo.setCurrentIndex(index_t)
        self.vista.tabla_inventario.setCellWidget(fila, 4, cb_tipo)

        # 4. Campos de texto (Marca, Modelo, Observaciones)
        for col in [5, 6, 8]:
            texto = datos_originales[col]
            item = QTableWidgetItem(str(texto) if texto else "")
            self.vista.tabla_inventario.setItem(fila, col, item)

        item_correo = QTableWidgetItem(str(datos_originales[3]))
        item_correo.setFlags(Qt.ItemIsEnabled) # Solo habilitado para lectura
        self.vista.tabla_inventario.setItem(fila, 3, item_correo)

        # --- Usar DatePicker en lugar de QLineEdit ---
        fecha_db = datos_originales[7] if datos_originales[7] else "2026-01-01"
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd") # Formato visual que prefieres
        # Convertimos el texto de la DB a objeto QDate para el widget
        date_edit.setDate(QDate.fromString(fecha_db, "yyyy-MM-dd"))
        self.vista.tabla_inventario.setCellWidget(fila, 7, date_edit)

        # 5. Cambiar botones de acción a Guardar/Cancelar
        panel = QWidget()
        ly = QHBoxLayout(panel)
        ly.setContentsMargins(0, 0, 0, 0)
        btn_save = QPushButton("💾")
        btn_save.setFixedSize(30, 25)
        btn_cancel = QPushButton("🔙")
        btn_cancel.setFixedSize(30, 25)

        ly.addWidget(btn_save)
        ly.addWidget(btn_cancel)

        btn_save.clicked.connect(lambda: self.guardar_cambios_edicion(fila, d_id))
        btn_cancel.clicked.connect(self.actualizar_tabla)
        self.vista.tabla_inventario.setCellWidget(fila, 9, panel)

    def guardar_cambios_edicion(self, fila, d_id):
        try:
            # CORREGIDO: Obtener texto de items, no de widgets (que no existen en esas columnas)
            tipo_id = self.vista.tabla_inventario.cellWidget(fila, 4).currentData()
            marca = self.vista.tabla_inventario.item(fila, 5).text()
            modelo = self.vista.tabla_inventario.item(fila, 6).text()
            observaciones = self.vista.tabla_inventario.item(fila, 8).text()
            
            widget_fecha = self.vista.tabla_inventario.cellWidget(fila, 7)
            fecha_para_db = widget_fecha.date().toString("yyyy-MM-dd") 

            cb_lugar = self.vista.tabla_inventario.cellWidget(fila, 1)
            cb_usuario = self.vista.tabla_inventario.cellWidget(fila, 2)

            datos = {
                'tipo_id': tipo_id,
                'marca': marca,
                'modelo': modelo,
                'ubicacion_id': cb_lugar.currentData(),
                'usuario_id': cb_usuario.currentData(),
                'fecha': fecha_para_db,
                'observaciones': observaciones
            }

            if self.modelo.actualizar_dispositivo_completo(d_id, datos):
                self.actualizar_tabla()
        except Exception as e:
            QMessageBox.critical(self.vista, "Error", f"Error al guardar: {e}")

    def importar_datos(self):
        ruta, _ = QFileDialog.getOpenFileName(self.vista, "Seleccionar CSV", "", "CSV Files (*.csv)")
        if not ruta: return

        import csv
        try:
            with open(ruta, newline='', encoding='utf-8-sig') as f:
                total_filas = sum(1 for _ in f) - 1

            self.vista.progreso.setMaximum(total_filas)
            self.vista.progreso.setValue(0)
            self.vista.progreso.show()

            # ABRIMOS UNA SOLA CONEXIÓN PARA TODO
            with self.modelo.conectar() as conn:
                # Optimizaciones de velocidad para SQLite
                conn.execute("PRAGMA synchronous = OFF")
                conn.execute("PRAGMA journal_mode = MEMORY")
                
                with open(ruta, newline='', encoding='utf-8-sig') as csvfile:
                    lector = csv.DictReader(csvfile, delimiter=';')
                    exitos = 0
                    
                    for n_fila, fila in enumerate(lector, 1):
                        if not fila.get('Tipo dispositivo') and not fila.get('Modelo'):
                            continue
                        
                        # PASAMOS LA CONEXIÓN 'conn' PARA QUE NO ABRA NUEVAS
                        s_id = self.modelo.obtener_o_crear_seccion(fila.get('Sección'), conn=conn)
                        ub_id = self.modelo.obtener_o_crear_ubicacion(fila.get('Ubicación'), s_id, conn=conn)
                        t_id = self.modelo.obtener_o_crear_tipo_dispositivo(fila.get('Tipo dispositivo'), conn=conn)
                        u_id = self.modelo.obtener_o_crear_usuario(fila.get('Apellidos y nombre'), fila.get('Correo'), conn=conn)

                        # Definir la fecha (si no viene en el CSV, usar hoy)
                        fecha_registro = (fila.get('Fecha') or QDate.currentDate().toString("yyyy-MM-dd")).strip()

                        cursor = conn.cursor()
                        # 1. Insertamos en 'dispositivos' incluyendo la fecha_registro
                        cursor.execute(
                            "INSERT INTO dispositivos (tipo_dispositivo_id, marca, modelo, observaciones, fecha_registro) VALUES (?,?,?,?,?)",
                            (t_id, (fila.get('Marca') or 'S/M').strip(), (fila.get('Modelo') or 'S/M').strip(), 
                             (fila.get('Observaciones') or '').strip(), fecha_registro)
                        )
                        d_id = cursor.lastrowid
                        
                        # 2. Insertamos en 'asignaciones' SIN la columna 'fecha' (Aquí estaba el error)
                        cursor.execute(
                            "INSERT INTO asignaciones (dispositivo_id, ubicacion_id, usuario_id) VALUES (?,?,?)",
                            (d_id, ub_id, u_id)
                        )
                        exitos += 1

                        if n_fila % 10 == 0:
                            self.vista.progreso.setValue(n_fila)
                            QApplication.processEvents()

                conn.commit() # <--- GUARDADO FINAL
            
            # REFRESCAR TODO
            self.actualizar_tabla()
            self.cargar_filtros() # <--- RELLENA LOS COMBOS
            
            self.vista.progreso.hide()
            QMessageBox.information(self.vista, "Éxito", f"Importación terminada: {exitos} registros cargados.")
            
        except Exception as e:
            if 'self.vista.progreso' in locals() or hasattr(self.vista, 'progreso'):
                self.vista.progreso.hide()
            QMessageBox.critical(self.vista, "Error", f"Fallo en importación: {str(e)}")

    def generar_informe_pdf(self):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.units import cm

        doc = None
        try:
            ruta, _ = QFileDialog.getSaveFileName(self.vista, "Guardar Informe", "", "PDF Files (*.pdf)")
            if not ruta: return

            datos = self.modelo.obtener_datos_informe_agrupado()
            if not datos:
                QMessageBox.warning(self.vista, "Aviso", "No hay datos para exportar.")
                return

            doc = SimpleDocTemplate(
                ruta, 
                pagesize=landscape(A4),
                rightMargin=1.5*cm, leftMargin=1.5*cm, 
                topMargin=1.5*cm, bottomMargin=1.5*cm
            )
            
            elementos = []
            estilos = getSampleStyleSheet()
            
            # --- ESTILOS PERSONALIZADOS ---
            estilo_titulo = ParagraphStyle('DocTitle', parent=estilos['Title'], fontSize=22, alignment=0, textColor=colors.HexColor("#2c3e50"))
            estilo_seccion = ParagraphStyle('Sec', parent=estilos['Heading1'], fontSize=16, textColor=colors.HexColor("#27ae60"), spaceBefore=15, fontName='Helvetica-Bold')
            estilo_lugar = ParagraphStyle('Lug', parent=estilos['Heading2'], fontSize=12, textColor=colors.HexColor("#2980b9"), spaceBefore=10)
            estilo_cabecera = ParagraphStyle('Cab', parent=estilos['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.whitesmoke, alignment=1)
            estilo_celda = ParagraphStyle('Cel', parent=estilos['Normal'], fontSize=9, alignment=1)

            def añadir_pie_pagina(canvas, document):
                canvas.saveState()
                fecha_hoy = QDate.currentDate().toString('dd/MM/yyyy')
                texto_pie = f"Página {document.page} - Generado el {fecha_hoy} - Inventario Tecnológico"
                canvas.setFont('Helvetica', 9)
                canvas.drawCentredString(landscape(A4)[0] / 2, 1 * cm, texto_pie)
                canvas.restoreState()

            # --- ENCABEZADO (TÍTULO + LOGO) ---
            titulo_parrafo = Paragraph("INVENTARIO DE DISPOSITIVOS TECNOLÓGICOS", estilo_titulo)
            try:
                path_logo = resource_path("logo_servicio.png")
                ancho_logo = 4.5 * cm
                alto_logo = (484 / 1240) * ancho_logo
                logo_img = Image(path_logo, width=ancho_logo, height=alto_logo)
                
                header_table = Table([[titulo_parrafo, logo_img]], colWidths=[20*cm, 6.7*cm])
                header_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ]))
                elementos.append(header_table)
            except:
                elementos.append(titulo_parrafo)

            elementos.append(Spacer(1, 10))

            # --- LÓGICA DE AGRUPACIÓN ---
            seccion_actual = None
            lugar_actual = None
            tabla_data = []

            def volcar_tabla_al_pdf(data_list):
                if len(data_list) > 1: # Solo si hay algo más que la cabecera
                    # Anchos: Tipo(3), Marca(3), Modelo(4), Usuario(7.5), Fecha(2.5), Obs(7.2) = 27.2cm total aprox
                    anchos = [3*cm, 3*cm, 4*cm, 7.5*cm, 2.7*cm, 6.5*cm]
                    t = Table(data_list, repeatRows=1, colWidths=anchos)
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#34495e")),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ]))
                    elementos.append(t)
                    elementos.append(Spacer(1, 15))

            for fila in datos:
                d = dict(fila) # Convertimos sqlite3.Row a diccionario
                
                # 1. ¿Ha cambiado la Sección?
                if d['seccion'] != seccion_actual:
                    if tabla_data:
                        volcar_tabla_al_pdf(tabla_data)
                        tabla_data = []
                    
                    seccion_actual = d['seccion']
                    elementos.append(Paragraph(f"🏢 SECCIÓN: {str(seccion_actual).upper()}", estilo_seccion))
                    lugar_actual = None # Forzamos que se escriba el lugar al cambiar de sección

                # 2. ¿Ha cambiado el Lugar?
                if d['lugar'] != lugar_actual:
                    if tabla_data:
                        volcar_tabla_al_pdf(tabla_data)
                    
                    lugar_actual = d['lugar']
                    elementos.append(Paragraph(f"📍 Ubicación: {lugar_actual}", estilo_lugar))
                    
                    # Reiniciamos la tabla con sus encabezados
                    tabla_data = [[
                        Paragraph("Tipo", estilo_cabecera), Paragraph("Marca", estilo_cabecera),
                        Paragraph("Modelo", estilo_cabecera), Paragraph("Usuario (Email)", estilo_cabecera),
                        Paragraph("Fecha", estilo_cabecera), Paragraph("Observaciones", estilo_cabecera)
                    ]]

                # 3. Añadir los datos del dispositivo
                tabla_data.append([
                    Paragraph(str(d['tipo'] or ""), estilo_celda),
                    Paragraph(str(d['marca'] or ""), estilo_celda),
                    Paragraph(str(d['modelo'] or ""), estilo_celda),
                    Paragraph(str(d['usuario'] or "---"), estilo_celda),
                    Paragraph(str(d['fecha'] or ""), estilo_celda),
                    Paragraph(str(d['observaciones'] or ""), estilo_celda)
                ])

            # Volcamos la última tabla pendiente
            volcar_tabla_al_pdf(tabla_data)

            # --- GENERACIÓN FINAL ---
            doc.build(elementos, onFirstPage=añadir_pie_pagina, onLaterPages=añadir_pie_pagina)
            QMessageBox.information(self.vista, "Éxito", "Informe PDF generado correctamente y agrupado.")

        except Exception as e:
            QMessageBox.critical(self.vista, "Error al generar PDF", f"Detalle técnico: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    modelo = InventarioModel()
    vista = InventarioVista()
    ctrl = InventarioControlador(modelo, vista)
    vista.show()
    sys.exit(app.exec())