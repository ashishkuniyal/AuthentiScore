# AuthentiScore

**AuthentiScore** is an AI-powered profile authenticity, fraud intelligence, and bot detection platform. It combines calibrated ensemble machine learning (Logistic Regression + Random Forest + XGBoost), explainable AI (SHAP), keyword and sentiment bio NLP analysis, and heuristic rules to assess social media profile risk.

---

## 🚀 Tech Stack

### Frontend
- **Framework:** React 19 + Vite
- **Styling:** Tailwind CSS v4, custom glassmorphism design system
- **Data Visualization:** Recharts
- **Icons:** Lucide React
- **Authentication:** Firebase Auth (JWT verification on backend)

### Backend
- **Framework:** FastAPI (Python 3.10+)
- **Server:** Uvicorn (ASGI)
- **Database:** MongoDB (via PyMongo, non-blocking lifespan setup)
- **Real-Time:** WebSockets with authenticated per-user connection management

### AI / Machine Learning
- **Ensemble Model:** CalibratedClassifierCV wrapping Logistic Regression, Random Forest, and XGBoost
- **Explainability:** SHAP TreeExplainer & LinearExplainer (strictly serializable feature contributions)
- **Bio NLP:** Hybrid lexicon-based risk categorizer with sentiment and spam heuristics
- **Feature Engineering:** Strict non-leaking feature extractor with shared profile completeness logic

---

## ⚙️ Setup and Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Node.js 20+
- MongoDB 6.0+ (running locally or cloud URI)

### 1. Backend Setup

```bash
cd backend
python -m venv venv

# On Windows:
.\venv\Scripts\activate

# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt -r requirements-dev.txt
```

#### Environment Variables
Create `backend/.env` using `backend/.env.example`:
```bash
cp .env.example .env
```
Key configuration parameters:
- `MONGODB_URI`: MongoDB connection string (e.g. `mongodb://localhost:27017`)
- `MONGODB_DATABASE`: Database name (`authentiscore`)
- `FIREBASE_PROJECT_ID`: Firebase project ID for token verification
- `ADMIN_EMAILS`: Comma-separated admin emails
- `CORS_ORIGINS`: Allowed origins (e.g. `http://localhost:5173`)
- `ENABLE_SIMULATED_FORENSICS`: Set `false` to hide simulated network/image data (default: `false`)
- `SCAN_RETENTION_DAYS`: Auto-pruning retention window in days (default: `30`)

### 2. Frontend Setup

```bash
cd frontend
npm ci
cp .env.example .env
```
Configure `VITE_API_URL` (default: `http://localhost:8000`).

---

## 🏃 Running Locally

### Start Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
API runs at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

### Start Frontend
```bash
cd frontend
npm run dev
```
Frontend runs at `http://localhost:5173`.

---

## 🧠 ML Model Training & Retraining

AuthentiScore uses a calibrated ensemble model (`v3`). Training requires dataset files in `data/`:
```bash
cd backend
python -m scripts.train_v3_ensemble
```
The script evaluates class-weighted vs SMOTE resampled variants, selects the variant with the superior Brier score, and exports:
- `backend/trained_models/authentiscore_ensemble_v3.pkl`
- `backend/trained_models/authentiscore_features_v3.json`
- `backend/trained_models/metrics_v3.json`

Without trained model files, the backend starts gracefully in fallback mode (lazy-loaded model store).

---

## 🧪 Testing & Quality Assurance

### Backend Hermetic Test Suite
Runs hermetically without live MongoDB, network access, or pre-existing pkl files:
```bash
cd backend
pytest -q
```
80 unit, integration, and regression tests verify token security, risk bands, BSON serialization, WebSocket thread-safety, and collector error handling.

### Frontend Quality
```bash
cd frontend
npm run lint   # Enforces 0 Oxlint warnings across all files
npm run build  # Compiles production bundle cleanly
```

---

## ⚠️ Limitations & Disclaimers

1. **Platform Scope:** The supervised ML classifier is trained primarily on Instagram profile attributes. While generic profiles can be evaluated using heuristics and NLP, behavior on other networks is an approximation.
2. **Scraper Availability:** Third-party profile scrapers (Instaloader, Apify, public endpoints) rely on public page structures and may be rate-limited or blocked. AuthentiScore provides an explicit manual fallback form when automated data collection is incomplete.
3. **NLP Heuristics:** Natural language analysis of bios uses category-matching and sentiment heuristics; it should be used in conjunction with behavioral features, not as sole proof of automation.

---

## 🛡️ License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
