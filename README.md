# Sentinel — DevOps Incident Triage Copilot

An agentic AI co-pilot that assists DevOps/SRE engineers throughout the full incident lifecycle: automatic detection, evidence collection, triage, root cause analysis, human-in-the-loop action approval, and post-incident reporting.

**Universidad EAFIT · Proyecto Integrador 2 · Client: SoftServe**

Live deployment: https://sentinel-softserve-1.onrender.com

---

## How it works

```
Docker / Podman / Kubernetes / PostgreSQL incident occurs
        |
cAdvisor / postgres-exporter detects it
        |
Prometheus fires alert -> Alertmanager -> POST /api/alerts
        |
Backend fetches logs from Loki, creates incident in Supabase
        |
LangGraph multi-agent engine (background):
  Guardrail Input  — sanitize logs, detect prompt injection
  Lab 1            — Alert Intake: classify incident type (GPT-4o-mini)
  Lab 2            — Investigation: specialist agent + RAG runbooks + tools
  Guardrail Output — validate analysis stays in DevOps domain
  Lab 3            — Decision & Planning: propose safe corrective action
        |
Engineer approves action in Dashboard
        |
  Lab 4            — Action & Verification: execute + verify recovery
  Lab 5            — Post-Incident: generate post-mortem, update episodic memory
        |
React Dashboard updates in real time via Supabase Realtime
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite 7 + Tailwind CSS v4 + shadcn/ui |
| Backend | FastAPI + Uvicorn |
| AI Orchestration | LangGraph + LangChain |
| LLM | OpenAI gpt-4o-mini |
| Knowledge Base | ChromaDB (runbooks RAG + episodic memory) |
| Auth & DB | Supabase (email/password, JWT, Realtime) |
| Agent Observability | LangFuse v2 (self-hosted) |
| Incident Detection | cAdvisor + Prometheus + Alertmanager |
| Logs | Loki + Promtail |
| Dashboards | Grafana |

---

## Supported Runtimes

| Runtime | Agent | Tools |
|---|---|---|
| Docker | DockerAgent | docker_inspect, docker_logs, docker_stats, docker_ps |
| Podman | PodmanAgent | podman_inspect, podman_logs, podman_stats, podman_ps |
| Kubernetes | KubernetesAgent | get_pod_status, describe_pod, get_pod_logs, get_pod_events, get_deployment_status, list_failing_pods |
| PostgreSQL | PostgresAgent | pg_stat_activity, pg_stat_database, pg_stat_replication, pg_locks |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- [Node.js 20+](https://nodejs.org/)
- [Python 3.9+](https://www.python.org/)
- Supabase project credentials (provided by the team)
- OpenAI API key

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/nicolas344/Sentinel-SoftServe.git
cd Sentinel-SoftServe
```

### 2. Configure environment variables

**Backend** — create `Backend/.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3001

LOKI_URL=http://localhost:3100
CHROMA_HOST=http://localhost:8001
PROMETHEUS_URL=http://localhost:9090
```

**Frontend** — create `Frontend/.env.local`:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=http://localhost:8000
```

### 3. Start the infrastructure stack

```bash
docker compose up -d
```

### 4. Set up the backend

```bash
cd Backend
python3 -m venv env
source env/bin/activate      # Windows: env\Scripts\activate
pip install -r requirements.txt
```

### 5. Seed ChromaDB with runbooks (one time only)

```bash
cd Backend
source env/bin/activate
python scripts/seed_chromadb.py          # Docker runbooks
python scripts/seed_postgres_runbooks.py # PostgreSQL runbooks
python scripts/seed_podman_runbooks.py   # Podman runbooks
python scripts/seed_kubernetes_runbooks.py # Kubernetes runbooks
```

---

## Running the project

**Terminal 1 — Backend**
```bash
cd Backend
source env/bin/activate
uvicorn main:app --reload --host 0.0.0.0
# http://localhost:8000
# http://localhost:8000/docs  (Swagger UI)
```

**Terminal 2 — Frontend**
```bash
cd Frontend
npm install   # first time only
npm run dev
# http://localhost:5173
```

---

## Service URLs

| Service | URL | Credentials |
|---|---|---|
| Sentinel Dashboard | http://localhost:5173 | Supabase email/password |
| Backend API | http://localhost:8000 | — |
| API Docs (Swagger) | http://localhost:8000/docs | — |
| Grafana | http://localhost:3000 | admin / sentinel123 |
| Prometheus | http://localhost:9090 | — |
| Alertmanager | http://localhost:9093 | — |
| LangFuse | http://localhost:3001 | local account |
| ChromaDB | http://localhost:8001 | — |

---

## Simulate an incident

```bash
docker run -d --name demo-crash alpine sh -c "
  echo '[INFO] Starting service on port 8080'
  echo '[INFO] Connecting to postgres://db:5432...'
  sleep 5
  echo '[ERROR] Connection pool exhausted after 3 retries'
  sleep 5
  echo '[FATAL] Could not recover connection. Shutting down.'
  exit 1
"
```

Wait 20–30 seconds. Sentinel will automatically detect the crash, fetch logs, classify the incident, investigate with the DockerAgent, and propose a corrective action for your approval.

---

## Project Structure

```
Sentinel-SoftServe/
├── docker-compose.yml
├── prometheus/                     # Alert rules + scraping config
├── alertmanager/                   # Webhook routing to backend
├── loki/ & promtail/               # Log collection config
├── Backend/
│   ├── main.py                     # FastAPI app + CORS + routers
│   ├── auth.py                     # JWT validation (ES256/HS256)
│   ├── routers/
│   │   ├── incidents.py            # Incident CRUD + export + post-mortem
│   │   ├── alerts.py               # Alertmanager webhook
│   │   ├── actions.py              # Execute / reject / postpone actions
│   │   └── health.py               # Integration health check
│   ├── services/
│   │   ├── alert_processor.py      # Alert -> Supabase incident
│   │   ├── verification.py         # Post-action verification
│   │   ├── incident_events.py      # Status transition events
│   │   ├── postmortem/             # Post-mortem generation
│   │   └── agents/
│   │       ├── supervisor.py       # Orchestrates classify -> route -> investigate -> persist
│   │       ├── guardrails.py       # Deterministic safety rules
│   │       ├── guardrail_graph.py  # LangGraph guardrail pipeline
│   │       ├── llm_guardrail.py    # LLM semantic judge
│   │       ├── docker/             # DockerAgent + tools
│   │       ├── podman/             # PodmanAgent + tools
│   │       ├── kubernetes/         # KubernetesAgent + tools
│   │       ├── postgres/           # PostgresAgent + tools
│   │       └── memory/             # ChromaDB runbooks + episodic memory
│   └── scripts/
│       └── seed_*.py               # ChromaDB runbook loaders
└── Frontend/
    └── src/
        ├── pages/                  # Login, Dashboard, Setup
        ├── components/             # IncidentCard, ApprovalBanner, AgentReasoningPanel, ...
        ├── services/               # incidentActions, incidentExports
        └── contexts/               # AuthContext
```

---

## Deployment

The application is deployed on Render:

- Frontend: https://sentinel-softserve-1.onrender.com
- Backend API: https://sentinel-softserve.onrender.com

See the [Deployment Guide](https://github.com/nicolas344/Sentinel-SoftServe/wiki/Deploy) for full instructions.

---

## Team

| Name | GitHub | Role |
|---|---|---|
| Nicolas Rico Montesino | [@nicolas344](https://github.com/nicolas344) | Scrum Master, Developer |
| Leon Daniel Jaramillo | [@leonjaramillo](https://github.com/leonjaramillo) | Product Owner (SoftServe) |
| Santiago Alvares Diaz | [@sxntiagoad](https://github.com/sxntiagoad) | Developer |
| Jacobo Montes Castaño | [@jacoEafit](https://github.com/jacoEafit) | UX/UI |
| Nicol Garcia Tabares | [@nfgarciat](https://github.com/nfgarciat) | Tester |
| Thomas Osorio Zambrano | [@thomaszambrano](https://github.com/thomaszambrano) | Developer |
| Alejandro Rendon Correa | [@arendonc2](https://github.com/arendonc2) | Architect |

---

[Backlog](https://github.com/users/nicolas344/projects/3) · [Wiki](https://github.com/nicolas344/Sentinel-SoftServe/wiki) · [API Docs](https://sentinel-softserve.onrender.com/docs)
