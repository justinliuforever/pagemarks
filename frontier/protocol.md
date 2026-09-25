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

## Pages left empty

After the second run, as empty / pages. "Blank" counts answers with no notes on every ask, kept as blank pages; the
benchmark has nine title pages without staves.

| Model | Public | Benchmark | Sibelius | Scans | Held-out scans | Photographs | SMB | SMB 2× |
|---|---|---|---|---|---|---|---|---|
| GPT-6 Astra | 0 / 48 | 0 / 83, 4 blank | 0 / 92, 2 blank | 1 / 48 | 2 / 61 | 0 / 10 | 14 / 101 | 13 / 101 |
| GPT-6 Sol | 0 / 48 | 0 / 83, 7 blank | 0 / 92, 2 blank | 0 / 48 | 0 / 61 | 0 / 10 | 1 / 101 | 2 / 101 |
| Grok 4.6 | 0 / 48 | 9 / 83, 9 blank | 14 / 92, 2 blank | 12 / 48 | 11 / 61 | 0 / 10 | 10 / 101 | 0 / 101 |
| Claude Opus 5.5 | 0 / 48 | 0 / 83, 9 blank | 0 / 92, 2 blank | 0 / 48 | 0 / 61 | 0 / 10 | 0 / 101 | 0 / 101 |

- Grok 4.6: the Azure endpoint closed the stream after about 29 minutes, mid-answer, on every ask. Its upscaled SMB
  run, made on 24 September, lost no page to that; two pages whose three answers held no MusicXML were answered on
  the 90-minute rerun. The Sibelius works, the scans and the held-out scans, run on 24 September with 90 minutes a
  page from the start, left 22 pages without an answer in 90 minutes and 15 with no complete MusicXML in three
  answers.
- GPT-6 Astra: no answer within 90 minutes.
- GPT-6 Sol: declined ("I can't reliably read every note…").
- Claude Opus 5.5: 42 upscaled SMB pages first failed on the account's spend limit and were answered on a second run.
