# Cloud_Cost_Prediction_And_Optimization — Phase 1: Platform Foundation

Cloud_Cost_Prediction_And_Optimization (Automated Multi-Cloud Cost Prediction and Optimization) is a FinOps platform for collecting cloud-cost data, forecasting spend, finding waste, and supporting safe remediation. This repository currently implements **Phase 1**: the local application foundation on which later project phases are built.

> Phase 1 is intentionally safe: it does not connect to AWS, Azure, or GCP, collect billing data, predict costs, or make cloud changes.

## What Phase 1 does

Phase 1 provides a repeatable local workspace and core contracts shared by future components.

1. Runs a FastAPI application with generated OpenAPI/Swagger documentation.
2. Starts a PostgreSQL database alongside the API using Docker Compose.
3. Defines a normalized relational model for cloud accounts, resources, cost records, and future remediation audit logs.
4. Supplies an Alembic migration for creating that schema in controlled environments.
5. Defines a provider-neutral adapter interface for AWS, Azure, and GCP.
6. Exposes a health endpoint for people, Docker, and later CI/CD checks.
7. Includes small contract tests for the health route and adapter registry.

### Current request flow

```text
Browser / API client
        |
        v
FastAPI: GET /api/v1/health  --->  { "status": "ok", "environment": "development" }

Future workers (Phase 3+) ---> CloudAdapter contract ---> AWS | Azure | GCP SDKs
                                                |
                                                v
                                           PostgreSQL schema
```

At this stage, provider adapters are placeholders. Calling their collection, discovery, or remediation methods raises `NotImplementedError`; no cloud credentials or resources are required.

## Phase 1 deliverables

| Area | Delivered capability |
| --- | --- |
| API | FastAPI app, versioned `/api/v1` router, `/health` endpoint, Swagger UI |
| Database | SQLAlchemy ORM models and PostgreSQL connection/session setup |
| Schema management | Alembic configuration and initial schema migration |
| Cloud abstraction | One common adapter interface with AWS, Azure, and GCP registrations |
| Local operations | Dockerfile, Docker Compose stack, environment-variable template |
| Quality | Pytest test cases and Python dependency manifest |

## Repository structure and Phase 1 ownership

All source items below are part of Phase 1 unless marked generated. `venv/` is a local Python environment, not application source.

```text
Cloud_Cost_Prediction_And_Optimization/
├── app/                                    # Phase 1 application source
│   ├── main.py                              # FastAPI startup and router registration
│   ├── core/config.py                       # Typed settings from .env/environment
│   ├── db/base.py                           # SQLAlchemy declarative base
│   ├── db/session.py                        # PostgreSQL engine and DB session
│   ├── models/
│   │   ├── enums.py                         # Provider/resource/remediation states
│   │   ├── cloud_account.py                 # Connected account model
│   │   ├── resource.py                      # Normalized resource model
│   │   ├── cost_record.py                   # Daily/hourly cost model
│   │   └── remediation.py                   # Future action audit-log model
│   ├── adapters/
│   │   ├── base.py                          # Provider-neutral CloudAdapter contract
│   │   ├── aws.py                           # AWS adapter placeholder
│   │   ├── azure.py                         # Azure adapter placeholder
│   │   ├── gcp.py                           # GCP adapter placeholder
│   │   └── registry.py                      # Provider-to-adapter lookup
│   ├── api/router.py                        # Versioned route aggregation
│   ├── api/routes/health.py                 # Health endpoint
│   └── schemas/health.py                    # Health response schema
├── alembic/
│   ├── env.py                               # Alembic environment
│   └── versions/20260904_0001_initial_schema.py  # Initial schema migration
├── tests/
│   ├── test_health.py                       # Health route test
│   └── test_adapters.py                     # Registry and safety tests
├── Dockerfile                               # API image definition
├── docker-compose.yml                       # API + PostgreSQL local stack
├── requirements.txt                         # Runtime/test dependencies
├── .env.example                             # Safe configuration template
├── alembic.ini                              # Migration CLI configuration
└── .gitignore                               # Ignores secrets, virtualenvs, caches
```

`__pycache__/` folders and the `postgres_data` Docker volume are generated at runtime and are not Phase 1 source code.

## Database design

```text
cloud_accounts (1) ──< cloud_resources
       |
       └────────────< cost_records

cloud_resources (1) ──< remediation_logs
```

| Table | Purpose | Important fields |
| --- | --- | --- |
| `cloud_accounts` | Connected provider account/project/subscription | provider, external account ID, display name |
| `cloud_resources` | Discovered compute, storage, and other cloud assets | resource ID/type, region, state, tags, estimated cost, idle reason |
| `cost_records` | Normalized granular usage charges for later analytics | date, service, region, amount, currency, dimensions |
| `remediation_logs` | Audit record of requested and completed actions | resource, action, status, requester, provider response/error |

The initial migration enforces unique provider-account and account-resource combinations, preventing duplicate imported identities.

## Prerequisites

Use either of the following:

- **Recommended:** Docker Desktop with Docker Compose v2.
- **Alternative:** Python 3.13+ and a reachable PostgreSQL 16+ database.

For tests or direct Python execution, install the packages in `requirements.txt` into a Python virtual environment.

## Run Phase 1 with Docker (recommended)

From the project root in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Docker Compose will create the local PostgreSQL volume, start PostgreSQL on port `5432`, wait for its health check, build the API image, start FastAPI on port `8000`, and create the Phase 1 tables for local development.

Open these URLs after startup:

| URL | Result |
| --- | --- |
| `http://localhost:8000/docs` | Interactive Swagger/OpenAPI documentation |
| `http://localhost:8000/api/v1/health` | `{"status":"ok","environment":"development"}` |
| `http://localhost:8000/openapi.json` | OpenAPI specification JSON |

Stop the foreground stack with `Ctrl+C`. To stop containers while preserving local database data:

```powershell
docker compose down
```

## Run without Docker

1. Ensure PostgreSQL is running and create an empty `cloud_cost_prediction_and_optimization` database/user, or point `DATABASE_URL` to an existing development database.
2. Create and activate a virtual environment:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies and create local configuration:

   ```powershell
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

4. Edit `.env`, changing the Docker hostname `db` to `localhost`:

   ```dotenv
   DATABASE_URL=postgresql+psycopg://cloud_cost_prediction_and_optimization:cloud_cost_prediction_and_optimization@localhost:5432/cloud_cost_prediction_and_optimization
   ```

5. Apply the migration and start the API:

   ```powershell
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

For a production-like environment, always run `alembic upgrade head`; automatic table creation is a local-development convenience only.

## Configuration

Copy `.env.example` to `.env`. Never commit `.env`, because later phases will use credentials and secrets.

| Variable | Default / example | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Cloud_Cost_Prediction_And_Optimization` | API title shown in Swagger |
| `APP_ENV` | `development` | Deployment environment reported by health check |
| `API_V1_PREFIX` | `/api/v1` | Prefix for versioned API routes |
| `DATABASE_URL` | `postgresql+psycopg://...` | SQLAlchemy PostgreSQL connection string |
| `POSTGRES_DB` | `cloud_cost_prediction_and_optimization` | Database used by Docker Compose |
| `POSTGRES_USER` | `cloud_cost_prediction_and_optimization` | Docker Compose PostgreSQL user |
| `POSTGRES_PASSWORD` | `cloud_cost_prediction_and_optimization` | Local-development PostgreSQL password |
| `LOG_LEVEL` | `INFO` | Reserved for application logging configuration |

## Validate Phase 1

After dependencies are installed:

```powershell
python -m pytest -q
```

Syntax can be checked without installing dependencies:

```powershell
.\venv\Scripts\python.exe -m compileall -q app tests alembic
```

Expected checks:

- `GET /api/v1/health` returns HTTP 200 with `status: ok`.
- The adapter registry returns the matching AWS, Azure, or GCP adapter.
- Adapter remediation is unavailable and raises `NotImplementedError`.
- PostgreSQL contains `cloud_accounts`, `cloud_resources`, `cost_records`, and `remediation_logs` after startup or migration.

## Explicitly not included yet

| Future phase | Planned work |
| --- | --- |
| Phase 2 | Terraform sandbox infrastructure for AWS, Azure, and GCP |
| Phase 3 | Real provider SDK integrations, batch ingestion, and cost/resource API routes |
| Phase 4 | Preprocessing, Prophet forecasting, and anomaly detection |
| Phase 5 | Streamlit dashboard and approval-controlled one-click remediation |
| Phase 6 | Jenkins CI/CD, integration tests, deployment automation, documentation |

## Security notes

- Do not commit cloud keys, service-account JSON, or provider tokens.
- Phase 1 makes no cloud calls by design.
- Future adapters should use workload identity or least-privilege credentials and require an explicit remediation approval workflow.
## Phase 5 dashboard

Phase 5 adds the HTML/CSS/JavaScript dashboard in [`dashboard/`](dashboard/)
and approval-controlled remediation endpoints. See [`Phase-5.md`](Phase-5.md) for
the API contract and startup commands.
