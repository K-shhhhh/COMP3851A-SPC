# Hetzner staging deployment

This guide deploys the shared SPC Docker stack to `spc-staging-01`. It is a
staging deployment: do not place real student data on it until HTTPS, backups,
access hardening and privacy checks are complete.

## Architecture

```text
Internet
   |
Hetzner Firewall (22, 80, 443)
   |
Nginx :80
   |-- React frontend
   `-- /api and /docs --> FastAPI
                              |
                +-------------+-------------+
                |             |             |
             Celery       PostgreSQL      Redis
             worker       + pgvector      queues/cache
                |
                `--------> External GPU inference API
```

PostgreSQL and Redis have no host ports. They are reachable only by containers
on the private Docker network. PgAdmin is deliberately disabled in staging.

## 1. One-time server preparation

The project owner should first confirm that every approved team member can use
their own SSH key. Project-level keys added after server creation are not
automatically inserted into the server.

Create a non-root deployment account, give it Docker access, and disable SSH
password authentication only after key-based access has been tested. Also
enable Hetzner deletion/rebuild protection and choose a backup policy.

Install Docker Engine, the Docker Compose plugin, Git and a host firewall if
they are not already present. The Hetzner Cloud Firewall must remain attached.

## 2. Clone the repository

```bash
sudo mkdir -p /opt/spc-staging
sudo chown "$USER":"$USER" /opt/spc-staging
git clone https://github.com/K-shhhhh/COMP3851A-SPC.git /opt/spc-staging
cd /opt/spc-staging
```

## 3. Create staging secrets

```bash
cp .env.staging.example .env.staging
chmod 600 .env.staging
```

Replace every `replace_with_...` value. Generate independent database, Redis
and application secrets. Configure the inference URL and API key only after the
external GPU endpoint is approved. Never commit `.env.staging`.

Check that the environment file contains no example secrets:

```bash
./scripts/validate-staging-env.sh .env.staging
```

## 4. Validate and deploy

```bash
docker compose --env-file .env.staging \
  -f docker-compose.yml -f docker-compose.staging.yml config --quiet

docker compose --env-file .env.staging \
  -f docker-compose.yml -f docker-compose.staging.yml up --build -d

docker compose --env-file .env.staging \
  -f docker-compose.yml -f docker-compose.staging.yml ps
```

Verify from the server and then from another machine:

```bash
curl --fail http://127.0.0.1/api/v1/health
curl --fail http://168.119.99.65/api/v1/health
```

The expected API result contains `"status":"healthy"`.

## 5. Routine update

Deploy only reviewed changes from `main`:

```bash
cd /opt/spc-staging
git fetch origin
git checkout main
git pull --ff-only origin main

docker compose --env-file .env.staging \
  -f docker-compose.yml -f docker-compose.staging.yml up --build -d
```

Check status and logs after every update:

```bash
docker compose --env-file .env.staging \
  -f docker-compose.yml -f docker-compose.staging.yml ps

docker compose --env-file .env.staging \
  -f docker-compose.yml -f docker-compose.staging.yml logs --tail=100 backend worker nginx
```

## 6. Database backup before migrations

Create a backup directory outside the repository and take a logical dump:

```bash
mkdir -p "$HOME/spc-backups"
docker compose --env-file .env.staging \
  -f docker-compose.yml -f docker-compose.staging.yml exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "$HOME/spc-backups/spc-before-migration.dump"
```

Copy important backups off the server. A snapshot is useful before a major
server change, but it is not a replacement for tested database backups.

## 7. HTTPS release gate

Before using real accounts or documents:

1. Point a staging DNS name to the server IP.
2. Configure a valid TLS certificate and redirect HTTP to HTTPS.
3. Confirm SSH passwords and direct root login are disabled.
4. Restrict or protect `/docs` and do not expose PgAdmin.
5. Test database restore, log rotation and disk monitoring.
6. Confirm the RAG and inference services isolate data by user and study group.

## Rollback

Application rollback should use a known-good Git commit rather than deleting
volumes:

```bash
cd /opt/spc-staging
git checkout <known-good-commit>
docker compose --env-file .env.staging \
  -f docker-compose.yml -f docker-compose.staging.yml up --build -d
```

Do not run `docker compose down --volumes` on staging; it deletes persistent
PostgreSQL and Redis data.
