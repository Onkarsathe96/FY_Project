# Cloud Cost Prediction and Optimization

Cloud Cost Prediction and Optimization is a multi-cloud FinOps application. It
collects cloud billing data, stores it in a common format, finds idle resources,
predicts future costs, detects unusual spending, and provides a controlled way
to stop or delete resources after explicit approval.

The project supports **AWS, Microsoft Azure, and Google Cloud Platform (GCP)**.
It also includes deterministic sample data, so the complete application can be
demonstrated without connecting to a real cloud account.

## What the project does

The application follows this workflow:

1. Select one or more cloud providers.
2. Ingest daily cost data and optional idle-resource data.
3. Normalize provider-specific responses into one internal data model.
4. Save accounts, costs, resources, forecasts, anomalies, and actions in
   PostgreSQL.
5. Run cost analysis:
   - forecast upcoming daily costs;
   - identify costs above a calculated upper threshold.
6. Review results in the browser dashboard or through the REST API.
7. Remediate an idle or stopped resource only after a user sends
   `approved: true`.
8. Keep a permanent remediation log containing the action, result, requester,
   and any error.

## Main features

- Multi-cloud cost ingestion for AWS, Azure, and GCP.
- Provider-neutral adapter interface that keeps cloud SDK code isolated.
- Local sample mode for development and testing.
- Daily cost records grouped by provider, service, region, and currency.
- Cost forecasting with Prophet when enough history is available.
- Linear-trend forecasting fallback when Prophet is unavailable or disabled.
- Rolling upper-bound anomaly detection with `high` and `critical` severity.
- Detection of stopped EC2 instances, unattached EBS volumes, and empty S3
  buckets in AWS; deallocated VMs and unattached managed disks in Azure; and
  stopped VMs and unattached persistent disks in GCP.
- Approval-controlled `stop` and `delete` remediation actions. Empty S3
  buckets, EBS volumes, managed disks, and persistent disks expose delete only.
- Audit logging for successful and failed remediation requests.
- FastAPI OpenAPI documentation.
- Light HTML/CSS/JavaScript dashboard served directly by FastAPI for
  synchronization, analysis, visualization, and remediation.
- PostgreSQL database with SQLAlchemy models and Alembic migrations.
- Terraform sandbox modules for AWS, Azure, and GCP networking.

## Technology stack

### Backend

- **Python 3.13** - application language.
- **FastAPI** - REST API framework and request validation.
- **Uvicorn** - ASGI server.
- **Pydantic and pydantic-settings** - typed API schemas and environment
  configuration.
- **SQLAlchemy 2** - ORM and database access.
- **Alembic** - database schema migrations.
- **PostgreSQL 16** - persistent relational database.

### Cloud integrations

- **boto3** - AWS STS, Cost Explorer, and EC2.
- **azure-identity** - Azure credential discovery through
  `DefaultAzureCredential`.
- **azure-mgmt-costmanagement** - Azure cost queries.
- **azure-mgmt-compute** - Azure VM discovery and actions.
- **google-cloud-bigquery** - GCP Billing Export queries.
- **google-cloud-compute** - GCP Compute Engine discovery and actions.

### Analytics and user interface

- **Prophet** - daily time-series forecasting with weekly seasonality.
- **pandas** - data preparation for Prophet.
- **Python statistics and Decimal** - fallback forecasting, thresholds, and
  currency-safe calculations.
- **HTML, CSS, and vanilla JavaScript** - responsive browser dashboard.

### Infrastructure and quality

- **Docker and Docker Compose** - local API and PostgreSQL orchestration.
- **Terraform 1.6+** - optional provider sandbox infrastructure.
- **pytest** - automated tests.
- **httpx** - HTTP testing support.

## Architecture

```text
Cloud providers
    |
    +--> AWSAdapter
    +--> AzureAdapter
    +--> GCPAdapter
    +--> SampleAdapter
              |
              v
       Normalized provider records
              |
              v
 FastAPI routes -> services -> SQLAlchemy -> PostgreSQL
       |             |             |
       |             |             +--> accounts, costs, resources
       |             |             +--> forecasts, anomalies, remediation logs
       |             |
       |             +--> ingestion, analytics, remediation
       |
       +--> HTML/CSS/JavaScript dashboard
```

The provider adapters implement the same `CloudAdapter` contract. Each adapter
returns `ProviderCostRecord` and `ProviderResource` objects, so the rest of the
application does not need provider-specific logic.

## Repository structure

```text
.
├── app/
│   ├── adapters/          # AWS, Azure, GCP, and sample provider adapters
│   ├── api/
│   │   ├── routes/        # health, ingestion, analysis, remediation routes
│   │   └── router.py      # API route registration
│   ├── core/              # application settings
│   ├── db/                # SQLAlchemy engine, sessions, and base model
│   ├── models/            # database entities and enums
│   ├── schemas/           # Pydantic request and response models
│   ├── services/          # ingestion, analytics, and remediation logic
│   └── main.py            # FastAPI application entry point
├── dashboard/
│   ├── index.html          # Browser dashboard shell
│   ├── style.css           # Light-theme dashboard styles
│   └── app.js              # Dashboard API interactions and charts
├── alembic/
│   ├── env.py
│   └── versions/          # database migration history
├── infra/terraform/       # optional cloud sandbox infrastructure
├── tests/                 # pytest test suite
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Requirements

Choose one of these setup styles:

- Python 3.13 and PostgreSQL 16 installed locally; or
- Python 3.13 and Docker Desktop, using Docker Compose for PostgreSQL and the
  API.

For real cloud ingestion, also configure the credentials for the provider you
want to use. Sample mode does not require any cloud credentials.

## Local setup on Windows

### 1. Create and activate a virtual environment

```powershell
cd D:\FinalYearProject\Cloud_Cost_Prediction_And_Optimization
py -3.13 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### 2. Configure environment variables

```powershell
Copy-Item .env.example .env
```

For a locally installed PostgreSQL server, set `DATABASE_URL` in `.env` to a
valid SQLAlchemy URL, for example:

```text
postgresql+psycopg://cloud_cost_prediction_and_optimization:password@localhost:5432/cloud_cost_prediction_and_optimization
```

When using the supplied Docker Compose file, use `db` instead of `localhost`:

```text
postgresql+psycopg://cloud_cost_prediction_and_optimization:cloud_cost_prediction_and_optimization@db:5432/cloud_cost_prediction_and_optimization
```

### 3. Create or migrate the database

For a normal deployment, apply the Alembic migrations:

```powershell
.\venv\Scripts\alembic.exe upgrade head
```

For local development, the FastAPI lifespan also calls
`Base.metadata.create_all()`. Migrations are still recommended because they
track schema changes and are the repeatable deployment method.

### 4. Start the API

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API is available at:

- Health check: <http://localhost:8000/api/v1/health>
- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

### 5. Open the dashboard

The FastAPI service serves the HTML/CSS/JavaScript dashboard at
<http://localhost:8000/>. Start the API, then open that URL in a browser.

## Docker Compose setup

Docker Compose starts PostgreSQL and the FastAPI service, including the browser
dashboard:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The API and dashboard are then available at <http://localhost:8000/>.

To stop the services:

```powershell
docker compose down
```

To also remove the local PostgreSQL volume and its data:

```powershell
docker compose down -v
```

Do not use the `-v` option if the database data must be preserved.

## Sample-data walkthrough

Sample mode is the safest way to verify the application without cloud
credentials. It produces repeatable cost data for all three providers and one
idle resource per provider.

### Ingest sample data

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/ingestion/sync `
  -ContentType "application/json" `
  -Body '{"providers":["aws","azure","gcp"],"include_resources":true,"use_sample_data":true}'
```

If dates are omitted, the API uses a seven-day window ending tomorrow. Both
`start_date` and `end_date` must be supplied together when overriding it.

### Run forecasting and anomaly analysis

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/analysis/run `
  -ContentType "application/json" `
  -Body '{"providers":["aws","azure","gcp"],"forecast_days":7,"prefer_prophet":false}'
```

Use `"prefer_prophet": true` to try Prophet first. A series needs at least
three days of history. The Prophet model is used when it has at least seven
observations and its dependencies work; otherwise the linear trend fallback is
used.

### Review resources and logs

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/ingestion/costs
Invoke-RestMethod http://localhost:8000/api/v1/remediation/resources
Invoke-RestMethod http://localhost:8000/api/v1/analysis/forecasts
Invoke-RestMethod http://localhost:8000/api/v1/analysis/anomalies
Invoke-RestMethod http://localhost:8000/api/v1/remediation/logs
```

### Test a simulated remediation

1. Ingest sample data.
2. Read `/api/v1/remediation/resources` and copy the returned resource UUID.
3. Submit an approved action:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/remediation/resources/RESOURCE_UUID" `
  -ContentType "application/json" `
  -Body '{"action":"stop","approved":true,"requested_by":"demo-user"}'
```

Sample accounts end with `-sample`, so remediation is simulated and does not
change a real cloud resource. The resource is still updated to `stopped`, and
the action is written to the remediation log.

## REST API

All routes below are prefixed with `/api/v1`.

### System

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Returns service status and environment. |

### Ingestion

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/ingestion/connectivity/aws` | Validates AWS credentials through STS without returning secrets. |
| `POST` | `/ingestion/sync` | Fetches and stores costs and optional idle resources. |
| `GET` | `/ingestion/accounts` | Lists normalized cloud accounts. |
| `GET` | `/ingestion/costs` | Lists cost records with provider/date filters. |
| `GET` | `/ingestion/resources` | Lists stored resources. |

`POST /ingestion/sync` accepts:

```json
{
  "providers": ["aws", "azure", "gcp"],
  "start_date": "2026-09-01",
  "end_date": "2026-09-08",
  "include_resources": true,
  "use_sample_data": false
}
```

Provider failures are recorded in that provider's result and do not stop other
selected providers from being processed.

### Analysis

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/analysis/run` | Creates forecasts and detects anomalies. |
| `GET` | `/analysis/forecasts` | Lists stored forecast points. |
| `GET` | `/analysis/anomalies` | Lists stored cost anomalies. |

### Remediation

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/remediation/resources` | Lists only idle or stopped candidates. |
| `POST` | `/remediation/resources/{resource_id}` | Executes an approved `stop` or `delete`. |
| `GET` | `/remediation/logs` | Lists the remediation audit trail. |

Remediation is intentionally restrictive:

- `approved` must be exactly `true`;
- only `stop` and `delete` are accepted;
- the resource must exist;
- the resource must currently be idle or stopped;
- provider failures are persisted as failed logs and returned as an error.

## Cloud provider implementation

### AWS

- Cost data comes from Cost Explorer `get_cost_and_usage`.
- Costs are grouped daily by `SERVICE` and `REGION`, using the
  `UnblendedCost` metric.
- AWS STS is used for the connectivity check.
- Stopped EC2 instances and unattached EBS volumes are candidates.
- EC2 instances can be stopped or terminated.
- Unattached EBS volumes can be deleted.
- Credentials can come from the AWS profile or the normal boto3 environment
  credential chain.

### Azure

- Cost data comes from Azure Cost Management `ActualCost` queries.
- Costs are grouped daily by service name and resource location.
- `DefaultAzureCredential` is used for authentication.
- Deallocated or stopped virtual machines are candidates.
- VMs can be deallocated or deleted.

### GCP

- Cost data is read from a BigQuery Billing Export table.
- The query groups by date, service, region, and currency.
- Terminated, stopping, or suspended zonal Compute Engine instances are
  candidates.
- Instances can be stopped or deleted.
- The billing export table must be supplied as a fully qualified BigQuery table
  name.

## Configuration

The main settings are loaded from environment variables or `.env`:

| Variable | Meaning |
| --- | --- |
| `APP_NAME` | Application display name. |
| `APP_ENV` | Environment label such as `development`. |
| `API_V1_PREFIX` | API route prefix; defaults to `/api/v1`. |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection URL. |
| `LOG_LEVEL` | Logging level configuration. |
| `AWS_PROFILE` | Optional AWS named profile. |
| `AWS_REGION` | AWS region used for SDK operations. |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription used for cost and VM operations. |
| `GCP_PROJECT_ID` | GCP project used for BigQuery and Compute Engine. |
| `GCP_BILLING_EXPORT_TABLE` | Fully qualified GCP Billing Export table. |

Never commit `.env`, cloud credential files, private keys, or Terraform state
containing secrets.

## Database design

The application stores:

- `cloud_accounts` - provider and external account identity.
- `cost_records` - normalized daily service costs.
- `cloud_resources` - normalized resources, status, tags, and metadata.
- `cost_forecasts` - predicted amount and lower/upper bounds.
- `cost_anomalies` - actual amount, expected amount, threshold, severity, and
  explanation.
- `remediation_logs` - requested action, approval result, provider response,
  status, and timestamps.

Cost and resource data are linked to an account. Resource identifiers are unique
within an account. Forecasts and anomalies are regenerated for the selected
accounts each time analysis runs.

## Analytics implementation

### Preprocessing

Records are grouped by account, service, region, and currency. Multiple records
on the same day are added together. Missing dates between the first and last
observation are filled with zero, creating a continuous daily series.

### Forecasting

The preferred model is Prophet with weekly seasonality. It requires at least
seven observations. If Prophet is not selected, does not have enough history,
or raises a supported runtime/import/value error, the service uses a linear
trend model. Forecast values are never below zero and include an uncertainty
interval.

### Anomaly detection

For each daily series, the service compares a new value with the mean and
population standard deviation of earlier values. The upper threshold is the
largest of:

- mean plus `1.96 * standard deviation`;
- `125%` of the mean;
- `0.01` minimum threshold.

Values above the threshold are stored as anomalies. A value at least twice the
threshold is marked `critical`; other anomalies are marked `high`.

## Terraform sandbox

`infra/terraform` contains optional, sandbox-only modules for AWS, Azure, and
GCP. All providers and compute resources are disabled by default. Networking is
tagged and designed not to expose inbound internet access by default.

Prerequisites:

- Terraform 1.6 or later.
- Authenticated provider CLI/session.

Safe workflow:

```powershell
cd D:\FinalYearProject\Cloud_Cost_Prediction_And_Optimization\infra\terraform
# Review and edit terraform.tfvars before enabling a provider.
terraform init
terraform fmt -recursive -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

Enable only the provider being tested in `terraform.tfvars`. Compute creation
is separately disabled by default because it can create billable resources.
Review the plan before applying it. When finished, use a reviewed destroy plan:

```powershell
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Never apply this sandbox configuration to a production Terraform workspace.

## Testing

Run the test suite from the project root:

```powershell
.\venv\Scripts\python.exe -m pytest
```

The tests cover:

- provider adapter registry behavior;
- deterministic sample cost and resource generation;
- default ingestion window validation;
- cost aggregation and gap filling;
- linear forecasting;
- anomaly detection severity;
- health endpoint behavior;
- sample remediation action validation.

## Operational notes and limitations

- The default ingestion window is seven days. The dashboard may request a
  larger window for its views.
- The current AWS cost query stores cost amounts, not AWS `UsageQuantity`.
  Dashboard usage charts therefore use billing-record counts as a usage proxy.
- Forecasting quality depends on the amount and regularity of historical data.
- Provider SDK credentials and permissions must be configured outside this
  project.
- Real remediation can stop, terminate, delete, deallocate, or delete cloud
  resources and may cause data loss or service interruption. Always review the
  resource, action, and audit log before approving.
- The local `create_all` startup convenience is useful for development, but
  production deployments should run `alembic upgrade head` explicitly.

## License

No license file is currently included in the repository. Add an appropriate
license before distributing the project outside its intended academic or
internal use.
