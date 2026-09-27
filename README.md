# Airline Price Index (APIx) - Flight Fare Monitoring

A beginner-friendly, local-first flight fare monitoring and Airline Price Index (APIx) project built with Python 3.12, PostgreSQL, SQLAlchemy, APScheduler, Pandas, Streamlit, Plotly, and FastAPI.

---

## 🛡️ Safety & Compliance First
- **Permitted Sources Only**: Collects fare observations strictly from permitted public flight-search sources or authorized developer APIs.
- **Respects Access Rules**: Strictly adheres to `robots.txt`, terms of service, rate limits, and access rules.
- **No CAPTCHA Bypass**: Never bypasses CAPTCHA, bot protections, login walls, or paywalls. Automatically stops and logs when a block or rate limit is encountered.
- **No Privacy Violations**: Never stores user credentials, session cookies, payment cards, or passenger details.
- **Transparent Provenance**: Clearly distinguishes synthetic demo / replay data from live collections.

---

## 📁 Repository Structure

```text
flight-price-index/
├── collector/          # Base adapter interface & permitted source adapters
│   ├── base_adapter.py # ABC enforcing safety, SHA-256 hashing, and persistence
│   ├── example_adapter.py # DEL-BOM T+7 adapter with live source extension points
│   └── run_single_collection.py # Standalone runner
├── scheduler/          # APScheduler daily & demo collection schedules
│   ├── safety_guard.py # Concurrency lock (1 session/domain) & zero-retry circuit breaker
│   ├── demo_mode.py    # 3-run max demo mode
│   ├── research_mode.py# Daily 10:00 AM & 6:00 PM cron schedules
│   └── run_scheduler.py# CLI launcher
├── database/           # PostgreSQL configuration, models, queries, and seed data
│   ├── connection.py   # SQLAlchemy engine with SQLite fallback
│   ├── models.py       # collection_runs, raw_responses, fare_quotes, source_health
│   ├── init_db.py      # Table creation script
│   └── seed_demo_data.py # 30-day synthetic pilot data generator
├── pipeline/           # Cleaning, validation, deduplication, missing data logic
│   ├── deduplication.py# Signature-based deduplication
│   ├── cleaner_validator.py # Code standardization & fare component validation
│   ├── outliers.py     # Transparent IQR & MAD outlier flagging (never deletes)
│   ├── missing_data_report.py # Route & booking window completeness audit
│   └── run_pipeline.py # Complete data quality orchestrator
├── analytics/          # Economic indexing engine
│   ├── metrics.py      # Daily medians, 7-day base benchmark, weighted geometric APIx
│   └── apix_calculator.py # Unified APIx calculation engine
├── dashboard/          # Streamlit + Plotly interactive dashboard
│   └── app.py          # 6-tab interactive monitoring UI
├── api/                # FastAPI read-only REST API
│   ├── schemas.py      # Pydantic request/response models
│   └── main.py         # REST endpoints with Swagger UI at /docs
├── tests/              # Pytest test suite (29 tests across all phases)
├── docs/               # Setup guides and architecture documentation
│   └── postgresql_setup_windows.md
├── Dockerfile          # Container specification
├── docker-compose.yml  # Multi-service setup (Postgres + FastAPI + Streamlit)
├── requirements.txt    # Python dependencies
└── README.md
```

---

## ✈️ Fixed Pilot Rules (30-Day Collection Methodology)

| Parameter | Specification |
| :--- | :--- |
| **Routes** | `DEL–BOM`, `DEL–BLR`, `BOM–BLR`, `DEL–CCU`, `BLR–HYD`, `MAA–DEL` |
| **Passenger** | 1 Adult |
| **Journey Type** | One-way |
| **Cabin Class** | Economy |
| **Currency** | INR (Indian Rupee) |
| **Flight Types** | Direct (`stop_count=0`) and Connecting (`stop_count>=1`) separated |
| **Fare Composition** | Mandatory payable fare (`base_fare + taxes + mandatory_charges = total_fare`) |
| **Advance Windows** | `T+1`, `T+7`, `T+15`, `T+30`, `T+45` |
| **Exclusions** | Login discounts, loyalty points, promo codes, seats, meals, baggage extras |

---

## 🚀 Quickstart Guide (Windows PowerShell)

### 1. Environment Setup
```powershell
cd "c:\All Folder\APIx\flight-price-index"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Initialize Database & Seed Pilot Data
```powershell
python -m database.init_db
python -m database.seed_demo_data
```

### 3. Run Data Quality Pipeline
```powershell
python -m pipeline.run_pipeline
```

### 4. Run the Streamlit Interactive Dashboard
```powershell
streamlit run dashboard/app.py
```
👉 Open browser at: **`http://localhost:8501`**

### 5. Run the FastAPI REST Service
```powershell
uvicorn api.main:app --reload --port 8000
```
👉 Interactive Swagger Docs at: **`http://127.0.0.1:8000/docs`**

### 6. Run Automated Test Suite
```powershell
pytest -v
```

---

## 🐳 Docker Deployment (Optional)

To launch the entire stack (PostgreSQL + FastAPI + Streamlit Dashboard) in Docker:

```powershell
docker-compose up --build
```
- Streamlit Dashboard: `http://localhost:8501`
- FastAPI REST API: `http://localhost:8000/docs`
- PostgreSQL Database: `localhost:5432`

---

## 📋 Project Status: **100% Completed**
- [x] **Phase 1: Project & Database Setup**
- [x] **Phase 2: First Permitted-Source Adapter**
- [x] **Phase 3: Data Quality Pipeline**
- [x] **Phase 4: Scheduling & Safety Controls**
- [x] **Phase 5: Analytics & APIx Index Engine**
- [x] **Phase 6: Streamlit Interactive Dashboard**
- [x] **Phase 7: FastAPI, Comprehensive Testing & Docker**
