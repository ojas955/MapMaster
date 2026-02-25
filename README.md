<p align="center">
  <h1 align="center">🧠 KaushalyaAI — AI-Driven Skill Assessment Platform</h1>
  <p align="center">
    <em>Measures real skills, not rote knowledge.</em>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
    <img src="https://img.shields.io/badge/React_19-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
    <img src="https://img.shields.io/badge/Gemini_AI-4285F4?style=for-the-badge&logo=google&logoColor=white" />
    <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />
    <img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" />
  </p>
</p>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#1-backend-setup)
  - [Frontend Setup](#2-frontend-setup)
  - [SkillSync Coding Backend](#3-skillsync-coding-backend-optional)
- [Environment Variables](#-environment-variables)
- [API Reference](#-api-reference)
- [AI & Anti-Cheat Pipeline](#-ai--anti-cheat-pipeline)
- [Proctoring System](#-proctoring-system)
- [Multilingual Support](#-multilingual-support)
- [Deployment](#-deployment)
- [Demo Credentials](#-demo-credentials)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Overview

**KaushalyaAI** is a full-stack, AI-powered skill assessment platform designed to evaluate **higher-order thinking** skills using Bloom's Taxonomy. Unlike traditional MCQ-based tests, KaushalyaAI generates open-ended, scenario-based, and analytical questions from uploaded PDF content, evaluates free-text answers using Google Gemini AI, and provides rich multi-dimensional feedback with anti-cheat integrity scoring.

The platform features real-time **webcam-based proctoring** (face detection, gaze tracking, object detection), **AI-generated plagiarism detection**, **certificate generation with QR verification**, and an integrated **coding assessment engine** with AST-based plagiarism detection.

---

## ✨ Key Features

### 🎓 Assessment Engine
- **PDF-to-Assessment**: Upload any PDF → AI extracts content → generates Bloom's Taxonomy-aligned questions (Apply, Analyze, Evaluate, Create)
- **Adaptive Follow-ups**: AI generates follow-up challenge questions based on student answers in real-time
- **Multi-difficulty**: Beginner, Intermediate, Advanced question generation
- **Timed Assessments**: Configurable time limits per assessment

### 🤖 AI-Powered Evaluation
- **4-Dimensional Scoring**: Each answer is scored on Depth, Accuracy, Application, and Originality (0–10 each)
- **Rich Feedback**: Personalized AI feedback with strengths, weaknesses, and improvement suggestions per question
- **Confidence Analysis**: AI evaluates answer confidence and certainty levels
- **Learning Pathway Generation**: Personalized study recommendations based on identified skill gaps

### 🛡️ Anti-Cheat & Integrity System
- **AI-Generated Content Detection**: N-gram pattern matching against known AI/ChatGPT phrases
- **Plagiarism Detection**: Sequence matching against source PDF text and cross-submission comparison
- **Tab-Switch Tracking**: Monitors browser focus changes during assessment
- **Copy-Paste Detection**: Tracks clipboard usage events
- **Webcam Proctoring**: Real-time face detection, multi-face detection, gaze tracking, and object detection (phones, books, etc.)
- **Integrity Score**: Composite score combining all anti-cheat signals

### 💻 Coding Assessment (SkillSync Engine)
- **Live Code Execution**: Monaco Editor with Python code execution
- **AST Structural Fingerprinting**: Detects plagiarism even with variable renaming, comment changes, and whitespace tricks
- **Originality Engine**: 5-signal analysis (AST fingerprint, code skeleton ratio, behavioral signals, naming conventions, comment density)
- **Batch Submissions**: Submit and evaluate multiple coding problems at once

### 📜 Certificates
- **Auto-Generated Certificates**: Beautiful PNG certificates with gradient borders and decorative elements
- **QR Code Verification**: Each certificate has a unique QR code for third-party verification
- **Downloadable & Shareable**: Direct download links and verification endpoints

### 👤 User Management
- **Role-Based Access**: Student and Admin roles with protected routes
- **XP & Streak System**: Gamified learning with XP points and daily streaks
- **Student Portfolio**: Track all assessments, scores, certificates, and learning progress
- **Profile Customization**: Bio, college, phone, avatar color, preferred language

### 📊 Analytics Dashboard
- **Admin Dashboard**: Overview of all assessments, submissions, and platform statistics
- **Student Dashboard**: Personal performance metrics, score trends, and skill radar
- **Assessment Analytics**: Per-assessment completion rates, average scores, and difficulty distribution

---

## 🏗️ Architecture

```
┌─────────────────────────────────┐
│         React 19 Frontend       │
│   (Vite + React Router + Axios) │
│   Webcam Proctoring (face-api)  │
│   Monaco Editor (Coding)        │
└──────────────┬──────────────────┘
               │  HTTP/REST (JWT Auth)
               │  Proxy: /api → :8000
               ▼
┌─────────────────────────────────┐
│       FastAPI Backend           │
│   KaushalyaAI Core (port 8000) │
│                                 │
│  ┌──────────┐  ┌──────────────┐│
│  │ AI Svc   │  │ Anti-Cheat   ││
│  │ (Gemini) │  │ Service      ││
│  └──────────┘  └──────────────┘│
│  ┌──────────┐  ┌──────────────┐│
│  │ Cert Svc │  │ Whisper Svc  ││
│  │ (PIL+QR) │  │ (Audio STT)  ││
│  └──────────┘  └──────────────┘│
│                                 │
│  ┌─────────────────────────────┐│
│  │  SkillSync Coding Backend   ││
│  │  Mounted at /api/coding     ││
│  │  (Plagiarism + Originality) ││
│  └─────────────────────────────┘│
│                                 │
│  SQLite Database (kaushalya.db) │
└─────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **FastAPI** | High-performance async Python web framework |
| **SQLAlchemy** | ORM for database models and queries |
| **SQLite** | Lightweight embedded database |
| **Google Gemini AI** (`gemini-2.5-flash`) | Question generation, answer evaluation, pathway recommendation |
| **OpenAI Whisper** | Audio transcription for voice-based answers |
| **Pillow + qrcode** | Certificate image generation with QR codes |
| **pdfplumber** | PDF text extraction |
| **sentence-transformers** | Semantic similarity for plagiarism detection |
| **python-jose + bcrypt** | JWT authentication and password hashing |
| **scikit-learn** | TF-IDF vectorization for text plagiarism detection |

### Frontend
| Technology | Purpose |
|---|---|
| **React 19** | UI framework with hooks |
| **Vite 7** | Lightning-fast dev server and bundler |
| **React Router 7** | Client-side routing with protected routes |
| **Axios** | HTTP client with JWT interceptors |
| **face-api.js** | Face detection, landmark detection, expression recognition |
| **TensorFlow.js + COCO-SSD** | Real-time object detection (phone, book detection) |
| **Monaco Editor** | VS Code-like code editor for coding assessments |
| **Recharts + Chart.js** | Data visualization and analytics charts |
| **Lucide React** | Icon library |

---

## 📂 Project Structure

```
SAO-1/
├── backend_final/              # Main FastAPI backend
│   ├── main.py                 # App entry point, lifespan, CORS, router mounting
│   ├── config.py               # Pydantic settings (env vars, paths, API keys)
│   ├── database.py             # SQLAlchemy engine, session, table creation
│   ├── models.py               # ORM models (User, PDF, Assessment, Submission, Certificate, PathwayStep)
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── auth.py                 # JWT auth, password hashing, role guards
│   ├── seed_data.py            # Demo data auto-seeder (runs on first startup)
│   ├── requirements.txt        # Python dependencies
│   ├── routes/
│   │   ├── auth_routes.py      # POST /register, /login, GET /me
│   │   ├── pdf_routes.py       # POST /upload, GET /list
│   │   ├── assessment_routes.py# CRUD assessments, follow-up generation
│   │   ├── submission_routes.py# Submit answers, audio upload, AI evaluation
│   │   ├── certificate_routes.py# Generate, download, verify certificates
│   │   ├── analytics_routes.py # Admin/student analytics endpoints
│   │   └── user_routes.py      # Profile management
│   ├── services/
│   │   ├── ai_service.py       # Gemini AI: question gen, evaluation, pathways
│   │   ├── anticheat_service.py# Plagiarism, AI detection, integrity scoring
│   │   ├── certificate_service.py# PNG cert generation with QR codes
│   │   ├── whisper_service.py  # Audio transcription via Whisper
│   │   └── pdf_service.py      # PDF parsing and text extraction
│   ├── uploads/                # Uploaded PDF storage
│   └── certificates/           # Generated certificate images
│
├── frontend_final/             # React 19 + Vite frontend
│   ├── package.json            # Node dependencies
│   ├── vite.config.js          # Vite config with API proxy to :8000
│   ├── index.html              # HTML entry point
│   ├── src/
│   │   ├── App.jsx             # Root component with routing
│   │   ├── main.jsx            # React DOM entry
│   │   ├── api/
│   │   │   └── client.js       # Axios instance with JWT interceptors
│   │   ├── context/
│   │   │   ├── AuthContext.jsx  # Authentication state management
│   │   │   └── LangContext.jsx  # i18n translations (EN/HI/MR)
│   │   ├── pages/
│   │   │   ├── Landing.jsx     # Public landing page
│   │   │   ├── Login.jsx       # Login form
│   │   │   ├── Register.jsx    # Registration form
│   │   │   ├── StudentDashboard.jsx  # Student home with assessments
│   │   │   ├── AdminDashboard.jsx    # Admin panel with analytics
│   │   │   ├── TakeAssessment.jsx    # Assessment-taking interface
│   │   │   ├── AssessmentResult.jsx  # Detailed result view
│   │   │   ├── Portfolio.jsx         # Student portfolio & certificates
│   │   │   ├── Profile.jsx          # Profile editing
│   │   │   └── CodingSkills.jsx     # Coding assessment (Monaco Editor)
│   │   └── components/
│   │       ├── Proctor.jsx     # Webcam proctoring (face-api + COCO-SSD)
│   │       ├── ProctorStats.jsx# Proctoring statistics display
│   │       └── Sidebar.jsx     # Navigation sidebar
│   └── public/
│       └── models/             # face-api.js pre-trained model weights
│
├── skillsync-backend/          # Coding assessment microservice
│   ├── main.py                 # FastAPI app: code execution, Gemini analysis
│   ├── plagiarism_engine.py    # AST-based code plagiarism detection
│   ├── originality_engine.py   # 5-signal originality analysis engine
│   └── test_full_flow.py       # Integration tests
│
└── README.md                   # ← You are here
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** and **npm**
- **Google Gemini API Key** ([Get one free](https://aistudio.google.com/apikey))

### 1. Backend Setup

```bash
# Navigate to backend
cd backend_final

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (macOS/Linux)
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env
echo "SECRET_KEY=your-secret-key-change-in-production" >> .env

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend will:
- Auto-create the SQLite database (`kaushalya.db`)
- Auto-seed demo assessments and users on first run
- Serve API docs at [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend_final

# Install dependencies
npm install

# Start dev server
npm run dev
```

The frontend starts at [http://localhost:5173](http://localhost:5173) and automatically proxies `/api` requests to the backend at `:8000`.

### 3. SkillSync Coding Backend (Optional)

The coding assessment engine is **automatically mounted** by the main backend at startup. No separate setup is needed — when the main backend starts, it detects the `skillsync-backend/` directory and mounts all its routes under `/api/coding/*`.

If you need to run it independently:

```bash
cd skillsync-backend
pip install fastapi uvicorn python-dotenv google-generativeai PyMuPDF beautifulsoup4 scikit-learn
uvicorn main:app --port 8001
```

---

## 🔐 Environment Variables

Create a `.env` file in the `backend_final/` directory:

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | — | Google Gemini API key for AI features |
| `SECRET_KEY` | ✅ Yes | `kaushalya-super-secret-key...` | JWT signing secret (change in production!) |
| `DATABASE_URL` | No | `sqlite:///./kaushalya.db` | SQLAlchemy database connection string |
| `FRONTEND_URL` | No | `http://localhost:5173` | Frontend URL for CORS and certificate QR links |
| `BACKEND_URL` | No | `http://localhost:8000` | Backend URL for QR verification links |

---

## 📡 API Reference

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Register new user (student/admin) |
| `POST` | `/api/auth/login` | Login and receive JWT token |
| `GET` | `/api/auth/me` | Get current authenticated user |

### PDFs
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/pdfs/upload` | Upload PDF → extract text → generate assessment |
| `GET` | `/api/pdfs/list` | List all uploaded PDFs |

### Assessments
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/assessments` | List all assessments (with filters) |
| `GET` | `/api/assessments/{id}` | Get assessment details with questions |
| `POST` | `/api/assessments` | Create assessment (admin) |
| `POST` | `/api/assessments/{id}/followup` | Generate adaptive follow-up question |
| `DELETE` | `/api/assessments/{id}` | Delete assessment (admin) |

### Submissions
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/submissions` | Submit answers → AI evaluation → scoring |
| `POST` | `/api/submissions/{id}/audio` | Upload audio recording for transcription |
| `GET` | `/api/submissions/mine` | Get current user's submissions |
| `GET` | `/api/submissions/{id}` | Get detailed submission result |

### Certificates
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/certificates/generate/{submission_id}` | Generate certificate for a submission |
| `GET` | `/api/certificates/download/{qr_hash}` | Download certificate image |
| `GET` | `/api/certificates/verify/{qr_hash}` | Verify certificate authenticity |
| `GET` | `/api/certificates/mine` | List user's certificates |

### Coding (SkillSync)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/coding/execute` | Execute Python code |
| `POST` | `/api/coding/submit` | Submit coding solution for evaluation |
| `POST` | `/api/coding/batch-submit` | Batch submit multiple solutions |

### Users & Analytics
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/users/me` | Get user profile |
| `PUT` | `/api/users/profile` | Update user profile |

> 📖 Full interactive API docs available at **`/docs`** (Swagger UI) when the backend is running.

---

## 🤖 AI & Anti-Cheat Pipeline

When a student submits an assessment, the following pipeline executes:

```
Student Submits Answers
        │
        ▼
┌──────────────────────┐
│  1. Anti-Cheat Check  │  Plagiarism vs source PDF
│     (anticheat_svc)   │  Cross-submission similarity
│                       │  AI phrase detection (30+ patterns)
│                       │  Tab-switch & copy-paste counts
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  2. AI Evaluation     │  Gemini scores each answer on:
│     (ai_service)      │  • Depth (0-10)
│                       │  • Accuracy (0-10)
│                       │  • Application (0-10)
│                       │  • Originality (0-10)
│                       │  + Detailed text feedback
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  3. AI Detection      │  Detects if answers are
│     (ai_service)      │  AI-generated using Gemini
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  4. Confidence Score  │  Analyzes answer certainty
│     (ai_service)      │  and conviction level
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  5. Learning Pathway  │  Identifies skill gaps
│     (ai_service)      │  Recommends study topics
│                       │  Suggests next assessments
└──────────┬───────────┘
           ▼
    Result + Certificate
```

---

## 📹 Proctoring System

The frontend includes a real-time AI-powered proctoring component (`Proctor.jsx`) that runs entirely in the browser:

| Signal | Technology | What It Detects |
|---|---|---|
| **Face Presence** | face-api.js | No face / face left frame |
| **Multiple Faces** | face-api.js | Another person in frame |
| **Gaze Tracking** | Face landmarks (68-point) | Looking away from screen |
| **Object Detection** | TensorFlow.js COCO-SSD | Phone, book, laptop, etc. |
| **Expression Analysis** | face-api.js expressions | Stress / confusion indicators |

All proctoring data is aggregated into:
- **Confidence Score**: Based on face presence % and gaze-on % 
- **Integrity Score**: Starts at 100, deductions for violations
- **Violation Log**: Timestamped list of all detected incidents

---

## 🌐 Multilingual Support

KaushalyaAI supports three languages out of the box:

| Language | Code | Coverage |
|---|---|---|
| 🇬🇧 English | `en` | Full UI + AI-generated questions |
| 🇮🇳 Hindi | `hi` | Full UI + AI-generated questions |
| 🇮🇳 Marathi | `mr` | Full UI + AI-generated questions |

Language selection is available per user profile and affects:
- All UI text (translations via `LangContext`)
- AI-generated assessment questions
- AI evaluation feedback
- Certificate text

---

## 🚢 Deployment

The project includes deployment configurations for multiple platforms:

### Railway
```bash
# backend_final/railway.json and nixpacks.toml included
# Deploy via Railway CLI or GitHub integration
```

### Render
```bash
# backend_final/render.yaml included
# Connect GitHub repo → auto-deploy
```

### Vercel (Frontend)
```bash
# frontend_final/vercel.json included
cd frontend_final
npx vercel
```

### Docker (Manual)
```bash
# Backend
cd backend_final
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend_final
npm run build
# Serve dist/ with any static server (Caddy, Nginx, etc.)
```

---

## 🔑 Demo Credentials

On first startup, the backend auto-seeds demo data. Use these credentials:

| Role | Email | Password |
|---|---|---|
| 👨‍🎓 Student | `student@kaushalya.ai` | `student123` |
| 👨‍💼 Admin | `admin@kaushalya.ai` | `admin123` |

> The seeder also creates 5 pre-built assessments covering Machine Learning, Web Development, Data Structures, Cybersecurity, and Cloud Computing.

---

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### Development Tips
- Backend API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Frontend hot-reload: `npm run dev` in `frontend_final/`
- Database resets: Delete `kaushalya.db` and restart backend for fresh seed data
- AI fallback: If `GEMINI_API_KEY` is not set, the platform uses hardcoded fallback evaluations

---



