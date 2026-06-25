# Job Portal - Backend

REST and WebSocket API for a task marketplace (Airtasker-style). Customers post jobs; taskers bid, complete work, and get paid via wallet and escrow. Django 5 + Django REST Framework, with real-time chat, Celery, and Nepal payment gateways (Khalti / eSewa).

## Tech stack

| Layer | Technology |
|-------|------------|
| Framework | Django 5, Django REST Framework |
| Auth | SimpleJWT, django-allauth (Google / Facebook) |
| Real-time | Django Channels, Daphne, Redis |
| Jobs | Celery, Celery Beat |
| Database | PostgreSQL (SQLite for local dev) |
| Payments | Khalti, eSewa, wallet escrow |
| Admin | Jazzmin + custom analytics dashboards |
| API docs | drf-spectacular (OpenAPI) |

## Features

- User accounts, roles, profiles, badges
- Tasks, bids, and full task lifecycle
- Wallets, recharges, withdrawals, platform fees
- Escrow and payment processing
- Real-time chat
- Reviews, disputes, configurable rule engine
- Notifications (in-app and email)
- Admin analytics dashboards

## Apps

```
apps/
  users/          accounts/       tasks/          bids/
  wallets/        payments/       fees/           chat/
  reviews/        disputes/       rules/          notifications/
  analytics/      locations/      search/         dashboard/
  blog/           uploads/
```

## Getting started

**Prerequisites:** Python 3.11+, PostgreSQL 14+, Redis 6+

```bash
git clone https://github.com/everpeaknp/Job-Portal-Backend.git
cd Job-Portal-Backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements/base.txt
cp .env.example .env           # edit values
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

**Background workers (optional):**

```bash
celery -A config worker -l info
celery -A config beat -l info
```

For WebSockets, run with Daphne: `daphne config.asgi:application`

## Deployment

### Level 1: Minimal VPS setup

This is the default path for a small server:

```bash
cp .env.example .env
# edit .env for production values
bash scripts/deploy.sh
```

The default container startup does:

- database migrations
- static file collection
- Daphne server startup

Run workers only if you need them:

```bash
docker compose --profile worker --profile beat up -d
```

Create admin users manually when needed:

```bash
docker compose exec web python manage.py createsuperuser
```

### Level 2: Proper production VPS setup

Use the same image, but keep the process split:

- `web` for the API
- `worker` for background jobs
- `beat` for scheduled jobs

Put the stack behind Nginx or Caddy, terminate TLS there, and keep `.env` on the server only.

### Level 3: Cloud-native container deployment

This codebase also fits a managed container platform:

- Cloud Run
- Azure Container Apps
- ECS/Fargate

Build one image, push it, and run the API container with platform-managed ingress and secrets.

## API docs

With the server running:

- Swagger UI: `/api/schema/swagger-ui/`
- OpenAPI schema: `/api/schema/`
- Admin: `/admin/`

## Environment

Copy `.env.example` to `.env`. See that file for database, Redis, JWT, OAuth, payment, and email settings.

## License

Proprietary. All rights reserved.
