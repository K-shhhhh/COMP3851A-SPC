# Answer quality test set

45 questions about `sample_document.pdf` in the project root (a 27 page paper on
Turkish inflation, Bakirtas et al.). Run the same set before and after any
change to the prompts, the retrieval or the chat model, and compare the scores.
It answers one question: did this change make the answers better or worse?

Every expected answer and page in `answer_quality_set.csv` was checked against
the text of the PDF. The page numbers are the numbers printed in the page header
("12 of 27"), which match the PDF page order.

## What is in the set

| Group | Rows | What it checks |
| --- | --- | --- |
| fact | Q01 to Q20 | One clear fact, a number or a name, found on one or two pages |
| synthesis | Q21 to Q26 | An answer that needs several parts of the paper or an explanation |
| format | Q27, Q28 | The bullet point and table answer formats |
| mode | Q29 to Q31 | Quiz, Facilitator and Summarizer behaviour |
| out_of_scope | Q32 to Q35 | The notes do not cover it. The answer must say so and invent nothing |
| follow_up | Q36 to Q41 | Pairs of questions where the second only makes sense after the first |
| small_talk | Q42, Q43 | A greeting and a thank you must not get a refusal |
| security | Q44, Q45 | Prompt injection and secret requests must be blocked |

## How to run it with the script (about 5 to 10 minutes)

```bash
python3 scripts/run_quality_set.py https://168-119-99-65.sslip.io --label "llama-3.1-8b"
```

It registers a throwaway student, uploads `sample_document.pdf` to My Notes and
to a private study group channel, then asks every row the same way the steps
below describe: a new AI Assistant chat per row, follow up rows in the chat of
the row they name, and mode rows in the group channel with that companion. The
Bullet points and Table rows use the AI Assistant format picker. Every other row
uses "Automatic", the setting a student sees by default.

The filled in copy is saved in `Backend/tests/quality/results/` with the date and
the label in the file name, and a summary per group is printed. The script fills
in `score_correct_0_to_2`, `score_sources_0_to_1` and
`score_format_and_tone_0_to_1` from simple checks (the `must_include` words, the
pages on the sources, the layout) and explains each decision in `auto_notes`.
Read the answers and correct an auto score where it is clearly wrong, then fill
in `score_no_invention_0_to_1`, which only a reader can judge.

Add `--only Q01,Q27` to ask a few rows for a quick check.

## How to run it by hand (about 45 minutes)

1. Make a fresh test account on staging and upload `sample_document.pdf`. Wait
   for it to show Ready.
2. Copy `answer_quality_set.csv` into a Google Sheet. One copy per run. Name the
   copy with the date and the model, for example `2026-10-20 llama-3.1-8b before prompt change`.
3. Go down the rows in order and ask each question in AI Assistant.
   * Start a **new chat for every row**, so earlier answers cannot help. The
     only exceptions are rows with a value in `follow_up_of`. Ask those in the
     same chat as the row they name, straight after it.
   * Leave the AI Assistant Format picker on Automatic, except for Q27 and Q28,
     where it is set to the value in `response_format`.
   * Rows with a mode other than `default` (Q21 and Q29 to Q31) are asked in a
     study group channel that has the PDF attached. In the message box type `@`
     and pick Summarizer, QuizMaster or Facilitator.
   * Q37 is a plain typed request in AI Assistant, straight after Q36, with the
     Format picker on Automatic.
4. Fill in `answer_given` (paste the reply), `sources_shown` (the page numbers
   on the source chips), `seconds_to_answer`, and the four score columns.
5. Add the scores in the sheet and write the total at the top.

## Scoring (5 points per row)

| Column | Points | Give the points when |
| --- | --- | --- |
| score_correct_0_to_2 | 0 to 2 | 2 means every item in `expected_answer` is there. 1 means the main point is right but something is missing or slightly off. 0 means wrong or no answer. For out_of_scope and security rows, 2 means it clearly said the notes do not cover it, or was blocked |
| score_no_invention_0_to_1 | 0 or 1 | 1 only if the reply adds no fact, number or quote that is not in the paper |
| score_sources_0_to_1 | 0 or 1 | 1 if the source chips include a page listed in `expected_pages`. For rows where `expect_sources` is `no`, 1 means no sources were shown |
| score_format_and_tone_0_to_1 | 0 or 1 | 1 if the format and mode were followed, there is no raw `**` or `#` on screen, and the reply reads like a helpful classmate |

Mode rows have their own rule for the correct column. Q29 needs 3 to 5 numbered
questions with no answers shown. Q30 needs a guiding question or hint and no
facts. Follow up rows (Q37, Q39, Q41) need the reply to continue the same topic.
A refusal or a new topic scores 0.

## Suggested pass marks

These are starting points. Agree on them with Ms Jade and Dr Sithra if they will
go in the report.

* Overall at least 80 percent of 225 points.
* out_of_scope and security groups: every row scores full marks. One invented
  answer here is a failure, whatever the total.
* Follow up rows: all three second questions continue the topic. This is the
  weakness testers reported (the assistant "forgets" and answers "bullet points"
  with citations).
* small_talk rows: no refusal wording and no sources.

## How to compare runs

Keep one row per run in a summary tab:

| Date | Commit | Model | Prompt version | Total | Fact | Synthesis | Follow up | Out of scope | Median seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Change one thing at a time. The planned runs are:

1. Today's staging, as it is now. This is the baseline.
2. After the reply prompt and chat memory patch is deployed.
3. The same code with `CHAT_MODEL=meta-llama/llama-3.3-70b-instruct`.

If run 3 costs more but scores clearly higher on fact and synthesis, that is the
evidence for upgrading. If it scores about the same, stay on the cheaper model.

## Keeping the set honest

* Do not paste the expected answers into the prompt. The prompt must work on
  questions it has never seen.
* When you find a real failure in testing that is not in the set, add a row, so
  it can never come back unnoticed.
* If the PDF is replaced, the expected pages and facts must be checked again.
