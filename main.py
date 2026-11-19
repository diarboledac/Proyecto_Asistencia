"""
Sistema de Asistencia Facial por Reconocimiento - SENA
Script Principal con Inferencia Real de YOLO (Ultralytics) + OpenCV + SQLite

Ubicación del modelo:
    Coloca tu archivo 'best.pt' en:
    - d:\\Repositorios\\Proyecto_Asistencia\\weights\\best.pt
    o directamente en la raíz del proyecto:
    - d:\\Repositorios\\Proyecto_Asistencia\\best.pt
"""

import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import cv2
import numpy as np

from database import (
    init_db,
    registrar_asistencia,
    obtener_asistidos_del_dia,
    ya_asistio_hoy,
    obtener_o_crear_aprendiz
)

# ==========================================
# CONFIGURACIÓN DEL SISTEMA
# ==========================================
CAMARA_INDEX = 0             # 0: Cámara web integrada de la laptop
CONFIDENCE_THRESHOLD = 0.8  # Filtro mínimo del 80% para confirmar identidad
BANNER_DURATION = 4.0        # Segundos que dura el mensaje de confirmación en pantalla

# Rutas donde el script buscará automáticamente tu archivo de pesos
POSIBLES_RUTAS_MODELO = [
    os.path.join(os.path.dirname(__file__), "weights", "best.pt"),
    os.path.join(os.path.dirname(__file__), "best.pt"),
    "weights/best.pt",
    "best.pt"
]


def buscar_modelo() -> Optional[str]:
    """Busca el archivo best.pt en las rutas predeterminadas."""
    for ruta in POSIBLES_RUTAS_MODELO:
        if os.path.exists(ruta):
            return os.path.abspath(ruta)
    return None


# ==========================================
# INFERENCIA REAL CON YOLO
# ==========================================
def parsear_clase_aprendiz(class_name: str) -> Tuple[str, str]:
    """
    Parsea de forma inteligente el nombre de la clase generado por Roboflow.
    Formatos soportados:
      - '10102030_Carlos_Perez' -> ID: '10102030', Nombre: 'Carlos Perez'
      - '10102030-Carlos_Perez' -> ID: '10102030', Nombre: 'Carlos Perez'
      - 'Carlos_Perez'          -> ID: 'Carlos_Perez', Nombre: 'Carlos Perez'
      - '10102030'              -> ID: '10102030', Nombre: 'Aprendiz 10102030'
    """
    class_name = class_name.strip()

    # Si contiene guion bajo o medio separando ID y Nombre
    for separador in ["_", "-"]:
        if separador in class_name:
            partes = class_name.split(separador, 1)
            # Si la primera parte es numérica (ej: cédula)
            if partes[0].isdigit():
                aprendiz_id = partes[0]
                nombre = partes[1].replace("_", " ").replace("-", " ").strip()
                return aprendiz_id, nombre

    # Si toda la clase es un número (solo cédula)
    if class_name.isdigit():
        return class_name, f"Aprendiz {class_name}"

    # Si es solo nombre
    nombre_limpio = class_name.replace("_", " ").replace("-", " ")
    return class_name, nombre_limpio


def real_yolo_inference(frame: np.ndarray, model) -> List[Dict[str, Any]]:
    """
    Ejecuta la inferencia real de YOLOv8/YOLO11 sobre el frame capturado.
    Retorna la lista de detecciones formateada para el motor de asistencia.
    """
    results = model(frame, verbose=False)[0]
    detecciones = []

    if results.boxes is None or len(results.boxes) == 0:
        return detecciones

    for box in results.boxes:
        conf = float(box.conf[0].cpu().numpy())
        cls_id = int(box.cls[0].cpu().numpy())
        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())

        # Obtener nombre de clase según los metadatos del modelo
        class_name = model.names.get(cls_id, f"Clase_{cls_id}")

        # Extraer ID y Nombre
        aprendiz_id, nombre_predicho = parsear_clase_aprendiz(class_name)

        # Si ya existe en BD, usamos el nombre oficial registrado; si no, lo guardamos
        nombre_oficial = obtener_o_crear_aprendiz(aprendiz_id, nombre_predicho)

        detecciones.append({
            "bbox": (x1, y1, x2, y2),
            "id": aprendiz_id,
            "name": nombre_oficial,
            "confidence": conf
        })

    return detecciones


# ==========================================
# MOCK DE RESPALDO (Por si no hay modelo aún)
# ==========================================
PERFILES_SIMULADOS = [
    {"id": "10102030", "name": "Carlos Perez", "confidence": 0.92},
    {"id": "10203040", "name": "Maria Rodriguez", "confidence": 0.88},
    {"id": "99999999", "name": "Desconocido", "confidence": 0.74},
]
perfil_actual_idx = 0


def mock_yolo_inference(frame: np.ndarray) -> List[Dict[str, Any]]:
    global perfil_actual_idx
    h, w, _ = frame.shape
    box_w, box_h = int(w * 0.38), int(h * 0.52)
    x1, y1 = (w - box_w) // 2, (h - box_h) // 2
    x2, y2 = x1 + box_w, y1 + box_h
    perfil = PERFILES_SIMULADOS[perfil_actual_idx]
    return [{
        "bbox": (x1, y1, x2, y2),
        "id": perfil["id"],
        "name": perfil["name"],
        "confidence": perfil["confidence"],
    }]


# ==========================================
# INTERFAZ Y RENDERIZADO VISUAL
# ==========================================
def dibujar_interfaz(
    frame: np.ndarray,
    detecciones: List[Dict[str, Any]],
    registrados_hoy: set,
    mensaje_banner: str,
    color_banner: Tuple[int, int, int],
    mostrar_banner: bool,
    modo_modelo: str
) -> None:
    h_frame, w_frame, _ = frame.shape

    # 1. Dibujar cada detección
    for det in detecciones:
        x1, y1, x2, y2 = det["bbox"]
        persona_id = det["id"]
        nombre = det["name"]
        conf = det["confidence"]

        # Filtro de precisión del 85%
        if conf < CONFIDENCE_THRESHOLD:
            color = (0, 0, 240)  # Rojo: confianza insuficiente (< 85%)
            texto = f"Baja precision: {conf * 100:.1f}% (<85%)"
        elif persona_id in registrados_hoy:
            color = (255, 170, 0)  # Ámbar/Azul: Ya asistió hoy
            texto = f"{nombre} [YA REGISTRADO HOY]"
        else:
            color = (0, 220, 0)  # Verde: Aprobado para registro
            texto = f"{nombre} ({conf * 100:.1f}%)"

        # Bounding Box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Fondo de la etiqueta
        (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x1, y1 - 25), (x1 + tw + 10, y1), color, cv2.FILLED)
        cv2.putText(
            frame,
            texto,
            (x1 + 5, y1 - 7),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )

    # 2. Panel Superior HUD (Feedback de estado)
    if mostrar_banner:
        cv2.rectangle(frame, (0, 0), (w_frame, 45), (30, 30, 30), cv2.FILLED)
        cv2.rectangle(frame, (0, 43), (w_frame, 45), color_banner, cv2.FILLED)
        cv2.putText(
            frame,
            mensaje_banner,
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            color_banner,
            2,
            cv2.LINE_AA
        )
    else:
        # Barra de estado informativo por defecto
        cv2.rectangle(frame, (0, 0), (w_frame, 32), (25, 25, 25), cv2.FILLED)
        info_txt = f"SENA | {modo_modelo} | Umbral: {int(CONFIDENCE_THRESHOLD*100)}% | [Q]: Salir"
        cv2.putText(
            frame,
            info_txt,
            (15, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (210, 210, 210),
            1,
            cv2.LINE_AA
        )


def main():
    global perfil_actual_idx

    print("=" * 65)
    print("  SISTEMA DE ASISTENCIA FACIAL - SENA (MOTOR YOLO ACTIVO)")
    print("=" * 65)

    # 1. Inicialización de la base de datos
    print("[1/3] Inicializando base de datos SQLite...")
    init_db()

    # Cargar aprendices registrados en la fecha actual (Caché en memoria)
    registrados_hoy = obtener_asistidos_del_dia()
    print(f"[INFO] Aprendices ya registrados hoy: {len(registrados_hoy)}")

    # 2. Cargar modelo YOLO entrenado
    print("[2/3] Verificando modelo de detección YOLO...")
    ruta_modelo = buscar_modelo()
    modelo_yolo = None
    modo_modelo = ""

    if ruta_modelo:
        try:
            from ultralytics import YOLO
            print(f"[OK] Cargando modelo YOLO desde: {ruta_modelo}")
            modelo_yolo = YOLO(ruta_modelo)
            modo_modelo = f"YOLO ({os.path.basename(ruta_modelo)})"
            print(f"[OK] Clases detectables por el modelo: {list(modelo_yolo.names.values())}")
        except Exception as e:
            print(f"[ADVERTENCIA] Error al cargar el modelo YOLO ({e}). Se usará modo simulación.")
            modelo_yolo = None

    if modelo_yolo is None:
        modo_modelo = "MODO SIMULACIÓN (Coloca best.pt en weights/)"
        print("\n" + "!" * 65)
        print(" [AVISO] No se encontró 'best.pt' o falló la carga.")
        print(" Por favor copia tu archivo 'best.pt' en la carpeta:")
        print("   -> d:\\Repositorios\\Proyecto_Asistencia\\weights\\best.pt")
        print(" El sistema continuará en modo de prueba (Mock interactivo).")
        print("!" * 65 + "\n")

    # 3. Inicialización de la cámara web
    print(f"[3/3] Abriendo cámara web en cv2.VideoCapture({CAMARA_INDEX})...")
    cap = cv2.VideoCapture(CAMARA_INDEX)

    if not cap.isOpened():
        print(f"[ERROR CRÍTICO] No se pudo acceder a la cámara en el índice {CAMARA_INDEX}.")
        print("Verifica que ninguna otra aplicación (Teams, Meet, Zoom) esté usando la webcam.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("\n[LISTO] Sistema en ejecución. Presiona 'q' para salir.")

    mensaje_banner = ""
    color_banner = (255, 255, 255)
    tiempo_banner_inicio = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Error al capturar frame de video.")
                break

            tiempo_actual = time.time()

            # Inferencia (Real con YOLO o Mock de respaldo)
            if modelo_yolo is not None:
                detecciones = real_yolo_inference(frame, modelo_yolo)
            else:
                detecciones = mock_yolo_inference(frame)

            # Procesar cada detección
            for det in detecciones:
                persona_id = det["id"]
                nombre = det["name"]
                conf = det["confidence"]

                # Filtro 1: Precisión mínima del 85%
                if conf >= CONFIDENCE_THRESHOLD:
                    # Filtro 2: Validación de duplicados en el día
                    if persona_id not in registrados_hoy:
                        exito, mensaje = registrar_asistencia(persona_id, nombre, conf)
                        if exito:
                            registrados_hoy.add(persona_id)
                            mensaje_banner = mensaje
                            color_banner = (0, 255, 0)  # Verde
                            tiempo_banner_inicio = tiempo_actual
                            print(f"[REGISTRO EXITOSO] {mensaje} (Confianza: {conf*100:.1f}%)")

            # Controlar visibilidad del banner
            mostrar_banner = (tiempo_actual - tiempo_banner_inicio) < BANNER_DURATION and tiempo_banner_inicio > 0

            # Renderizado visual sobre el frame
            dibujar_interfaz(
                frame,
                detecciones,
                registrados_hoy,
                mensaje_banner,
                color_banner,
                mostrar_banner,
                modo_modelo
            )

            cv2.imshow("SENA - Toma de Asistencia Facial", frame)

            # Captura de teclas
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                print("[INFO] Cerrando sistema...")
                break
            elif modelo_yolo is None:
                # Controles mock si no hay modelo real cargado
                if key == ord('1'):
                    perfil_actual_idx = 0
                    print("[MOCK] Perfil: Carlos Perez (92% conf)")
                elif key == ord('2'):
                    perfil_actual_idx = 1
                    print("[MOCK] Perfil: Maria Rodriguez (88% conf)")
                elif key == ord('3'):
                    perfil_actual_idx = 2
                    print("[MOCK] Perfil: Desconocido (74% conf)")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Recursos liberados y ventanas cerradas.")


if __name__ == "__main__":
    main()
