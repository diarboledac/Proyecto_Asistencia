import json
import sqlite3
from app import app, db, DB_PATH

def run_tests():
    # Limpiar base de datos antes de las pruebas para estado determinista
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM asistencia;")

    client = app.test_client()

    # 1. Probar ruta raíz
    res_index = client.get('/')
    assert res_index.status_code == 200, f"Fallo index: {res_index.status_code}"
    print("[PASS] Test 1: Ruta raíz '/' sirve HTML correctamente.")

    # 2. Probar JSON válido de carnet SENA
    sena_qr = json.dumps({
        "nom": "Diego Alejandro Arboleda Cuero",
        "doc": "CC 1087834596",
        "cargo": "Aprendiz",
        "rh": "O+",
        "ficha": "3564995",
        "dep": "9220",
        "prog": "ANALISIS Y DESARROLLO DE SOFTWARE - 228118 V1"
    })

    # Primer registro (Exitoso)
    res1 = client.post('/registrar', json={"qr_data": sena_qr})
    assert res1.status_code == 200, f"Error res1: {res1.data}"
    data1 = res1.get_json()
    assert data1["status"] == "exitoso", f"Estado no exitoso: {data1}"
    print(f"[PASS] Test 2: Primer registro exitoso ({data1['aprendiz']['nombre']}).")

    # Segundo registro (Duplicado)
    res2 = client.post('/registrar', json={"qr_data": sena_qr})
    assert res2.status_code == 200, f"Error res2: {res2.data}"
    data2 = res2.get_json()
    assert data2["status"] == "duplicado", f"Estado no duplicado: {data2}"
    print(f"[PASS] Test 3: Anti-rebote confirmado ({data2['mensaje']}).")

    # 3. Probar QR no válido / no JSON
    res_invalido = client.post('/registrar', json={"qr_data": "https://www.google.com"})
    assert res_invalido.status_code == 400, f"Status inesperado: {res_invalido.status_code}"
    data_inv = res_invalido.get_json()
    assert data_inv["status"] == "error"
    print(f"[PASS] Test 4: QR no JSON rechazado limpiamente ({data_inv['mensaje']}).")

    # 4. Probar JSON incompleto
    res_incompleto = client.post('/registrar', json={"qr_data": json.dumps({"clave": "valor"})})
    assert res_incompleto.status_code == 400
    print(f"[PASS] Test 5: JSON sin datos de carnet rechazado con error 400.")

    # 5. Probar listado de hoy
    res_hoy = client.get('/api/asistencias/hoy')
    assert res_hoy.status_code == 200
    data_hoy = res_hoy.get_json()
    assert data_hoy["total"] >= 1
    print(f"[PASS] Test 6: API /api/asistencias/hoy reporta {data_hoy['total']} registro(s).")

    # Limpiar al finalizar para dejar la DB limpia para el usuario
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM asistencia;")

    print("\n==============================================")
    print("TODAS LAS PRUEBAS DE ARQUITECTURA PASARON (6/6)")
    print("==============================================")

if __name__ == "__main__":
    run_tests()
