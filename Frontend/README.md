# SPC React frontend structure

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
