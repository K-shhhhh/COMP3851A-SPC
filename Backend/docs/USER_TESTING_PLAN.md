# User testing plan: Smart Peer Companion

Target: 50 testers. Run it in waves so a failure affects 5 people, not 50.

## 1. Goals and what counts as success

| Measure | Target |
| --- | --- |
| Testers who complete the core tasks (upload, ask, get a cited answer) | at least 80% |
| Median time for an upload to become ready | under 3 minutes for a 10 page PDF |
| Helpfulness of answers (survey, 1 to 5) | average 3.5 or higher |
| Another student's data visible to a tester | zero cases |
| Uploads that end in `failed` | under 10% |

## 2. Waves

1. **Wave 0, the team (about 1 hour).** Everyone runs the task script below on the live
   server. Fix anything that blocks a task before anyone outside the team sees it.
2. **Wave 1, 10 testers.** Watch the logs while they work. Fix, then continue.
3. **Wave 2, the rest, in groups of 10 to 15 spread over a few hours or days.** Embeddings
   run on CPU, so 50 people uploading at once simply queue. Staggering keeps waits
   short.

Ask testers to use PDFs of 20 pages or fewer: a book makes everyone behind it wait.

## 3. Message to send testers (copy and adapt)

> Thanks for helping test Smart Peer Companion, an AI study platform for university
> students. It takes about 15 minutes.
>
> Link: https://YOUR-HOSTNAME
>
> Please create a test account (any name, and an email address you do not mind sharing;
> use a password you do not use anywhere else). Only upload study material that is not
> private or confidential. Your questions and the text of your documents are processed by
> an external AI provider to produce answers. Test data is deleted when the evaluation
> ends. Follow the task list, then fill in the short survey: SURVEY-LINK

## 4. Task list for testers

1. Register and log in.
2. Upload a PDF of your own study material (10 MB or less). Note roughly how long it
   takes to show as Ready.
3. In AI Assistant, ask two questions about the document. Check the answer matches the
   document and shows its source.
4. Ask a third question and change the answer format to bullet points, then table.
5. Ask something that is not in the document. It should say it cannot find it.
6. Join a public study group, or create one and a channel, and send a message.
7. In the channel, attach a PDF, then ask using @Summarizer, @QuizMaster and
   @Facilitator. Note how each one differs.

## 5. Survey questions

1. Which tasks did you manage to complete? (checkboxes for tasks 1 to 7)
2. Rate each from 1 (poor) to 5 (excellent): ease of use, accuracy of answers,
   usefulness of answers, speed of uploads, speed of answers, how the app looks.
3. Rate your agreement from 1 to 5:
   * I would use this to study.
   * I found it easy to use.
   * I felt confident the answers came from my own notes.
   * The AI modes (Summarizer, QuizMaster, Facilitator) were useful.
   * I would recommend it to a classmate.
4. What was the most useful thing? What was the most frustrating?
5. What is missing that you expected?
6. Did you ever see anything that looked wrong or private to someone else? (yes or no,
   describe if yes)
7. Course and year of study.

## 6. Objective numbers (run on the server)

```bash
sh scripts/staging.sh exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < scripts/test_stats.sql
```

This prints registered students, uploads and messages, how uploads ended, processing
time, and the most common failure reasons. Run it after each wave and keep the output.

## 7. While testing is running

* `sh scripts/staging.sh logs -f --tail=50 worker backend`
* `docker stats --no-stream` (is the server out of memory or CPU?)
* `df -h` (disk)

Pause the next wave if more than 1 in 5 uploads fails or answers take over a minute.

## 8. Afterwards

Export the survey responses and the stats output first. Then delete the test data. This
is the one case where removing the PostgreSQL volume is intended:
`sh scripts/staging.sh down` followed by `docker volume rm spc-staging_postgres_data`.
