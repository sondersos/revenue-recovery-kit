# ADR-0004: Claude Insights Prompt Strategy

**Date:** 2026-05-14
**Status:** Accepted
**Deciders:** Bayanda

---

## Context

Raw detection counts and flagged records are not useful to a founder who needs to act. A list of 12 stalled invoices tells the founder nothing about urgency, nothing about cost, and nothing about what to do next. The system must distill detections into a short, opinionated executive summary that (a) names the scale of the problem, (b) quantifies the cost, and (c) gives exactly 3 recommended actions.

The summary is the headline feature shown on the dashboard and the primary evidence of AI value in the portfolio. It must meet four constraints:

1. **Actionability.** The output must end with concrete next steps, not observations. A founder reading the summary should know exactly what to do before closing the tab.

2. **Auditability.** Every summary must be reproducible from its inputs. If the prompt changes in a future sprint, historical summaries must remain valid records of what the model was told and what it said.

3. **Cost predictability.** The system may run a detection + insight cycle multiple times per day. Token costs must be bounded and foreseeable.

4. **Consistency.** The tone and structure of the summary must be stable across runs. A founder who reads Monday's summary and Wednesday's summary should experience the same voice and format, not a different persona each time.

---

## Decision

### Input Payload Structure

The insight service assembles a structured JSON payload from the most recent detection run before calling Claude. The payload shape is fixed:

```json
{
  "run_id": "<uuid>",
  "window_days": 30,
  "counts": {
    "stalled_invoice": 4,
    "stale_lead": 7,
    "recovery_candidate": 2,
    "sequence_eligible": 5
  },
  "top_examples": [
    { "type": "stalled_invoice", "contact": "Jane Smith", "amount_usd": 3200.00, "days": 12 },
    { "type": "recovery_candidate", "contact": "Acme Corp", "amount_usd": 8750.00, "days": 34 }
  ],
  "total_at_risk_usd": 24650.00
}
```

`top_examples` is capped at 5 entries, selected by descending `amount_usd`, to keep the payload within a predictable token budget. The `run_id` is included so the stored insight record can be cross-referenced with the detection run that produced it.

### System Prompt and Output Structure

The system prompt establishes a fixed persona and a fixed output contract:

**Persona:** Revenue operations analyst writing for the founder of a 5-person service business. The tone is direct, data-led, and brief. No filler phrases ("It's important to note that..."), no hedging, no generic advice.

**Output contract — exactly 3 paragraphs:**

- **Paragraph 1 — What is happening.** Name the patterns by rule type. Cite the counts from the payload. Do not editorialize; describe.
- **Paragraph 2 — What it is costing.** Quantify using `total_at_risk_usd` and the top examples. Name specific contacts and amounts where available. Make the cost concrete.
- **Paragraph 3 — Top 3 recommended actions.** Each action is one concrete, imperative sentence. Actions must be specific to the data in the payload, not generic advice about chasing invoices.

The three-paragraph contract is enforced by the system prompt. It is not left to the model's discretion. Deviating from three paragraphs is a prompt defect, not a model quirk.

### Model and Sampling Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Model | `claude-sonnet-4-5-20250929` | Configured via `settings.anthropic_model` / `ANTHROPIC_MODEL` env var |
| Temperature | `0.2` | Low variance; consistent tone; minimal hallucination risk on structured financial data |
| Max tokens | `800` | Sufficient for 3 dense paragraphs; prevents runaway generation |

The model identifier is read from `settings.anthropic_model`, which is populated from the `ANTHROPIC_MODEL` environment variable. Swapping to Haiku (lower cost) or Opus (higher capability) requires one environment variable change and no code change.

Temperature 0.2 was chosen over 0.0 (fully deterministic) to allow minor phrasing variation across runs while keeping the output stable enough that a founder reading two summaries from the same data set would not notice a meaningful difference.

### Persistence

Both the input payload and the model's output are stored in the `insights` table:

| Column | Type | Contents |
|---|---|---|
| `id` | UUID | Primary key |
| `detection_run_id` | UUID | FK → `detection_runs.id` |
| `input_payload` | JSONB | The exact JSON sent to Claude, before any prompt templating |
| `summary_text` | TEXT | The raw text returned by Claude |
| `model` | VARCHAR | The model ID used (e.g. `claude-sonnet-4-5-20250929`) |
| `created_at` | TIMESTAMPTZ | Timestamp of the Claude API call |

Storing both `input_payload` and `summary_text` means every insight is independently auditable: given a stored `input_payload`, the summary can be reproduced (within temperature variance) by resubmitting the payload. Changing the prompt in a future sprint does not corrupt historical records — old records reflect what the model was actually told at the time.

### Empty-State Guard

If the detection run contains zero detections across all rule types, the `prompts.py` module must detect this condition before calling Claude and return a fixed empty-state message rather than calling the API. Calling Claude with an empty payload would produce a response with no grounding in real data, incur unnecessary API cost, and risk generating a confusing or misleading summary. The empty-state guard is a required implementation constraint, not an optional optimisation.

---

## Rejected Alternative 1: Multi-Shot Conversation

A multi-turn conversation would allow the model to ask clarifying questions before writing the summary — for example, "Do you want me to focus on the highest-value invoices or the oldest ones?" This mirrors how a human analyst might work.

This approach is rejected for three reasons. First, it adds latency: two round-trips to the Claude API instead of one. For a background task that runs on a schedule, this doubles API wait time with no user-facing benefit. Second, it requires the insight service to maintain conversation state between turns, complicating the implementation and the persistence model — storing a conversation thread is more complex than storing a single input/output pair. Third, the clarifying-question pattern offers no quality improvement for this specific task because all inputs are known upfront and the output structure is fixed. The three-paragraph contract eliminates the ambiguity that multi-shot conversation exists to resolve.

---

## Rejected Alternative 2: Function Calling / Tool Use

Claude's tool use feature would return structured JSON fields — for example, `{ "headline": "...", "cost_summary": "...", "actions": ["...", "...", "..."] }` — instead of freeform prose. This would make the output machine-parseable without any text processing.

This approach is rejected because the dashboard wants a readable narrative, not a JSON object. The founder reading the dashboard is not a developer; they are looking at a prose paragraph, not a rendered JSON tree. Tool use would require a rendering layer in the frontend to convert the structured fields back into readable prose — adding frontend complexity to solve a problem that does not exist if the model writes prose directly. The output contract (3 paragraphs, fixed structure) already provides enough implicit structure for the dashboard to render the text without parsing it.

---

## Rejected Alternative 3: Streaming

Streaming the Claude response via Server-Sent Events or chunked transfer would reduce time-to-first-token. The founder would see words appear on the dashboard as the model generates them, rather than waiting for the full summary.

This approach is rejected because the insight generation is an async background task whose results are polled from the dashboard — not a real-time interactive session. The dashboard checks whether an insight record exists for the current detection run; if it does, it displays `summary_text`; if it does not, it shows a loading state. Streaming into this polling model would require the server to buffer a partial response in a temporary store before the full text is available to write to the `insights` table, adding complexity for no UX benefit. If the dashboard is redesigned in a future sprint to display insights in real time (e.g. triggered by a user action rather than a background schedule), streaming can be added at that point.

---

## Consequences

### Positive

- Every insight is reproducible from its stored `input_payload`. Prompt changes in future sprints do not affect the validity of historical records.
- Estimated cost at current Sonnet pricing is approximately $0.003–$0.01 per insight — well under $1/day even at aggressive polling frequencies.
- The model is configurable via `ANTHROPIC_MODEL` env var. Switching to Haiku for cost reduction or Opus for quality improvement requires one environment change and zero code changes.
- The three-paragraph output contract and temperature 0.2 setting produce consistent, comparable summaries across runs. A founder reading summaries over time will experience a stable voice.
- Storing `model` alongside each insight means that if the model identifier changes, historical records retain an accurate record of which model produced each summary.

### Trade-offs

- Temperature 0.2 produces consistent but occasionally dry prose. Founders may prefer a warmer, more conversational tone. This is a Day 5 prompt-tuning opportunity; the stored `input_payload` makes A/B testing prompt variants straightforward.
- The `max_tokens: 800` ceiling means that a detection run with many high-value examples may produce a summary that feels truncated. If founders consistently report that summaries feel cut off, the limit should be raised to 1000 and the cost impact reassessed.
- No streaming means the dashboard must poll or receive a webhook to know when an insight is ready. This is acceptable for a Day 3 background-task architecture; it should be revisited on Day 5 if the dashboard requires lower latency.
- The empty-state guard in `prompts.py` is a required implementation constraint. If it is omitted, a detection run with zero detections will call Claude unnecessarily and may produce a misleading "no problems found" narrative that does not accurately reflect whether the system ran correctly or simply found nothing.

---

## Decision Summary

Single-shot Claude Sonnet prompt with structured JSON input. Fixed three-paragraph output contract: what is happening, what it is costing, top 3 actions. Model `claude-sonnet-4-5-20250929` configurable via env var. Temperature 0.2, max 800 tokens. Both `input_payload` and `summary_text` persisted against `detection_run_id` for full auditability. Empty-state guard in `prompts.py` prevents API calls on zero-detection runs.
