# Iaco Binance Portfolio API (Production-ready starter)

## What you get
- FastAPI REST API
- MariaDB (SQLAlchemy 2.0)
- Alembic migrations
- JWT auth (access + refresh, refresh rotation)
- Roles: `admin` and `user`
- Portfolio management per user
- Price alerts per user (Celery + Redis beat/worker checks alerts)
- Binance public price endpoint integration (no API keys required)

## Quick start (Docker)
1. Copy env:
   ```bash
   cp .env.example .env
   ```
2. Start:
   ```bash
   docker compose up --build
   ```
3. Open docs:
   - http://localhost:8000/docs

## Create an admin user
Registration endpoint creates `user` role by default.
To create an admin quickly, you can either:
- update `users.role` in DB to `admin`, OR
- modify `/auth/register` to accept role only for internal setup.

Example SQL:
```sql
UPDATE users SET role='admin' WHERE email='admin@iaco.local';
```

## Main endpoints
### Auth
- POST `/auth/register`
- POST `/auth/login`
- POST `/auth/refresh`
- GET `/auth/me`

### Prices (requires auth)
- GET `/prices/{symbol}`

### Admin prices (admin only)
- GET `/admin/price/{symbol}`

### Portfolio (requires auth)
- GET `/portfolio`
- POST `/portfolio` (upsert by symbol)
- DELETE `/portfolio/{asset_id}`
- GET `/portfolio/valuation`

### Alerts (requires auth)
- POST `/alerts`
- GET `/alerts`
- POST `/alerts/{alert_id}/deactivate`
- DELETE `/alerts/{alert_id}`
- GET `/alerts/events`

## Notes
- Alert checking interval: 30 seconds (`app/workers/celery_app.py`).
- Notifications: stored as `alert_events` (you can plug email/push/webhook later).
