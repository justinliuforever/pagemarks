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
| Public set | rendered at 300 dpi, 2480×3509 or 2550×3300 |
| SMB subset | as published, 900 to 2515 pixels wide, and upscaled 2×; both were run |

A PDF page becomes a PNG with PyMuPDF, `page.get_pixmap(dpi=300)`. For Claude alone, a PNG over 4.5 MB is shrunk in
steps of 3/4 until it fits the API's image limit: 28 of the 101 upscaled SMB pages. A provider may rescale an image
further.

## Rules

- The PNG is sent in base64. Azure requests put the prompt before the image and set no `detail`, so the service default
  applies; Anthropic requests put the image before the prompt.
- The answer kept is the first `<score-partwise>…</score-partwise>` in the reply, with any XML declaration and DOCTYPE
  before it.
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

Pages without an answer after the second run, out of the pages sent.

| Model | Public | SMB | SMB 2× |
|---|---|---|---|
| GPT-6 Astra | 0 / 48 | 14 / 101 | 13 / 101 |
| GPT-6 Sol | 0 / 48 | 1 / 101 | 2 / 101 |
| Grok 4.6 | 0 / 48 | 10 / 101 | 0 / 101 |
| Claude Opus 5.5 | 0 / 48 | 0 / 101 | 0 / 101 |

- Grok 4.6: the Azure endpoint closed the stream after about 29 minutes, mid-answer, on every ask. Its upscaled SMB run,
  made on 24 September, lost no page to that; two pages whose three answers held no MusicXML were answered on the
  90-minute rerun.
- GPT-6 Astra: no answer within 90 minutes.
- GPT-6 Sol: declined ("I can't reliably read every note…").
- Claude Opus 5.5: 42 upscaled SMB pages first failed on an account limit and were answered on a second run.

## Audiveris

Audiveris 5.11.0 read the same 300 dpi PNGs with fingering recognition switched on, and its exported MusicXML is scored
as it is:

```
Audiveris -batch -export -constant org.audiveris.omr.sheet.ProcessingSwitches.fingerings=true -output DIR page.png
```
