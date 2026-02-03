# Jobot API (Production-ready starter)

## Included
- FastAPI REST API
- MariaDB (SQLAlchemy 2.0)
- Alembic migrations
- JWT auth (access + refresh, refresh rotation)
- Roles: `admin` and `user`
- Portfolio management per user + valuation
- Price alerts per user (Celery + Redis beat/worker checks alerts)
- Binance public price endpoint integration (no API keys required)
- ✅ Unit tests with pytest (SQLite in-memory)

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

## Run unit tests (local)
> Tests run on SQLite in-memory (no MariaDB/Redis needed)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q
```

## Create an admin user
Registration endpoint creates `user` role by default.
To create an admin quickly:
```sql
UPDATE users SET role='admin' WHERE email='admin@jobot.local';
```

Then re-login to get an access token with the `admin` role claim.

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

## Start
### Application
uvicorn app.main:app --reload --port 8000


