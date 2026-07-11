# AlumniAI — AI-Powered Alumni Management System

> A complete career acceleration platform connecting students, alumni, and faculty through AI-powered tools, live sessions, smart referrals, and real-time notifications.

## 🚀 Live Demo
[Deployment URL Pending]

## 📋 Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Running Tests](#running-tests)
- [API Documentation](#api-documentation)
- [Deployment](#deployment)
- [Project Structure](#project-structure)

---

## Overview

AlumniAI is a full-stack Django application built as a final year capstone project. It solves the problem of disconnected alumni networks at colleges by creating a comprehensive ecosystem where:

- **Students** get AI-powered career tools, can book sessions from alumni/faculty, and apply to job referrals
- **Alumni** can host paid sessions, post job referrals, and earn 70% of every booking
- **Faculty** can recommend students to alumni referrals and host paid sessions
- **Admin** gets full platform control including user verification, payout management, and revenue analytics

---

## Features

### AI Tools (Powered by OpenAI GPT-4o-mini)
- **Resume Score Checker** — AI scores resume 0-100 with ATS analysis (1 free, ₹49/use)
- **AI Mock Interviewer** — Personalized interview questions + per-answer feedback (₹99/session)
- **Skill Gap Analyzer** — Identifies missing skills with learning roadmap (₹79/analysis)
- **AI Resume Builder** — Generates professional resume from profile (₹149/build)

### Sessions & Booking
- 7 session types: Group, 1:1, Cohort, Doubt Clearing, Project Guidance, Career, Recorded
- Razorpay payment integration with signature verification
- 70/30 revenue split (alumni gets 70%, platform keeps 30%)
- Free demo session for students (first booking)
- Celery-powered session reminders 1 hour before

### Referral System
- AI skill matching — students get a match score (0-100) before applying
- Students below 40% match cannot apply (skill-gated)
- Faculty can recommend students directly to alumni referrals
- Max 5 applicants per referral (first come first serve)
- Application status tracking: Applied → Shortlisted → Interview → Hired

### Payments & Wallet
- Centralized Transaction model tracking all money movement
- Wallet system for alumni and faculty with weekly payouts
- Admin manually approves and processes payouts every Monday
- ₹500 minimum withdrawal threshold
- Invoice generated for every transaction

### Real-time Notifications
- Django Channels WebSocket for instant notifications
- JWT-authenticated WebSocket connections
- Toast notifications for new in-app alerts
- Email notifications via Celery (preferences-based)
- Polling fallback when WebSocket is unavailable

### Admin Dashboard
- Complete user management (suspend, verify, delete)
- Alumni verification queue with document review
- Content moderation (posts, sessions, referrals)
- Revenue analytics with Chart.js visualizations
- Payout management (approve, process, reject)
- Broadcast notifications to all users or specific roles
- Full audit log of all admin actions

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.x, Django REST Framework |
| Authentication | JWT (djangorestframework-simplejwt) |
| Real-time | Django Channels 4.x, WebSocket |
| Async Tasks | Celery 5.x, Redis |
| Database | PostgreSQL |
| Cache | Redis |
| AI | OpenAI GPT-4o-mini |
| Payments | Razorpay |
| CV Parsing | PyPDF2, python-docx |
| Static Files | WhiteNoise |
| Frontend | Django Templates, Tailwind CSS, Vanilla JS, Chart.js |
| ASGI Server | Daphne |
| Production Server | Gunicorn + Uvicorn Workers |

---

## Architecture

```
Browser / Client
       │
       ├── HTTP Requests ──────→ Django (DRF REST API)
       │                               │
       │                               ├── PostgreSQL (data)
       │                               ├── Redis (cache)
       │                               └── OpenAI API / Razorpay API
       │
       └── WebSocket ──────────→ Django Channels
                                       │
                                       └── Redis Channel Layer

Celery Worker ←── Redis Broker ←── Django (task queue)
     │
     ├── Email notifications
     ├── Session reminders
     └── Notification cleanup
```

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Git

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/alumniai.git
cd alumniai
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env with your actual values
```

### 5. Create database
```bash
createdb alumniai_db
```

### 6. Run migrations
```bash
python manage.py migrate --settings=alumni_platform.settings.dev
```

### 7. Create dev users (for testing)
```bash
python manage.py create_dev_users --settings=alumni_platform.settings.dev
```

### 8. Collect static files
```bash
python manage.py collectstatic --noinput --settings=alumni_platform.settings.dev
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values:

| Variable | Description | Required |
|----------|-------------|----------|
| SECRET_KEY | Django secret key (long random string) | Yes |
| DEBUG | True for dev, False for prod | Yes |
| DATABASE_URL | PostgreSQL connection URL | Yes |
| REDIS_URL | Redis connection URL | Yes |
| OPENAI_API_KEY | OpenAI API key for AI tools | Yes |
| RAZORPAY_KEY_ID | Razorpay public key | Yes |
| RAZORPAY_KEY_SECRET | Razorpay secret key | Yes |
| DEFAULT_FROM_EMAIL | Email sender address | Yes |
| EMAIL_HOST_USER | SMTP email address | Prod only |
| EMAIL_HOST_PASSWORD | SMTP app password | Prod only |

---

## Running the Project

### Development server (with WebSocket support)
```bash
# Option 1: Using Daphne (recommended — supports WebSocket)
daphne -p 8000 alumni_platform.asgi:application

# Option 2: Django's runserver (also supports channels)
python manage.py runserver --settings=alumni_platform.settings.dev
```

### Start Celery worker (required for email and task queues)
```bash
celery -A alumni_platform worker --loglevel=info
```

### Start Celery Beat (for periodic tasks — session reminders, cleanup)
```bash
celery -A alumni_platform beat --loglevel=info
```

### Using Makefile shortcuts
```bash
make dev        # Start dev server
make worker     # Start Celery worker
make beat       # Start Celery Beat
make test       # Run all tests
make migrate    # Run migrations
make shell      # Open Django shell
make devusers   # Create dev test users
```

### DEV Role Switcher
A floating "DEV" button appears in the bottom-left corner of every page.
Click it to instantly switch between roles without logging in:
- 🟡 Student: dev.student@college.ac.in
- 🟣 Alumni: dev.alumni@techcompany.com
- 🟢 Faculty: dev.faculty@college.ac.in
- 🔴 Admin: dev.admin@alumniai.com

---

## Running Tests

```bash
# Run all tests
pytest tests/ --ds=alumni_platform.settings.dev

# Run with verbose output
pytest tests/ -v --ds=alumni_platform.settings.dev

# Run specific test file
pytest tests/test_sessions.py -v --ds=alumni_platform.settings.dev

# Run with coverage report
pytest tests/ --ds=alumni_platform.settings.dev --cov=apps --cov-report=term-missing

# Run with coverage minimum threshold
pytest tests/ --ds=alumni_platform.settings.dev --cov=apps --cov-fail-under=70
```

### Test Coverage by Module
| Module | Tests | Coverage |
|--------|-------|----------|
| Auth & Profiles | 24 | ~90% |
| Feed System | 20 | ~85% |
| Sessions & Booking | 32 | ~88% |
| Referral System | 33 | ~90% |
| Payments & Wallet | 28 | ~85% |
| AI Tools | 33 | ~82% |
| Admin Dashboard | 30 | ~85% |
| Notifications | 32 | ~88% |
| Integration Tests | 6 | — |
| **Total** | **238+** | **~87%** |

---

## API Documentation

### Authentication
All API endpoints require a JWT Bearer token in the Authorization header:
```
Authorization: Bearer <access_token>
```

### Key Endpoints

#### Auth
- `POST /api/accounts/register/` — Register new user
- `POST /api/accounts/login/` — Login (returns JWT)
- `POST /api/accounts/logout/` — Logout (blacklists token)
- `GET /api/accounts/me/` — Get current user info

#### Feed
- `GET /api/feed/` — Get feed posts (paginated, filterable)
- `POST /api/feed/` — Create post (alumni/faculty only)
- `POST /api/feed/{id}/like/` — Toggle like
- `POST /api/feed/{id}/comments/` — Add comment

#### Sessions
- `GET /api/sessions/` — Browse sessions (filterable)
- `POST /api/sessions/` — Create session (alumni/faculty)
- `POST /api/sessions/{id}/book/` — Book session
- `POST /api/sessions/payment/verify/` — Verify Razorpay payment
- `GET /api/sessions/my-bookings/` — Student's bookings
- `GET /api/sessions/hosting/` — Alumni's hosted sessions

#### Referrals
- `GET /api/referrals/` — Browse referrals (with skill match scores)
- `POST /api/referrals/` — Post referral (alumni/faculty)
- `GET /api/referrals/{id}/match-check/` — Check skill match score
- `POST /api/referrals/{id}/apply/` — Apply (if match ≥ 40%)
- `GET /api/referrals/my-applications/` — Student's applications

#### Payments
- `GET /api/payments/wallet/` — Wallet balance + transactions
- `POST /api/payments/payout/` — Request payout
- `POST /api/payments/ai-tools/init/` — Initiate AI tool payment
- `POST /api/payments/ai-tools/verify/` — Verify AI tool payment
- `POST /api/payments/boost/` — Boost referral (₹99)

#### AI Tools
- `POST /api/ai/resume-score/` — Score resume
- `POST /api/ai/resume-build/` — Build resume
- `POST /api/ai/interview/` — AI interview (start/answer/finish)
- `POST /api/ai/skill-gap/` — Analyze skill gap

#### Notifications
- `GET /api/notifications/` — List notifications
- `GET /api/notifications/unread-count/` — Unread badge count
- `PATCH /api/notifications/{id}/` — Mark as read
- `POST /api/notifications/bulk/` — Bulk actions
- `GET/PATCH /api/notifications/preferences/` — Manage preferences

#### Admin
- `GET /api/dashboard/admin/overview/` — Platform stats
- `GET /api/dashboard/admin/users/` — User management
- `POST /api/dashboard/admin/users/{id}/action/` — User actions
- `GET/POST /api/dashboard/admin/alumni/verification/` — Alumni verification
- `GET/POST /api/dashboard/admin/moderation/` — Content moderation
- `POST /api/dashboard/admin/broadcast/` — Send broadcast

### WebSocket
Connect to real-time notifications:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/notifications/?token=ACCESS_TOKEN');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.type: 'new_notification' | 'unread_count'
};
```

---

## Deployment

### Deploy to Render.com (Recommended)

1. Push code to GitHub
2. Go to render.com → New → Blueprint
3. Connect your GitHub repository
4. Render will detect `render.yaml` and create the web, Redis, PostgreSQL, worker, and beat services automatically
5. Set the required environment variables in Render:
  - `ALLOWED_HOSTS` with your Render domain, for example `your-app.onrender.com`
  - `OPENAI_API_KEY`
  - `RAZORPAY_KEY_ID`
  - `RAZORPAY_KEY_SECRET`
  - `DEFAULT_FROM_EMAIL`
  - `EMAIL_HOST_USER`
  - `EMAIL_HOST_PASSWORD`
  - `GROQ_API_KEY` if you use the Groq-powered AI tools
  - `GEMINI_API_KEY` if you use Gemini-based parsing
  - `AFFINDA_API_KEY` and related Affinda IDs if you use Affinda parsing
6. Deploy

### Render Notes

- `DJANGO_SETTINGS_MODULE` is set to `alumni_platform.settings.prod` in `render.yaml`
- `ENVIRONMENT=prod` is used to force production settings selection
- Migrations run before deploy, and Celery worker/beat services are included in the blueprint
- Use a long random `SECRET_KEY`; Render can generate it automatically

### Render Environment Variables

Set these in the Render dashboard if you are not relying entirely on the blueprint-generated values:

- `ALLOWED_HOSTS` - your Render app domain, for example `your-app.onrender.com`
- `OPENAI_API_KEY`
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `DEFAULT_FROM_EMAIL`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `GROQ_API_KEY` if you use the Groq AI tools
- `GEMINI_API_KEY` if you use Gemini-based parsing
- `AFFINDA_API_KEY`, `AFFINDA_WORKSPACE_ID`, and `AFFINDA_COLLECTION_ID` if you use Affinda parsing

### Deploy with Docker
```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f web

# Run migrations
docker-compose exec web python manage.py migrate --settings=alumni_platform.settings.prod

# Create dev users
docker-compose exec web python manage.py create_dev_users --settings=alumni_platform.settings.prod
```

---

## Project Structure

```
alumniai/
├── alumni_platform/          # Django project config
│   ├── settings/
│   │   ├── base.py           # Shared settings
│   │   ├── dev.py            # Development settings
│   │   └── prod.py           # Production settings
│   ├── urls.py               # Main URL config
│   ├── asgi.py               # ASGI config (WebSocket)
│   └── celery.py             # Celery config
│
├── apps/                     # All Django apps
│   ├── accounts/             # Auth, profiles, user management
│   ├── feed/                 # Posts, likes, comments
│   ├── sessions_app/         # Sessions, bookings, reviews
│   ├── referrals/            # Referrals, applications
│   ├── payments/             # Transactions, wallet, payouts, AI tool usage
│   ├── ai_tools/             # AI tool views and page routes
│   ├── notifications/        # Notifications, WebSocket consumer
│   └── dashboard/            # Admin dashboard and role dashboards
│
├── utils/                    # Shared utilities
│   ├── notify.py             # Central notification sender
│   ├── skill_matcher.py      # AI skill matching engine
│   ├── payment_utils.py      # Razorpay helpers, split calculations
│   ├── ai_tools_service.py   # OpenAI service functions
│   ├── permissions.py        # Custom DRF permissions
│   ├── middleware.py         # JWT auth middleware
│   └── auth_helpers.py       # Token helpers
│
├── templates/                # Django HTML templates
│   ├── base.html             # Base template (user-facing)
│   ├── admin_panel/          # Admin dashboard templates
│   ├── accounts/             # Auth and profile templates
│   ├── feed/                 # Feed templates
│   ├── sessions_app/         # Session templates
│   ├── referrals/            # Referral templates
│   ├── payments/             # Payment and wallet templates
│   ├── ai_tools/             # AI tool templates
│   ├── notifications/        # Notification templates
│   └── dashboard/            # Role dashboard templates
│
├── static/
│   ├── css/main.css          # Global styles
│   └── js/                   # JavaScript files
│       ├── api.js            # API fetch helpers
│       ├── main.js           # Global JS (navbar, toast, logout)
│       ├── feed.js           # Feed page JS
│       ├── sessions.js       # Sessions page JS
│       ├── referrals.js      # Referrals page JS
│       ├── payments.js       # Payments page JS
│       ├── ai_tools.js       # AI tools page JS
│       ├── notifications.js  # Real-time notifications JS
│       ├── admin_panel.js    # Admin dashboard JS
│       └── profile.js        # Profile page JS
│
├── tests/                    # Test suite
│   ├── conftest.py           # Shared fixtures
│   ├── test_auth_flow.py     # Auth tests
│   ├── test_profiles.py      # Profile tests
│   ├── test_feed.py          # Feed tests
│   ├── test_sessions.py      # Session tests
│   ├── test_referrals.py     # Referral tests
│   ├── test_payments.py      # Payment tests
│   ├── test_ai_tools.py      # AI tool tests
│   ├── test_admin.py         # Admin tests
│   ├── test_notifications.py # Notification tests
│   └── test_integration.py   # End-to-end integration tests
│
├── logs/                     # Log files (gitignored)
├── media/                    # User uploads (gitignored)
├── staticfiles/              # Collected static files (gitignored)
│
├── Dockerfile
├── docker-compose.yml
├── Procfile
├── render.yaml
├── gunicorn.conf.py
├── Makefile
├── runtime.txt
├── requirements.txt
├── .env.example
├── .env.production.example
├── .gitignore
└── README.md
```

---

## Development Notes

### Dev Role Switcher
The DEV panel is only visible when `DEBUG=True`. It creates test users automatically and lets you switch roles instantly for testing.

### Running with WebSocket
Use `daphne` instead of `runserver` for full WebSocket support:
```bash
daphne -p 8000 alumni_platform.asgi:application
```

### Razorpay Test Mode
Use Razorpay test keys (rzp_test_...) during development. Test card: 4111 1111 1111 1111.

### OpenAI Costs
AI tools make real API calls to OpenAI. Use the mock fixtures in tests to avoid costs:
```python
@pytest.fixture
def mock_openai(monkeypatch):
    # See tests/conftest.py for the complete mock
```

---

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/your-feature`
3. Write tests for your feature
4. Ensure all tests pass: `make test`
5. Submit a pull request

---

## License

MIT License — see LICENSE file for details.

---

## Acknowledgements

Built with Django, OpenAI, Razorpay, Redis, PostgreSQL, and Django Channels.
Final Year Capstone Project — 2024-25.




run ##
D:\AI-Powered-Alumni-Management-System\AI-Powered-Alumni-Management-System> & 'C:\Users\shyam\AppData\Local\Programs\Python\Python311\python.exe' manage.py runserver 127.0.0.1:8000




<!-- final run in terminal -->

Windows PowerShell me local run ke liye ye steps use karo:
Set-Location D:\AI-Powered-Alumni-Management-System\AI-Powered-Alumni-Management-System

Agar pehli baar run kar rahe ho to dependencies install karo:

& 'C:\Users\shyam\AppData\Local\Programs\Python\Python311\python.exe' -m pip install -r requirements.txt

Dev environment set karo:

$env:DJANGO_SETTINGS_MODULE='alumni_platform.settings.dev'
$env:ENVIRONMENT='dev'
$env:ALLOWED_HOSTS='localhost,127.0.0.1,testserver'

Database migrate karo:

& 'C:\Users\shyam\AppData\Local\Programs\Python\Python311\python.exe' manage.py migrate --settings=alumni_platform.settings.dev

Server run karo:

& 'C:\Users\shyam\AppData\Local\Programs\Python\Python311\python.exe' manage.py runserver 127.0.0.1:8000

Agar WinError 10048 aaye to port 8000 pe pehle se server chal raha hai. Usko band karo:

Get-NetTCPConnection -LocalPort 8000 -State Listen
Stop-Process -Id <PID>
