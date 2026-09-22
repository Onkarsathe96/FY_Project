# ⚡ CloudOptima: Cloud Cost Intelligence & Optimization Engine

CloudOptima is an automated FinOps intelligence, cost forecasting, and waste remediation platform built with Python, FastAPI, and Machine Learning. It replaces traditional, reactive billing reviews by ingesting cloud cost and performance telemetry, predicting 30-day spending trends with time-series ML, detecting underutilized infrastructure, and providing safe auto-remediation workflows.

---

## 📌 Features

* **Data Ingestion & Cleaning:** Standardizes multi-service pricing and billing CSVs into structured analytics DataFrames.
* **Time-Series ML Forecasting:** Uses additive models (Facebook Prophet / Ridge Regression) to model weekly cyclical spending and project 30-day future costs with confidence bounds.
* **Waste Detection Engine:** Evaluates compute and storage usage to identify idle EC2 instances ($< 5\%$ average CPU over 14 days), unattached EBS volumes, and orphaned resources.
* **Safety-Gated Remediation:** Policy engine distinguishes non-production assets (safe for auto-cleanup) from production workloads (auto-deletion blocked, alerts dispatched via Webhook/Slack).
* **One-Click Actions:** Asynchronous REST endpoints empower engineering teams to trigger immediate resource cleanup directly from the UI.
* **Interactive Dashboard:** Modern web UI rendered using FastAPI, Jinja2, and Chart.js.
* **100% Offline Capability:** Operates locally on downloaded pricing/usage datasets without requiring live cloud credentials.

---

## 📂 Project Structure

```text
cloudoptima/
│
├── data/
│   └── pricing/                      # Store per-service CSV files (e.g., AmazonEC2.csv, AmazonS3.csv)
│
├── app/
│   ├── __init__.py
│   ├── config.py                     # Path configuration & global variables
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── dataset_loader.py         # Multi-CSV ingestion and cleaning pipeline
│   │   ├── cost_analyzer.py          # Daily and monthly cost trend aggregations
│   │   ├── predictor.py              # Time-series ML forecasting engine
│   │   ├── waste_detector.py         # Heuristic waste inspection rules
│   │   ├── remediation_engine.py     # Automated and one-click action handler
│   │   └── notification_service.py   # Webhook/Slack alerting for production resources
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── cost_routes.py            # API routes for trends and ML predictions
│   │   ├── waste_routes.py           # API routes for infrastructure waste scans
│   │   └── remediation_routes.py     # API routes for bulk and one-click fixes
│   │
│   └── templates/
│       └── dashboard.html            # Real-time Chart.js interactive dashboard
│
├── requirements.txt                  # Application dependencies
└── main.py                           # Server entrypoint




🛠️ Tech Stack & Dependencies

    Backend: Python 3.10+, FastAPI, Uvicorn
    Data Processing & Analytics: Pandas, NumPy, Scikit-learn / Facebook Prophet
    Frontend: HTML5, Bootstrap 5, Chart.js, Jinja2
    Cloud & Automation: Boto3 SDK, Asynchronous REST APIs

🧪 Testing with Mock / Fallback Data
    CloudOptima contains automatic fallback logic across cost_analyzer.py and waste_detector.py:
        Brand New or Free-Tier Cloud Environments: If an account or dataset has $\$0$ spend history, the system initializes synthetic time-series data so the ML forecasting model can fit seasonal curves.
        Clean Environments: If no unattached volumes or idle instances exist in the scanned data, structured mock findings are populated to allow safe verification of UI tables, charts, and remediation endpoints.
        Safe Simulation: When executing one-click remediation actions offline, the platform safely simulates resource states without altering external cloud infrastructure

⚙️ Steps to Run the Project
1. Prerequisites
Python 3.10, 3.11, or 3.12 installed on your system.

2. Clone / Setup Project Folder
Create and navigate into your root project directory:
cd cloudoptima

3. Create & Activate Virtual Environment
On Windows (PowerShell):
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
python -m venv venv
.\venv\Scripts\Activate.ps1

On Windows (Command Prompt):
python -m venv venv
venv\Scripts\activate.bat

On macOS / Linux:
python3 -m venv venv
source venv/bin/activate

4. Install Dependencies
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

5. Place Dataset Files
Place your downloaded service CSV files (e.g., AmazonEC2.csv, AmazonS3.csv, AWSELB.csv) into the data/pricing/ directory.

6. Start the Web Server
Launch the application using Uvicorn with the Python module flag:
python -m uvicorn main:app --reload

📊 Platform Access
Interactive Web Dashboard: Open http://127.0.0.1:8000/ in your browser.

Swagger API Documentation: Open http://127.0.0.1:8000/docs to inspect and execute backend endpoints directly.

🛡️ Core REST Endpoints
Method	Endpoint	Description
GET	/api/cost/trends	Returns historical monthly spend grouped by service.
GET	/api/cost/predict?days=30	Runs the time-series forecasting model for a 30-day projection.
GET	/api/waste/scan	Scans loaded infrastructure metrics to flag cost leaks.
POST	/api/remediate/auto-process	Executes automated policies on non-production assets.
POST	/api/remediate/one-click	Executes a targeted manual fix on a specific resource.