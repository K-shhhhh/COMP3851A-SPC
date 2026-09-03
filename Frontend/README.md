# SPC React frontend structure

For service ownership, local proxy setup and current API readiness, read
[the integration handover](INTEGRATION_HANDOFF.md).

The frontend is a Vite-powered React single-page application. It uses a hybrid
page/component structure so customer and administrator screens can share UI and
services without duplicating logic.

```text
Frontend/
├── public/                           Static files copied without bundling
├── src/
│   ├── assets/
│   │   ├── animations/
│   │   ├── fonts/
│   │   ├── icons/
│   │   └── images/
│   ├── components/
│   │   ├── common/                   Shared application components
│   │   ├── ui/                       Small reusable UI primitives
│   │   ├── layout/                   Headers, navigation and page shells
│   │   ├── forms/                    Shared form controls
│   │   ├── ai/                       Companion and AI response components
│   │   ├── chat/                     Channel and message components
│   │   ├── notes/                    Notes and upload components
│   │   └── knowledgeGraph/           Graph visualization components
│   ├── pages/
│   │   ├── Login/                    Customer and admin sign-in
│   │   ├── Register/
│   │   ├── Dashboard/
│   │   ├── GroupStudy/
│   │   ├── Notes/
│   │   ├── Companion/
│   │   ├── KnowledgeGraph/
│   │   ├── Profile/
│   │   ├── Settings/
│   │   ├── Admin/                    Administrator portal pages
│   │   └── NotFound/
│   ├── services/                     HTTP/WebSocket API clients by capability
│   ├── redux/
│   │   ├── store.js
│   │   └── slices/                   Shared client-side state
│   ├── routes/                       Route definitions and access guards
│   ├── contexts/                     Narrow React contexts
│   ├── hooks/                        Reusable application hooks
│   ├── validators/                   Form and request validation
│   ├── constants/                    Route names and fixed configuration
│   ├── utils/                        Pure helpers
│   ├── styles/                       Global tokens and shared styles
│   ├── App.jsx
│   └── main.jsx
├── Dockerfile
├── nginx.conf
├── package.json
└── vite.config.js
```

## Placement rules

1. Route-level screens belong in `pages/<ScreenName>`.
2. A component used by only one page stays inside that page folder when it is
   implemented. Reusable capability components go under `components`.
3. Network calls must remain in `services`, not inside visual components.
4. Authentication and authorization checks belong in route guards and shared
   state, with the backend remaining the final authority.
5. Customer and admin pages may share `ui`, `forms`, layouts and services, but
   administrator routes must be clearly separated under `pages/Admin`.
6. Never place API keys or secrets in React environment variables or bundles.

## Design references

- [Customer high-fidelity design](https://www.figma.com/make/wXF61zpc81twwJ7zoF0jig/Untitled?t=WdyqcFvKK8ZbcKJw-1)
- [Admin high-fidelity design](https://www.figma.com/make/b5NA6uTYpkkg5GbHQSlk0W/Admin-Portal-UI-Design?t=WdyqcFvKK8ZbcKJw-1)

## Parallel integration mode

Copy `.env.example` to `.env.local` and keep `VITE_USE_MOCKS=true` while the
real API, database and model endpoint are under development. Components call
`submitAIJob`, `getAIJob` and `subscribeToAIJob` from `services/aiService.js`;
they must not import mock modules directly. When the backend contract is ready,
set `VITE_USE_MOCKS=false` without changing component code.

This flag applies only to services that implement mock switching (currently AI).
The AI backend endpoints are not enabled yet. Run the shared helper tests with
`node --test tests/integration.test.js` from this folder using Node 22.

## Package files

`package.json` defines dependencies and dev/build/preview commands. `package-lock.json`
records resolved dependencies for `npm ci`. These files use JSON, which does not allow
code comments. The current Dockerfile still installs from package.json with npm install;
reproducible lockfile-based Docker installation is a follow-up improvement.
