# Airline Price Index (APIx) - Flight Fare Monitoring

A production-grade, real-time flight fare monitoring and Airline Price Index (APIx) engine built for Smart India Hackathon (SIH 2026, Problem Statement 26056 - MoSPI / RBI). 

Powered by **Python 3.12, FastAPI, PostgreSQL 18, SQLAlchemy, APScheduler, Polars**, and a modern **Next.js 14 / React 18 / Tailwind CSS / Chart.js** web dashboard.

---

## 🛡️ Safety & Ethical Compliance (RFC 9309)
- **Permitted Sources Only**: Collects unauthenticated, public fare observations strictly from permitted airline portals and major online travel aggregators (OTAs).
- **RFC 9309 Compliance**: Strictly adheres to `robots.txt`, access rules, and automated circuit-breakers (halts on HTTP 403, 429, or CAPTCHA).
- **Cryptographic Data Integrity**: Every raw payload is timestamped and hashed with **SHA-256** before cleaning to maintain a tamper-evident audit trail for statistical reproducibility.
- **Privacy Safe**: Never collects or stores passenger identities, personal credentials, payment data, or session cookies.

---

## 📁 Repository Structure

```text
flight-price-index/
├── frontend/           # Modern Next.js 14 + React 18 + Tailwind CSS Web Application
│   ├── src/app/        # App Router pages (Dashboard, Heatmap, Velocity Analytics)
│   ├── public/         # Static assets and icons
│   └── package.json    # Frontend dependencies
├── api/                # High-Performance FastAPI REST Service
│   ├── main.py         # REST endpoints with Swagger UI at /docs
│   └── schemas.py      # Pydantic request/response validation models
├── collector/          # Base adapter interface & permitted source adapters
│   ├── base_adapter.py # ABC enforcing safety, SHA-256 hashing, and persistence
│   ├── example_adapter.py # DEL-BOM adapter with live source extension points
│   └── run_single_collection.py # Standalone runner
├── scheduler/          # APScheduler automated collection & safety guards
│   ├── safety_guard.py # Concurrency lock (1 session/domain) & zero-retry circuit breaker
│   ├── daily_auto_collector.py # Automated daily incremental cron ingestion
│   └── research_mode.py# Scheduled research collection windows
├── database/           # PostgreSQL configuration, models, queries, and seed data
│   ├── connection.py   # SQLAlchemy engine with SQLite fallback
│   ├── models.py       # collection_runs, raw_responses, fare_quotes, source_health
│   └── init_db.py      # Table creation and schema migration script
├── pipeline/           # Cleaning, validation, deduplication, missing data logic
│   ├── cleaner_validator.py # Code standardization & fare component validation
│   ├── deduplication.py# Signature-based deduplication
│   ├── outliers.py     # Transparent IQR & MAD outlier flagging (never deletes)
│   └── run_pipeline.py # Complete data quality orchestrator
├── analytics/          # Economic indexing engine
│   ├── apix_calculator.py # DGCA-weighted Jevons geometric index calculator
│   └── metrics.py      # Daily medians, 7-day base benchmark, velocity metrics
├── tests/              # Pytest test suite (29 tests across all phases)
├── docs/               # Setup guides and architecture documentation
├── Dockerfile          # Container specification for FastAPI backend
├── docker-compose.yml  # Multi-service setup (PostgreSQL + FastAPI + Next.js)
├── requirements.txt    # Python backend dependencies
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

## 🚀 Quickstart Guide (Local Development)

### 1. Backend Setup (FastAPI + PostgreSQL)
```powershell
# Navigate to project root
cd "c:\All Folder\APIx\flight-price-index"

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r requirements.txt

# Run the FastAPI REST Server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
👉 Interactive Swagger Docs: **`http://localhost:8000/docs`**

---

### 2. Frontend Setup (Next.js 14 Web Application)
```powershell
# In a new terminal, navigate to the frontend directory
cd "c:\All Folder\APIx\flight-price-index\frontend"

# Install frontend dependencies
npm install

# Start Next.js development server
npm run dev
```
👉 Web Dashboard: **`http://localhost:3000`**

---

### 3. Run Automated Tests
```powershell
pytest -v
```

---

## 🐳 Docker Deployment

To launch the full production stack (**PostgreSQL + FastAPI Backend + Next.js Web App**) with a single command:

```powershell
docker-compose up --build
```
- **Next.js Web Dashboard:** `http://localhost:3000`
- **FastAPI REST API:** `http://localhost:8000/docs`
- **PostgreSQL Database:** `localhost:5432`

---

## 📋 Project Status: **100% Completed**
- [x] **Phase 1: Project & Database Setup** (PostgreSQL 18 + TimescaleDB ready)
- [x] **Phase 2: Permitted-Source Adapter Engine** (RFC 9309 compliant Playwright)
- [x] **Phase 3: Data Quality Pipeline** (SHA-256 integrity, deduplication, MAD outliers)
- [x] **Phase 4: Scheduling & Safety Controls** (Automated daily incremental crawls)
- [x] **Phase 5: Analytics & APIx Index Engine** (IMF Jevons geometric aggregates + DGCA weights)
- [x] **Phase 6: Modern Next.js 14 Web Application** (Dynamic Heatmap, Dual-Axis Velocity Analytics, Report Viewer)
- [x] **Phase 7: FastAPI REST API, Comprehensive Pytest Suite & Docker**
