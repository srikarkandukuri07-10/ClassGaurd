# ClassGuard

AI-based classroom focus monitoring system for engineering colleges. Faculty don't watch student screens — AI monitors and detects studying, off-task, or suspicious activity.

## Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│  Student Agent       │     │   AI Service          │     │  Faculty Dashboard│
│  (Tauri + Rust)      │────▶│  (FastAPI)            │◀────│  (React + TS)    │
│                      │     │  Classifies screens   │     │                  │
│  - Screen capture    │     │  Window titles, OCR   │     │  - Login          │
│  - WebSocket client  │     └──────────┬───────────┘     │  - Dashboard      │
│  - Native notifs     │                │                  │  - Section view   │
│  - Heartbeat         │                ▼                  │  - Add students   │
└─────────────────────┘     ┌──────────────────────┐     │  - Realtime WS    │
                            │   Backend Server     │◀────┘                  │
                            │   (FastAPI)          │     └──────────────────┘
                            │                      │
                            │  - REST API          │
                            │  - WebSocket hub     │     ┌──────────────────┐
                            │  - Warning system    │────▶│  PostgreSQL      │
                            │  - Heartbeat monitor │     │  Database        │
                            └──────────────────────┘     └──────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Desktop Agent | Tauri 2 + Rust |
| Backend | FastAPI (Python) |
| Database | PostgreSQL 16 |
| Frontend | React 18 + TypeScript + Tailwind CSS |
| AI Service | FastAPI + heuristic classifier (ML-ready) |
| Realtime | WebSockets |
| Notifications | notify-rust (Windows native) |

## Folder Structure

```
classguard/
├── backend/                  # FastAPI backend server
│   ├── app/
│   │   ├── api/              # Route handlers
│   │   │   ├── auth.py       # Faculty login/register
│   │   │   ├── students.py   # CRUD for students
│   │   │   ├── monitoring.py # Start/stop/heartbeat
│   │   │   ├── disable_requests.py  # Pause requests
│   │   │   └── ai_events.py  # AI classification handler
│   │   ├── core/             # Config, DB, security, deps
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── ws/               # WebSocket manager & routes
│   │   └── main.py           # App entry point
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                 # React faculty dashboard
│   ├── src/
│   │   ├── components/       # Reusable UI components
│   │   ├── pages/            # Login & Dashboard pages
│   │   ├── services/         # API client & WebSocket
│   │   ├── types/            # TypeScript interfaces
│   │   └── App.tsx           # Router setup
│   ├── package.json
│   └── Dockerfile
├── desktop-agent/            # Tauri + Rust student agent
│   ├── src/                  # Rust source
│   │   ├── main.rs           # Entry point
│   │   ├── screen_capture.rs # Desktop capture
│   │   ├── ws_client.rs      # WebSocket + heartbeat
│   │   └── notifications.rs  # Windows native notifications
│   ├── src-tauri/            # Tauri config
│   ├── Cargo.toml
│   └── build.rs
├── ai-service/               # AI classification engine
│   ├── app/
│   │   ├── main.py           # FastAPI entry
│   │   └── classifier.py     # Activity classifier
│   ├── requirements.txt
│   └── Dockerfile
└── docker-compose.yml
```

## Database Schema

```
faculties
  id            INT PRIMARY KEY
  name          VARCHAR(255)
  email         VARCHAR(255) UNIQUE
  hashed_password VARCHAR(255)

students
  id              INT PRIMARY KEY
  name            VARCHAR(255)
  section         VARCHAR(10)
  device_id       VARCHAR(255) UNIQUE
  monitoring_enabled  BOOLEAN
  monitoring_paused   BOOLEAN
  pause_reason        VARCHAR(500)
  current_status      VARCHAR(50)  -- studying/off-task/suspicious/offline
  warning_count       INT
  heartbeat_at        TIMESTAMPTZ
  created_at          TIMESTAMPTZ

monitoring_sessions
  id          INT PRIMARY KEY
  student_id  INT FK → students
  is_active   BOOLEAN
  started_at  TIMESTAMPTZ
  ended_at    TIMESTAMPTZ

warnings
  id          INT PRIMARY KEY
  student_id  INT FK → students
  level       INT
  reason      VARCHAR(500)
  created_at  TIMESTAMPTZ

disable_requests
  id          INT PRIMARY KEY
  student_id  INT FK → students
  reason      VARCHAR(500)
  status      VARCHAR(20)  -- pending/approved/rejected
  reviewed_at TIMESTAMPTZ
  created_at  TIMESTAMPTZ
```

## API Endpoints

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Faculty login |
| POST | `/api/auth/register` | Faculty registration |

### Students
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/students` | List all students (optional `?section=S01`) |
| POST | `/api/students/` | Add a new student |
| DELETE | `/api/students/{id}` | Remove a student |
| POST | `/api/students/{id}/re-enable` | Re-enable monitoring |
| GET | `/api/students/sections` | List distinct sections |

### Monitoring
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/monitoring/start` | Start all monitoring |
| POST | `/api/monitoring/stop` | Stop all monitoring |
| GET | `/api/monitoring/state` | Current state summary |
| POST | `/api/monitoring/heartbeat` | Student heartbeat |

### Disable Requests
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/disable-requests/` | Create request (from agent) |
| GET | `/api/disable-requests/` | List (optional `?status_filter=pending`) |
| POST | `/api/disable-requests/review` | Approve/reject |

### AI
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ai/result` | AI classification callback |

### WebSocket
| Path | Params | Description |
|------|--------|-------------|
| `/ws/faculty` | `?token=...` | Faculty realtime updates |
| `/ws/agent` | `?device_id=...` | Agent connection |

### WebSocket Events (Server → Client)
| Event | Payload |
|-------|---------|
| `student_status` | `{student_id, name, section, status, reason, warning_count}` |
| `faculty_notification` | `{type, student_name, section, reason}` |
| `disable_requested` | `{student_name, section, reason, request_id}` |
| `warning` | `{level, message, reason}` |
| `monitoring_started` | `{}` |
| `monitoring_stopped` | `{}` |
| `monitoring_paused` | `{reason}` |

## Setup Instructions

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16
- Rust (for desktop agent)
- Docker (optional)

### 1. Database
```bash
# Using Docker
docker run -d --name classguard-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=classguard \
  -p 5432:5432 \
  postgres:16-alpine
```

### 2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. AI Service
```bash
cd ai-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 5. Desktop Agent
```bash
cd desktop-agent

# Create device ID and server config
echo "CG-MY-DEVICE-001" > classguard_device_id.txt
echo "localhost:8000" > classguard_server.txt

# Run
cargo run
```

### 6. Register Faculty
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"faculty@college.edu","password":"admin123"}'
```

### 7. Add Students (from dashboard or API)
```bash
# Login first
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"faculty@college.edu","password":"admin123"}' | jq -r '.access_token')

# Add student
curl -X POST http://localhost:8000/api/students/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Rahul Sharma","section":"S01","device_id":"CG-MY-DEVICE-001"}'
```

### 8. Start Monitoring (from dashboard)
Click "Start Monitoring" on the dashboard, or:
```bash
curl -X POST http://localhost:8000/api/monitoring/start \
  -H "Authorization: Bearer $TOKEN"
```

## Workflow

1. **Faculty registers** students via dashboard (name, section, device ID)
2. **Student runs** ClassGuard Agent on their laptop
3. **Faculty clicks** "Start Monitoring" — agent begins capturing + sending
4. **AI Service** classifies screen content every ~5 seconds
5. **Students receive** native Windows warnings if off-task (3 strikes)
6. **Faculty dashboard** shows real-time status per section/student
7. **Students can request** temporary disable with reason
8. **Faculty approves/rejects** — monitoring pauses for that student only
9. **If agent closes**, backend detects missing heartbeat → marks offline

## AI Classification Logic

The classifier uses keyword matching on:
- **Window titles** (e.g., "Visual Studio Code" → studying)
- **Browser tab titles** (e.g., "Netflix" → off-task)
- **YouTube content patterns** (lecture/tutorial → studying; trailer/movie → off-task)

Extensible to:
- OCR text extraction (tesseract)
- ML-based screen classification
- Active window tracking

## Warning System

| Warning | Action |
|---------|--------|
| 1st | "You appear to be off-task." (student notification) |
| 2nd | "Second warning. Please return to class activities." |
| 3rd | "Final warning. Faculty has been notified." + faculty alert |
