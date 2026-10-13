# Christmas Charity Raffle

Angular front end + FastAPI back end + PostgreSQL.

- Public users need no login: pick squares on the picture grid, confirm with name + employee number, later enter a lock-in code.
- Held squares are released automatically after `hold_days` (default 5) if no code is entered.
- Admin (`/admin`) sees every entry with details and lock-in code, can release squares, regenerate codes, mark entries locked, manage prizes, upload the image, set grid size, price, charity %, and title.
- Admin can manage charity vote options; each locked-in entry can cast one vote by re-entering its lock-in code. Public vote totals are visible on the home page.

## Run it

```powershell
# 1. Database
docker compose up -d

# 2. Backend (http://localhost:8000, docs at /docs)
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # then edit ADMIN_PASSWORD and JWT_SECRET
.\.venv\Scripts\uvicorn app.main:app --reload

# 3. Front end (http://localhost:4200, proxies /api to :8000)
cd frontend
npm install
npm start
```

Tables are created automatically on first start. Uploaded images live in `backend/uploads`.

## Deploy to Red Hat OpenShift

The following example builds the application images with Podman, pushes them to a
container registry accessible by your cluster, then deploys PostgreSQL and the
application into the current OpenShift project. Install `oc` and Podman, log in
to the cluster with `oc login`, and select your project with `oc project
your-project` first. These examples use a POSIX-compatible shell such as
Git Bash or WSL. Replace the example registry and secret values below.

Build and push both images from the repository root:

```sh
REGISTRY=quay.io/your-account
TAG=latest
BACKEND_IMAGE="$REGISTRY/christmas-backend:$TAG"
FRONTEND_IMAGE="$REGISTRY/christmas-frontend:$TAG"

podman login "$REGISTRY"
podman build -f backend/Containerfile -t "$BACKEND_IMAGE" .
podman push "$BACKEND_IMAGE"
podman build -f frontend/Containerfile -t "$FRONTEND_IMAGE" .
podman push "$FRONTEND_IMAGE"
```

Create PostgreSQL and store its credentials in an OpenShift Secret. Use a
strong, URL-safe password (letters and numbers only) so it can also be used in
the backend connection URL without URL-encoding:

```sh
oc create secret generic raffle-db \
  --from-literal=POSTGRES_USER=raffle \
  --from-literal=POSTGRES_PASSWORD='replace-with-a-strong-url-safe-password' \
  --from-literal=POSTGRES_DB=raffle
oc new-app postgres:16-alpine --name=raffle-db
oc set env deployment/raffle-db --from=secret/raffle-db
oc set env deployment/raffle-db PGDATA=/var/lib/postgresql/data/pgdata
oc set volume deployment/raffle-db --add --name=raffle-db-data \
  --type=pvc --claim-size=5Gi --mount-path=/var/lib/postgresql/data
oc rollout status deployment/raffle-db
```

Create the backend Secret with the same database password, plus a strong admin
password and a long random JWT secret. Do not commit real secret values:

```sh
oc create secret generic raffle-api \
  --from-literal=DATABASE_URL='postgresql+psycopg://raffle:replace-with-a-strong-url-safe-password@raffle-db:5432/raffle' \
  --from-literal=ADMIN_USERNAME=admin \
  --from-literal=ADMIN_PASSWORD='replace-with-a-strong-admin-password' \
  --from-literal=JWT_SECRET='replace-with-a-long-random-secret'
oc new-app "$BACKEND_IMAGE" --name=raffle-api
oc set env deployment/raffle-api --from=secret/raffle-api
oc set volume deployment/raffle-api --add --name=raffle-uploads \
  --type=pvc --claim-size=1Gi --mount-path=/app/uploads
oc rollout status deployment/raffle-api
```

The backend runs database migrations when it starts. Keep it at one replica:
the uploads volume stores the admin-uploaded image and is intended for a single
backend pod. PostgreSQL data and uploads are stored in persistent volume claims.
This example database is a single PostgreSQL pod for small deployments; use
your organization's managed database or PostgreSQL Operator for production
high availability and backup policies.

Deploy and expose the frontend. Its Nginx configuration serves Angular routes
and forwards `/api` requests to the backend service, so the backend does not
need a public route:

```sh
oc new-app "$FRONTEND_IMAGE" --name=raffle-web
oc rollout status deployment/raffle-web
oc create route edge raffle-web --service=raffle-web --insecure-policy=Redirect
oc get route raffle-web
```

Open the route's HTTPS URL. For updates, rebuild and push an image with a new
tag, then update the matching deployment image (for example,
`oc set image deployment/raffle-api raffle-api="$BACKEND_IMAGE"`). Back up the
PostgreSQL and uploads persistent volumes. `CORS_ORIGINS` can be left unset for
this same-origin frontend/API setup; set it to the allowed origin(s) only if
you call the API directly from another website.

## Notes

- Lock-in codes (`XXXX-XXXX`) are generated on every confirmation and are visible only to the admin. Regenerating a code also restarts the hold period. After 10 wrong attempts the entry must have its code regenerated.
- Grid size can only change while no entries exist.
- Charity votes are associated with the employee number (case-insensitive), so creating multiple entries or buying multiple squares still allows only one vote per employee. Charity options with votes and entries that have voted cannot be deleted or released, preserving the tally.
- Production: set `JWT_SECRET`, a strong `ADMIN_PASSWORD`, `CORS_ORIGINS`, build with `ng build`, and serve `dist/` behind a reverse proxy that forwards `/api`.
