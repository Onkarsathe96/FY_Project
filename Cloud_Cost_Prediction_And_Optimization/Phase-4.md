# Phase 4 — Cost Forecasting and Anomaly Detection

## Purpose

Phase 4 turns the normalized daily cost data collected in Phase 3 into useful FinOps analysis. It prepares daily cost series, predicts future spend, identifies unexpectedly high daily costs, and stores the results so they can be used by the Phase 5 dashboard and optimization workflow.

Phase 4 works with Phase 3 **sample data** and does not require AWS, Azure, or GCP credentials. When live billing data is available later, the same pipeline will analyze it without changing its API.

## What was implemented

### 1. Cost preprocessing

Raw `CostRecord` rows are converted into a consistent daily time series for each unique combination of:

- Cloud account
- Service name
- Region
- Currency

During preprocessing, the service:

1. Sums multiple cost records belonging to the same group and day.
2. Sorts observations by date.
3. Fills dates missing between the first and last observation with a zero-value cost record.
4. Preserves money values at four decimal places.

This produces clean data for forecasting and prevents gaps in billing exports from breaking a time-series calculation.

### 2. Forecasting

Each cost series with at least three days of history receives a configurable number of future daily predictions (seven days by default).

The system supports two forecasting modes:

| Model | When used | Output |
| --- | --- | --- |
| Prophet | `prophet` and its dependencies are installed, at least seven history days exist, and `prefer_prophet` is enabled | Daily prediction with Prophet lower and upper intervals |
| Linear trend fallback | Prophet is unavailable, data has fewer than seven days, or Prophet cannot fit the data | Daily linear-regression prediction with statistically derived bounds |

The fallback is intentional: Phase 4 remains runnable in a clean local environment and with the short sample-data history created in Phase 3.

Every forecast stores:

- Forecast date
- Predicted cost
- Lower and upper bounds
- Service, region, currency, and cloud account
- The model used (`prophet` or `linear_trend_fallback`)

### 3. Upper-bound anomaly detection

An anomaly is detected when a daily actual cost is above an upper threshold calculated only from prior daily costs in that series.

For each eligible day, the detector calculates:

```text
expected cost = average of preceding daily costs
upper bound   = max(expected + 1.96 × standard deviation,
                    expected × 1.25,
                    0.01)
```

If the actual cost is above the upper bound, an anomaly is stored. Its severity is based on how far the actual amount exceeds the threshold:

| Ratio: actual / upper bound | Severity |
| --- | --- |
| At least 2.0 | `critical` |
| At least 1.5 | `high` |
| More than 1.0 | `medium` |

The stored anomaly includes the actual cost, expected cost, upper bound, severity, explanation, and calculation metadata. This method is explainable and avoids using the day being checked as part of its own baseline.

### 4. Analysis persistence

Phase 4 adds two PostgreSQL tables:

| Table | Stores |
| --- | --- |
| `cost_forecasts` | Future daily predictions and confidence bounds |
| `cost_anomalies` | Daily costs that exceeded their calculated upper bound |

When a new analysis run starts, previous forecasts and anomaly results for the selected cloud accounts are replaced. Raw Phase 3 `cost_records` are never changed.

### 5. REST API

Phase 4 adds the following endpoints under the existing `/api/v1` prefix:

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/analysis/run` | Run forecasting and anomaly detection for selected providers |
| `GET` | `/api/v1/analysis/forecasts` | List stored forecast values |
| `GET` | `/api/v1/analysis/anomalies` | List detected anomalies |

All endpoints are available through Swagger UI while the app runs:

```text
http://localhost:8000/docs
```

## Phase 4 files and folders

| Path | Responsibility |
| --- | --- |
| `app/services/analytics.py` | Preprocessing, fallback forecasting, optional Prophet integration, anomaly detection, and persistence orchestration |
| `app/models/forecast.py` | SQLAlchemy `CostForecast` model for future cost predictions |
| `app/models/anomaly.py` | SQLAlchemy `CostAnomaly` model for detected spend anomalies |
| `app/models/__init__.py` | Registers Phase 4 database models with SQLAlchemy |
| `app/schemas/analysis.py` | Request and response schemas for analysis APIs |
| `app/api/routes/analysis.py` | `POST /analysis/run` and result-listing routes |
| `app/api/router.py` | Registers the analysis router |
| `alembic/versions/20260905_0002_phase4_analysis.py` | Database migration for `cost_forecasts` and `cost_anomalies` |
| `tests/test_analytics.py` | Tests for aggregation, missing dates, fallback forecasting, and anomaly detection |
| `requirements.txt` | Adds optional `prophet` forecasting dependency |

Phase 4 also uses these earlier-phase components:

| Existing path | Why Phase 4 needs it |
| --- | --- |
| `app/models/cost_record.py` | Supplies normalized historical daily costs from Phase 3 |
| `app/models/cloud_account.py` | Associates forecasts and anomalies with a cloud provider/account |
| `app/api/routes/ingestion.py` | Imports sample or live cost data before an analysis run |
| `app/services/ingestion.py` | Persists Phase 3 source cost records |

## Processing flow

```text
Phase 3 cost_records
        |
        v
Group by account + service + region + currency
        |
        v
Aggregate daily amounts and fill missing dates with zero
        |
        +---------------------------+
        |                           |
        v                           v
Forecast next N days          Compare actuals with
(Prophet or fallback)         prior-history upper bounds
        |                           |
        v                           v
cost_forecasts                 cost_anomalies
        \                           /
         \                         /
          v                       v
       GET analysis API endpoints
```

## Prerequisites

- Docker Desktop and Docker Compose for the containerized run, or Python virtual environment configured in Phase 1.
- PostgreSQL started through the project Docker Compose stack.
- Phase 3 sample data or real cloud cost data already ingested.
- No cloud credential is needed when using Phase 3 sample data.

## Run Phase 4 with sample data

### 1. Open the project folder

```powershell
cd D:\FinalYearProject\Cloud_Cost_Prediction_And_Optimization
```

### 2. Start the application and PostgreSQL

```powershell
docker compose up --build
```

Keep this terminal open. The API will be available on port 8000.

### 3. Apply the Phase 4 database migration

For an existing database created before Phase 4, open a second PowerShell window and run:

```powershell
cd D:\FinalYearProject\Cloud_Cost_Prediction_And_Optimization
.\venv\Scripts\alembic.exe upgrade head
```

For a fresh local database, the application also registers the tables during startup. Using Alembic remains the recommended approach for an existing or deployed database.

### 4. Ingest sample data from Phase 3

Open `http://localhost:8000/docs`. In `POST /api/v1/ingestion/sync`, select **Try it out** and submit:

```json
{
  "providers": ["aws", "azure", "gcp"],
  "start_date": "2026-09-01",
  "end_date": "2026-09-15",
  "include_resources": true,
  "use_sample_data": true
}
```

The end date is exclusive, so this creates fourteen days of sample history. That is enough to demonstrate preprocessing and gives Prophet enough history to attempt a fit when installed.

### 5. Run the analysis

In `POST /api/v1/analysis/run`, submit:

```json
{
  "providers": ["aws", "azure", "gcp"],
  "forecast_days": 7,
  "prefer_prophet": true
}
```

The response reports how many series were analyzed, how many forecasts were created, anomalies detected, and which model was used.

### 6. View results

Use the following Swagger endpoints:

```text
GET /api/v1/analysis/forecasts
GET /api/v1/analysis/anomalies
```

Examples of optional filters:

```text
/api/v1/analysis/forecasts?provider=aws
/api/v1/analysis/forecasts?start_date=2026-09-15&end_date=2026-09-22
/api/v1/analysis/anomalies?provider=gcp
```

## PowerShell API example

With the services running, execute this in another PowerShell window:

```powershell
$body = @{
  providers = @("aws", "azure", "gcp")
  forecast_days = 7
  prefer_prophet = $true
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/analysis/run" `
  -ContentType "application/json" `
  -Body $body
```

Retrieve generated forecasts:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/analysis/forecasts?provider=aws"
```

## API request options

### `POST /api/v1/analysis/run`

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `providers` | array | `aws`, `azure`, `gcp` | Cloud providers whose stored cost data should be analyzed |
| `forecast_days` | integer | `7` | Number of future daily predictions; valid range is 1–90 |
| `prefer_prophet` | boolean | `true` | Uses Prophet when available; otherwise uses the fallback model |

### Result-listing endpoints

Both `GET /analysis/forecasts` and `GET /analysis/anomalies` accept:

| Query parameter | Meaning |
| --- | --- |
| `provider` | Optional provider filter: `aws`, `azure`, or `gcp` |
| `start_date` | Inclusive ISO date filter |
| `end_date` | Exclusive ISO date filter |
| `limit` | Result limit from 1–1000; default 200 |

## Prophet installation

`prophet` has been added to `requirements.txt`. To enable it in the local virtual environment, run:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

If Prophet or its dependencies cannot be installed on the current machine, Phase 4 remains functional. The service automatically returns `linear_trend_fallback` forecasts instead of failing.

## Verification completed

The implementation was validated with:

```powershell
.\venv\Scripts\python.exe -m compileall app
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe -m py_compile alembic\versions\20260905_0002_phase4_analysis.py
```

Result: **11 tests passed**.

The Phase 4 tests verify:

- Same-day costs are aggregated.
- Missing days become zero-value observations.
- The fallback forecaster produces the requested number of future dates and valid bounds.
- A significant daily cost spike is classified as a critical anomaly.

## Scope and current limitations

Phase 4 is an analysis layer. It does not create, stop, resize, or delete cloud resources.

- It needs at least three daily observations in a service series to create a forecast.
- Prophet is optional and requires at least seven daily observations before it is attempted.
- The anomaly threshold is a transparent statistical baseline, not a trained machine-learning anomaly model.
- Analysis results are replaced for the providers selected in each new analysis run; raw cost data remains unchanged.
- Scheduling recurring imports or recurring analysis is not part of Phase 4.

## Next phase

Phase 5 can consume `cost_forecasts` and `cost_anomalies` to provide a Streamlit FinOps dashboard, recommendations, reviewable remediation actions, and controlled one-click remediation endpoints.
