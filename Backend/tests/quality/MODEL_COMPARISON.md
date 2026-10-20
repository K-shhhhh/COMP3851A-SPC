# Chat model comparison plan (Task 11)

Question to answer: is a bigger model worth its extra cost for the answers
students see? The answer comes from running the 45 question set
(`answer_quality_set.csv`, see `README.md`) on each model and comparing scores,
speed and cost. Nothing here has been run yet. The plan and the cost estimates
are ready so the runs can start as soon as the reply prompt patch is on staging.

## 1. Models to compare

The model is chosen by `CHAT_MODEL` in `.env.staging` (RUNBOOK section 4).
Embeddings do not change, so retrieval is identical across runs.

| Run | Model name on OpenRouter | Why it is in the plan |
| --- | --- | --- |
| A | `meta-llama/llama-3.1-8b-instruct` | The current model. This is the baseline |
| B | `meta-llama/llama-3.3-70b-instruct` | The most likely upgrade. Same family, much bigger, still cheap |
| C | `meta-llama/llama-4-maverick` | A stronger and costlier option, to see if the extra cost buys anything |
| D (optional) | `meta-llama/llama-4-scout` | Only if there is time. Price from a third party site, check it on OpenRouter first |

Other model families can be added to the same table later. The test set does not
depend on the family. Check each exact name on openrouter.ai before use, since
names and prices change.

## 2. Prices

Read from the OpenRouter model pages on 18 October 2026. Prices are in US
dollars per million tokens.

| Model | Input | Output | Context | Source |
| --- | --- | --- | --- | --- |
| Llama 3.1 8B Instruct | 0.02 | 0.04 | 131,072 | [OpenRouter](https://openrouter.ai/compare/meta-llama/llama-3.1-8b-instruct) |
| Llama 3.3 70B Instruct | 0.10 | 0.32 | 131,072 | [OpenRouter](https://openrouter.ai/compare/meta-llama/llama-3.3-70b-instruct) |
| Llama 4 Maverick | 0.1875 | 0.6525 | 1,048,576 | [OpenRouter](https://openrouter.ai/compare/meta-llama/llama-4-maverick) |
| Llama 4 Scout | 0.18 | 0.59 | 131,072 | [Third party calculator](https://www.getmaxim.ai/bifrost/llm-cost-calculator/provider/openrouter/model/llama-4-scout), data dated 15 October 2026, not confirmed on OpenRouter |

OpenRouter can route a model to different providers at different prices, so the
real bill can differ from this table. The Activity page in the OpenRouter
account shows what was actually charged.

## 3. Cost per 1000 questions

This is an estimate with stated assumptions. Replace the assumptions with real
numbers from the first run (the OpenRouter Activity page shows tokens per call).

Assumptions for one question:

* 5 retrieved passages of about 350 words each, which is about 2,400 tokens
* About 600 tokens of instructions and about 600 tokens of earlier messages
* About 3,500 input tokens in total and about 400 output tokens

| Model | Input cost | Output cost | Per 1000 questions |
| --- | --- | --- | --- |
| Llama 3.1 8B | 0.07 | 0.02 | about 0.09 dollars |
| Llama 3.3 70B | 0.35 | 0.13 | about 0.48 dollars |
| Llama 4 Maverick | 0.66 | 0.26 | about 0.92 dollars |
| Llama 4 Scout | 0.63 | 0.24 | about 0.87 dollars |

Even the most expensive row is under one dollar per 1000 questions, so cost is
unlikely to be the deciding factor for a class sized evaluation. A tester asking
20 questions a day for a week is about 140 questions each. What matters more is
whether the OpenRouter account has credit, and whether a spend limit is set there.

Picture descriptions during upload are a separate model and a separate cost.

## 4. How to run

Do this one model at a time, on staging, with the reply prompt patch deployed.

1. Make a fresh test account. Upload `sample_document.pdf` and wait for Ready.
2. Set `CHAT_MODEL` and restart the backend (RUNBOOK section 4). Confirm with
   `printenv CHAT_MODEL`, and run the smoke test.
3. Copy `answer_quality_set.csv` into a new sheet named
   `2026-10-NN <model name>`.
4. Ask all 45 questions as described in `README.md`. Fill in the answers,
   sources, seconds and scores.
5. Two people should score the same run, or score separately and compare, for at
   least the first model pair. This shows how much the scores depend on the
   person.
6. Add the run to the summary tab.
7. Note the cost shown in the OpenRouter Activity page for the run.

Order: A first (the baseline, before the patch if you want a true before and
after), then A after the patch, then B, then C. Change one thing at a time.

## 5. Decision rule

Decide this before looking at the scores, so the result cannot shape the rule.

Move to a bigger model only if all of these hold against the same model with the
same prompt.

1. The total score is higher by at least 10 percentage points, or fact plus
   synthesis rows are higher by at least 10 percentage points.
2. Out of scope and security rows are not worse. One invented answer in these
   groups fails the model, whatever the total.
3. All three follow up second questions continue the topic.
4. Median time to answer is under 10 seconds, or no more than double the
   baseline. Students already rated waiting during upload as the weakest part of the app, so slow answers would add to that. The 10 seconds is a suggestion to agree with the supervisors.
5. The projected monthly cost fits the team's credit.

If run B meets all five, choose B. Run C only needs to be tried if B falls short
on fact or synthesis. If B and A score within a few points of each other, keep A
and use the saved time on retrieval and prompt problems instead.

Ten points is a starting suggestion. With 45 questions, a gap of one or two
questions is noise.

## 6. What to watch for with a bigger model

* **Refusal wording.** The system hides source chips when the reply contains the
  phrase "not available in the supplied study material". A different model may
  say it in other words and the chips would then show on a refusal. Check
  `sources_shown` on the out of scope rows (Q32 to Q35) for every model.
* **Longer replies.** Bigger models write more. Check that answers still start
  with the answer and stay short, as the prompt asks.
* **Speed.** A 70B model is usually slower per token. Record seconds for every
  row.
* **Markdown.** Check that no raw `**` or `#` shows on screen. The renderer
  handles bold, italics, code and headings, but not everything.
* **Provider limits.** Free and cheap routes can rate limit during a test.
  Record any error with the time.

## 7. Report line

When the runs are done, add one table to the final report.

| Model | Total | Fact | Synthesis | Follow up | Out of scope | Median seconds | Cost per 1000 questions |
| --- | --- | --- | --- | --- | --- | --- | --- |

Write one sentence under it saying which model was chosen and which rule decided
it.
