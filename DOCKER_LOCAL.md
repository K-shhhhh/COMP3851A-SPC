# SPC local Docker environment

## Start the core stack

```bash
docker compose up --build -d
docker compose restart nginx
docker compose ps
```

Restarting Nginx refreshes its internal Docker service addresses after a
backend or frontend container has been replaced.

Open:

- SPC health page: <http://localhost:8080>
- FastAPI documentation: <http://localhost:8080/docs>

## Start optional pgAdmin

```bash
docker compose --profile admin up -d pgadmin
```

Open <http://localhost:5050>. The PostgreSQL host from inside pgAdmin is
`postgres`, not `localhost`.

## Useful checks

```bash
docker compose logs -f backend worker
docker compose exec redis redis-cli ping
docker compose exec postgres psql -U spc_backend -d spc -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
docker compose exec worker celery -A app.workers.celery_app:celery_app inspect ping
```

## Stop the stack

```bash
docker compose down
```

To also delete local database, Redis and pgAdmin data:

```bash
docker compose down --volumes
```

Do not use the example local credentials for the Hetzner deployment. Production
secrets, TLS and backups will be configured separately after the server exists.
