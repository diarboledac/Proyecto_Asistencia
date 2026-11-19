# Sistema de Control de Asistencia SENA (Web & Hardware)

Evolución arquitectónica para registro de asistencia mediante lectura de códigos QR institucionales en carnets SENA. Soporta **escáner físico USB**, **cámara de celular vía WiFi** y **captura de fotos**.

---

## 🚀 Inicio Rápido

### 1. Requisitos
- Python 3.8 o superior
- Estar conectado a la misma red WiFi que el celular para el modo inalámbrico.

### 2. Instalación de Dependencias
```bash
pip install -r requirements.txt
```

### 3. Ejecutar el Servidor
```bash
python app.py
```

El servidor iniciará en el puerto `5000`:
- **En tu computadora**: [http://localhost:5000](http://localhost:5000)
- **Desde tu celular**: [http://192.168.20.21:5000](http://192.168.20.21:5000) *(o la IP local que reporte `ipconfig`)*

---

## 🛠️ Arquitectura y Modos de Operación

### 1. Escáner Físico USB (Entrada por Teclado HID)
- Los escáneres QR por USB emulan un teclado físico que inyecta el string y pulsa `Enter`.
- La interfaz web incluye un campo de texto con **autoenfoque permanente**.
- Conecta el escáner a cualquier puerto USB, abre la web y dispara sobre el carnet. El sistema captura la lectura instantáneamente.

### 2. Modo Celular / Móvil (Cámara WiFi)
- Abre el navegador de tu celular y entra a `http://<TU_IP_LOCAL>:5000`.
- **Cámara en vivo**: Presiona **"Activar Cámara Móvil"** y apunta al carnet.
- **Modo Foto (Respaldo universal)**: Si el navegador móvil restringe el stream continuo sobre HTTP, usa el botón **"Tomar Foto al Carnet"**; abrirá la cámara nativa del teléfono y procesará el QR al instante.

### 3. Parseo Estricto de JSON y Anti-Rebote
- Valida estrictamente el formato del carnet SENA:
  ```json
  {"nom":"Diego Alejandro Arboleda Cuero","doc":"CC 1087834596","cargo":"Aprendiz","rh":"O+","ficha":"3564995","dep":"9220","prog":"ANALISIS Y DESARROLLO DE SOFTWARE - 228118 V1"}
  ```
- Si se escanea un QR ajeno, devuelve `400 Bad Request` sin interrumpir la operación del servidor.
- Consulta en SQLite si el documento ya tiene registro en la fecha actual (`YYYY-MM-DD`). Si ya existe, marca "Ya registrado hoy".

---

## 🧪 Pruebas Automatizadas
Para verificar el backend y la lógica de negocio:
```bash
python test_endpoints.py
```
