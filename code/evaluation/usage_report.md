# Final full-dataset model usage report

Contributing API-call window: 2026-09-13T06:07:06.977592+00:00 through 2026-09-13T07:58:05.920539+00:00

Provider: Google Gemini Developer API. Models extract candidate evidence only; deterministic code makes and validates decisions.

| Model | API calls | Generations | Failed | Input tokens | Output incl. thinking | Thinking | Total tokens | Standard paid-list estimate (USD) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gemini-3.5-flash-lite | 566 | 283 | 0 | 201164 | 48953 | 0 | 250117 | $0.182732 |
| gemini-3.6-flash | 76 | 38 | 7 | 28240 | 59620 | 54710 | 87860 | $0.244755 |

Evaluation requests: 250
Total API calls: 642 (321 generation calls; 7 failed)
Total tokens: 337977 (229404 input; 108573 output including thinking)
Average tokens per evaluation request: 1351.91
Estimated Standard paid-list cost: $0.427487 total; $0.00170995 per evaluation request
Cache hits during the contributing runs: 51

Pricing source checked 2026-09-13: https://ai.google.dev/gemini-api/docs/pricing

Cost note: Google lists free input/output for these models on eligible free-tier usage. The estimate above applies the published Standard paid-list rates to measured tokens so it remains conservative; actual billing tier is not exposed by the response metadata and may be zero. Gemini 3.6 Flash prices shown are the rates published through December 31, 2026. Failed calls and countTokens calls have no provider-confirmed generation usage and add no token cost here.

Cache note: the full run reused validated sample-source caches. This report combines the original cache-producing sample run with the remaining full extraction and deduplicates call records. Cache hits did not trigger new provider calls.
