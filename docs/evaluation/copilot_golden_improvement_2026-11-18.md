# Copilot golden set: improvement run (2026-11-18)

Live `run_copilot` on Gemini 3.8 Flash (Vertex AI) against the team Firestore data. 36 fast cases (18 dev, 18 reworded holdout variants; the four meeting-brief cases are slow and were left out), 2 repeats per arm.

```bash
python -m self_improving_ai.evaluation.copilot.improve --repeats 2 --cycles 2 --concurrency 4
```

## Arms

- **baseline**: the deployed behavior, empty learned memory.
- **hand_fixes**: today's date (New York) and a client directory (household name to `client_id`, with "if a name matches no household, say so") rendered into the orchestrator prompt.
- **learner_cycle_N**: hand fixes plus lessons Gemini proposed from dev failures (intent corrections, tool notes, plan templates). Client names and IDs are scrubbed, tools must exist in the live catalog, and a candidate is adopted only if `harness.gate` passes on holdout (paired t-test, min gain, no regressions on either split, no new forbidden calls, no more than 1.1x the calls).

## Results

| Arm | Dev pass | Holdout pass | Calls per question | Right tools | Right args | Facts |
|---|---|---|---|---|---|---|
| baseline | 86% | 86% | 4.6 | 99% | 90% | 90% |
| hand_fixes | 89% | 97% | 1.6 | 99% | 99% | 93% |
| learner_cycle_1 | 92% | 100% | 1.4 | 100% | 100% | 96% |
| learner_cycle_2 | 94% | 97% | 1.3 | 100% | 100% | 96% |

## What it means

- **Hand fixes are the real win.** Calls per question fell from 4.6 to 1.6 (paired over 36 cases, p = 0.001). The worst baseline cases were the unknown-client questions (G17 and V17: 23 and 20 calls while the model searched for a household that does not exist). With the directory, the model answers in 0 to 1 calls. Argument accuracy rose from 90% to 99% because the model no longer guesses `client_id` values, and "next meeting" questions now use today's date instead of picking a past event.
- **The pass-rate gain from the hand fixes is not significant yet** (holdout 86% to 97%, p = 0.22). With 18 holdout cases and 2 repeats the test cannot separate an 11-point gain from noise. Calls are the metric that clearly moved.
- **The learner was rejected in both cycles, correctly.** Cycle 1 added +2.8 holdout points (p = 0.33) and cycle 2 added +0.0. Holdout is already at the ceiling after the hand fixes, so there is little left to learn. Its lessons were sensible (ask which client before briefing, say "no such household" without tools), but the gate needs evidence, not plausibility. Final version: **hand_fixes**.
- **Still flaky:** G16 ("Prepare a meeting brief" with no client) sometimes briefs a guessed client, and G17/V17 sometimes keep searching. Both are clarification behaviors, so they are the next target, measured with more repeats.

## Rerun after checker and scorer fixes (2026-11-19)

The first run's traces showed three problems outside the orchestrator's plan:

- **The completion checker read only the first 2,000 characters** of an answer, so complete long answers (Roth IRA, wash sale, a list of 8 emails) looked cut off and the whole copilot ran again. This happened in 16 of 288 runs. The checker now sees the start and the end of an answer (`clip_for_checker`).
- **The checker treated a correct clarifying question as unfinished** ("which client?" for an unnamed meeting brief) and retried until the loop cap, once taking 255 s. Its prompt now counts asking for a missing client, saying a client does not exist, or declining a forbidden action as complete.
- **The scorer was too strict.** Correct answers such as "the Johnson family does not exist in our database" and "please provide the client name" failed the phrase check, and V17 was labeled with the Johnson description. Rescoring run 1 with wider phrases puts the hand fixes at 99% and the learner at 100%.

| Arm | Dev pass | Holdout pass | Calls per question | Median time | Runs that retried |
|---|---|---|---|---|---|
| baseline | 92% | 83% | 4.7 | 23 s | 0 of 72 |
| hand_fixes | 94% | 97% | 1.6 | 94 s (see note) | 0 of 72 |
| learner_cycle_1 | 100% | 100% | 1.7 | 16 s | 0 of 72 |
| learner_cycle_2 | 100% | 100% | 1.6 | 24 s | 0 of 72 |

- **Retries are gone:** 0 of 288 runs looped, down from 11 to 12 of 72 per arm in run 1, and the baseline p90 time fell from 85 s to 47 s.
- **Note on hand_fixes timing:** that arm ran during a 40 minute window in which responses were slow, and G01 and G07 timed out at 300 s. The learner arms ran the same prompt plus lessons right afterwards with medians of 14 to 25 s, so the slowdown was most likely on the Vertex side, not the change.
- **The learner reached 100% on both splits**, learning from the G01 and G07 failures, but the gate again rejected it (+2.8 holdout points, p = 0.33). The holdout set is saturated: the hand fixes already pass 97%, so one more passing case cannot be significant with 18 cases and 2 repeats.

## Next steps

1. Ship the hand fixes (they are in `agents/orchestrator/agent.py` and on by default).
2. Add harder cases (two clients in one request, ambiguous names, multi-step requests) and run a learner arm from the baseline, so the learner has room to show a gain. Use 5 repeats with the slow meeting-brief cases included to get power on pass rate.
3. Fix `get_upcoming_events(client_id)`: it needs the Firestore composite index or no `order_by("date")` in `calendar_store.py`.
