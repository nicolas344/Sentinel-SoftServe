# Guía de Instalación - Sentinel Backend

Esta guía te llevará paso a paso por la configuración del entorno de desarrollo del backend.

## 📋 Requisitos Previos

### Software Requerido

| Software | Versión Mínima | Propósito |
|----------|---------------|-----------|
| **Python** | 3.9+ | Runtime principal |
| **pip** | 21.0+ | Gestor de paquetes Python |
| **Git** | 2.30+ | Control de versiones |
| **Docker** | 20.10+ | Contenedores de infraestructura |
| **Docker Compose** | 2.0+ | Orquestación de contenedores |

### Verificar Instalaciones

```bash
python --version      # Debe mostrar Python 3.9 o superior
pip --version         # Debe mostrar pip 21.0 o superior
git --version         # Debe mostrar git 2.30 o superior
docker --version      # Debe mostrar Docker 20.10 o superior
docker compose version # Debe mostrar Docker Compose 2.0 o superior
```

## 🚀 Pasos de Instalación

### 1. Clonar el Repositorio

```bash
git clone https://github.com/nicolas344/Sentinel-SoftServe.git
cd Sentinel-SoftServe/Backend
```

### 2. Crear Entorno Virtual

#### Windows (PowerShell)

```powershell
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Si obtienes error de política de ejecución, ejecuta primero:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Linux / macOS

```bash
# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate
```

**Verificar que el entorno esté activado:**
Deberías ver `(venv)` al inicio de tu línea de comando.

### 3. Instalar Dependencias

```bash
# Actualizar pip a la última versión
python -m pip install --upgrade pip

# Instalar todas las dependencias del proyecto
pip install -r requirements.txt
```

**Tiempo estimado**: 2-3 minutos dependiendo de tu conexión a internet.

### 4. Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env  # Linux/Mac
copy .env.example .env  # Windows
```

Edita el archivo `.env` con tus credenciales reales:

```env
# ============================================
# SUPABASE - Base de Datos y Autenticación
# ============================================
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=tu-jwt-secret-aqui

# ============================================
# OPENAI - LLM para Análisis
# ============================================
OPENAI_API_KEY=sk-proj-...

# ============================================
# LANGFUSE - Observabilidad de IA
# ============================================
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3001

# ============================================
# INFRAESTRUCTURA
# ============================================
LOKI_URL=http://localhost:3100
CHROMA_HOST=http://localhost:8001

# ============================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ============================================
ENVIRONMENT=development
DEBUG=True
PORT=8000
HOST=0.0.0.0
```

#### ¿Dónde Obtener las Credenciales?

##### Supabase
1. Ve a [https://app.supabase.com](https://app.supabase.com)
2. Selecciona tu proyecto
3. Ve a **Settings** → **API**
4. Copia:
   - `URL` → `SUPABASE_URL`
   - `service_role key` → `SUPABASE_SERVICE_KEY`
   - `JWT Secret` → `SUPABASE_JWT_SECRET`

##### OpenAI
1. Ve a [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Crea una nueva API key
3. Copia y pega en `OPENAI_API_KEY`

##### LangFuse
1. Levanta el stack Docker (ver paso 5)
2. Accede a [http://localhost:3001](http://localhost:3001)
3. Crea una cuenta local
4. Crea un nuevo proyecto "sentinel"
5. Copia las keys generadas

### 5. Levantar Infraestructura Docker

Desde la **raíz del proyecto** (no desde `Backend/`):

```bash
cd ..  # Volver a la raíz del proyecto
docker compose up -d
```

Esto levantará:
- **Prometheus** (métricas) - `:9090`
- **Alertmanager** (alertas) - `:9093`
- **Grafana** (visualización) - `:3000`
- **Loki** (logs) - `:3100`
- **Promtail** (recolector de logs)
- **cAdvisor** (métricas de contenedores) - `:8080`
- **LangFuse** (observabilidad IA) - `:3001`
- **ChromaDB** (vector database) - `:8001`

**Verificar que todos los contenedores estén corriendo:**

```bash
docker ps
```

Deberías ver 8-9 contenedores en estado `Up`.

### 6. Aplicar Migraciones de Base de Datos

```bash
cd Backend
python scripts/run_migrations.py
```

Este script te mostrará el SQL que debes ejecutar manualmente en Supabase Dashboard:

1. Ve a [https://app.supabase.com](https://app.supabase.com)
2. Selecciona tu proyecto
3. Ve a **SQL Editor**
4. Crea una nueva query
5. Copia y pega el SQL mostrado por el script
6. Ejecuta la query (botón **Run**)
7. Verifica que no haya errores
8. Ve a **Settings** → **API** → **Reload Schema**

**Alternativa**: Copia manualmente el contenido de `db/migrations/001_add_agent_columns.sql`

### 7. Seed ChromaDB con Runbooks (Opcional)

```bash
python scripts/seed_chromadb.py
```

Esto cargará runbooks operacionales en ChromaDB para el sistema RAG.

### 8. Iniciar el Servidor

```bash
uvicorn main:app --reload --host 0.0.0.0
```

**Salida esperada:**

```
INFO:     Will watch for changes in these directories: ['C:\\...\\Backend']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using WatchFiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## ✅ Verificar Instalación

### 1. Health Check

```bash
curl http://localhost:8000/health
```

**Respuesta esperada:**

```json
{
  "status": "healthy",
  "timestamp": "2026-03-02T10:30:00Z"
}
```

### 2. Documentación Interactiva

Abre en tu navegador:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 3. Test de Conexión a Supabase

```bash
curl -X GET http://localhost:8000/api/incidents
```

Debería retornar una lista vacía o incidentes existentes.

### 4. Verificar Infraestructura

- **Grafana**: [http://localhost:3000](http://localhost:3000) (admin / sentinel123)
- **Prometheus**: [http://localhost:9090](http://localhost:9090)
- **LangFuse**: [http://localhost:3001](http://localhost:3001)
- **cAdvisor**: [http://localhost:8080](http://localhost:8080)

## 🐛 Troubleshooting

### Problema: `ModuleNotFoundError: No module named 'langchain'`

**Solución:**

```bash
pip install --upgrade --force-reinstall -r requirements.txt
```

### Problema: `SupabaseException: supabase_url is required`

**Causa**: El archivo `.env` no está configurado correctamente o no se encuentra.

**Solución:**

1. Verifica que el archivo `.env` exista en `Backend/`
2. Verifica que `SUPABASE_URL` esté definido y no esté vacío
3. Reinicia el servidor

### Problema: `Could not find the 'agent_reasoning' column`

**Causa**: Las migraciones de base de datos no se aplicaron.

**Solución:** Ejecuta el paso 6 de la instalación (Aplicar Migraciones)

### Problema: Error de política de ejecución en PowerShell

**Solución:**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problema: Docker contenedores no inician

**Solución:**

```bash
# Ver logs de error
docker compose logs

# Reiniciar todo el stack
docker compose down
docker compose up -d
```

## 🔄 Comandos Útiles

### Gestión de Entorno Virtual

```bash
# Activar
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Linux/Mac

# Desactivar
deactivate

# Eliminar y recrear
Remove-Item -Recurse -Force venv  # Windows
rm -rf venv                       # Linux/Mac
python -m venv venv
```

### Gestión de Dependencias

```bash
# Instalar nueva dependencia
pip install <paquete>

# Actualizar requirements.txt
pip freeze > requirements.txt

# Verificar paquetes instalados
pip list

# Buscar paquete específico
pip show <paquete>
```

### Gestión del Servidor

```bash
# Modo desarrollo con hot reload
uvicorn main:app --reload

# Modo producción
uvicorn main:app --host 0.0.0.0 --port 8000

# Con logs de debug
uvicorn main:app --log-level debug

# Con workers para mejor rendimiento
uvicorn main:app --workers 4
```

## 📚 Próximos Pasos

1. Lee la [Guía de Configuración](./02-configuration.md) para entender todas las variables de entorno
2. Revisa la [Guía de Quick Start](./03-quickstart.md) para probar el sistema end-to-end
3. Consulta la [Estructura del Proyecto](./development/project-structure.md) para entender la organización del código
4. Lee las [Convenciones de Código](./development/coding-standards.md) antes de empezar a desarrollar

## 🆘 ¿Necesitas Ayuda?

- Consulta la sección de [Troubleshooting](../troubleshooting/common-issues.md)
- Revisa los [Issues en GitHub](https://github.com/nicolas344/Sentinel-SoftServe/issues)
- Contacta al equipo en el canal de Slack del proyecto
