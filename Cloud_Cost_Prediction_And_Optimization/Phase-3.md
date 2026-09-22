# Phase 3 — Multi-Cloud Data Ingestion and API

## Purpose

Phase 3 adds the data-collection layer of **Cloud_Cost_Prediction_And_Optimization**. It retrieves (or simulates) daily cloud-cost data and idle-resource candidates from AWS, Azure, and Google Cloud, stores the normalized results in PostgreSQL, and exposes them through a FastAPI API.

The phase is deliberately **read-only**: it does not stop, delete, resize, or otherwise change cloud resources. Automated remediation belongs to Phase 5.

## What was completed

### 1. Provider-neutral adapter contract

The base adapter now defines a common format for all cloud providers:

- `ProviderCostRecord` represents one normalized daily cost observation: date, service, region, amount, currency, granularity, and dimensions.
- `ProviderResource` represents a discovered cloud resource and its status.
- Each provider implements `collect_costs()`, `find_idle_resources()`, and a placeholder `remediate()` method.

This means downstream code can process AWS, Azure, and GCP information without needing provider-specific database schemas.

### 2. AWS, Azure, and GCP ingestion adapters

| Provider | Cost source | Idle-resource discovery |
| --- | --- | --- |
| AWS | AWS Cost Explorer, grouped daily by service and region | Stopped EC2 instances and unattached EBS volumes across enabled regions |
| Azure | Azure Cost Management usage query, grouped daily by service and location | Virtual machines whose power state is `stopped` or `deallocated` |
| GCP | BigQuery Cloud Billing export table | Compute Engine instances in `TERMINATED`, `STOPPING`, or `SUSPENDED` state |

Cloud SDK imports are lazy. Therefore the API and tests can start without credentials when sample mode is used.

### 3. Local sample-data adapter

A deterministic sample adapter produces safe, predictable records for AWS, Azure, and GCP. It creates two daily service-cost records per provider and one idle-resource candidate per provider. This makes Phase 3 demonstrable without any cloud account, API key, billable resource, or cloud SDK authentication.

### 4. Ingestion service and database persistence

The ingestion service:

1. Creates or reuses one cloud-account entry per provider.
2. Collects cost records for the requested date range.
3. Replaces existing cost rows only for that same account and date range, preventing duplicate imports on a repeat run.
4. Upserts resources using the cloud account plus external resource ID.
5. Returns a separate status, record counts, and errors for each provider, so one provider failure does not hide successful imports from another provider.

The data is persisted through the existing PostgreSQL models from Phase 1: `CloudAccount`, `CostRecord`, and `CloudResource`.

### 5. FastAPI endpoints

The Phase 3 router is exposed below the existing API prefix (`/api/v1`):

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/ingestion/sync` | Import costs and optionally resource candidates for one or more providers |
| `GET` | `/api/v1/ingestion/accounts` | List imported cloud accounts; optional `provider` filter |
| `GET` | `/api/v1/ingestion/costs` | List stored cost observations; supports provider, date, and limit filters |
| `GET` | `/api/v1/ingestion/resources` | List stored discovered resources; supports provider and limit filters |
| `GET` | `/api/v1/health` | Existing health check from Phase 1 |

Interactive OpenAPI documentation is available at `http://localhost:8000/docs` while the stack is running.

## Files and folders included in Phase 3

| Path | Phase 3 responsibility |
| --- | --- |
| `app/adapters/base.py` | Provider-independent cost and resource data contracts |
| `app/adapters/aws.py` | AWS Cost Explorer and EC2/EBS discovery adapter |
| `app/adapters/azure.py` | Azure Cost Management and VM discovery adapter |
| `app/adapters/gcp.py` | GCP BigQuery billing-export and Compute discovery adapter |
| `app/adapters/sample.py` | Credential-free deterministic test/demo data |
| `app/adapters/_placeholder.py` | Safe default behavior for unsupported adapter operations |
| `app/adapters/registry.py` | Existing provider-to-adapter registry used by ingestion |
| `app/services/ingestion.py` | Orchestration, validation, deduplication, persistence, and provider-level results |
| `app/schemas/ingestion.py` | Request and response validation schemas |
| `app/api/routes/ingestion.py` | Phase 3 REST endpoints |
| `app/api/router.py` | Registers the ingestion router in the API application |
| `.env.example` | Documents optional AWS, Azure, and GCP runtime configuration |
| `requirements.txt` | Adds AWS, Azure, and GCP SDK dependencies |
| `tests/test_ingestion.py` | Unit tests for sample data and ingestion date-window behavior |
| `tests/test_health.py` | Updated health-route test compatible with the current router setup |

Phase 1 database models, database session handling, migrations, Docker files, and the health route remain prerequisites and are reused by this phase.

## How Phase 3 works

```text
POST /api/v1/ingestion/sync
          |
          v
Select sample adapter or AWS / Azure / GCP adapter
          |
          v
Collect normalized daily costs + idle-resource candidates
          |
          v
Ingestion service validates, replaces date-range costs, and upserts resources
          |
          v
PostgreSQL: cloud_accounts, cost_records, cloud_resources
          |
          v
GET ingestion endpoints (and Phase 4/5 features later)
```

## Prerequisites

- Docker Desktop, with Docker Compose available.
- The project checkout at `D:\FinalYearProject\Cloud_Cost_Prediction_And_Optimization`.
- For local sample mode: no cloud credentials are required.
- For live-cloud mode: provider SDK dependencies and read-only credentials as described below.

## Run Phase 3 with sample data (recommended first run)

This route verifies the complete application, API, PostgreSQL persistence, and data flow without contacting a cloud provider.

1. Open PowerShell in the project directory:

   ```powershell
   cd D:\FinalYearProject\Cloud_Cost_Prediction_And_Optimization
   ```

2. Build and start the API and PostgreSQL services:

   ```powershell
   docker compose up --build
   ```

3. Open the interactive API page:

   ```text
   http://localhost:8000/docs
   ```

4. In Swagger UI, open `POST /api/v1/ingestion/sync`, select **Try it out**, and submit:

   ```json
   {
     "providers": ["aws", "azure", "gcp"],
     "start_date": "2026-09-01",
     "end_date": "2026-09-05",
     "include_resources": true,
     "use_sample_data": true
   }
   ```

   `start_date` is inclusive and `end_date` is exclusive. The example therefore imports four days: September 1 through September 4.

5. Confirm the response shows each provider with `status: "success"`. Then use:

   ```text
   GET /api/v1/ingestion/accounts
   GET /api/v1/ingestion/costs
   GET /api/v1/ingestion/resources
   ```

   You can filter, for example, with `?provider=aws` or `?start_date=2026-09-01&end_date=2026-09-05`.

### Equivalent PowerShell request

With the services running, the sync request can also be submitted from another PowerShell window:

```powershell
$body = @{
  providers = @("aws", "azure", "gcp")
  start_date = "2026-09-01"
  end_date = "2026-09-05"
  include_resources = $true
  use_sample_data = $true
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/ingestion/sync" `
  -ContentType "application/json" `
  -Body $body
```

To stop the stack, press `Ctrl+C` in the terminal running Compose. To remove the containers while preserving the database volume, run `docker compose down`.

## Run against real cloud accounts

Use this only after sample mode succeeds. Real ingestion reads billing and resource metadata, and needs cloud-provider permissions. It does not modify resources.

1. Install the added SDK dependencies if running outside Docker:

   ```powershell
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set only the provider variables you need. Do not commit `.env` or credentials.

   ```text
   AWS_PROFILE=your-aws-profile
   AWS_REGION=us-east-1
   AZURE_SUBSCRIPTION_ID=your-azure-subscription-id
   GCP_PROJECT_ID=your-gcp-project-id
   GCP_BILLING_EXPORT_TABLE=project.dataset.table
   ```

3. Authenticate using the normal provider mechanisms:

   - **AWS:** an AWS CLI profile, environment credentials, or an IAM role with Cost Explorer read access plus EC2 describe permissions.
   - **Azure:** `DefaultAzureCredential` (for example, `az login` locally) with Cost Management Reader and virtual-machine read access for the selected subscription.
   - **GCP:** Application Default Credentials (for example, `gcloud auth application-default login` locally), BigQuery access to the billing-export table, and Compute Viewer access.

4. Start the stack as above and submit the same endpoint with `use_sample_data` set to `false`:

   ```json
   {
     "providers": ["aws"],
     "start_date": "2026-09-01",
     "end_date": "2026-09-05",
     "include_resources": true,
     "use_sample_data": false
   }
   ```

Start with one provider to validate its permissions and billing setup. The response reports provider-specific errors rather than failing silently.

## Request options

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `providers` | array | AWS, Azure, and GCP | Providers to ingest: `aws`, `azure`, `gcp` |
| `start_date` | ISO date | Seven-day window if both dates are omitted | First day included in the import |
| `end_date` | ISO date | Seven-day window if both dates are omitted | First day excluded from the import |
| `include_resources` | boolean | `true` | Whether idle-resource discovery is performed |
| `use_sample_data` | boolean | `false` | Uses deterministic local records instead of real cloud APIs |

Provide both `start_date` and `end_date`, or omit both. A request with only one date is rejected.

## Testing and verification performed

The Phase 3 code was checked with:

```powershell
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe -m compileall app
```

Result: **8 tests passed**. The checks cover the health endpoint, sample-adapter costs, sample idle-resource discovery, and the default seven-day ingestion window. Live AWS, Azure, and GCP calls require the account credentials and permissions described above, so they must be validated in the target cloud environment.

## Scope boundaries and next phase

Phase 3 collects, normalizes, stores, and serves cost/resource information. It does **not** yet:

- Forecast future cost.
- Detect anomalies.
- Produce optimization recommendations.
- Execute remediation actions.
- Schedule background ingestion.

Phase 4 will use the stored cost history for preprocessing, forecasting, and anomaly detection. Phase 5 will add dashboard and controlled remediation workflows.
