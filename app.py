"""
Sistema Web y de Hardware para Control de Asistencia SENA.
Arquitectura: Flask + SQLite3 + Soporte Escáner USB + Cámara Móvil en Vivo y por Foto (OpenCV).
"""

import os
import sys
import json
import sqlite3
import datetime
import cv2
import numpy as np
from typing import Optional, Dict, Any, Tuple
from flask import Flask, render_template, request, jsonify
from pyzbar import pyzbar

# ==============================================================================
# CONFIGURACIÓN Y CONSTANTES
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "registro_aprendices.db")
CERT_FILE = os.path.join(BASE_DIR, "cert.pem")
KEY_FILE = os.path.join(BASE_DIR, "key.pem")

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))


# ==============================================================================
# GESTOR DE BASE DE DATOS LOCAL (SQLite3)
# ==============================================================================
class DatabaseManager:
    """Administra la conexión y persistencia estructurada en SQLite."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._inicializar_tabla()

    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _inicializar_tabla(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS asistencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT NOT NULL,
            nombre TEXT NOT NULL,
            ficha TEXT,
            programa TEXT,
            datos_qr TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL
        );
        """
        with self._conectar() as conn:
            conn.execute(query)

    def registrar_asistencia(self, aprendiz: Dict[str, str], raw_qr: str, fecha: str, hora: str) -> Tuple[str, bool]:
        """
        Lógica Anti-Duplicados:
        Verifica si el documento ya tiene registro en la fecha actual.
        """
        documento = aprendiz["documento"]

        with self._conectar() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, hora FROM asistencia WHERE documento = ? AND fecha = ?",
                (documento, fecha)
            )
            existe = cursor.fetchone()

            if existe:
                return "duplicado", False

            cursor.execute(
                """
                INSERT INTO asistencia (documento, nombre, ficha, programa, datos_qr, fecha, hora)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    documento,
                    aprendiz["nombre"],
                    aprendiz.get("ficha", ""),
                    aprendiz.get("programa", ""),
                    raw_qr,
                    fecha,
                    hora
                )
            )
            return "exitoso", True

    def obtener_asistencias_hoy(self, fecha: str) -> list:
        with self._conectar() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, documento, nombre, ficha, programa, hora 
                FROM asistencia 
                WHERE fecha = ? 
                ORDER BY id DESC
                """,
                (fecha,)
            )
            filas = cursor.fetchall()
            return [
                {
                    "id": f[0],
                    "documento": f[1],
                    "nombre": f[2],
                    "ficha": f[3],
                    "programa": f[4],
                    "hora": f[5]
                }
                for f in filas
            ]


db = DatabaseManager()


# ==============================================================================
# PARSER ESTRICTO DE CARNET SENA (JSON)
# ==============================================================================
def parsear_carnet_sena(payload_str: str) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """Intenta parsear de forma estricta el JSON del carnet SENA."""
    if not payload_str or not isinstance(payload_str, str):
        return None, "El código escaneado está vacío o no es texto."

    payload_limpio = payload_str.strip()

    try:
        data = json.loads(payload_limpio)
    except json.JSONDecodeError:
        return None, "El código QR no contiene un formato JSON válido (QR ajeno al SENA)."

    if not isinstance(data, dict):
        return None, "Estructura JSON no reconocida (se esperaba un carnet institucional)."

    nombre = str(data.get("nom", "")).strip()
    documento = str(data.get("doc", "")).strip()
    ficha = str(data.get("ficha", "")).strip()
    programa = str(data.get("prog", "")).strip()
    cargo = str(data.get("cargo", "Aprendiz")).strip()
    rh = str(data.get("rh", "")).strip()

    if not documento or not nombre:
        return None, "El código QR no contiene los campos obligatorios del carnet SENA (nom, doc)."

    datos_aprendiz = {
        "nombre": nombre,
        "documento": documento,
        "ficha": ficha,
        "programa": programa,
        "cargo": cargo,
        "rh": rh
    }

    return datos_aprendiz, None


# ==============================================================================
# RUTAS WEB Y ENDPOINTS REST
# ==============================================================================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/registrar", methods=["POST"])
def registrar():
    """Recibe la cadena del QR escaneado (por la cámara o por lector USB)."""
    req_data = request.get_json(silent=True)
    if not req_data:
        return jsonify({"status": "error", "mensaje": "Petición inválida (se esperaba JSON)."}), 400

    qr_data = req_data.get("qr_data")
    if not qr_data and "doc" in req_data and "nom" in req_data:
        qr_data = json.dumps(req_data)

    if not qr_data:
        return jsonify({"status": "error", "mensaje": "Campo 'qr_data' requerido."}), 400

    aprendiz, error_msg = parsear_carnet_sena(qr_data)
    if error_msg:
        return jsonify({"status": "error", "mensaje": error_msg}), 400

    ahora = datetime.datetime.now()
    fecha_actual = ahora.strftime("%Y-%m-%d")
    hora_actual = ahora.strftime("%H:%M:%S")

    estado, fue_insertado = db.registrar_asistencia(
        aprendiz=aprendiz,
        raw_qr=qr_data,
        fecha=fecha_actual,
        hora=hora_actual
    )

    if fue_insertado:
        print(f"\n[REGISTRO EXITOSO] [{hora_actual}] {aprendiz['nombre']} | {aprendiz['documento']} | Ficha: {aprendiz['ficha']}")
        return jsonify({
            "status": "exitoso",
            "mensaje": "Ingreso registrado correctamente.",
            "aprendiz": aprendiz,
            "hora": hora_actual,
            "fecha": fecha_actual
        }), 200
    else:
        print(f"[DUPLICADO OMITIDO] [{hora_actual}] {aprendiz['nombre']} ya cuenta con asistencia hoy.")
        return jsonify({
            "status": "duplicado",
            "mensaje": "Ya registrado hoy.",
            "aprendiz": aprendiz,
            "hora": hora_actual,
            "fecha": fecha_actual
        }), 200


@app.route("/registrar_foto", methods=["POST"])
def registrar_foto():
    """
    Decodifica una imagen/foto del carnet enviada por el celular usando OpenCV y pyzbar.
    Respaldo de alta precisión para cámaras que no decodificaron en el frontend.
    """
    if "foto" not in request.files:
        return jsonify({"status": "error", "mensaje": "No se recibió ninguna imagen."}), 400

    archivo = request.files["foto"]
    file_bytes = np.frombuffer(archivo.read(), np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        return jsonify({"status": "error", "mensaje": "La imagen enviada está dañada o no es válida."}), 400

    # Redimensionar fotos muy grandes para acelerar detección y ahorrar memoria
    h, w = img.shape[:2]
    max_dim = 1600
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))

    # 1. Intentar con pyzbar en escala de grises y color
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    codigos = pyzbar.decode(gray) or pyzbar.decode(img)
    qr_texto = None

    for bar in codigos:
        try:
            qr_texto = bar.data.decode("utf-8").strip()
            if qr_texto:
                break
        except Exception:
            pass

    # 2. Respaldo secundario con OpenCV QRCodeDetector
    if not qr_texto:
        detector = cv2.QRCodeDetector()
        datos_cv, _, _ = detector.detectAndDecode(gray)
        if datos_cv:
            qr_texto = datos_cv.strip()

    if not qr_texto:
        return jsonify({
            "status": "error",
            "mensaje": "No se detectó el código QR en la foto. Acércalo más y evita sombras o reflejos."
        }), 400

    aprendiz, error_msg = parsear_carnet_sena(qr_texto)
    if error_msg:
        return jsonify({"status": "error", "mensaje": error_msg}), 400

    ahora = datetime.datetime.now()
    fecha_actual = ahora.strftime("%Y-%m-%d")
    hora_actual = ahora.strftime("%H:%M:%S")

    estado, fue_insertado = db.registrar_asistencia(
        aprendiz=aprendiz,
        raw_qr=qr_texto,
        fecha=fecha_actual,
        hora=hora_actual
    )

    if fue_insertado:
        print(f"\n[FOTO PROCESADA CON ÉXITO] [{hora_actual}] {aprendiz['nombre']} | Doc: {aprendiz['documento']}")
    else:
        print(f"[FOTO DUPLICADO] [{hora_actual}] {aprendiz['nombre']} ya registrado hoy.")

    return jsonify({
        "status": "exitoso" if fue_insertado else "duplicado",
        "mensaje": "Ingreso registrado correctamente." if fue_insertado else "Ya registrado hoy.",
        "aprendiz": aprendiz,
        "hora": hora_actual,
        "fecha": fecha_actual
    }), 200


@app.route("/api/asistencias/hoy", methods=["GET"])
def asistencias_hoy():
    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d")
    registros = db.obtener_asistencias_hoy(fecha_actual)
    return jsonify({
        "fecha": fecha_actual,
        "total": len(registros),
        "registros": registros
    })


# ==============================================================================
# INICIO DEL SERVIDOR (HTTP / HTTPS)
# ==============================================================================
if __name__ == "__main__":
    PUERTO = 5000
    IP_HOST = "192.168.20.21"

    usar_https = "--https" in sys.argv

    print("\n" + "=" * 75)
    print("        SISTEMA DE ASISTENCIA SENA - SERVIDOR WEB ACTIVO")
    print("=" * 75)

    if usar_https and os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print(f" [MODO HTTPS ACTIVO]")
        print(f" -> En esta Computadora : https://localhost:{PUERTO}")
        print(f" -> En tu Teléfono Móvil : https://{IP_HOST}:{PUERTO}")
        print(" NOTA: Acepta la advertencia de certificado en tu celular para ingresar.")
        print("=" * 75 + "\n")
        app.run(host="0.0.0.0", port=PUERTO, ssl_context=(CERT_FILE, KEY_FILE), debug=False)
    else:
        print(f" [MODO HTTP ESTÁNDAR]")
        print(f" -> En esta Computadora : http://localhost:{PUERTO}")
        print(f" -> En tu Teléfono Móvil : http://{IP_HOST}:{PUERTO}")
        print("=" * 75)
        print(" TIP: Si deseas iniciar con HTTPS para la cámara en vivo, ejecuta:")
        print("      python app.py --https")
        print("=" * 75 + "\n")
        app.run(host="0.0.0.0", port=PUERTO, debug=False)
