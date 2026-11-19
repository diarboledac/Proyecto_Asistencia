# Informe Técnico de Estado, Diagnóstico y Hoja de Ruta

**Proyecto:** Sistema de Control de Asistencia mediante Códigos QR de Carnets SENA  
**Fecha:** 2026-10-11  
**Ubicación:** `d:\Repositorios\Asistencia_QR`  
**Destinatario:** Desarrollador / Agente Relevo  

---

## 1. Resumen Ejecutivo del Problema

El sistema actual tiene la arquitectura backend, la persistencia en SQLite, el parseo estricto del JSON institucional del SENA y la lógica anti-duplicados **completamente funcionales y verificados con pruebas automatizadas**.

**El único componente pendiente de resolver es:**  
> **La transmisión de la cámara web en vivo desde el navegador del teléfono celular (`navigator.mediaDevices.getUserMedia` / `html5-qrcode`) a través de la red local Wi-Fi.**

Este documento detalla qué funciona, por qué falla la cámara en vivo en móviles y cuáles son las alternativas exactas para solucionarlo **sin tocar ni romper lo que ya está construido y probado**.

---

## 2. Lo Que Ya Funciona al 100% (NO MODIFICAR NI DAÑAR)

Los siguientes módulos y contratos de software están estables y respaldados por la suite de pruebas automatizadas [`test_endpoints.py`](file:///d:/Repositorios/Asistencia_QR/test_endpoints.py) (6/6 tests pasando):

### A. Base de Datos Autónoma (`registro_aprendices.db`)
- Motor: SQLite3 con modo `WAL` (`PRAGMA journal_mode = WAL;`) para alta concurrencia.
- Tabla `asistencia`:
  ```sql
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
  ```
- **Lógica Anti-Duplicados (Anti-Rebote):**
  Consulta por `documento` y `fecha` (`YYYY-MM-DD`). Si el aprendiz ya ingresó hoy, devuelve estado `"duplicado"` sin registrar doble asistencia.

### B. Parseo Estricto de Carnet SENA (`parsear_carnet_sena`)
- Los carnets reales del SENA contienen un string JSON con este formato exacto:
  ```json
  {"nom":"Diego Alejandro Arboleda Cuero","doc":"CC 1087834596","cargo":"Aprendiz","rh":"O+","ficha":"3564995","dep":"9220","prog":"ANALISIS Y DESARROLLO DE SOFTWARE - 228118 V1"}
  ```
- El backend procesa el string con `json.loads` dentro de un bloque `try ... except json.JSONDecodeError`.
- Si se escanea un QR ajeno (ej. una URL web o texto plano), responde con HTTP `400 Bad Request` informando del error de forma limpia, **sin que el servidor se caiga ni se interrumpa**.

### C. Endpoints REST del Backend ([`app.py`](file:///d:/Repositorios/Asistencia_QR/app.py))
- `GET /`: Sirve la interfaz web responsiva [`templates/index.html`](file:///d:/Repositorios/Asistencia_QR/templates/index.html).
- `POST /registrar`: Recibe `{ "qr_data": "<string_json>" }`, parsea, valida anti-duplicados y persiste en SQLite. Devuelve:
  - `HTTP 200` + `{ "status": "exitoso", "aprendiz": {...}, "hora": "...", "fecha": "..." }`
  - `HTTP 200` + `{ "status": "duplicado", "mensaje": "Ya registrado hoy.", "aprendiz": {...} }`
  - `HTTP 400` + `{ "status": "error", "mensaje": "..." }`
- `POST /registrar_foto`: Endpoint multipart donde el celular sube una foto del carnet; el servidor la decodifica con OpenCV (`cv2`) y `pyzbar` en Python.
- `GET /api/asistencias/hoy`: Devuelve la lista en tiempo real de aprendices registrados en la fecha actual.

### D. Soporte para Escáner Físico USB (Teclado HID)
- Los lectores USB comerciales actúan como teclados que inyectan caracteres a alta velocidad y presionan la tecla `Enter`.
- El frontend tiene un input con foco permanente (`#usb-scanner-input`) que escucha el evento `Enter` y despacha la petición al endpoint `/registrar`.

### E. Firewall de Windows
- Se creó y habilitó la regla de entrada en el Firewall de Windows Defender para el puerto `5000`:
  `DisplayName: Asistencia_SENA_5000` (Protocolo TCP, puerto 5000, perfil Any, acción Allow).

---

## 3. Diagnóstico del Problema: ¿Por Qué Falla la Cámara en Vivo en el Celular?

### Causa Raíz Técnica: Restricción W3C "Secure Context"
Por especificación de seguridad de los navegadores web modernos (Google Chrome, Apple Safari, Mozilla Firefox, Microsoft Edge en Android e iOS):

1. **Restricción de `getUserMedia` sobre HTTP:**
   La API `navigator.mediaDevices.getUserMedia` (usada por librerías como `html5-qrcode` o `zxing`) **SOLO se activa en contextos seguros** (`https://` o `http://localhost`).
   Cuando un celular accede por red local a una dirección IP no cifrada como `http://192.168.20.21:5000`:
   - El navegador define `navigator.mediaDevices = undefined`.
   - La librería falla arrojando: *"Camera streaming not supported or insecure context"*.

2. **El Problema con Certificados Autofirmados locales (Self-Signed SSL):**
   Al activar HTTPS en Flask con certificados autofirmados (`cert.pem`, `key.pem`):
   - El navegador del celular detecta que el certificado no está firmado por una Autoridad Certificadora (CA) pública de confianza.
   - Muestra la pantalla de advertencia roja `NET::ERR_CERT_AUTHORITY_INVALID`.
   - En muchos modelos de Android y en Safari (iOS), las políticas de seguridad estrictas impiden que la cámara se active aun cuando el usuario presiona "Continuar al sitio", o bien bloquean el protocolo WebRTC por falta de cadena de confianza SSL.

---

## 4. Soluciones Viables Sin Dañar el Código Existente

Cualquiera de las siguientes opciones resuelve el problema **manteniendo el 100% del backend y la base de datos intactos**.

---

### OPCIÓN A (Altamente Recomendada): Túnel HTTPS con Certificado SSL Válido
**Idea:** Utilizar un túnel seguro temporal (como **Cloudflare Tunnel** o **Ngrok**) para exponer el puerto `5000` local a través de una URL HTTPS pública con certificado SSL de confianza (Let's Encrypt / Cloudflare).

- **Ventajas:**
  - Cero cambios en `app.py`, cero cambios en SQLite y cero cambios en la interfaz.
  - La URL generada (ej. `https://asistencia-sena.trycloudflare.com`) cuenta con un certificado SSL 100% válido y reconocido por todos los celulares del mundo.
  - Al abrir esa URL en el celular, el navegador no muestra ninguna advertencia roja y **la cámara en vivo se enciende de inmediato tras pulsar "Permitir"**.
- **Cómo implementarlo:**
  1. Descargar el ejecutable ligero de Cloudflare (`cloudflared.exe`) o Ngrok.
  2. Ejecutar: `cloudflared tunnel --url http://localhost:5000`
  3. Copiar la URL HTTPS generada y abrirla en el celular.

---

### OPCIÓN B: App Móvil Externa / Escáner Webhook
**Idea:** No usar el navegador web para abrir la cámara, sino una app nativa gratuita de escaneo de QR instalada en el celular que envíe la lectura por HTTP POST al servidor.

- **Herramientas existentes:**
  - **Barcode to PC** (App Android/iOS + receptor).
  - **HTTP Request Scanner** / **QR Droid Webhook**.
- **Ventajas:**
  - Las apps nativas tienen acceso directo al hardware de la cámara sin restricciones de HTTPS de los navegadores.
  - Al escanear el carnet, la app hace un `POST http://192.168.20.21:5000/registrar` enviando el JSON del aprendiz.
  - El backend procesa la asistencia normalmente.

---

### OPCIÓN C: Instalación de Certificado de Confianza con `mkcert`
**Idea:** Crear una autoridad certificadora (CA) local mediante la herramienta `mkcert`, instalar el certificado raíz en el celular y levantar Flask con ese certificado.

- **Ventajas:** Permite seguir trabajando en la red local pura sin internet.
- **Desventajas:** Requiere instalar manualmente el archivo `.crt` en la configuración de certificados de usuario del celular.

---

## 5. Instrucciones para el Próximo Agente / Desarrollador

Si vas a continuar este desarrollo:

1. **NO modifiques el esquema de la base de datos** (`documento`, `nombre`, `ficha`, `programa`, `datos_qr`, `fecha`, `hora`).
2. **NO elimines el parseo estricto de JSON** en [`app.py`](file:///d:/Repositorios/Asistencia_QR/app.py). Es el formato real de los carnets del SENA.
3. **Conserva el endpoint `/registrar`** con su firma actual, ya que es el contrato utilizado tanto por el lector USB como por las pruebas.
4. **Ejecuta siempre la suite de pruebas** tras cualquier cambio para garantizar que no hay regresiones:
   ```powershell
   python test_endpoints.py
   ```
5. **Para resolver la cámara móvil:** Adopta prioritariamente la **Opción A (Túnel HTTPS)** o la **Opción B (App cliente nativa)**; son las únicas vías que no chocan con la política de seguridad W3C de los navegadores móviles.
