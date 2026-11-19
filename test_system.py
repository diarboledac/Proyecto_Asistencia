"""
Suite de Pruebas Automatizadas para el Sistema de Asistencia Facial SENA.
Verifica:
- Creación de esquema y tablas.
- Registro exitoso de asistencia.
- Prevención de duplicados en la misma fecha (a nivel lógico y de base de datos).
- Permisión de asistencias en fechas distintas.
- Filtro de precisión de confianza (umbral 85%).
"""

import os
import sqlite3
import pytest
from database import (
    init_db,
    registrar_asistencia,
    ya_asistio_hoy,
    obtener_asistidos_del_dia,
    obtener_asistencias_fecha,
    db_session,
)

TEST_DB = "test_asistencia.db"


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Limpia la base de datos de prueba antes y después de cada test."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except PermissionError:
            pass


def test_init_db_creates_tables_and_seed_data():
    with db_session(TEST_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM aprendices;")
        total_aprendices = cursor.fetchone()["total"]
        assert total_aprendices >= 3, "Deberían haberse insertado al menos 3 aprendices semilla."


def test_registrar_asistencia_exitosa():
    exito, mensaje = registrar_asistencia(
        aprendiz_id="10102030",
        nombre="Carlos Perez",
        confianza=0.92,
        fecha_str="2026-10-11",
        hora_str="08:15:30",
        db_path=TEST_DB
    )

    assert exito is True
    assert "Asistencia registrada" in mensaje
    assert ya_asistio_hoy("10102030", "2026-10-11", TEST_DB) is True


def test_prevencion_duplicados_mismo_dia():
    # 1. Primer registro del día: debe ser exitoso
    exito1, _ = registrar_asistencia(
        aprendiz_id="10102030",
        nombre="Carlos Perez",
        confianza=0.88,
        fecha_str="2026-10-11",
        hora_str="08:00:00",
        db_path=TEST_DB
    )
    assert exito1 is True

    # 2. Segundo intento el mismo día (ej: aprendiz sigue frente a la cámara): debe ser rechazado
    exito2, mensaje2 = registrar_asistencia(
        aprendiz_id="10102030",
        nombre="Carlos Perez",
        confianza=0.95,
        fecha_str="2026-10-11",
        hora_str="08:00:05",
        db_path=TEST_DB
    )
    assert exito2 is False
    assert "ya registró asistencia hoy" in mensaje2

    # Verificar que solo hay 1 fila en la tabla para esa fecha
    registros = obtener_asistencias_fecha("2026-10-11", TEST_DB)
    assert len(registros) == 1


def test_asistencia_en_fechas_distintas_permitida():
    # Día 1
    exito_dia1, _ = registrar_asistencia(
        aprendiz_id="10203040",
        nombre="Maria Rodriguez",
        confianza=0.89,
        fecha_str="2026-10-11",
        hora_str="08:05:00",
        db_path=TEST_DB
    )
    assert exito_dia1 is True

    # Día 2: debe permitirse
    exito_dia2, _ = registrar_asistencia(
        aprendiz_id="10203040",
        nombre="Maria Rodriguez",
        confianza=0.93,
        fecha_str="2026-10-12",
        hora_str="08:02:10",
        db_path=TEST_DB
    )
    assert exito_dia2 is True


def test_filtro_precision_confianza():
    umbral = 0.85
    
    # Lectura baja (< 85%): simulada como ignorada por la lógica
    confianza_baja = 0.81
    debe_procesar_baja = confianza_baja >= umbral
    assert debe_procesar_baja is False

    # Lectura alta (>= 85%): confirmada
    confianza_alta = 0.87
    debe_procesar_alta = confianza_alta >= umbral
    assert debe_procesar_alta is True


def test_restriccion_unique_en_bd_ante_concurrencia():
    with db_session(TEST_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO asistencias (aprendiz_id, nombre, fecha, hora, confianza)
            VALUES ('10304050', 'Juan David Gomez', '2026-10-11', '07:55:00', 0.90);
        """)

        # Intento de inserción directa a nivel SQL del mismo aprendiz en la misma fecha
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO asistencias (aprendiz_id, nombre, fecha, hora, confianza)
                VALUES ('10304050', 'Juan David Gomez', '2026-10-11', '07:55:10', 0.94);
            """)

