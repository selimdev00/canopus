# Canopus - customized Apache Superset 6.1.0

A customized, production-style build of [Apache Superset](https://superset.apache.org/)
`6.1.0`. `main` is the Superset 6.1.0 source snapshot; each customization landed
as its own pull request:

| PR | Change |
|----|--------|
| #1 | Build the production image from source + install `clickhouse-connect` |
| #2 | Replace the favicon |
| #3 | Replace the logo |
| #4 | Remove the "Powered by Apache Superset" watermark |
| #5 | Set one dashboard as the start page (works for non-admins) |
| #6 | Strip the `/superset/` prefix from URLs |
| #7 | This README |

All customizations live in `docker/canopus/` (config, branding, init scripts),
the `canopus` stage of the `Dockerfile`, and small backend patches in
`superset/views/`. None of them require a frontend rebuild.

## Requirements

- Docker + Docker Compose v2
- ~6 GB free disk and RAM for the first build (the frontend bundle is compiled
  from source).

## 1. Configure

```bash
cp .env.example .env
# edit .env: set a strong SUPERSET_SECRET_KEY (openssl rand -base64 42) and
# change the DB / examples passwords.
```

## 2. Build the image

The production image is the `canopus` Docker stage (upstream `lean` + the
postgres driver + `clickhouse-connect` + baked config and branding):

```bash
docker compose build
```

## 3. Run

```bash
docker compose up -d
```

Services: `superset` (gunicorn), `superset-init` (one-shot migrations + admin
user + roles + examples + start-page setup), `superset-worker`,
`superset-worker-beat`, `db` (postgres 17), `redis` (7).

Wait for `canopus_init` to finish, then open <http://localhost:8088>.

| User | Login | Role |
|------|-------|------|
| Admin | `admin` / `admin` | Admin |
| Demo viewer | `viewer` / `viewer` | Gamma (non-admin) |

Both land on the configured start dashboard (a clean `/dashboard/<id>/` URL,
no `/superset/` prefix). Tear down with `docker compose down -v`.

## Connecting to ClickHouse

`clickhouse-connect` is baked in. Add a database in Superset with a URI like:

```
clickhousedb://<user>:<password>@<host>:<port>/<database>
```

## What I would change for production

This compose is a faithful *emulation*, not a hardened deployment. For real
production I would:

- **TLS + reverse proxy.** Terminate HTTPS at nginx/Traefik in front of
  gunicorn; set `ENABLE_PROXY_FIX`, `TALISMAN`/CSP, and `SESSION_COOKIE_SECURE`.
- **Managed, separate stateful services.** Move postgres and redis off the
  compose to managed instances (RDS/Cloud SQL, ElastiCache) with backups and
  failover; don't run the metadata DB in a container with a local volume.
- **Secrets management.** Source `SUPERSET_SECRET_KEY` and DB/Redis credentials
  from a secrets manager (Vault, AWS/GCP secrets) instead of a committed-shaped
  `.env`; rotate the secret key with `superset re-encrypt-secrets`.
- **Run as non-root.** The compose runs containers as root for bind-mount
  convenience; production images should run as the `superset` user.
- **Scale the web + worker tiers** horizontally behind the proxy; tune gunicorn
  workers/threads (`SERVER_WORKER_AMOUNT`, `--timeout`), and size Celery
  workers for async queries, alerts, and thumbnails.
- **Drop the bundled examples** (`SUPERSET_LOAD_EXAMPLES=no`) and provision real
  databases/datasets; pin image digests and scan them in CI.
- **Observability.** Centralized logs, Prometheus/StatsD metrics, healthcheck
  alerting, and Sentry for errors.
- **Default new users to the start dashboard** via an on-login mutator or
  `DASHBOARD_TEMPLATE_ID`, rather than only seeding existing users at init time.
