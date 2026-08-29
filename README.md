# Smart Peer Companion (SPC)

Interactive AI-assisted peer-learning platform developed for COMP3851A/B.

## Application stack

- React single-page application
- FastAPI backend organized by domain and clean-architecture layers
- Celery background workers with Redis
- PostgreSQL 16 with pgvector
- Nginx reverse proxy
- Docker Compose for local development and Hetzner staging
- External GPU inference endpoint for the custom Llama model

## Run locally

See [DOCKER_LOCAL.md](DOCKER_LOCAL.md).

## Deploy to Hetzner staging

See [HETZNER_STAGING.md](HETZNER_STAGING.md). The staging override keeps
PostgreSQL and Redis private and adds required secrets and bounded container
logs without changing the local developer workflow.

## High-fidelity design references

- [Customer portal](https://www.figma.com/make/wXF61zpc81twwJ7zoF0jig/Untitled?t=WdyqcFvKK8ZbcKJw-1)
- [Admin portal](https://www.figma.com/make/b5NA6uTYpkkg5GbHQSlk0W/Admin-Portal-UI-Design?t=WdyqcFvKK8ZbcKJw-1)
