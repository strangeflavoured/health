# Dev Workflow

## Project Structure (Reference)

```
health/
  backend/
    apps/
      api/
        connection.py   # Redis singleton wrapping docker_redis_connect
        views.py
        urls.py
      workers/
        tasks.py        # empty, ready for Celery
    config/
      settings/
        base.py
        dev.py
        prod.py
      urls.py
      wsgi.py
    requirements/
      base.txt
      dev.txt
      prod.txt
    manage.py
    Dockerfile
    .env                # DJANGO_SETTINGS_MODULE, REDIS_HOST/PORT/DB etc.
  frontend/
    src/
      components/
      hooks/
      pages/
      services/
        api.js          # all axios calls live here
    vite.config.js      # proxy: /api/* → localhost:8000
    Dockerfile
  src/                  # existing importer
    importer/
    connection.py       # docker_redis_connect - shared with backend
  secrets/              # Docker secrets (gitignored)
  scripts/
  nginx/
    nginx.conf          # prod only
  compose.yml
  compose.prod.yml
  .env                  # DJANGO_SECRET_KEY (gitignored)
  .env.example          # variable names with dummy values (committed)
  .gitignore
```

---

## Starting the Stack

```bash
# start redis in background
./scripts/compose-wrapper up -d redis redisinsight backend frontend

# rebuild images (after changing Dockerfile or requirements)
docker compose --build backend frontend
```

The importer has `restart: "no"` — it runs once on startup to load data into
Redis, then exits. Re-run it manually if needed:

```bash
docker compose run --rm importer
```

**Services when running:**

| Service | URL                         |
| ------- | --------------------------- |
| React   | http://localhost:5173       |
| Django  | http://localhost:8000       |
| Admin   | http://localhost:8000/admin |
| Redis   | localhost:6379 (internal)   |

---

## First-Time Setup

Run these once after initial clone or after wiping the database:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

---

## Day-to-Day Backend (Django)

```bash
# run a migration after changing models
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate

# open a Django Python shell (Django ORM + settings loaded)
docker compose exec backend python manage.py shell

# check for config errors
docker compose exec backend python manage.py check

# install a new package
# 1. add to requirements/base.txt
# 2. rebuild
docker compose up --build backend
```

Code changes in `backend/` hot-reload automatically via the volume mount —
no rebuild needed for `.py` file edits.

---

## Day-to-Day Frontend (React)

```bash
# install a new npm package
./scripts/compose-wrapper exec frontend npm install <package>
# then commit the updated package.json and package-lock.json
```

Code changes in `frontend/src/` hot-reload automatically via Vite's HMR —
no restart needed.

To add a new API call, add it to `frontend/src/services/api.js`:

```javascript
export const getMyData = (params) => api.get("/api/my-endpoint/", { params });
```

The Vite proxy in `vite.config.js` forwards all `/api/*` requests to
`http://localhost:8000` — no CORS config needed in dev.

---

## Adding a New API Endpoint

1. Add the view in `backend/apps/api/views.py`
2. Register the URL in `backend/apps/api/urls.py`
3. Call it from `frontend/src/services/api.js`

```python
# views.py
@api_view(['GET'])
def my_endpoint(request):
    r = get_redis_client()
    value = r.get('some_key')
    return Response({'result': value})
```

```python
# urls.py
urlpatterns = [
    path('health/', views.health),
    path('my-endpoint/', views.my_endpoint),  # add here
]
```

```javascript
export const getMyData = (params) => api.get("/api/my-endpoint/", { params });
```

---

## Logs

```bash
# follow all logs
docker compose logs -f

# follow a single service
docker compose logs -f backend
docker compose logs -f frontend

# last 50 lines
docker compose logs --tail 50 backend
```

---

## Stopping and Cleaning Up

```bash
# stop all services (keeps containers and volumes)
./scripts/compose-wrapper down

# stop and remove volumes (wipes Redis data and SQLite)
./scripts/compose-wrapper down -v

# stop a single service
docker compose stop backend
```

---

## Running Tests

```bash
# backend
docker compose exec backend python -m pytest

# with coverage
docker compose exec backend python -m pytest --cov=apps

# frontend (if configured)
docker compose exec frontend npm test
```

---

## Remote Access (Tailscale)

With Tailscale installed and running on both devices:

```bash
# find your Tailscale IP
tailscale ip

# then on any device on your Tailscale network
http://100.x.x.x:3000   # React
http://100.x.x.x:8000   # Django API
```

No tunnels or port forwarding needed. Works across WiFi and mobile data.

---

## Environment Variables Reference

```bash
# backend/.env
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY=your-dev-secret-key
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
```

Secrets (Redis password, certs) are mounted via Docker secrets from `secrets/`
and read directly by `docker_redis_connect()` — they do not go in `.env`.
