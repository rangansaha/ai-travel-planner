<div align="center">

# ✈️ AI Travel Planner

### Plan smarter. Travel better. ✨

An AI-powered travel planning application that creates personalized trip itineraries based on your destination, budget, travel style, interests, duration, and number of travelers.

<br>

![Next.js](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql)
![Ollama](https://img.shields.io/badge/Ollama-AI-black?style=for-the-badge)

<br>

**🌍 Discover destinations · 🤖 Generate itineraries · 💰 Manage budgets · 🌦️ Check weather · 💾 Save trips**

</div>

---

## 🌟 About The Project

**AI Travel Planner** is a full-stack travel planning application designed to make trip planning faster and more personalized.

Instead of manually searching through dozens of websites, users can provide their travel preferences and let the application generate a complete travel plan.

The application combines an interactive frontend, a FastAPI backend, PostgreSQL persistence, AI-powered itinerary generation, and weather information into one platform.

---

## ✨ Features

### 🤖 AI-Powered Trip Planning

Generate personalized travel plans based on:

- 📍 Destination
- 🌎 Country
- 📅 Trip duration
- 👥 Number of travelers
- 💰 Budget
- 🎒 Travel style
- ❤️ Personal interests

---

### 🗺️ Personalized Itineraries

Get a structured day-by-day travel plan with:

- 📅 Daily activities
- 📍 Places to visit
- 🍜 Food recommendations
- 🎯 Activities
- 📝 Travel tips
- ⏱️ Suggested schedules

---

### 💰 Budget Breakdown

The generated trip includes an estimated budget breakdown for:

| Category | Included |
|---|---|
| 🍜 Food | ✅ |
| 🚗 Transport | ✅ |
| 🎯 Activities | ✅ |
| 🏨 Accommodation | ✅ |
| 📦 Miscellaneous | ✅ |

The application also compares estimated spending against the user's budget.

---

### 🌦️ Weather Information

The application integrates weather information to help travelers understand the conditions at their destination.

---

### 💾 Saved Trips

Users can save generated travel plans and access them later.

Saved trips include:

- Destination
- Country
- Duration
- Travelers
- Budget
- Travel style
- Generated itinerary
- Creation date

Trips can also be viewed and deleted directly from the application.

---

### 🎨 Modern UI

The frontend features a dark, modern interface with:

- Responsive layouts
- Interactive cards
- Smooth UI elements
- Travel-focused visual design
- Expandable saved-trip section
- Clean dashboard experience

---

## 🧠 How It Works

```text
                 ┌──────────────────┐
                 │      User        │
                 │ Travel Preferences│
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │   Next.js UI     │
                 │   React Frontend │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │     FastAPI      │
                 │     Backend      │
                 └───────┬───┬──────┘
                         │   │
             ┌───────────┘   └────────────┐
             ▼                            ▼
      ┌──────────────┐             ┌──────────────┐
      │ AI / Ollama  │             │   Weather    │
      │   Service    │             │   Service    │
      └──────┬───────┘             └──────────────┘
             │
             ▼
      ┌──────────────┐
      │  PostgreSQL  │
      │   Database   │
      └──────────────┘
```

---

## 🚀 Running Locally

### Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.13** | A virtual environment already exists at `backend/venv` |
| **Node.js 20+** | Required by Next.js 16 |
| **PostgreSQL** | Running, with a database matching `DB_NAME` |
| **[Ollama](https://ollama.com)** | Running, with the model pulled |

Pull the model once:

```bash
ollama pull llama3.2:latest
```

---

### 1. Configure the backend

`backend/.env` holds the database connection (it is gitignored — create it if missing):

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ai_travel_planner
DB_USER=postgres
DB_PASSWORD=your_password
```

Everything else has a working default and only needs setting to override it:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.2:latest` | Model used to generate itineraries |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | **Always include the port** — with a scheme but no port, the client silently targets port 80 |
| `OLLAMA_READ_TIMEOUT` | `300` | Seconds to wait for one generation |
| `DB_POOL_MIN` | `2` | Connections kept warm |
| `DB_POOL_MAX` | `40` | Matches the anyio worker-thread limit for sync endpoints |

Tables are created automatically on startup. If PostgreSQL is unreachable the app still boots — `/health` and the AI routes do not need it.

---

### 2. Start the backend

From the `backend/` directory:

```bash
./venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

Serves on **http://127.0.0.1:8000**, with interactive docs at **/docs**.

> On macOS or Linux the interpreter is `venv/bin/python` instead.

---

### 3. Start the frontend

From the `frontend/` directory, in a second terminal:

```bash
npm install
```

```bash
npm run dev
```

Opens on **http://localhost:3000**.

---

### ⚠️ The ports are not currently configurable

The frontend hardcodes `http://127.0.0.1:8000` in four places, and the backend's CORS policy allows frontend origins only on port 3000. Changing either port means editing both sides.

| Service | Port | Fixed in |
|---|---|---|
| Frontend | 3000 | `backend/app/main.py` (CORS allowlist) |
| Backend | 8000 | `frontend/app/page.tsx` (four `fetch` calls) |

---

### 4. Run the tests

The suite passes with nothing else running: model calls are stubbed, and database tests are skipped when PostgreSQL is unavailable. From `backend/`:

```bash
./venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

```bash
./venv/Scripts/python.exe -m pytest
```

Two groups of tests need real services and are handled automatically:

| Marker | Behaviour |
|---|---|
| `db` | Runs when PostgreSQL is reachable, skipped when it is not |
| `live` | Calls the real model. Skipped unless you pass `--live`, and takes minutes |

```bash
./venv/Scripts/python.exe -m pytest --live
```
