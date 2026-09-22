# Phase 5: FinOps dashboard and controlled remediation

Phase 5 adds a light-theme HTML/CSS/JavaScript dashboard and approval-controlled
remediation workflow. FastAPI serves the dashboard from `/`.

## API

- `GET /api/v1/ingestion/connectivity/aws` validates AWS credentials through STS
  and returns the account ID, caller ARN, profile, and region (never secrets).
- `GET /api/v1/remediation/resources` lists idle and stopped resources.
- `POST /api/v1/remediation/resources/{resource_id}` executes `stop` or `delete`.
- `GET /api/v1/remediation/logs` lists the audit trail.

Every mutation requires `approved: true`. The service rejects unsupported actions,
missing resources, and resources that are not idle or stopped. Successful actions
update the normalized resource status and persist the provider response; failed
provider calls are persisted as failed remediation logs.

## Provider actions

- AWS: stops/terminates EC2 instances and deletes unattached EBS volumes.
- Azure: deallocates or deletes virtual machines.
- GCP: stops or deletes zonal Compute Engine instances.
- Sample mode: simulates the action without changing cloud state.

## Running the dashboard

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up --build
```

Open <http://localhost:8000/> after the API starts. The dashboard syncs the latest
30-day window, shows billing dates and the AWS
`UnblendedCost` currency unit, service usage and cost rankings, stored forecasts,
anomalies, optimization suggestions, and idle resources. The service usage chart
uses billing-record count as a usage proxy because the current Cost Explorer query
does not ingest `UsageQuantity`. Run the forecast analysis after an AWS sync to
populate the forecast view. If the dashboard reports
`WinError 10061`, the local API is not running or did not start successfully;
check the API logs and confirm the database is healthy.
It intentionally requires a second explicit checkbox confirmation before the
mutation button becomes available.

Use **Sync AWS costs and idle resources** after the connectivity check succeeds.