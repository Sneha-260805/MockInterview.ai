# Intelligent Mock Interview Agent

A hackathon project that helps candidates practice interviews with AI-powered question generation, real-time feedback, and performance analytics.

---

## Tech Stack

| Layer    | Technology                              |
|----------|-----------------------------------------|
| Frontend | React 18, Vite, Tailwind CSS, React Router, Axios |
| Backend  | Python, FastAPI, Pydantic v2, Uvicorn   |
| Database | MongoDB (in-memory fallback if unavailable) |

---

## Project Structure

```
mock-interview-agent/
├── backend/
│   ├── main.py                    # FastAPI app + CORS + lifespan
│   ├── config.py                  # Pydantic settings (reads .env)
│   ├── requirements.txt
│   ├── routes/
│   │   ├── health.py              # GET /api/health
│   │   └── resume_routes.py      # POST /api/resume/upload
│   ├── services/
│   │   └── pdf_parser.py         # PDF + TXT text extraction (PyMuPDF)
│   ├── models/
│   │   └── resume.py             # ResumeRecord, ResumeUploadResponse
│   ├── agents/                   # AI agent logic (future)
│   └── database/
│       └── connection.py         # MongoDB + in-memory fallback
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── App.jsx                # Routes: /, /upload, /dashboard, *
│       ├── main.jsx
│       ├── index.css
│       ├── pages/
│       │   ├── Home.jsx
│       │   ├── ResumeUpload.jsx  # Upload form + text preview
│       │   ├── Dashboard.jsx
│       │   └── NotFound.jsx
│       ├── components/
│       │   ├── Navbar.jsx
│       │   └── UploadBox.jsx     # Drag-and-drop file picker
│       └── services/
│           ├── api.js            # Axios base instance
│           └── resumeService.js  # uploadResume()
├── sample_data/
├── docs/
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## Quick Start (Local Dev)

### 1. Configure environment

```bash
cd mock-interview-agent
cp .env.example .env          # edit values as needed
```

### 2. Run the Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --port 8000
```

API is live at: http://localhost:8000  
Interactive docs: http://localhost:8000/docs  
Health check: http://localhost:8000/api/health

> **Note:** MongoDB is optional. If it's not running the app automatically switches to an in-memory store, and `/api/health` will report `"storage": "in-memory"`.

### 3. Run the Frontend

```bash
cd frontend

npm install
npm run dev
```

App is live at: http://localhost:5173

---

## Running with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

| Service  | URL                    |
|----------|------------------------|
| Frontend | http://localhost:5173  |
| Backend  | http://localhost:8000  |
| MongoDB  | localhost:27017        |

---

## API Endpoints

| Method | Path                  | Description                        |
|--------|-----------------------|------------------------------------|
| GET    | `/`                   | Root welcome                       |
| GET    | `/api/health`         | Health + storage mode              |
| POST   | `/api/resume/upload`  | Upload PDF/TXT, returns extracted text |
| GET    | `/docs`               | Swagger UI                         |

---

## Testing Resume Upload

### Option A — Frontend UI

1. Start the backend and frontend (see above).
2. Navigate to http://localhost:5173/upload.
3. Drop a PDF or TXT resume onto the upload box (or click to browse).
4. Click **Extract Resume Text**.
5. The extracted text preview appears below the button.
6. `candidate_id` is saved to `localStorage` automatically for use in later phases.

### Option B — curl

```bash
curl -X POST http://localhost:8000/api/resume/upload \
  -F "file=@/path/to/resume.pdf"
```

Expected response:

```json
{
  "candidate_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "resume.pdf",
  "raw_text": "John Doe\nSoftware Engineer\n...",
  "status": "success"
}
```

### Option C — Swagger UI

1. Open http://localhost:8000/docs.
2. Expand **POST /api/resume/upload**.
3. Click **Try it out**, upload a file, and execute.

### Supported formats

| Format | Notes |
|--------|-------|
| `.pdf` | Text-based PDFs only; scanned/image-only PDFs will return an error |
| `.txt` | UTF-8, Latin-1, and CP1252 encodings are all handled |

---

## Roadmap

- [x] Project skeleton (FastAPI + React + Tailwind)
- [x] Resume upload & text extraction (Phase 1)
- [ ] AI-powered interview question generation
- [ ] Voice / video interview mode
- [ ] Real-time transcription & feedback
- [ ] Job recommendation engine
- [ ] Performance analytics dashboard
