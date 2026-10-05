# Staging go live checklist

Use this together with `HETZNER_STAGING.md`. That guide is good, but it was written
before the AI pipeline landed, so this file lists what it does not cover yet and the
order to do things in.

## 0. Check first (2 minutes)

* Can you SSH in? `ssh <deploy-user>@168.119.99.65`. If not, the project owner has to
  add your key (guide section 1) or run these steps for you.
* Is staging already running? From your laptop: `curl http://168.119.99.65/api/v1/health`.
  If it answers, staging exists and section 2B probably applies.
* Server size: run `nproc && free -h` on the server. About 4 vCPU and 8 GB is the
  practical minimum with embeddings on CPU. If it is smaller, rescale it in the Hetzner
  console before testers arrive.

## 1. Gaps in the existing guide

1. **The embedding model is never pulled.** The Ollama container starts empty, so
   without `nomic-embed-text` every upload fails on staging. Fixed in section 3.
2. **An old database breaks the new backend.** PostgreSQL only runs schema scripts on a
   completely empty volume. If staging was deployed before schema 006, its volume still
   holds the old tables. Staging holds only test data, so recreate that one volume
   (section 2B).
3. **Chat needs a provider key.** Set `INFERENCE_API_KEY` to your OpenRouter key and
   leave `INFERENCE_API_URL` empty (it defaults to OpenRouter). The template says to wait
   for an external GPU endpoint, but none exists yet. The chat model name has no
   `:free` suffix, so it bills per token: check the account has credits.
4. **HTTPS is not set up.** Over plain HTTP, passwords travel unencrypted. The guide's
   own release gate (section 7) forbids real accounts before this. See section 4.
5. **`/docs` is public.** The Caddyfile in section 4 hides it from testers.
6. **CPU tuning.** `docker-compose.staging-tuning.yml` (new) limits the worker to 2
   documents at a time and keeps the embedding model loaded between questions.
7. **Feature flags.** Defaults are right for a first deploy: semantic search on,
   knowledge graph off. Turn the graph on only after it passes (section 6).

## 2. Deploy

### 2A. First deployment or a normal update

```bash
cd /opt/spc-staging
git pull --ff-only origin main

# first time only
cp .env.staging.example .env.staging && chmod 600 .env.staging
nano .env.staging     # replace every replace_with_ value
                      # add INFERENCE_API_KEY=<your OpenRouter key>
                      # set NGINX_HTTP_PORT=8080   (so Caddy can use port 80)

./scripts/validate-staging-env.sh .env.staging
sh scripts/staging.sh config --quiet
sh scripts/staging.sh up --build -d
```

### 2B. If staging already has an older database (do this before `up`)

```bash
sh scripts/staging.sh down
docker volume ls | grep postgres
docker volume rm spc-staging_postgres_data     # use the exact name from the list
sh scripts/staging.sh up --build -d
```

Never use `down --volumes`: it also deletes the downloaded Ollama model.

## 3. Pull the embedding model (once)

```bash
sh scripts/staging.sh exec ollama ollama pull nomic-embed-text
sh scripts/staging.sh exec ollama ollama list
sh scripts/staging.sh restart nginx
```

The download is about 274 MB and persists across restarts.

## 4. HTTPS and hiding the API docs

1. Install Caddy using the official instructions for Debian/Ubuntu
   (caddyserver.com/docs/install).
2. Copy `deploy/Caddyfile.example` to `/etc/caddy/Caddyfile` and replace the hostname.
   Use your own domain pointed at the server, or a free name that already resolves to
   the IP such as `168-119-99-65.sslip.io`.
3. `sudo systemctl reload caddy`
4. Make sure `NGINX_HTTP_PORT=8080` is in `.env.staging` and re-run
   `sh scripts/staging.sh up -d`. The Hetzner firewall must allow only 22, 80 and 443.

## 5. Verify

On the server, before relying on HTTPS:

```bash
python3 scripts/smoke_test.py http://127.0.0.1:8080
```

From your laptop, through HTTPS:

```bash
python3 scripts/smoke_test.py https://<your-hostname>
```

Every check must pass. Write down PROCESSING TIME and ANSWER TIME: that is your staging
baseline for the report.

| Symptom | Cause and fix |
| --- | --- |
| Upload ends in `failed`, worker log says model not found | Section 3 was skipped |
| Backend unhealthy, "relation does not exist" or password authentication failed | Old database volume, section 2B |
| Question answers fail with a provider error | `INFERENCE_API_KEY` missing or no credits |
| Certificate error | Hostname does not resolve to the server, or port 80 is blocked. Check `sudo journalctl -u caddy --no-pager \| tail -30` |
| Health check works on the server but not from your laptop | Hetzner firewall or Caddy not reloaded |

## 6. Turning on the knowledge graph later

```bash
echo "ENABLE_KNOWLEDGE_GRAPH_GENERATION=true" >> .env.staging
sh scripts/staging.sh up -d
python3 scripts/smoke_test.py https://<your-hostname> --graph
```

## 7. Large documents

The default upload limit is 10 MB. For a one off large document demo, set
`MAX_NOTE_UPLOAD_SIZE_BYTES=52428800` (nginx allows 50 MB) and expect processing to take
many minutes on CPU. Put the default back afterwards.

## Rollback

See `HETZNER_STAGING.md`: deploy a known good commit, never delete volumes.
