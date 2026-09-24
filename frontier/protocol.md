# Frontier model protocol

One request a page: a single user turn holding the page as a PNG and [`prompt.txt`](prompt.txt). No system prompt, no
examples, streamed, sampling left at each API's default.

| Model | Access | Version returned | Reasoning | Output cap |
|---|---|---|---|---|
| GPT-6 Astra | Azure AI Foundry, Chat Completions `2025-04-01-preview` | `gpt-6-astra-2026-09-03` | `reasoning_effort: "high"` | `max_completion_tokens: 110000` |
| GPT-6 Sol | Azure AI Foundry, Chat Completions `2025-04-01-preview` | `gpt-6-sol-2026-09-22` | `reasoning_effort: "high"` | `max_completion_tokens: 110000` |
| Grok 4.6 | Azure AI Foundry, Chat Completions `2025-04-01-preview` | `grok-4.6` | `reasoning_effort: "high"` | `max_completion_tokens: 110000` |
| Claude Opus 5.5 | Anthropic Messages API `2023-06-01` | `claude-opus-5-5` | `thinking: {"type": "adaptive"}`, `output_config: {"effort": "high"}` | `max_tokens: 128000` |

## Pages

| Set | PNG sent |
|---|---|
| Public set, benchmark, Sibelius engravings | rendered at 300 dpi, 2480×3509 or 2550×3300 |
| Scans | 300 dpi, 2481×3367 to 3210×4404 |
| Photographs | as taken, 1080×1920 to 1536×2048 |
| SMB subset | as published, 900×1224 to 2515×3107, and upscaled 2×; the better of the two is reported |

For Claude alone, a PNG over 4.5 MB is shrunk in steps of 3/4 until it fits the API's image limit: 28 of the 101
upscaled SMB pages. A provider may rescale an image further.

## Rules

- A send that fails (HTTP 408, 429, 500, 502, 503 or 504, 529 from Anthropic, a connection error, or a stream silent
  past the limit below) is repeated, up to three sends.
- An answer that stops at the output cap, holds no complete `score-partwise` document, does not parse, or holds no notes
  is asked again, up to three asks. An answer with no notes on every ask is kept as a blank page.
- First pass: 50 minutes a page and 10 minutes of stream silence. Every page that failed was run again with 90 minutes
  and 40 minutes of silence; Claude ran with those limits from the start.
- A page still without an answer counts as empty.
- No kept answer reached its output cap: each ended with `stop` or `end_turn`.
- Runs: 23–24 September 2026.
