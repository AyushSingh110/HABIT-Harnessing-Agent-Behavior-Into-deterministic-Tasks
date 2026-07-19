# OpenTelemetry GenAI field mapping

HABIT trajectory fields aligned to OpenTelemetry GenAI semantic conventions. This is field
alignment only — HABIT does not emit spans or depend on the OTel SDK.

| HABIT field | Model | OTel GenAI attribute |
|---|---|---|
| `provider` | `LLMCall` | `gen_ai.system` |
| `model` | `LLMCall` | `gen_ai.request.model` |
| `input_tokens` | `LLMCall` | `gen_ai.usage.input_tokens` |
| `output_tokens` | `LLMCall` | `gen_ai.usage.output_tokens` |
| `tool_name` | `ToolCall` | `gen_ai.tool.name` |
| `call_id` | `ToolCall` | `gen_ai.tool.call.id` |

## HABIT-specific fields (no OTel GenAI equivalent)

| HABIT field | Model | Purpose |
|---|---|---|
| `context_available` | `Step` | item_ids present in the context window at this step. |
| `context_reads` | `Step` | item_ids the step actually read; the raw signal Layer 3 learns from. |
| `tool_result_schema_fingerprint` | `Step` | stable hash of the tool result's key/type structure; the Layer 4 divergence signal. |
