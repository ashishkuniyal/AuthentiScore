# AuthentiScore

**AuthentiScore** is an AI-Powered Fake Social Media Profile Detection System. It leverages advanced machine learning (ML) and natural language processing (NLP) to analyze social media profiles (e.g., Instagram) and accurately determine their authenticity.

## 🚀 Tech Stack

### Frontend (UI)
- **Framework:** React + Vite
- **Styling:** Tailwind CSS
- **Data Visualization:** Recharts
- **Icons:** Lucide React
- **Services:** Firebase

### Backend (API)
- **Framework:** FastAPI (Python)
- **Server:** Uvicorn
- **Database:** MongoDB (via PyMongo)

### AI / Machine Learning
- **Traditional ML:** Scikit-Learn, XGBoost
- **Deep Learning & NLP:** PyTorch, Hugging Face Transformers (`sentence-transformers`), SpaCy, NLTK
- **Data Processing:** Pandas, NumPy
- **Model Explainability:** SHAP
- **Data Scraping:** Instaloader, BeautifulSoup4

---

## 📁 Project Structure

- `/backend/` - Contains the FastAPI application, REST endpoints, ML models, and backend logic.
- `/frontend/` - Contains the React user interface and components.
- `/data/` - For storing raw and processed datasets.
- `/docs/` - Project documentation.
- `/notebooks/` - Jupyter notebooks for ML model training, exploratory data analysis, and testing.

---

## ⚙️ Setup and Installation

### Prerequisites
- Python 3.9+
- Node.js (v18+)
- MongoDB (running locally or a cloud instance like MongoDB Atlas)

### 1. Backend Setup

Open a terminal and navigate to the backend directory:
```bash
cd backend
```

Create a virtual environment and activate it:
```bash
python -m venv venv

# On Windows:
.\venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

Install the required Python packages:
```bash
pip install -r requirements.txt
```

**Environment Variables:** 
Ensure you configure your `.env` file inside the `backend` directory with necessary credentials (e.g., MongoDB URI, API Keys).

### 2. Frontend Setup

Open a new terminal and navigate to the frontend directory:
```bash
cd frontend
```

Install the Node.js dependencies:
```bash
npm install
```

---

## 🏃‍♂️ Running the Application

You will need to run both the backend API and frontend dev server simultaneously in separate terminal windows.

### Start the Backend
```bash
cd backend
.\venv\Scripts\activate  # Ensure your virtual environment is active
uvicorn app.main:app --reload
```
The FastAPI server will be running at: `http://localhost:8000`
You can view the interactive API documentation at: `http://localhost:8000/docs`

### Start the Frontend
```bash
cd frontend
npm run dev
```
The React frontend will be running at: `http://localhost:5173`

---

## 📡 Core API Endpoints

- `GET /` - API root and status
- `GET /health` - Health check (verifies MongoDB connection)
- `/auth` - Authentication routes
- `/scan` - Single profile scanning operations
- `/bulk` - Bulk profile scanning operations
- `/analytics` - Data analytics and reporting
- `/history` - User scan history
- `WS /ws/notifications` - WebSockets for real-time background task updates

---

## 🛡️ License
[Specify License Here, e.g., MIT License]
