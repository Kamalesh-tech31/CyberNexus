# CyberNexus

ML-powered phishing/spam detection across SMS, Email, and URL channels, with
model-grounded explainability and a real-time analysis API.

## Architecture

```
Frontend (React + Vite)  →  FastAPI Backend  →  Supabase  →  ML Service
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- A Supabase project (URL + service role key)

## Setup

### 1. Clone and enter the project

```cmd
git clone <repo-url>
cd CyberNexus
```

### 2. Backend — Python environment

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Backend — environment variables

Copy the example file and fill in real values:

```cmd
copy .env.example .env
```

Required in `.env`:

```
SUPABASE_URL=your-project-url
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

### 4. Backend — model artifacts

Trained model files (`.pkl` / `.joblib`) are **not committed to this repo**
(see `.gitignore`). Place trained models under:

```
ml/models/sms/
ml/models/email/
ml/models/url/
ml/calibration/
```

Regenerate them by running the training scripts under `ml/training/` /
`ml/evaluation/`, or obtain them separately (see project maintainer).

### 5. Frontend — dependencies

```cmd
cd frontend
npm install
```

### 6. Frontend — environment variables

Create `frontend/.env`:

```
VITE_API_BASE_URL=http://localhost:8000
```

## Running the project

### Start the backend (from project root)

```cmd
.venv\Scripts\activate
.venv\Scripts\python.exe -m uvicorn backend.app:app --reload
```

Backend runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### Start the frontend (from `frontend/`)

```cmd
npm run dev
```

Frontend runs at `http://localhost:3000` (or the port Vite reports).

## Running tests

```cmd
.venv\Scripts\python.exe -m unittest ^
  ml.explainability.tests.test_explainability ^
  backend.tests.test_ml_service ^
  backend.tests.test_analysis_api ^
  backend.tests.test_response_contract ^
  backend.tests.test_supabase_service ^
  -v
```

## Project structure

```
CyberNexus/
├── backend/          # FastAPI app, routes, services
├── ml/
│   ├── models/        # Trained model artifacts (gitignored)
│   ├── calibration/    # Calibration artifacts (gitignored)
│   ├── feature_engineering/
│   ├── explainability/
│   └── training/
├── data/              # Training datasets
├── frontend/          # React + Vite app
└── requirements.txt
```

## Status

- ML inference (SMS / Email / URL) — working
- Explainability (Tier 1/2/3 progressive disclosure) — working
- Supabase — foundation only, not yet used for persistence
- Authentication — not yet implemented (frontend auth UI is currently a placeholder, not connected to any backend)
- QR channel — not yet implemented (returns HTTP 501)
