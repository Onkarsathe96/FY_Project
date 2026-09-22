# Merged Cloud FinOps Projects

This folder keeps both applications intact and adds a single launcher.

## Run both dashboards on one port

From this folder:

```powershell
python run.py
```

Open <http://127.0.0.1:8000/> and select which dashboard to open. Each dashboard
is displayed separately. Direct links are:

- <http://127.0.0.1:8000/cost-optimization/>
- <http://127.0.0.1:8000/cloudoptima/>

The launcher starts the original applications on internal ports `8101` and
`8102`, then proxies them through port `8000`. Their original API routes remain
available, so no dashboard feature or endpoint has been removed.

Each project uses its existing `venv` when present. If a virtual environment is
not present, install that project's `requirements.txt` first.

When running with Python on Windows, the launcher automatically changes the
cost project's Docker database hostname from `db` to `127.0.0.1`. Start the
database container first if PostgreSQL is not installed locally:

```powershell
cd Cloud_Cost_Prediction_And_Optimization
docker compose up -d db
cd ..
python run.py --port 8080
```

The database must be available on port `5432`; the dashboard port can be
different, such as `8080`.

## Run only one project

```powershell
python run.py --project cost
python run.py --project optima
```

Both commands expose the selected original application on port `8000`. A
different public port can be selected with `--port`, for example:

```powershell
python run.py --project merged --port 8080
```

The original project folders and their existing startup commands are still
usable independently.
