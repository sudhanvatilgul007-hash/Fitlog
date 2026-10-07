# fitlog

A mobile-first personal food, protein and activity journal built from the supplied FitLog PRD, using the requested name **fitlog**. React + TypeScript + Vite, FastAPI + Pydantic, SQLAlchemy + Alembic, PostgreSQL in deployment. SQLite is supported for a quick local start.

## Start locally

Requirements: Python 3.13+, Node 22.12+ (Node 24 recommended), npm. From this repository:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock.txt
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.seed
../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, from the repository root:

```sh
cd frontend
npm ci
npm run dev
```

Open the URL printed by Vite (usually http://localhost:5173). Vite proxies `/api` to port 8000. `/api/docs` is not a route; the API documentation is at http://localhost:8000/docs.

The local seed is repeatable and does not overwrite edited presets/settings. The default SQLite database is `backend/fitlog.db`. Existing saved entries retain their original nutrition even when a preset changes. No AI request occurs during startup, logging, settings, history, or viewing saved analysis.

## Enable analysis

Copy `backend/.env.example` to `backend/.env` and set `LLM_API_KEY` privately, then start with:

```sh
cd backend
../.venv/bin/uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

The API key is server-only. Do not prefix it with `VITE_`, commit `.env`, or put it in Netlify frontend variables. Without a configured provider key the journal works; analysis returns an error and permits an explicit retry. Tests mock the provider and incur no charges.

Configuration:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL, or local SQLite fallback |
| `LLM_PROVIDER` | `openai` or `openai-compatible` |
| `LLM_MODEL` | A model supporting strict JSON schema output; default `gpt-4.1-mini` |
| `LLM_API_KEY` | Server-side provider key |
| `LLM_BASE_URL` | OpenAI-compatible API base URL, default `https://api.openai.com/v1` |
| `APP_TIMEZONE` | Server Today/history calendar, default `Asia/Kolkata` |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `APP_ENV`, `FRONTEND_URL` | Deployment metadata |
| `API_PROXY_TARGET` | Optional development backend proxy destination |
| `FRONTEND_DIST` | Optional path to a built frontend; set to `/app/static` in the combined Railway image |

The provider issues one HTTP request with strict schema output and no automatic retry. Format follows [OpenAI structured-output documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat). Its default model can be changed with the environment; compatible providers must support the same Chat Completions JSON-schema contract.

## Calculations and analysis behavior

- Nutrition = preset label values × entered quantity / base quantity.
- Walking estimate = configurable coefficient (0.5 initially) × weight kg × km. 95.5 kg × 8.16 km gives 389.64 kcal.
- Deficit = selected TDEE − food calories. Walking and gym burn are informational and never added to TDEE again.
- Cycling uses 6 MET; resistance sessions with duration use 3.5 MET; treadmill uses a level-walking speed estimate. Exercise-count-only sessions have no calorie estimate until duration is supplied (shown as zero). These are estimates, not personalized physiological calculations.
- Missing carb/fat labels are marked as partial totals, rather than presented as complete data.
- History averages use recorded days, including unfinished logs. The seven- and thirty-day windows end at `to` or the server’s current date. Protein adherence uses the current configured minimum.
- Food units must match each preset’s natural base unit. Create a separate preset for a spoon/serving conversion whose weight is unknown. Cooked and dry foods are visibly separate.
- Targets/formula configuration are included in the frozen analysis snapshot. Changing settings can mark an existing analysis stale.

Every Analyze action first creates a canonical SHA-256 snapshot claim with a database uniqueness constraint. Equivalent numeric values (2500 and 2500.0) have the same hash. Successful repeated requests return the stored result. Concurrent requests see a pending claim and cannot contact the provider. A changed snapshot with prior successful analysis requires `confirmReanalysis: true`; the UI displays a cost confirmation. Provider/network/JSON failures mark the attempt failed without corrupting the log; retry requires `retry: true`. Earlier successful analyses remain available for audit.

If the server dies after claiming an analysis, it deliberately leaves the claim pending to avoid silently issuing another potentially billed request. An operator must check the provider outcome before explicitly changing that pending attempt to failed in the database and permitting retry. Exactly-once completion across a provider call and a local database commit cannot be guaranteed by an HTTP-only provider; the implementation favors preventing duplicate calls over automatic recovery.

## Seed data

Weight 95.5 kg; TDEE profiles 2500/3000/3250 kcal; protein 150–170 g; deficit 800–1000 kcal. Biozyme, Amul, bread, cheese and Pintola values follow the PRD. Soya, chapathi, rice, dal, palak dal and palya are editable starter estimates because exact label/recipe values were not supplied. Update these in Settings. Historical nutrition snapshots do not change when you edit these estimates.

## Verify

```sh
cd backend
../.venv/bin/pytest -q
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.seed
cd ../frontend
npm test
npm run build
```

Backend coverage includes deterministic nutrition and walking, immutable history, zero provider calls from CRUD/history, unchanged snapshot reuse, confirmation for changed snapshots, invalid output/network retry behavior, weight/unit validation and simultaneous Analyze requests. Frontend tests check quantity scaling, date formatting and error propagation. The frontend lockfile and backend lock requirements capture verified dependency versions.

For PostgreSQL locally (Docker required):

```sh
docker compose up --build
cd frontend
npm ci
npm run dev
```

The container runs migrations and seeds before serving. Docker Compose persists PostgreSQL in `fitlog-data`.

## Deploy frontend and backend together on Railway

1. Push the repository to your own Git repository. Create a Railway project with a PostgreSQL service and a service from this repository.
2. Leave the service Root Directory empty (repository root `/`) and use `/railway.json`. The root Dockerfile builds React with Node 24, then copies its static output and the Python backend into one runtime image. Railway should log `Using detected Dockerfile!` instead of attempting Railpack language detection. Clear any old `/backend` Root Directory, custom build/start command, or backend config-file path; if `RAILWAY_DOCKERFILE_PATH` is set, clear it or set it to `Dockerfile`. Building only `/backend` will not include the frontend.
3. Set `DATABASE_URL` to Railway’s PostgreSQL URL. Plain `postgresql://` and `postgres://` URLs are converted to the psycopg driver.
4. Set `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `APP_ENV=production`, `APP_TIMEZONE=Asia/Kolkata`, `FRONTEND_URL` and `CORS_ORIGINS` to your Railway public origin, for example `https://fitlog-production-057f.up.railway.app`. Keep secrets in Railway variables. The Dockerfile sets `FRONTEND_DIST=/app/static`; do not override it to another directory.
5. Deploy. Startup runs `alembic upgrade head`, then `python -m app.seed`, then uvicorn on Railway’s `PORT`. Use one migration runner during initial deployment; coordinate migrations separately before scaling replicas.
6. Open your Railway domain at `/` for the fitlog UI. `/api/health` returns JSON, `/docs` shows API documentation, and `/assets/*` serves the frontend bundles. The frontend calls `/api` on the same origin, so no frontend proxy or separate deployment is needed. Verify logging before enabling paid analysis. Enable PostgreSQL backups.

If deployment fails with `Railpack could not determine how to build the app` and lists both `backend/` and `frontend/`, redeploy the latest commit with the root Dockerfile/config above. There is no need for a `start.sh`. If `/` returns JSON `Not Found`, check that the latest combined-build commit was deployed from repository root, rather than the backend-only Dockerfile.

To verify the combined serving locally after `npm run build`:

```sh
cd backend
FRONTEND_DIST="$PWD/../frontend/dist" ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Visit http://127.0.0.1:8000 for the UI and http://127.0.0.1:8000/api/health for the API. If Docker is available, `docker build -t fitlog .` from repository root exercises the same multi-stage build used on Railway.

## Optional separate frontend deployment on Netlify

The combined Railway deployment above does not need Netlify. Use this section only if you deliberately want separate frontend hosting.

1. Replace `YOUR-FITLOG-BACKEND` in root `netlify.toml` with the real Railway backend hostname.
2. Import the repository into Netlify. Base directory `frontend`, publish directory `dist`, build `npm ci && npm run build`. Set `NODE_VERSION=24`.
3. The first redirect proxies `/api/*` to Railway. The second provides SPA fallback. No provider key belongs in the frontend environment.
4. Set the custom domain in Netlify, then update backend `FRONTEND_URL` and `CORS_ORIGINS`.
5. Verify on a phone: add 8–12 entries, select TDEE, analyze once, reopen history and verify stored analysis. Confirm that provider logs show only the explicit analysis requests.

This MVP intentionally has no authentication, as specified by the PRD. Put deployment behind a private access gateway that protects **both** the frontend and backend, or keep it local; CORS is not authentication. Do not publish personal journal data through an unprotected public API. The models include user ownership fields and a per-user daily uniqueness constraint for a future auth implementation; current routes serve the single `personal` owner.

Live provider calls and production deployment require your credentials. PostgreSQL/Docker verification requires Docker or an available PostgreSQL service; no deployment account or production key is included in this repository.
