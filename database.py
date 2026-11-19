"""
Módulo de Gestión de Base de Datos para el Sistema de Asistencia Facial SENA.
Maneja la conexión a SQLite, creación de tablas, índices, consultas de validación
de duplicados diarios e inserción de nuevos registros.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Set, Tuple, Dict, Any, Generator

DEFAULT_DB_PATH = "asistencia_sena.db"


@contextmanager
def db_session(db_path: str = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager que abre la conexión, gestiona transacciones (commit/rollback)
    y garantiza el cierre de la conexión (evita bloqueos de archivo en Windows).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Inicializa las tablas e índices si no existen.
    Carga aprendices semilla si la tabla está vacía para pruebas inmediatas.
    """
    with db_session(db_path) as conn:
        cursor = conn.cursor()

        # 1. Tabla de Aprendices
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aprendices (
                id TEXT PRIMARY KEY,
                nombre_completo TEXT NOT NULL,
                ficha TEXT,
                activo INTEGER DEFAULT 1,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Tabla de Asistencias (con restricción de unicidad diaria)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asistencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aprendiz_id TEXT NOT NULL,
                nombre TEXT NOT NULL,
                fecha DATE NOT NULL,
                hora TIME NOT NULL,
                confianza REAL NOT NULL,
                metodo TEXT DEFAULT 'facial_yolo',
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (aprendiz_id) REFERENCES aprendices(id) ON DELETE CASCADE,
                UNIQUE (aprendiz_id, fecha)
            );
        """)

        # 3. Índices de rendimiento
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_asistencias_aprendiz_fecha 
            ON asistencias(aprendiz_id, fecha);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_asistencias_fecha 
            ON asistencias(fecha);
        """)

        # 4. Datos semilla para pruebas
        cursor.execute("SELECT COUNT(*) AS total FROM aprendices")
        if cursor.fetchone()["total"] == 0:
            semilla_aprendices = [
                ("10102030", "Carlos Perez", "ADSO-2671234"),
                ("10203040", "Maria Rodriguez", "ADSO-2671234"),
                ("10304050", "Juan David Gomez", "ADSO-2671234")
            ]
            cursor.executemany(
                "INSERT INTO aprendices (id, nombre_completo, ficha) VALUES (?, ?, ?)",
                semilla_aprendices
            )


def ya_asistio_hoy(aprendiz_id: str, fecha_hoy: Optional[str] = None, db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Verifica si un aprendiz ya tiene un registro de asistencia en la fecha indicada.
    """
    if fecha_hoy is None:
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM asistencias WHERE aprendiz_id = ? AND fecha = ? LIMIT 1;",
            (aprendiz_id, fecha_hoy)
        )
        return cursor.fetchone() is not None


def registrar_asistencia(
    aprendiz_id: str,
    nombre: str,
    confianza: float,
    fecha_str: Optional[str] = None,
    hora_str: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH
) -> Tuple[bool, str]:
    """
    Registra la asistencia de un aprendiz si aún no tiene registro en la fecha actual.

    Retorna:
        Tuple[bool, str]: (Éxito, Mensaje descriptivo)
    """
    ahora = datetime.now()
    fecha = fecha_str or ahora.strftime("%Y-%m-%d")
    hora = hora_str or ahora.strftime("%H:%M:%S")

    # 1. Validación previa en código
    if ya_asistio_hoy(aprendiz_id, fecha, db_path):
        return False, f"El aprendiz {nombre} ({aprendiz_id}) ya registró asistencia hoy."

    # 2. Inserción con protección de integridad (UNIQUE constraint)
    with db_session(db_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO asistencias (aprendiz_id, nombre, fecha, hora, confianza)
                VALUES (?, ?, ?, ?, ?);
            """, (aprendiz_id, nombre, fecha, hora, round(confianza, 4)))
            return True, f"Asistencia registrada: {nombre} - {hora}"
        except sqlite3.IntegrityError:
            # Captura posibles condiciones de carrera (Race Conditions)
            return False, f"El aprendiz {nombre} ya fue registrado simultáneamente."


def obtener_asistidos_del_dia(fecha_hoy: Optional[str] = None, db_path: str = DEFAULT_DB_PATH) -> Set[str]:
    """
    Retorna un conjunto (set) de los IDs de aprendices que ya asistieron hoy.
    Permite comprobaciones O(1) en memoria durante la captura de video a 30 FPS.
    """
    if fecha_hoy is None:
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT aprendiz_id FROM asistencias WHERE fecha = ?;", (fecha_hoy,))
        return {row["aprendiz_id"] for row in cursor.fetchall()}


def obtener_o_crear_aprendiz(aprendiz_id: str, nombre_defecto: str, db_path: str = DEFAULT_DB_PATH) -> str:
    """
    Retorna el nombre registrado del aprendiz en la base de datos.
    Si aún no existe en el catálogo, lo inserta automáticamente con el nombre detectado.
    """
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nombre_completo FROM aprendices WHERE id = ?;", (aprendiz_id,))
        row = cursor.fetchone()
        if row:
            return row["nombre_completo"]
        else:
            cursor.execute(
                "INSERT OR IGNORE INTO aprendices (id, nombre_completo, ficha) VALUES (?, ?, 'ADSO');",
                (aprendiz_id, nombre_defecto)
            )
            return nombre_defecto


def obtener_asistencias_fecha(fecha: Optional[str] = None, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Obtiene el listado completo de asistencias para auditoría o reporte."""
    if fecha is None:
        fecha = datetime.now().strftime("%Y-%m-%d")

    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.aprendiz_id, a.nombre, ap.ficha, a.fecha, a.hora, a.confianza, a.metodo
            FROM asistencias a
            LEFT JOIN aprendices ap ON a.aprendiz_id = ap.id
            WHERE a.fecha = ?
            ORDER BY a.hora ASC;
        """, (fecha,))
        return [dict(row) for row in cursor.fetchall()]

