# Data handling and deletion note

Smart Peer Companion, staging evaluation. This note says what data the system
keeps, who else receives it, how it can be deleted, and what is still missing.
It supports the Ethical AI and Data Privacy Policy and the User Consent
Paragraph in this folder and does not replace them.

Status: draft written from the code and compose files in the repository on
18 October 2026. Items marked **Open** need a decision or a fix before the
evaluation can be called compliant. Facts about the OpenRouter account could not
be checked from the code and are marked **Check**.

## 1. What the system stores

| Data | Where it lives | Who can see it |
| --- | --- | --- |
| Name, email, hashed password | PostgreSQL table `users` | The student. Team members with server access can read it in the database |
| Uploaded PDF files | The `note_uploads` Docker volume on the server | The student who uploaded it. Group members for files attached in a channel |
| Text taken from each PDF, split into chunks, with its embedding | PostgreSQL tables `chunks` and pgvector | Used only to answer that student's questions. Group files are searchable by that group |
| Picture descriptions made from PDF images | Inside the chunks | Same as the text chunks |
| Knowledge graph topics and links | PostgreSQL knowledge graph tables | The student who owns the note |
| AI Assistant chats and answers | PostgreSQL `messages` and `ai_responses` | The student only |
| Study group messages, members, channels | PostgreSQL | Members of that group |
| Server logs | Docker container logs on the server (at most 30 MB per service) and Caddy logs | Team members with server access. May include IP addresses and request paths |
| Database backups | `~/spc-backups` on the server, copies on teammates' laptops if copied | Anyone with that file. It contains everything in the database |
| Survey answers | Google Form and its Google Sheet | The team and supervisors with access to the sheet. The form asks for course and year but not name or email |

Embeddings are made on the server itself by Ollama, so the text of a PDF does
not leave the server to be embedded.

## 2. Who else receives student data

| Receiver | What it gets | Why |
| --- | --- | --- |
| OpenRouter, and the model provider behind it | The student's question, the retrieved passages from their notes, and (once the chat memory update is deployed) up to the last 6 messages of that same AI Assistant chat | To write the answer |
| OpenRouter, through the model `openrouter/free` | Pictures taken out of uploaded PDFs | To write a short description of each picture |

Two points need attention.

* **Open. Pictures go to a free model that is chosen automatically.** The model
  name `openrouter/free` picks whichever free vision model is available at that
  moment, so the team cannot say which company receives the pictures. Free
  providers often keep prompts and may train on them. The fix is to name one
  paid vision model with a no training policy in `Backend/app/ai/rag/parser.py`,
  or to turn picture descriptions off for evaluation uploads.
* **Check. OpenRouter account privacy settings.** In the OpenRouter account
  settings, confirm that prompt logging is off and that requests are only sent
  to providers that do not train on data. The project owner holds the account.

The policy says that no chat history is sent to the AI for group chats. That
still holds. The chat memory update sends earlier messages only for the
student's own AI Assistant chat, never for study group channels. The consent
text should say so (section 6).

## 3. How long data is kept

| Data | Planned retention |
| --- | --- |
| Everything on the staging server | Until the end of the evaluation, then wiped as in section 5. The date is **to be agreed with Ms Jade and Dr Sithra** and written into the consent text |
| Backups | 14 days on the server. Copies made elsewhere must be deleted at the same time as the wipe |
| Survey answers | Kept for the report. They hold no names or emails |
| Report, poster and slides | Only aggregate numbers. No uploaded text, no names |

## 4. What deleting inside the app does today

| Student action | What really happens | Gap |
| --- | --- | --- |
| Delete a note | The note disappears from My Notes and the PDF file is removed from storage. The database row is marked deleted | **Open.** The extracted text chunks and graph rows are not removed. They are no longer searched, but they stay in the database until the wipe |
| Delete an AI Assistant chat | The chat is marked deleted and disappears from the list. Its messages stay in the table | **Open.** Hidden, not erased |
| Delete an account | No such feature | **Open.** There is no way to delete or deactivate an account from the app |
| Leave a study group | The membership row is removed. A group owner must hand over ownership first | Messages the student wrote stay in the group. Deleting a group or a message only marks it deleted |

Because of these gaps, a student's request to "delete my data" cannot be fully
met from the app alone. During the evaluation it is met by the wipe in section 5.

## 5. End of evaluation wipe

Do this once testing is finished and the final numbers have been saved. It
removes all tester data from the server.

1. Save the final numbers first: run `scripts/test_stats.sql` and
   `scripts/monitor_stats.sql` (see `RUNBOOK.md`) and keep the output.
2. Tell the supervisors the date and time of the wipe.
3. Stop the stack, then remove the data volumes by their exact names, which
   `docker volume ls` shows. Do **not** remove the Ollama volume, because it only
   holds the downloaded embedding model.

   ```bash
   sh scripts/staging.sh down
   docker volume ls
   docker volume rm spc-staging_postgres_data spc-staging_note_uploads spc-staging_redis_data
   sh scripts/staging.sh up -d
   ```

   The stack starts again with an empty database and no uploaded files.
4. Delete every database backup: `rm -f ~/spc-backups/spc-*.dump` on the server,
   and delete any copy that teammates took onto their laptops.
5. Truncate or rotate the logs: `sudo journalctl --vacuum-time=1d` for the host
   and `docker compose` log files are removed when the containers are
   recreated in step 3.
6. Delete or archive the survey sheet according to what the supervisors
   decide. It holds no names or emails.
7. Write down the date, who did it, and what was removed, and give that record
   to the supervisors.

This procedure has not been run. Read it through with a second person before the
real date, and check the volume names on the server first.

## 6. Wording to show testers

Suggested text for the sign up page or the first screen after login. It keeps
the promise made in the User Consent Paragraph and adds the points above.

> Smart Peer Companion is a university project being evaluated. Only upload
> study material you are allowed to share and that is not private or
> confidential. When you ask the AI Assistant a question, your question, the
> matching passages from your notes, and up to the last 6 messages of that chat
> are sent to an external AI service to write the answer. Pictures inside your
> PDFs are also sent to an AI service to be described. AI answers can be wrong,
> so check them against your notes. Your account, uploads and chats are deleted
> when the evaluation ends on **[date]**. The AI never reads study group
> messages unless someone asks it in that channel.

## 7. Fixes in order of importance

1. Fix or switch off the free vision model route, and confirm the OpenRouter
   privacy settings (section 2).
2. Agree and publish the deletion date, and update the consent text.
3. Make deleting a note also delete its chunks and graph rows.
4. Add a way to delete an account together with its data.
5. Decide how long logs are kept, and set the Caddy and Docker log limits to
   match.
6. Practise the wipe on a copy of staging, then on the real server.
