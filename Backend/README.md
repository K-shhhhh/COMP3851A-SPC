# SPC backend structure

The backend uses domain-oriented Clean Architecture. The folders define where
code belongs and which direction dependencies should flow.

```text
Backend/
├── app/
│   ├── api/                         API composition and shared dependencies
│   │   ├── dependencies.py
│   │   ├── error_handlers.py
│   │   ├── router.py
│   │   └── routers/                 Thin compatibility imports / API-only routes
│   ├── core/                        Configuration, security, DB and observability
│   ├── domains/
│   │   ├── auth/
│   │   ├── users/
│   │   ├── notes/
│   │   ├── study_groups/
│   │   ├── knowledge_graph/
│   │   ├── analytics/
│   │   ├── notifications/
│   │   └── administration/
│   │       ├── presentation/        FastAPI routes and request/response schemas
│   │       ├── application/         Use cases and orchestration services
│   │       ├── domain/              Entities and repository interfaces
│   │       └── infrastructure/      PostgreSQL/external-service implementations
│   ├── ai/
│   │   ├── companions/              Facilitator, quiz and summary behaviours
│   │   ├── engine/                  AI orchestration and response formatting
│   │   ├── rag/                     Parse, chunk, embed, retrieve and cite
│   │   ├── providers/               Inference, embedding and OCR adapters
│   │   ├── memory/                  Conversation-memory implementations
│   │   ├── prompts/                 Versioned prompt templates
│   │   └── schemas/                 Provider-neutral AI data contracts
│   ├── platform/                    Shared technical capabilities
│   │   ├── cache/
│   │   ├── files/
│   │   ├── jobs/
│   │   ├── logging/
│   │   ├── notifications/
│   │   └── search/
│   ├── workers/                     Celery entry point and task modules
│   └── main.py                      FastAPI application factory
├── migrations/                      Database migrations
├── scripts/                         Backend maintenance commands
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── security/
│   └── end_to_end/
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

## Dependency rules

1. `domain` contains business concepts and interfaces. It must not import
   FastAPI, Celery, PostgreSQL clients or external AI SDKs.
2. `application` coordinates domain objects and repository interfaces.
3. `infrastructure` implements those interfaces for databases and providers.
4. `presentation` translates HTTP data and calls application services.
5. `app/api/router.py` composes the domain routers; business logic does not
   belong in `app/api/routers`.
6. Long-running parsing, embedding and generation work belongs in `workers`.
7. Provider-specific AI code belongs in `ai/providers`; the rest of the
   application should depend on provider-neutral contracts.

## Adding a backend feature

For a new business capability, add a folder under `app/domains` with the four
standard layers. Define the repository contract in `domain`, implement it in
`infrastructure`, inject it into an `application` service, and expose that
service through `presentation/router.py`. Finally, register its router in
`app/api/router.py` and add tests at the appropriate levels.
