# Staging runbook

How to look after the Smart Peer Companion staging server. It covers the jobs
the team does every week and what to do when something breaks. The first-time
setup lives in `HETZNER_STAGING.md` and `Backend/docs/STAGING_GO_LIVE.md`.

Every command below runs on the server, inside the project folder, unless it
says otherwise.

## Quick facts

| Item | Value |
| --- | --- |
| Server | `spc-staging-01`, 168.119.99.65 |
| Website | https://168-119-99-65.sslip.io |
| Project folder | `/opt/spc-staging` |
| Run any compose command with | `sh scripts/staging.sh <command>` |
| Services | nginx, frontend, backend, worker, postgres, redis, ollama (Caddy runs on the host for HTTPS) |
| Secrets file | `.env.staging` (never commit it) |
| Health check | `curl --fail https://168-119-99-65.sslip.io/api/v1/health` |
| Never run | `sh scripts/staging.sh down --volumes`. It deletes the database, Redis data and the downloaded embedding model. |

## 1. Daily check (3 minutes)

```bash
cd /opt/spc-staging
sh scripts/staging.sh ps
curl --fail https://168-119-99-65.sslip.io/api/v1/health
df -h /
sh scripts/staging.sh exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < scripts/monitor_stats.sql
```

What good looks like:

* Every service shows `running` or `healthy`.
* The health call answers with `"status":"healthy"`.
* Disk use is under 80 percent. If not, see "Disk is full" in section 9.
* In the first table of the monitor output, "uploads waiting or processing for
  over 15 minutes" is `0`. If it is not, go to section 5.
* The refusal percent in the AI answers table is not climbing day after day.
  A jump means the model or the retrieval changed for the worse.

## 2. Deploy an update

Deploy only reviewed code that is on `main`. Take a backup first, every time.

```bash
cd /opt/spc-staging
sh scripts/backup_db.sh
git fetch origin
git log --oneline HEAD..origin/main        # read what is about to go live
git pull --ff-only origin main
sh scripts/staging.sh config --quiet       # catches typos in the compose files
sh scripts/staging.sh up --build -d
sh scripts/staging.sh restart nginx
python3 scripts/smoke_test.py https://168-119-99-65.sslip.io
```

The smoke test registers a throwaway student, uploads a small PDF, asks a
question and checks that two students cannot see each other's notes. All lines
must say `PASS`. Write down the processing time and answer time it prints, so
the next deploy can be compared with this one.

### New database migration files

PostgreSQL runs the schema file only when its volume is empty. A new file in
`Backend/migrations` therefore has to be applied by hand, once, after the
backup. Read the file first. Then:

```bash
sh scripts/staging.sh exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < Backend/migrations/<file>.sql
```

Apply files in number order and never twice unless the file says
`if not exists`. To check what a table looks like now:

```bash
sh scripts/staging.sh exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\d attachments"'
```

## 3. Roll back

Find the last good commit and go back to it. Do not delete volumes.

```bash
git log --oneline -10
git checkout <good-commit>
sh scripts/staging.sh up --build -d
sh scripts/staging.sh restart nginx
```

If only the website is wrong, roll back just the frontend:

```bash
git checkout <good-commit> -- Frontend
sh scripts/staging.sh up --build -d frontend
sh scripts/staging.sh restart nginx
```

To go back to the newest frontend afterwards:

```bash
git checkout HEAD -- Frontend
sh scripts/staging.sh up --build -d frontend
sh scripts/staging.sh restart nginx
```

To return to normal after a full rollback, run `git checkout main` and
`git pull --ff-only origin main`, then deploy as in section 2.

Migrations that only add columns or tables do not need undoing when you roll
the code back. Restore the database from a backup (section 7) only if data was
damaged.

## 4. Switch the chat model

The model that writes the answers is set by `CHAT_MODEL` in `.env.staging`.
Empty means `meta-llama/llama-3.1-8b-instruct`. This works once the code that
reads `CHAT_MODEL` is deployed.

```bash
nano .env.staging                 # add or change: CHAT_MODEL=meta-llama/llama-3.3-70b-instruct
sh scripts/staging.sh up -d backend
sh scripts/staging.sh exec backend printenv CHAT_MODEL
python3 scripts/smoke_test.py https://168-119-99-65.sslip.io
```

Check the exact model name on openrouter.ai before using it, and check that the
account has credits. A bigger model costs more per question, so compare
quality and cost on the answer test set first (`Backend/tests/quality`).

To go back: set `CHAT_MODEL=` to nothing, then run `sh scripts/staging.sh up -d backend` again.

## 5. Uploads stuck in "queued" or "processing"

An upload is stuck when it has been waiting or processing for a long time and
the worker is not actually working on it. This happens when the worker is
restarted while it holds uploads. Celery hands a task over before running it,
so a task that was in flight when the worker stopped is lost, not retried.

Step 1. List the candidates. `object_path` is needed in step 3.

```bash
sh scripts/staging.sh exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
select attachment_id, processing_status, uploaded_at, processing_started_at, object_path
from attachments
where processing_status in ('queued', 'processing') and deleted_at is null
order by uploaded_at;
SQL
```

Step 2. Ask Celery what it is really doing. Any upload that appears here is
working, so leave it alone. The first argument of each task is the upload id.

```bash
sh scripts/staging.sh exec worker celery -A app.workers.celery_app:celery_app inspect active
sh scripts/staging.sh exec worker celery -A app.workers.celery_app:celery_app inspect reserved
```

Step 3. For each upload that is on the list from step 1 and not in step 2, send
the task again. Processing replaces the old chunks, so running it twice is safe.

```bash
sh scripts/staging.sh exec -T worker python - <<'PY'
from app.workers.attachment.processing_worker import process_attachment_task
process_attachment_task.delay(123, "the object_path from step 1")
PY
```

Step 4. Watch it finish with `sh scripts/staging.sh logs -f --tail=50 worker`.
If it fails again, read the reason with the failure query in
`scripts/monitor_stats.sql` before trying a third time.

## 6. Restart things safely

* **backend, nginx, frontend**: safe at any time. Students may see one failed
  request.
* **worker**: first run the `inspect active` command from section 5. If it
  lists uploads, wait for them. A restart now loses them.
* **postgres, redis**: take a backup first. Restart redis only when no upload is
  active, because the queue lives there.
* **ollama**: after a restart the first question is slow while the embedding
  model loads again.
* **whole server**: `sudo reboot` is fine. Every service has
  `restart: unless-stopped` and comes back by itself. Check section 1 afterwards.

## 7. Backups and the restore test

Take a backup by hand any time:

```bash
sh scripts/backup_db.sh
```

It writes `~/spc-backups/spc-<date>_<time>.dump`, refuses to keep an empty
dump, and deletes copies older than 14 days.

Make it automatic, every night, with `crontab -e`. Cron uses the server's
clock. Run `date` to see it. Hetzner servers usually run on UTC, so 19:00
there is 03:00 in Singapore.

```text
0 19 * * * cd /opt/spc-staging && sh scripts/backup_db.sh >> $HOME/spc-backups/backup.log 2>&1
```

Copy the backups off the server now and then, from your own laptop:

```bash
scp "<deploy-user>@168.119.99.65:spc-backups/spc-*.dump" ./spc-backups/
```

### Prove the backup works (do this once, then every month)

A backup nobody has restored is only a hope. This restores into a throwaway
database and leaves the real one alone:

```bash
sh scripts/staging.sh exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" spc_restore_test'
sh scripts/staging.sh exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d spc_restore_test --no-owner' < ~/spc-backups/<newest-file>.dump
sh scripts/staging.sh exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d spc_restore_test -c "select count(*) as students from users"'
sh scripts/staging.sh exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" spc_restore_test'
```

The student count should match the live database. Note the date you did this.

### Real restore after data loss

1. Take a backup of the damaged database first, in case the restore goes wrong.
2. Stop the writers: `sh scripts/staging.sh stop backend worker`.
3. Restore over the live database:
   `sh scripts/staging.sh exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < ~/spc-backups/<file>.dump`
4. Start again: `sh scripts/staging.sh start backend worker`, then run the smoke test.

Uploaded PDFs live in the note storage volume, not in the database. A database
restore does not bring back a deleted PDF file.

## 8. Hardening checklist (one time)

Tick each line and write the date. Do 1 before 2, so nobody is locked out.

* [ ] 1. Every teammate who needs access has logged in with their own SSH key.
  Test each key from a second terminal before changing anything else.
* [ ] 2. Turn off SSH passwords and direct root login. In
  `/etc/ssh/sshd_config.d/01-hardening.conf` put `PasswordAuthentication no` and
  `PermitRootLogin no`. The `01` matters, because SSH keeps the first value it
  reads and a cloud file such as `50-cloud-init.conf` may say the opposite.
  Then run `sudo sshd -t && sudo systemctl reload ssh` and check the result
  with `sudo sshd -T | grep -E "passwordauthentication|permitrootlogin"`. Keep
  the old terminal open until a new login works.
* [ ] 3. Install updates and reboot at a quiet time (the server reports
  "System restart required"): `sudo apt update && sudo apt upgrade -y`, then
  `sudo reboot`. Run section 1 afterwards.
* [ ] 4. Automatic security updates: `sudo apt install -y unattended-upgrades`
  then `sudo dpkg-reconfigure -plow unattended-upgrades`.
* [ ] 5. Block repeated login guessing: `sudo apt install -y fail2ban`. The
  default SSH rules are enough.
* [ ] 6. Host firewall that matches the Hetzner firewall. Allow only 22, 80 and
  443: `sudo ufw allow 22/tcp`, `sudo ufw allow 80/tcp`, `sudo ufw allow 443/tcp`,
  then `sudo ufw enable`. Do not allow 8080. Caddy reaches nginx locally.
  Docker can bypass ufw for published ports, so also confirm the Hetzner firewall
  is attached and shows only those three ports.
* [ ] 7. `.env.staging` is private: `chmod 600 .env.staging`, and
  `./scripts/validate-staging-env.sh .env.staging` passes.
* [ ] 8. The API docs are hidden. `curl -s -o /dev/null -w "%{http_code}\n" https://168-119-99-65.sslip.io/docs` prints `404`.
* [ ] 9. Nightly backup is in cron and the restore test in section 7 has passed once.
* [ ] 10. Hetzner deletion protection is on, and a server snapshot was taken
  after the last big change. The project owner does this in the Hetzner console.
* [ ] 11. The inference API key has a spending limit in the OpenRouter account,
  so a bug or a flood of questions cannot run up a large bill.
* [ ] 12. Passwords and the `SECRET_KEY` are replaced if they were ever pasted
  into a chat or a document.

## 9. When something breaks

| What you see | Likely cause | What to do |
| --- | --- | --- |
| Website will not load | Caddy or nginx down | `sudo systemctl status caddy`, then `sh scripts/staging.sh ps`, then restart nginx |
| Certificate warning | Caddy could not renew | `sudo journalctl -u caddy --no-pager \| tail -30`. Check port 80 is open |
| Everyone gets logged out | The access token lasts `ACCESS_TOKEN_EXPIRE_MINUTES` (15 by default), and the frontend does not call the refresh endpoint yet, or `SECRET_KEY` changed | Expected after that many minutes until the frontend uses `/api/v1/auth/refresh`. As a stopgap set `ACCESS_TOKEN_EXPIRE_MINUTES=120` in `.env.staging` and run `sh scripts/staging.sh up -d backend`. If logouts are sooner than set, check nobody edited `SECRET_KEY` |
| Questions fail with a provider error | `INFERENCE_API_KEY` wrong, no credits, or model name wrong | Check the OpenRouter account. Check `CHAT_MODEL`. Read `logs --tail=100 backend` |
| Every upload ends `failed` | Embedding model missing or provider down | Read the failure reasons with `scripts/monitor_stats.sql`. For a missing model run `sh scripts/staging.sh exec ollama ollama pull nomic-embed-text` |
| Uploads sit in `queued` | Worker stopped or busy | `sh scripts/staging.sh ps`, then section 5 |
| Answers got slower | Model provider slow, or Ollama reloading | Compare the answer times in the monitor output with the smoke test baseline |
| Disk is full | Logs, old images, Ollama or note storage | `docker system df`. Free space with `docker image prune -f` and `docker builder prune -f`. Never prune volumes |
| Backend unhealthy, "relation does not exist" | Old database volume | See `Backend/docs/STAGING_GO_LIVE.md` section 2B |
| A private group shows up under Public | The list could show a slow reply for the wrong filter. Fixed in the branch `krish/sprint10-quality` | If the fix is not deployed yet, tell testers to reload the page. After deploying, check by opening Private Groups then Public Groups in the menu |

## 10. Rules that keep the data safe

* Never run `down --volumes`, `docker volume rm` or `docker system prune --volumes`
  without a fresh backup and a second person agreeing.
* Never paste `.env.staging`, the OpenRouter key or a database dump into a chat
  or a ticket.
* Real student data does not go on this server until HTTPS, backups, the
  hardening list and the privacy checks are all done.
* After testing ends, delete the test accounts and uploaded files as described
  in `Project_Documents/04_Compliance_and_Ethics/DATA_HANDLING_AND_DELETION.md`.
