import { useEffect, useState } from "react";

export default function App() {
  const [backend, setBackend] = useState({ status: "checking" });

  useEffect(() => {
    fetch("/api/v1/health")
      .then((response) => response.json())
      .then((payload) => setBackend(payload))
      .catch(() => setBackend({ status: "unavailable" }));
  }, []);

  return (
    <main className="shell">
      <section className="card">
        <p className="eyebrow">SMART PEER COMPANION</p>
        <h1>Local Docker environment</h1>
        <p className="intro">
          Nginx, React, FastAPI, PostgreSQL with pgvector, Redis and the
          background worker are running as one Compose project.
        </p>

        <div className={`status status--${backend.status}`}>
          <span className="status__dot" />
          Backend: {backend.status}
        </div>

        <a href="/docs">Open FastAPI documentation</a>
      </section>
    </main>
  );
}
