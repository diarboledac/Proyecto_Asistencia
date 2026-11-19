"""
Script para visualizar los registros de asistencia de aprendices en SQLite.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "registro_aprendices.db")

def ver_registros():
    if not os.path.exists(DB_PATH):
        print(f"[AVISO] No se encontró la base de datos en: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, fecha, hora, documento, nombre, ficha, programa 
            FROM asistencia 
            ORDER BY id DESC
        """)
        filas = cursor.fetchall()
    except sqlite3.OperationalError:
        cursor.execute("SELECT id, fecha, hora, datos_qr FROM asistencia ORDER BY id DESC")
        filas = cursor.fetchall()

    conn.close()

    print("\n" + "=" * 105)
    print(f"REGISTROS DE ASISTENCIA SENA: {DB_PATH}")
    print("=" * 105)
    if not filas:
        print("La base de datos está vacía. Aún no se han registrado asistencias.")
    else:
        print(f"{'ID':<4} | {'FECHA':<10} | {'HORA':<8} | {'DOCUMENTO':<14} | {'FICHA':<9} | {'APRENDIZ':<28} | {'PROGRAMA'}")
        print("-" * 105)
        for fila in filas:
            if len(fila) == 7:
                _id, fecha, hora, doc, nom, ficha, prog = fila
                doc_str = doc or "N/A"
                nom_str = (nom[:26] + "..") if nom and len(nom) > 28 else (nom or "N/A")
                ficha_str = ficha or "N/A"
                prog_str = (prog[:25] + "..") if prog and len(prog) > 27 else (prog or "N/A")
                print(f"{_id:<4} | {fecha:<10} | {hora:<8} | {doc_str:<14} | {ficha_str:<9} | {nom_str:<28} | {prog_str}")
            else:
                _id, fecha, hora, qr = fila
                print(f"{_id:<4} | {fecha:<10} | {hora:<8} | QR: {qr[:60]}")
    print("=" * 105 + "\n")

if __name__ == "__main__":
    ver_registros()
