# AI Splitwise

AI-powered expense sharing application built with FastAPI, Next.js, and Google Gemini.

## Features

- **Authentication** — Register, login, JWT-based sessions
- **Groups** — Create groups (Trip/Home/Couple/Other), add/remove members by email, role-based permissions
- **Expenses** — Add & delete expenses with 3 split modes: Equal, Unequal, Percentage
- **Balances** — Auto-calculated net balances per group member
- **Smart Settlements** — Greedy algorithm that minimizes transactions to settle all debts
- **AI Expense Parser** — Type "$50 for dinner" → parsed expense → add to any group instantly
- **Receipt OCR** — Upload receipt photos via 📷 button → auto-extract total and add to group
- **AI Chatbot** — Ask questions about expenses, get budget advice (Gemini-powered)
- **Analytics** — Category breakdown with progress bars, monthly spending bar charts
- **AI Insights** — Spending summaries, top categories, and tips per group

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11, FastAPI 0.115, SQLAlchemy 2.0 (async), Pydantic 2.9, SQLite/PostgreSQL |
| Frontend | Next.js 16.1.6, React 19.2, TypeScript 5, TailwindCSS 4 |
| AI | Google Generative AI 0.8+, Tesseract OCR, Pillow |
| State | Zustand 5, React Query 5, Axios 1.13 |
| Auth | PyJWT 2.9, bcrypt 4.2, passlib |
| UI | Lucide React, Recharts 3, React Hot Toast, date-fns |

## Prerequisites

- **Python 3.11+** — [python.org/downloads](https://python.org/downloads)
- **Node.js 20+** — [nodejs.org](https://nodejs.org)

## Quick Start

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --port 8000
```

You should see:
```
🚀 AI Splitwise v1.0.0 starting...
✅ Database tables ready
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Frontend

Open a **second terminal**:

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

You should see:
```
▲ Next.js 16.x.x
- Local: http://localhost:3000
```

### 3. Open the App

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Frontend (main app) |
| http://localhost:8000/docs | Backend API docs (Swagger) |
| http://localhost:8000/health | Health check |

## Optional: Enable AI Features

Set your Google Gemini API key in `backend/.env`:

```
GEMINI_API_KEY=your-actual-gemini-api-key
```

Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

> The app works without the API key — expense parsing falls back to rule-based extraction.

## Project Structure

```
Splitwise AI/
├── backend/
│   ├── app/
│   │   ├── api/           # API endpoints (auth, groups, expenses, ai, analytics)
│   │   ├── core/          # Config, database, security, dependencies
│   │   ├── models/        # SQLAlchemy models (User, Group, Expense, etc.)
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── services/      # Business logic (balance engine, settlement algorithm)
│   │   └── main.py        # FastAPI app entry point
│   ├── alembic/           # Database migrations
│   ├── requirements.txt
│   ├── .env               # Environment variables (not committed)
│   └── .env.example       # Template for environment variables
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js pages (landing, login, dashboard, etc.)
│   │   ├── lib/           # API client with JWT interceptors
│   │   └── store/         # Zustand stores (auth, groups, expenses)
│   └── package.json
├── .gitignore
└── README.md
```

## Database

By default, uses **SQLite** (zero config — auto-creates `backend/splitwise.db`).

To switch to **PostgreSQL**, update `backend/.env`:
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/splitwise
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login, get JWT token |
| GET | `/api/auth/me` | Current user profile |
| GET/POST | `/api/groups` | List / create groups |
| POST | `/api/groups/{id}/members` | Add member by email |
| GET/POST | `/api/groups/{id}/expenses` | List / add expenses |
| DELETE | `/api/groups/{id}/expenses/{eid}` | Delete expense |
| GET | `/api/groups/{id}/balances` | Get net balances |
| GET | `/api/groups/{id}/settlements` | Get settlement suggestions |
| POST | `/api/groups/{id}/settle` | Record a settlement |
| POST | `/api/ai/parse-expense` | Parse natural language expense |
| POST | `/api/ai/scan-receipt` | OCR receipt image |
| POST | `/api/ai/chat` | AI chatbot |
| GET | `/api/ai/insights/{id}` | AI spending insights |
| GET | `/api/analytics/{id}/categories` | Category breakdown |
| GET | `/api/analytics/{id}/trends` | Monthly trends |

## License

MIT
