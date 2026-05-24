# Dev Workflow

## Project structure (reference)

```
health/
  backend/                  # Django project
    apps/
      api/                  # REST API: connection.py, views.py, urls.py, models.py
      workers/              # background-work app (models/tests scaffolding)
    config/
      settings/             # base.py, dev.py, prod.py, test.py
      urls.py  asgi.py  wsgi.py
    requirements/           # base.in/.txt, tests.in/.txt
    manage.py
  frontend/                 # Vite + React + TypeScript
    src/
      services/api.ts       # all API calls live here
      App.tsx  main.tsx
    vite.config.ts          # dev proxy /api/* -> backend
    package.json
  src/                      # Apple Health importer (ETL)
    importer/               # parser, transform, data_check, pipeline, importer
    model/                  # HealthKit quantity/category type definitions
    connection.py           # docker_redis_connect - shared mTLS client
  docker/                   # Dockerfile.* per service, compose.yml, docker-bake.hcl
  scripts/                  # compose-wrapper.sh, certificate + secret tooling, CI tools
  docs/                     # this documentation
```

There is no `nginx/`, `compose.prod.yml`, Celery `tasks.py`, or `.env`-based
Redis password: production fronting, task queues, and secret distribution are
handled by the Docker image targets, `compose.yml`, and `pass` respectively.

---

## Running the stack

Always drive Compose through the wrapper so `pass` secrets are injected onto a
tmpfs and cleaned up afterwards. Do **not** call `docker compose up/down`
directly.

```bash
# start services in the background (mTLS secrets injected automatically)
./scripts/compose-wrapper.sh up -d redis redisinsight backend frontend

# rebuild images after changing a Dockerfile or requirements file
./scripts/compose-wrapper.sh build backend frontend
```

`compose-wrapper.sh build` runs `docker buildx bake` against
`docker/docker-bake.hcl`; pass a target or group name (e.g. `backend`, `infra`,
`tests`, `sandbox`).

**Services when running:**

| Service      | URL / port                          | Notes                      |
| ------------ | ----------------------------------- | -------------------------- |
| Frontend     | http://localhost:5173               | Vite dev server (HMR)      |
| Backend API  | http://localhost:8000               | Django dev server          |
| Admin        | http://localhost:8000/admin         |                            |
| Redis        | localhost:6380 (TLS, mTLS required) | reachable only with a cert |
| RedisInsight | http://localhost:5540               | GUI for the Redis instance |

---

## Day-to-day backend (Django)

Source under `backend/` is bind-mounted, so `.py` edits hot-reload without a
rebuild.

```bash
# run inside the running backend container
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py shell
docker compose exec backend python manage.py check
```

To add a Python dependency, edit the relevant `.in` file and recompile (see
[Managing Requirements](dev-tools.md)), then rebuild the image.

---

## Day-to-day frontend (React)

`frontend/src/` hot-reloads via Vite HMR. Add API calls in
`frontend/src/services/api.ts`:

```typescript
export const getMyData = (params: MyParams) =>
  api.get('/api/my-endpoint/', { params })
```

The dev proxy in `vite.config.ts` forwards `/api/*` to the backend, so no CORS
configuration is needed in development.

To add an npm package:

```bash
docker compose exec frontend npm install <package>
# commit the updated package.json and package-lock.json
```

---

## Adding a new API endpoint

1. Add the view in `backend/apps/api/views.py`.
2. Register the route in `backend/apps/api/urls.py`.
3. Call it from `frontend/src/services/api.ts`.

The API reads Redis through the shared mTLS client (`docker_redis_connect`), so
new endpoints inherit authentication and ACL scoping automatically.

---

## Logs

```bash
docker compose logs -f             # all services
docker compose logs -f backend     # one service
docker compose logs --tail 50 redis
```

---

## Stopping and cleaning up

```bash
# stop services and wipe the secret tmpfs (use the wrapper, not plain compose)
./scripts/compose-wrapper.sh down

# also remove volumes (wipes Redis data) - destructive
./scripts/compose-wrapper.sh down -v
```

---

## Running tests

Tests run inside Docker; this is the authoritative path that CI uses.

```bash
./scripts/compose-wrapper.sh run --rm --build test-runner    # src/ ETL tests
docker compose run backend-test                              # Django, 80% gate
docker compose run frontend-test                             # Vitest
docker compose run scripts-tests                             # Python script tests
docker compose run bats-tests                                # shell script tests
```

---

## Remote access (Tailscale)

With Tailscale on both devices, reach the stack over its tailnet IP without port
forwarding:

```bash
tailscale ip
# then from any device on the tailnet
http://100.x.x.x:5173   # frontend
http://100.x.x.x:8000   # backend API
```

---

## Environment and secrets

Non-secret backend configuration is set via `backend/.env`:

```bash
DJANGO_SETTINGS_MODULE=config.settings.dev
REDIS_HOST=redis
REDIS_PORT=6380
REDIS_DB=0
```

Secrets — the Django secret key, Redis ACL passwords, and TLS certificates and
keys — are **not** stored in `.env`. They are kept in `pass`, materialised onto
a tmpfs by `compose-wrapper.sh`, and mounted into containers as Docker secrets
under `/run/secrets`. See [Secrets Management with `pass`](pass-secrets.md).
