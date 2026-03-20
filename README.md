# Sentinel — DevOps Incident Triage Copilot

> An agentic AI co-pilot that assists DevOps/SRE engineers throughout the full incident lifecycle: automatic detection, evidence collection, triage, root cause analysis, and post-incident reporting.

**Universidad EAFIT · Proyecto Integrador 2 · SoftServe**

---

## How it works

```
Docker container crashes
        ↓
cAdvisor detects it → Prometheus fires alert (ContainerCrashed)
        ↓
Alertmanager → POST /api/alerts → FastAPI Backend
        ↓
Backend fetches logs from Loki → creates incident in Supabase
        ↓
LangGraph Engine (background):
  Lab 1 — Alert Intake: classifies incident type with GPT-4o-mini
  Lab 2 — Investigation: RAG over runbooks → root cause + recommended actions
        ↓
React Dashboard updates in real time via Supabase Realtime
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite 7 + Tailwind CSS v4 |
| Backend | FastAPI + Uvicorn |
| AI Agent | LangGraph + OpenAI gpt-4o-mini |
| Knowledge Base | ChromaDB (runbooks RAG) |
| Auth & DB | Supabase (email/password, JWT ES256) |
| Observability | LangFuse v2 (self-hosted) |
| Detection | cAdvisor + Prometheus + Alertmanager |
| Logs | Loki + Promtail |
| Dashboards | Grafana |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- [Node.js 20+](https://nodejs.org/)
- [Python 3.9+](https://www.python.org/)
- A Supabase project (credentials provided by the team)

---

## Setup (first time only)

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

LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3001

LOKI_URL=http://localhost:3100
CHROMA_HOST=http://localhost:8001
```

**Frontend** — create `Frontend/.env.local`:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

### 3. Create the Python virtual environment

```bash
cd Backend
python3 -m venv env
source env/bin/activate      # Windows: env\Scripts\activate
pip install -r requirements.txt
```

### 4. Start the infrastructure stack

```bash
# From the project root
docker compose up -d cadvisor prometheus alertmanager loki promtail grafana langfuse langfuse-db chromadb
```

### 5. Seed ChromaDB with runbooks (one time only)

```bash
cd Backend
source env/bin/activate
python scripts/seed_chromadb.py
```

---

## Running the project

Open **three terminals**:

**Terminal 1 — Backend**
```bash
cd Backend
source env/bin/activate
uvicorn main:app --reload --host 0.0.0.0
# → http://localhost:8000
# → http://localhost:8000/docs (Swagger UI)
```

**Terminal 2 — Frontend**
```bash
cd Frontend
npm install      # first time only
npm run dev
# → http://localhost:5173
```

**Terminal 3 — Infrastructure (already running via Docker)**
```bash
docker compose ps    # verify all services are up
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
| cAdvisor | http://localhost:8080 | — |
| Loki | http://localhost:3100 | — |

---

## Simulate an incident (quick demo)

Run a container that crashes after printing realistic error logs:

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

Wait **~20–30 seconds**. Sentinel will automatically:
1. Detect the crash via Prometheus
2. Fetch the container logs from Loki
3. Create an incident in the dashboard
4. Run the AI agent (Lab 1 + Lab 2) and update the incident with root cause analysis

You can also create incidents manually from the dashboard using the **"Nuevo incidente"** button.

---

## Project Structure

```
Sentinel-SoftServe/
├── docker-compose.yml          # Full infrastructure stack
├── prometheus/                 # Alert rules + scraping config
├── alertmanager/               # Webhook routing to backend
├── loki/ & promtail/           # Log collection
├── Backend/
│   ├── main.py                 # FastAPI app + CORS + routers
│   ├── auth.py                 # JWT validation (ES256/HS256)
│   ├── routers/
│   │   ├── incidents.py        # CRUD endpoints
│   │   └── alerts.py           # Alertmanager webhook
│   ├── services/
│   │   ├── alert_processor.py  # Prometheus alert → Supabase incident
│   │   └── langgraph_engine.py # LangGraph Labs 1 & 2
│   └── scripts/
│       └── seed_chromadb.py    # Load runbooks into ChromaDB
└── Frontend/
    └── src/
        ├── pages/              # Login, Dashboard
        ├── components/         # ProtectedRoute, CreateIncidentModal
        ├── services/           # incidentNotifications.js
        └── contexts/           # AuthContext
```

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
