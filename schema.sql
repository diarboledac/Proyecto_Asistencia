-- Esquema de Base de Datos para Sistema de Asistencia Facial (SENA)
-- Motor: SQLite (Ligero, embebido, compatible con migración a PostgreSQL)

-- 1. Catálogo maestro de aprendices
CREATE TABLE IF NOT EXISTS aprendices (
    id TEXT PRIMARY KEY,                 -- Documento de identidad o ID único del aprendiz
    nombre_completo TEXT NOT NULL,       -- Nombres y apellidos
    ficha TEXT,                          -- Código de ficha / programa de formación SENA
    activo INTEGER DEFAULT 1,            -- 1: Activo, 0: Inactivo
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Historial de asistencias registradas
CREATE TABLE IF NOT EXISTS asistencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aprendiz_id TEXT NOT NULL,           -- Referencia al aprendiz
    nombre TEXT NOT NULL,                -- Copia del nombre para auditoría rápida
    fecha DATE NOT NULL,                 -- Formato YYYY-MM-DD
    hora TIME NOT NULL,                  -- Formato HH:MM:SS
    confianza REAL NOT NULL,             -- Porcentaje de confianza del modelo (ej: 0.91 = 91%)
    metodo TEXT DEFAULT 'facial_yolo',   -- Método de captura
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (aprendiz_id) REFERENCES aprendices(id) ON DELETE CASCADE,
    UNIQUE (aprendiz_id, fecha)          -- REGLA CRÍTICA: Solo 1 asistencia por aprendiz al día
);

-- 3. Índices para búsqueda de alta velocidad en tiempo real
CREATE INDEX IF NOT EXISTS idx_asistencias_aprendiz_fecha ON asistencias(aprendiz_id, fecha);
CREATE INDEX IF NOT EXISTS idx_asistencias_fecha ON asistencias(fecha);

