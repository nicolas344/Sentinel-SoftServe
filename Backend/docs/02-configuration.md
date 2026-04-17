# Guía de Configuración - Sentinel Backend

Esta guía explica en detalle todas las variables de entorno y opciones de configuración del backend.

## 📋 Variables de Entorno

Todas las variables de entorno se configuran en el archivo `.env` en el directorio `Backend/`.

### 🔐 Supabase (Base de Datos y Autenticación)

#### `SUPABASE_URL` **(Requerido)**
- **Descripción**: URL de tu proyecto de Supabase
- **Formato**: `https://<project-id>.supabase.co`
- **Ejemplo**: `https://euszupdecitqzjuztqeo.supabase.co`
- **Dónde obtenerlo**: Dashboard de Supabase → Settings → API → URL

#### `SUPABASE_SERVICE_KEY` **(Requerido)**
- **Descripción**: Service Role Key de Supabase (clave con permisos administrativos)
- **Formato**: JWT (comienza con `eyJ`)
- **Ejemplo**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3...`
- **Dónde obtenerlo**: Dashboard de Supabase → Settings → API → service_role key
- ⚠️ **ADVERTENCIA**: Esta clave tiene permisos completos. **NUNCA** la compartas ni la subas a control de versiones.

#### `SUPABASE_JWT_SECRET` **(Requerido)**
- **Descripción**: Secret key para validar JWTs de Supabase
- **Formato**: String alfanumérico largo
- **Ejemplo**: `7nDXK9zMqP4tR2vY8bGcH5jL6nQsW3uZ...`
- **Dónde obtenerlo**: Dashboard de Supabase → Settings → API → JWT Secret
- **Uso**: Validar tokens JWT enviados por el frontend

### 🤖 OpenAI (LLM para Análisis)

#### `OPENAI_API_KEY` **(Requerido en Sprint 1)**
- **Descripción**: API key de OpenAI para usar GPT-4o-mini
- **Formato**: `sk-proj-...` o `sk-...`
- **Ejemplo**: `sk-proj-abc123def456...`
- **Dónde obtenerlo**: [OpenAI Platform](https://platform.openai.com/api-keys)
- **Costo estimado**: ~$0.15 USD por 1M de tokens de entrada
- **Nota**: Se cambiará a Gemini 2.5 Flash-Lite en Sprint 2

### 📊 LangFuse (Observabilidad de IA)

#### `LANGFUSE_PUBLIC_KEY` **(Requerido)**
- **Descripción**: Clave pública de LangFuse para identificar el proyecto
- **Formato**: `pk-lf-...`
- **Ejemplo**: `pk-lf-1234567890abcdef`
- **Dónde obtenerlo**: 
  1. Accede a LangFuse en `http://localhost:3001`
  2. Crea un proyecto "sentinel"
  3. Ve a Settings → API Keys

#### `LANGFUSE_SECRET_KEY` **(Requerido)**
- **Descripción**: Clave secreta de LangFuse para autenticación
- **Formato**: `sk-lf-...`
- **Ejemplo**: `sk-lf-fedcba0987654321`
- **Dónde obtenerlo**: Mismo lugar que la public key

#### `LANGFUSE_HOST` **(Opcional)**
- **Descripción**: URL del servidor de LangFuse
- **Formato**: URL completa con protocolo
- **Valor por defecto**: `http://localhost:3001`
- **Ejemplo producción**: `https://cloud.langfuse.com`
- **Nota**: En desarrollo usamos LangFuse self-hosted

### 🏗️ Infraestructura (Logs y Vector DB)

#### `LOKI_URL` **(Opcional)**
- **Descripción**: URL del servidor de Loki para obtener logs de contenedores
- **Formato**: `http://host:puerto`
- **Valor por defecto**: `http://localhost:3100`
- **Uso**: Recolección de logs cuando un contenedor crashea

#### `CHROMA_HOST` **(Opcional)**
- **Descripción**: URL del servidor de ChromaDB para búsqueda vectorial
- **Formato**: `http://host:puerto`
- **Valor por defecto**: `http://localhost:8001`
- **Uso**: RAG (Retrieval Augmented Generation) sobre runbooks operacionales

### ⚙️ Configuración de la Aplicación

#### `ENVIRONMENT` **(Opcional)**
- **Descripción**: Entorno de ejecución
- **Valores permitidos**: `development`, `production`, `testing`
- **Valor por defecto**: `development`
- **Impacto**:
  - `development`: Logs verbosos, CORS permisivo, hot reload
  - `production`: Logs estructurados, CORS restrictivo, optimizaciones
  - `testing`: Mocks habilitados, base de datos de pruebas

#### `DEBUG` **(Opcional)**
- **Descripción**: Habilita modo debug con trazas detalladas
- **Valores permitidos**: `True`, `False`
- **Valor por defecto**: `True` en development, `False` en production
- **Impacto**: Muestra stack traces completos en respuestas de error

#### `PORT` **(Opcional)**
- **Descripción**: Puerto en el que escuchará el servidor
- **Formato**: Número entre 1024 y 65535
- **Valor por defecto**: `8000`
- **Ejemplo**: `PORT=8080`

#### `HOST` **(Opcional)**
- **Descripción**: Interfaz de red en la que escuchará el servidor
- **Valores comunes**:
  - `0.0.0.0` - Acepta conexiones desde cualquier IP (recomendado)
  - `127.0.0.1` - Solo acepta conexiones locales
- **Valor por defecto**: `0.0.0.0`

## 🗂️ Archivo `.env` Completo (Plantilla)

```env
# ============================================
# SUPABASE - Base de Datos y Autenticación
# ============================================
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=tu-jwt-secret-muy-largo-y-seguro-aqui

# ============================================
# OPENAI - LLM para Análisis (Sprint 1)
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

## 🔒 Seguridad

### ⚠️ Variables Sensibles

Las siguientes variables **NUNCA** deben ser compartidas ni commiteadas a Git:

- `SUPABASE_SERVICE_KEY`
- `SUPABASE_JWT_SECRET`
- `OPENAI_API_KEY`
- `LANGFUSE_SECRET_KEY`

### ✅ Buenas Prácticas

1. **Nunca commitees el archivo `.env`**
   - Ya está en `.gitignore`
   - Usa `.env.example` como plantilla

2. **Rota las claves periódicamente**
   - Service keys de Supabase cada 3-6 meses
   - API keys de OpenAI si sospechas compromiso

3. **Usa diferentes claves por entorno**
   - Development: claves de desarrollo
   - Production: claves dedicadas con permisos mínimos

4. **Almacenamiento seguro en producción**
   - Usa servicios de secrets management (AWS Secrets Manager, Azure Key Vault)
   - Variables de entorno en plataforma de deployment (Vercel, Railway, etc.)

## 🔄 Carga de Variables de Entorno

El backend carga las variables de entorno usando `python-dotenv`:

```python
# db/supabase_client.py
from dotenv import load_dotenv
import os

load_dotenv()  # Carga automáticamente .env

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
```

### Orden de Prioridad

1. **Variables de entorno del sistema** (definidas en shell)
2. **Archivo `.env`** (en el directorio `Backend/`)
3. **Valores por defecto en código** (cuando existen)

## 🧪 Configuración de Testing

Para ejecutar tests, crea un archivo `.env.test`:

```env
SUPABASE_URL=https://test-project.supabase.co
SUPABASE_SERVICE_KEY=test-service-key
OPENAI_API_KEY=test-key  # O usa mocks
ENVIRONMENT=testing
DEBUG=True
```

Carga este archivo en tus tests:

```python
from dotenv import load_dotenv

load_dotenv('.env.test')
```

## 📊 Configuración de Producción

### Diferencias Clave vs Development

```env
# Production .env
ENVIRONMENT=production
DEBUG=False
HOST=0.0.0.0
PORT=8000

# Claves reales de producción
SUPABASE_URL=https://prod-project.supabase.co
SUPABASE_SERVICE_KEY=prod-service-key-con-permisos-minimos

# LangFuse cloud (si aplica)
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Checklist de Producción

- [ ] `DEBUG=False`
- [ ] Service key con permisos mínimos
- [ ] HTTPS habilitado
- [ ] CORS configurado con orígenes específicos
- [ ] Rate limiting habilitado
- [ ] Logs estructurados (JSON)
- [ ] Monitoring y alertas configurados

## 🐛 Troubleshooting

### Problema: Variables no se cargan

**Síntomas**: `os.getenv()` retorna `None`

**Soluciones**:

1. Verifica que el archivo `.env` esté en el directorio correcto (`Backend/`)
2. Verifica que no haya espacios alrededor del `=`:
   ```env
   # ❌ Incorrecto
   SUPABASE_URL = https://...
   
   # ✅ Correcto
   SUPABASE_URL=https://...
   ```
3. Reinicia el servidor después de editar `.env`

### Problema: Error de autenticación con Supabase

**Causa común**: `SUPABASE_SERVICE_KEY` incorrecta o expirada

**Solución**:

1. Ve a Supabase Dashboard → Settings → API
2. Regenera la service role key si es necesario
3. Actualiza `.env`
4. Reinicia el servidor

### Problema: LangFuse no traza ejecuciones

**Causa común**: Keys incorrectas o LangFuse no está corriendo

**Solución**:

1. Verifica que LangFuse esté corriendo: `docker ps | grep langfuse`
2. Accede a `http://localhost:3001` y verifica el proyecto
3. Regenera las keys en LangFuse si es necesario
4. Verifica que `LANGFUSE_HOST` apunte al servidor correcto

## 📚 Referencias

- [Documentación de python-dotenv](https://pypi.org/project/python-dotenv/)
- [Documentación de Supabase](https://supabase.com/docs)
- [Documentación de OpenAI](https://platform.openai.com/docs)
- [Documentación de LangFuse](https://langfuse.com/docs)

## ➡️ Próximos Pasos

1. Lee la [Guía de Quick Start](./03-quickstart.md) para probar el sistema
2. Revisa la [Arquitectura](./architecture/00-overview.md) para entender el flujo de datos
3. Consulta la [API Reference](./api/endpoints.md) para conocer todos los endpoints
