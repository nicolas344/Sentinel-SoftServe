# Sentinel Backend - Documentación Técnica

> **Sistema de Triage Inteligente de Incidentes DevOps con IA Agentica**

## 🎯 Propósito del Backend

El backend de Sentinel es una **API REST con orquestación de agentes IA** que automatiza la detección, clasificación y análisis de incidentes en infraestructura Docker. Utiliza **LangGraph** para coordinar múltiples laboratorios de análisis que procesan alertas de Prometheus y generan recomendaciones contextuales.

## 📖 Índice de Documentación

### 🚀 Getting Started
- [Guía de Instalación](./docs/01-installation.md) - Configuración del entorno de desarrollo
- [Configuración](./docs/02-configuration.md) - Variables de entorno y secretos
- [Primeros Pasos](./docs/03-quickstart.md) - Cómo levantar el servidor y probar

### 🏗️ Arquitectura
- [Visión General de Arquitectura](./docs/architecture/00-overview.md) - Diagrama y componentes principales
- [Flujo de Procesamiento de Incidentes](./docs/architecture/01-incident-flow.md) - De la alerta al análisis completo
- [LangGraph Engine](./docs/architecture/02-langgraph-engine.md) - Motor de agentes y laboratorios
- [Integraciones](./docs/architecture/03-integrations.md) - Prometheus, Loki, ChromaDB, Supabase

### 📡 API Reference
- [Endpoints](./docs/api/endpoints.md) - Especificación completa de la API REST
- [Modelos de Datos](./docs/api/models.md) - Schemas de Pydantic y estructura de base de datos
- [Autenticación](./docs/api/authentication.md) - JWT y autorización con Supabase
- [Webhooks](./docs/api/webhooks.md) - Integración con Alertmanager

### 🧪 Testing & Quality
- [Tests](./docs/testing/overview.md) - Estrategia de testing y cobertura
- [Linting y Formateo](./docs/testing/code-quality.md) - Estándares de código

### 🔧 Desarrollo
- [Estructura del Proyecto](./docs/development/project-structure.md) - Organización de archivos y módulos
- [Guía de Contribución](./docs/development/contributing.md) - Cómo contribuir al proyecto
- [Convenciones de Código](./docs/development/coding-standards.md) - Clean Code y principios SOLID

### 🚀 Deployment
- [Docker](./docs/deployment/docker.md) - Containerización del backend
- [Variables de Producción](./docs/deployment/production-env.md) - Configuración para producción
- [Migraciones de Base de Datos](./docs/deployment/migrations.md) - Cómo aplicar cambios de schema

### 📊 Observabilidad
- [Logs](./docs/observability/logging.md) - Sistema de logging estructurado
- [Métricas](./docs/observability/metrics.md) - Métricas de rendimiento
- [LangFuse Tracing](./docs/observability/langfuse.md) - Trazabilidad de agentes IA

### 🔍 Troubleshooting
- [Problemas Comunes](./docs/troubleshooting/common-issues.md) - Soluciones a errores frecuentes
- [Debugging](./docs/troubleshooting/debugging.md) - Técnicas de depuración

## 🛠️ Stack Tecnológico

| Categoría | Tecnología | Versión | Propósito |
|-----------|-----------|---------|-----------|
| **Framework** | FastAPI | 0.115+ | API REST de alto rendimiento |
| **Servidor** | Uvicorn | 0.30+ | Servidor ASGI asíncrono |
| **IA Framework** | LangChain | 0.3+ | Orquestación de LLMs |
| **Motor de Agentes** | LangGraph | 0.2+ | Grafo estatal para workflows IA |
| **LLM** | OpenAI GPT-4o-mini | - | Clasificación y análisis (Sprint 1) |
| **Vector DB** | ChromaDB | 0.5+ | RAG sobre runbooks operacionales |
| **Base de Datos** | Supabase (PostgreSQL) | - | Almacenamiento de incidentes |
| **Observabilidad IA** | LangFuse | 2.0+ | Trazas de ejecución de agentes |
| **Logs** | Loki | - | Recolección de logs de contenedores |
| **Métricas** | Prometheus | - | Detección de anomalías |
| **Validación** | Pydantic | 2.0+ | Validación de datos y schemas |

## 🌊 Flujo de Datos Simplificado

```
Alertmanager → POST /api/alerts → alert_processor.py
                                         ↓
                                  Crear incidente en Supabase
                                         ↓
                              BackgroundTask → LangGraph
                                         ↓
                         ┌───────────────┴───────────────┐
                         ↓                               ↓
                 Lab 1: Alert Intake          Lab 2: Investigation
                 (Clasificación)              (Análisis Root Cause)
                         ↓                               ↓
                    Update Supabase              Update Supabase
                         ↓                               ↓
                         └───────────────┬───────────────┘
                                         ↓
                          Frontend recibe update vía Realtime
```

## 📦 Dependencias Principales

```txt
fastapi>=0.115.0          # Framework web
uvicorn>=0.30.0           # Servidor ASGI
pydantic>=2.0.0           # Validación de datos
PyJWT>=2.8.0              # Tokens JWT
python-dotenv>=1.0.0      # Variables de entorno
supabase>=2.0.0           # Cliente de Supabase
langchain>=0.3.0          # Framework LLM
langgraph>=0.2.0          # Motor de agentes
langchain-openai>=0.1.0   # Integración OpenAI
langfuse>=2.0.0,<3.0.0    # Observabilidad
chromadb>=0.5.0           # Base de datos vectorial
```

## 🚀 Quick Start

```bash
# 1. Crear entorno virtual
cd Backend
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate     # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# 4. Aplicar migraciones de base de datos
# Ver docs/deployment/migrations.md

# 5. Iniciar servidor
uvicorn main:app --reload --host 0.0.0.0
```

El servidor estará disponible en `http://localhost:8000`

## 📝 Endpoints Principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/alerts` | Webhook de Alertmanager (crea incidentes) |
| `GET` | `/api/incidents` | Lista todos los incidentes |
| `GET` | `/api/incidents/{id}` | Detalle de un incidente |
| `PATCH` | `/api/incidents/{id}/status` | Actualizar estado de incidente |
| `GET` | `/health` | Health check del servicio |

Documentación interactiva: `http://localhost:8000/docs` (Swagger UI)

## 🔐 Autenticación

El backend utiliza **JWT de Supabase** para autenticación:

```http
Authorization: Bearer <supabase_jwt_token>
```

Los tokens son validados usando `SUPABASE_JWT_SECRET` con algoritmo `HS256`.

## 📂 Estructura del Proyecto

```
Backend/
├── main.py                    # Punto de entrada FastAPI
├── requirements.txt           # Dependencias Python
├── .env                       # Variables de entorno (NO COMMITEAR)
├── .env.example              # Plantilla de variables de entorno
│
├── auth.py                   # Middleware de autenticación JWT
│
├── db/
│   ├── supabase_client.py    # Cliente singleton de Supabase
│   └── migrations/           # Scripts SQL de migraciones
│       ├── README.md
│       └── 001_add_agent_columns.sql
│
├── models/
│   └── incident.py           # Schemas Pydantic (IncidentCreate, IncidentResponse)
│
├── routers/
│   ├── alerts.py             # POST /api/alerts (webhook Alertmanager)
│   └── incidents.py          # CRUD de incidentes
│
├── services/
│   ├── alert_processor.py    # Procesa alertas → crea incidentes
│   └── langgraph_engine.py   # Motor LangGraph (Labs 1 y 2)
│
├── scripts/
│   ├── setup_env.ps1         # Script de configuración de entorno
│   ├── run_migrations.py     # Ejecutor de migraciones
│   └── seed_chromadb.py      # Carga inicial de runbooks
│
└── docs/                     # Documentación técnica
    ├── 01-installation.md
    ├── 02-configuration.md
    ├── architecture/
    ├── api/
    ├── testing/
    ├── development/
    ├── deployment/
    └── observability/
```

## 🤝 Contribución

Lee la [Guía de Contribución](./docs/development/contributing.md) para conocer el proceso de desarrollo y estándares del proyecto.

## 📄 Licencia

Este proyecto es parte del Proyecto Integrador 2 de EAFIT en colaboración con SoftServe.

## 👥 Equipo

- **Product Owner**: Leon Daniel Jaramillo (SoftServe)
- **Scrum Master**: Nicolas Rico Montesino
- **Developers**: Santiago Alvares, Thomas Osorio, Alejandro Rendon
- **UX/UI**: Jacobo Montes
- **Tester**: Nicol Garcia

## 🔗 Enlaces Útiles

- [Repositorio GitHub](https://github.com/nicolas344/Sentinel-SoftServe)
- [Backlog del Proyecto](https://github.com/users/nicolas344/projects/3)
- [Wiki del Proyecto](https://github.com/nicolas344/Sentinel-SoftServe/wiki)
- [Documentación de Frontend](../Frontend/README.md)
