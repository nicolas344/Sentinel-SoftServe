# Framework multiagente de Sentinel

Cada dominio de DevOps (contenedores Docker, Kubernetes, Postgres, CI/CD, ...) tiene su propio agente especializado. El **Supervisor** recibe la alerta, la clasifica, elige al especialista y le delega la investigación.

## Estructura

```
services/agents/
├── base.py              # DomainAgent (contrato), IncidentContext, ToolCall
├── registry.py          # register_agent() + find_agent_for(ctx)
├── supervisor.py        # orquestador: clasifica → enruta → investiga → persiste
│
├── memory/
│   ├── chroma_client.py # conexión a ChromaDB (singleton)
│   ├── runbooks.py      # memoria curada (humano escribe, agente lee)
│   └── incidents.py     # memoria episódica (agente escribe y lee)
│
└── docker/              # ← plantilla de un dominio
    ├── agent.py         # class DockerAgent(DomainAgent)
    ├── tools.py         # @tool funciones read-only
    ├── prompt.md        # system prompt
    └── runbooks/        # (opcional) fuentes .md para seed
```

## Ciclo de un incidente

```
Alertmanager / UI
      ↓
routers/alerts.py → BackgroundTask(run_langgraph_engine)
      ↓
langgraph_engine.py → run_triage(IncidentContext)
      ↓
Supervisor
  ├─ 1. Clasifica (LLM → incident_type)
  ├─ 2. Busca agente: registry.find_agent_for(ctx)
  ├─ 3. Agent.investigate(ctx):
  │     ├─ recall_runbooks()         → runbooks-<dominio>
  │     ├─ recall_similar_incidents() → incidents-<dominio>
  │     ├─ LLM + tools (ReAct loop bounded)
  │     └─ devuelve InvestigationResult
  ├─ 4. Agent.remember_incident()    → escribe a incidents-<dominio>
  └─ 5. Actualiza Supabase (agent_reasoning, status=analyzed)
```

## Dos memorias sobre ChromaDB

| Colección | Escrita por | Contenido |
|---|---|---|
| `runbooks-<dominio>` | Humano (`scripts/seed_chromadb.py`) | Conocimiento canónico: cómo resolver X tipo de incidente |
| `incidents-<dominio>` | Agente (automático al cerrar) | Memoria organizacional: casos pasados + qué pasó + qué tools se usaron |

Cuando llega una alerta nueva, el agente consulta **las dos**: runbooks ("¿cómo se maneja este tipo?") + incidents ("¿esto ya pasó antes?").

## Cómo añadir un dominio nuevo

Ej.: queremos un `PostgresAgent`.

### 1. Crear la carpeta `services/agents/postgres/`

```
postgres/
├── __init__.py
├── agent.py
├── tools.py
└── prompt.md
```

### 2. `tools.py` — funciones read-only con `@tool`

```python
from langchain_core.tools import tool

@tool
def pg_stat_activity() -> str:
    """Devuelve las conexiones activas y queries en curso de PostgreSQL."""
    # ... implementación con psycopg / asyncpg, rol read-only ...
    return result
```

### 3. `agent.py` — subclass de `DomainAgent`

```python
from services.agents.base import DomainAgent, IncidentContext, InvestigationResult
from services.agents.registry import register_agent
from services.agents.postgres.tools import all_tools

class PostgresAgent(DomainAgent):
    name = "postgres"

    def matches(self, ctx: IncidentContext) -> bool:
        job = (ctx.labels.get("job") or "").lower()
        return "postgres" in job or "postgres" in ctx.target.lower()

    def tools(self): return all_tools()

    def system_prompt(self):
        return (Path(__file__).parent / "prompt.md").read_text()

    def investigate(self, ctx):
        # mismo patrón que DockerAgent: recall_runbooks + recall_similar_incidents
        # + ReAct loop. Copiar desde docker/agent.py
        ...

register_agent(PostgresAgent())
```

### 4. Registrar el import en `services/agents/__init__.py`

```python
from services.agents.postgres import agent as _postgres_agent  # noqa: F401
```

### 5. Cargar runbooks

Ejecutar un `seed_postgres_runbooks.py` similar al de Docker que cree la colección `runbooks-postgres`.

**Listo.** El Supervisor empieza a enrutar alertas `job=postgres` al nuevo agente sin cambiar ni una línea de su código.

## Reglas para los tools

- **Read-only por defecto.** Ninguna tool modifica estado ni ejecuta DML sin un *approval gate* explícito (se implementará más adelante).
- **Fail-soft.** Si un recurso no está disponible (socket Docker, conexión Postgres), la tool devuelve un string descriptivo — no excepciona — para que el agente siga razonando con lo que ya tiene.
- **Output en string.** LangChain espera strings; serializar dicts como JSON formateado.
- **Timeouts cortos.** Nada debe quedarse esperando más de ~5 s; si no hay respuesta, devolver un mensaje.

## Configuración

| Variable | Default | Uso |
|---|---|---|
| `OPENAI_API_KEY` | — | requerido |
| `OPENAI_MODEL` | `gpt-4o-mini` | modelo del supervisor y los agentes |
| `CHROMA_HOST` | `http://localhost:8001` | ChromaDB HTTP |
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | socket Docker (solo si montado) |
| `LANGFUSE_*` | — | trazabilidad opcional |
